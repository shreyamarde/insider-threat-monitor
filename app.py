"""
SHRUTU — Insider Threat Monitoring System
Application factory and entry point:  python app.py
"""
import logging
import os
from datetime import timedelta
from logging.handlers import RotatingFileHandler

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import csrf, db, login_manager, socketio
from utils.helpers import now, wants_json

log = logging.getLogger("itm")

ERROR_TEXT = {
    400: ("Bad request", "The request could not be understood."),
    403: ("Access denied", "You do not have permission to view this page. This attempt has been recorded."),
    404: ("Not found", "The page or record you are looking for does not exist."),
    405: ("Method not allowed", "That action is not allowed here."),
    429: ("Too many attempts", "Please wait a few minutes and try again."),
    500: ("Something went wrong", "An unexpected error occurred. The problem has been logged."),
    503: ("Service unavailable", "The database is currently unreachable. Please try again shortly."),
}


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    _configure_logging(app)
    if not os.getenv("SECRET_KEY") and not app.config["TESTING"]:
        log.warning("SECRET_KEY is not set — using a random key; sessions will reset on restart.")

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)
    _configure_login(app)

    from routes.api import api_bp
    from routes.auth import auth_bp
    from routes.employee import employee_bp
    from routes.manager import manager_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(api_bp)

    import services.notification_service  # noqa: F401  (registers the Socket.IO handlers)

    _register_hooks(app)
    _register_error_handlers(app)
    _register_template_helpers(app)

    if not app.config["TESTING"] and not app.config.get("AUTO_INIT_DB"):
        _prepare_database(app)  # (with AUTO_INIT_DB, wsgi.py prepares the database instead)
    return app


def _prepare_database(app):
    with app.app_context():
        try:
            from services.risk_engine import ensure_default_rules
            ensure_default_rules()
        except SQLAlchemyError:
            db.session.rollback()
            log.error("Database not reachable at startup — check .env and run `python init_db.py`.")
    return app


# ---------------------------------------------------------------------------

def _configure_logging(app):
    os.makedirs(os.path.dirname(app.config["LOG_FILE"]), exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    root = logging.getLogger()
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers) and not app.config["TESTING"]:
        file_handler = RotatingFileHandler(app.config["LOG_FILE"], maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(fmt)
        file_handler.setLevel(logging.INFO)
        root.addHandler(file_handler)
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)
    root.setLevel(logging.INFO)


def _configure_login(app):
    from models import User

    login_manager.login_view = "auth.login_page"
    login_manager.login_message = "Your session has expired or you are not signed in. Please sign in."
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(User, int(user_id))
        return user if user is not None and user.status == "active" else None

    @login_manager.unauthorized_handler
    def unauthorized():
        if wants_json():
            return {"error": "unauthorized", "message": "Session expired. Please sign in again."}, 401
        flash(login_manager.login_message, "warning")
        return redirect(url_for("auth.login_page", next=request.path if request.method == "GET" else None))


def _register_hooks(app):
    allowed_during_pw_change = {"auth.change_password", "auth.logout", "static"}

    @app.before_request
    def track_session():
        if not current_user.is_authenticated:
            return None
        current = now()
        if current_user.last_seen is None or current - current_user.last_seen > timedelta(seconds=30):
            try:
                current_user.last_seen = current
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
        if current_user.must_change_password and request.endpoint not in allowed_during_pw_change:
            if wants_json():
                return {"error": "password_change_required",
                        "message": "You must change your temporary password first."}, 403
            return redirect(url_for("auth.change_password"))
        return None

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
            "connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if current_user.is_authenticated and request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"  # no sensitive pages in the back/forward cache
        return response


def _register_template_helpers(app):
    @app.template_filter("dt")
    def format_datetime(value, fmt="%d %b %Y, %H:%M:%S"):
        return value.strftime(fmt) if value else "—"

    @app.template_filter("ago")
    def time_ago(value):
        if not value:
            return "never"
        seconds = max(0, int((now() - value).total_seconds()))
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{seconds // 60} min ago"
        if seconds < 86400:
            return f"{seconds // 3600} h ago"
        return f"{seconds // 86400} d ago"


def _register_error_handlers(app):

    def render_error(code, message=None):
        title, text = ERROR_TEXT.get(code, ERROR_TEXT[500])
        if wants_json():
            return {"error": title.lower().replace(" ", "_"), "message": message or text}, code
        try:  # never let the error page itself fail (e.g. when the database is down)
            home = (url_for("manager.dashboard") if current_user.is_manager else url_for("employee.dashboard"))                 if current_user.is_authenticated else url_for("auth.login_page")
        except Exception:
            db.session.rollback()
            home = url_for("auth.login_page")
        return render_template("errors/error.html", code=code, title=title, message=message or text,
                               home_url=home), code

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        if wants_json():
            return render_error(400, "Security token missing or expired. Refresh the page and try again.")
        flash("Your form expired. Please try again.", "warning")
        return redirect(request.referrer or url_for("auth.login_page"))

    @app.errorhandler(HTTPException)
    def http_error(e):
        return render_error(e.code, e.description if e.code not in ERROR_TEXT else None)

    @app.errorhandler(OperationalError)
    def db_down(e):
        db.session.rollback()
        log.error("Database error: %s", e.orig if hasattr(e, "orig") else e)
        return render_error(503)

    @app.errorhandler(SQLAlchemyError)
    def db_error(e):
        db.session.rollback()
        log.exception("Database error")
        return render_error(500)

    @app.errorhandler(Exception)
    def unhandled(e):
        log.exception("Unhandled error on %s %s", request.method, request.path)
        return render_error(500)


def start_background_jobs(app):
    """Periodic risk-score decay (runs inside the Socket.IO server)."""
    from services.risk_engine import apply_decay

    def decay_loop():
        while True:
            socketio.sleep(app.config["RISK_DECAY_INTERVAL_SECONDS"])
            with app.app_context():
                try:
                    changed = apply_decay()
                    if changed:
                        log.info("Risk decay applied to %d score(s)", changed)
                except Exception:
                    db.session.rollback()
                    log.exception("Risk decay job failed")

    socketio.start_background_task(decay_loop)


def _lan_ip():
    """Best guess at this machine's address on the local network (no traffic is sent)."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "<this-computer's-IP>"


if __name__ == "__main__":
    app = create_app()
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    if app.config["START_BACKGROUND_JOBS"]:
        start_background_jobs(app)
    log.info("SHRUTU running on http://%s:%s", host, port)
    if host == "0.0.0.0":
        log.info("Other devices on this network can open: http://%s:%s", _lan_ip(), port)
    socketio.run(app, host=host, port=port, debug=debug, use_reloader=False, allow_unsafe_werkzeug=True)
