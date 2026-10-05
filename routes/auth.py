"""Authentication: login (with lockout), logout, password change."""
from datetime import timedelta

from flask import (Blueprint, current_app, flash, redirect, render_template, request,
                   session, url_for)
from flask_login import current_user, login_user, logout_user

from extensions import db
from models import LoginAttempt, User
from services.activity_logger import log_activity
from services.notification_service import emit_presence
from utils.helpers import client_ip, client_user_agent, now
from utils.security import home_url_for, is_safe_next, login_required
from utils.validators import normalize_employee_id, validate_password

auth_bp = Blueprint("auth", __name__)

GENERIC_LOGIN_ERROR = "Invalid employee ID or password."


def _recent_failures(**filters):
    since = now() - timedelta(minutes=current_app.config["LOGIN_LOCKOUT_MINUTES"])
    return LoginAttempt.query.filter_by(success=False, **filters).filter(LoginAttempt.timestamp >= since).count()


def _is_locked_out(employee_id, ip):
    cfg = current_app.config
    return (_recent_failures(employee_id=employee_id) >= cfg["LOGIN_MAX_FAILURES"]
            or _recent_failures(ip_address=ip) >= cfg["LOGIN_IP_MAX_FAILURES"])


def _record_attempt(employee_id, user, success, reason):
    db.session.add(LoginAttempt(employee_id=employee_id[:20] or "UNKNOWN", user_id=user.id if user else None,
                                ip_address=client_ip(), user_agent=client_user_agent(),
                                timestamp=now(), success=success, reason=reason))


def _fail(employee_id, user, reason, description, message, status_code=401):
    """Store the failed attempt + FAILED_LOGIN activity (committed together by log_activity)."""
    _record_attempt(employee_id, user, False, reason)
    log_activity(user, "FAILED_LOGIN", resource="/login", description=description, status="FAILED",
                 employee_id=employee_id or "UNKNOWN", context={"failure_reason": reason.lower().replace("_", " ")})
    return render_template("login.html", error=message, employee_id=employee_id), status_code


@auth_bp.route("/")
def login_page():
    if current_user.is_authenticated:
        return redirect(home_url_for(current_user))
    return render_template("login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    employee_id = normalize_employee_id(request.form.get("employee_id"))
    password = request.form.get("password") or ""
    if not employee_id or not password:
        return render_template("login.html", error="Enter your employee ID and password.",
                               employee_id=employee_id), 400

    ip = client_ip()
    user = User.query.filter_by(employee_id=employee_id).first()

    if _is_locked_out(employee_id, ip):
        minutes = current_app.config["LOGIN_LOCKOUT_MINUTES"]
        return _fail(employee_id, user, "LOCKED_OUT", "Login blocked: too many failed attempts",
                     f"Too many failed attempts. Try again in {minutes} minutes.", 429)

    if user is None:
        return _fail(employee_id, None, "UNKNOWN_EMPLOYEE_ID", "Login with unknown employee ID", GENERIC_LOGIN_ERROR)
    if not user.check_password(password):
        return _fail(employee_id, user, "INVALID_PASSWORD", "Incorrect password", GENERIC_LOGIN_ERROR)
    if user.status != "active":
        return _fail(employee_id, user, "ACCOUNT_DISABLED", "Login attempt on a disabled account",
                     "This account is disabled. Please contact your manager.", 403)

    # ---- success
    session.clear()  # prevent session fixation
    login_user(user)
    session.permanent = True
    user.last_login = now()
    user.last_login_ip = ip
    user.last_seen = now()
    user.is_online = True
    _record_attempt(employee_id, user, True, "SUCCESS")
    action = "MANAGER_LOGIN" if user.is_manager else "LOGIN"
    log_activity(user, action, resource="/login", description="Signed in")
    emit_presence(user)

    if user.must_change_password:
        flash("Please set a new password before continuing.", "info")
        return redirect(url_for("auth.change_password"))
    target = request.args.get("next")
    return redirect(target if is_safe_next(target) else home_url_for(user))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    user = current_user._get_current_object()
    log_activity(user, "LOGOUT", resource="/logout", description="Signed out")
    user.is_online = False
    db.session.commit()
    emit_presence(user)
    logout_user()
    session.clear()
    flash("You have been signed out securely.", "success")
    return redirect(url_for("auth.login_page"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    forced = current_user.must_change_password
    if request.method == "POST":
        current_pw = request.form.get("current_password") or ""
        new_pw = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        error = None
        if not current_user.check_password(current_pw):
            error = "Your current password is incorrect."
        elif new_pw != confirm:
            error = "The new passwords do not match."
        elif new_pw == current_pw:
            error = "The new password must be different from the current one."
        else:
            error = validate_password(new_pw, current_app.config["PASSWORD_MIN_LENGTH"],
                                      employee_id=current_user.employee_id, name=current_user.name)
        if error:
            flash(error, "error")
            return render_template("change_password.html", forced=forced), 400

        current_user.set_password(new_pw)
        current_user.must_change_password = False
        log_activity(current_user._get_current_object(), "PASSWORD_CHANGE", resource="/change-password",
                     description="Changed own password" + (" (first login)" if forced else ""))
        flash("Password updated successfully.", "success")
        return redirect(home_url_for(current_user))
    return render_template("change_password.html", forced=forced)
