"""Manager interface pages. Data is loaded from /api/manager/* by page scripts."""
from flask import Blueprint, abort, current_app, render_template

from extensions import db
from models import ActivityLog, Alert, LoginAttempt, RiskEvent, User
from models.activity import EMPLOYEE_ACTIONS, MANAGER_ACTIONS
from models.alert import ALERT_TITLES, SEVERITIES
from services import dashboard_service
from services.employee_service import department_names, next_employee_id
from utils.security import manager_required

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")


@manager_bp.route("/")
@manager_bp.route("/dashboard")
@manager_required
def dashboard():
    return render_template("manager/dashboard.html", active="dashboard")


@manager_bp.route("/employees")
@manager_required
def employees():
    return render_template("manager/employees.html", active="employees", departments=department_names(),
                           suggested_id=next_employee_id())


@manager_bp.route("/employees/<int:user_id>")
@manager_required
def employee_detail(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    activities = (ActivityLog.query.filter_by(user_id=user.id)
                  .order_by(ActivityLog.timestamp.desc(), ActivityLog.id.desc()).limit(25).all())
    risk_events = (RiskEvent.query.filter_by(user_id=user.id)
                   .order_by(RiskEvent.created_at.desc(), RiskEvent.id.desc()).limit(25).all())
    alerts = (Alert.query.filter_by(user_id=user.id)
              .order_by(Alert.timestamp.desc(), Alert.id.desc()).limit(15).all())
    attempts = (LoginAttempt.query.filter_by(employee_id=user.employee_id)
                .order_by(LoginAttempt.timestamp.desc()).limit(10).all())
    return render_template("manager/employee_detail.html", active="employees", user=user,
                           activities=activities, risk_events=risk_events, alerts=alerts, attempts=attempts,
                           action_counts=dashboard_service.action_counter(user.id),
                           departments=department_names())


@manager_bp.route("/activity")
@manager_required
def activity():
    return render_template("manager/activity.html", active="activity",
                           actions=EMPLOYEE_ACTIONS + MANAGER_ACTIONS, severities=SEVERITIES)


@manager_bp.route("/alerts")
@manager_required
def alerts():
    return render_template("manager/alerts.html", active="alerts", severities=SEVERITIES,
                           alert_types=sorted(ALERT_TITLES.items(), key=lambda kv: kv[1]))


@manager_bp.route("/risk")
@manager_required
def risk():
    return render_template("manager/risk.html", active="risk")


@manager_bp.route("/audit")
@manager_required
def audit():
    return render_template("manager/audit_logs.html", active="audit", actions=MANAGER_ACTIONS)


@manager_bp.route("/settings")
@manager_required
def settings():
    cfg = current_app.config
    policy = {
        "levels": [(level, bound) for bound, level in reversed(cfg["RISK_LEVELS"])],
        "cap": cfg["RISK_SCORE_CAP"],
        "decay": cfg["RISK_DECAY_PER_HOUR"],
        "decay_grace": cfg["RISK_DECAY_GRACE_MINUTES"],
        "work_hours": f"{cfg['WORK_HOURS_START']:02d}:00 – {cfg['WORK_HOURS_END']:02d}:00, Monday – Friday",
        "alert_cooldown": cfg["ALERT_COOLDOWN_MINUTES"],
        "lockout": f"{cfg['LOGIN_MAX_FAILURES']} failures per ID / {cfg['LOGIN_IP_MAX_FAILURES']} per IP "
                   f"→ locked for {cfg['LOGIN_LOCKOUT_MINUTES']} minutes",
        "session": int(cfg["PERMANENT_SESSION_LIFETIME"].total_seconds() // 60),
        "presence": cfg["PRESENCE_TIMEOUT_SECONDS"],
    }
    return render_template("manager/settings.html", active="settings", policy=policy)
