"""
JSON REST API. Every endpoint enforces authorization on the server:
  /api/manager/*   -> @manager_required
  /api/employee/*  -> @employee_required
"""
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import ActivityLog, Alert, LoginAttempt, RiskEvent, RiskRule, RiskScore, User
from models.activity import MANAGER_ACTIONS
from models.alert import SEVERITIES
from models.risk import RULE_SEVERITIES
from services import alert_service, dashboard_service, employee_service, notification_service
from services.activity_logger import log_activity
from services.employee_service import EmployeeError
from utils.helpers import now
from utils.security import employee_required, manager_required
from utils.validators import clean, parse_date, parse_int

api_bp = Blueprint("api", __name__, url_prefix="/api")

LEVEL_BANDS = {"LOW": (0, 29), "MEDIUM": (30, 59), "HIGH": (60, 79), "CRITICAL": (80, 100)}


def error(message, status=400, field=None):
    body = {"error": "request_failed", "message": message}
    if field:
        body["field"] = field
    return jsonify(body), status


def me():
    return current_user._get_current_object()


def paginate(query, serializer, default_per_page=25):
    page = parse_int(request.args.get("page"), 1, minimum=1)
    per_page = parse_int(request.args.get("per_page"), default_per_page, minimum=1, maximum=100)
    result = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({"items": [serializer(x) for x in result.items], "total": result.total,
                    "page": result.page, "pages": result.pages or 1, "per_page": per_page})


def apply_date_range(query, column):
    date_from = parse_date(request.args.get("date_from"))
    date_to = parse_date(request.args.get("date_to"))
    if date_from:
        query = query.filter(column >= date_from)
    if date_to:
        query = query.filter(column < date_to + timedelta(days=1))
    return query


def employee_filter(query, id_column):
    """Filter by employee ID or (partial) name."""
    term = clean(request.args.get("employee"), 100)
    if not term:
        return query
    matching_ids = [eid for (eid,) in db.session.query(User.employee_id)
                    .filter(or_(User.employee_id.ilike(f"%{term}%"), User.name.ilike(f"%{term}%"))).all()]
    return query.filter(or_(id_column.ilike(f"%{term}%"), id_column.in_(matching_ids or [""])))


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# ====================================================================
#  Health (no auth: used to show DB status)
# ====================================================================

@api_bp.route("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "ok", "database": "up"})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"status": "degraded", "database": "down"}), 503


# ====================================================================
#  Manager: dashboard
# ====================================================================

@api_bp.route("/manager/dashboard")
@manager_required
def manager_dashboard():
    return jsonify(dashboard_service.dashboard_payload())


@api_bp.route("/manager/stats")
@manager_required
def manager_stats():
    return jsonify(dashboard_service.stats())


@api_bp.route("/manager/presence")
@manager_required
def manager_presence():
    return jsonify(dashboard_service.presence())


# ====================================================================
#  Manager: employees
# ====================================================================

@api_bp.route("/manager/employees", methods=["GET"])
@manager_required
def list_employees():
    q = User.query.outerjoin(RiskScore, RiskScore.user_id == User.id)
    term = clean(request.args.get("q"), 100)
    if term:
        like = f"%{term}%"
        q = q.filter(or_(User.employee_id.ilike(like), User.name.ilike(like), User.email.ilike(like)))
    for field in ("department", "status", "role"):
        value = clean(request.args.get(field), 60)
        if value:
            q = q.filter(getattr(User, field) == value)
    level = clean(request.args.get("risk_level"), 10).upper()
    if level in LEVEL_BANDS:
        q = q.filter(RiskScore.risk_level == level)
    if request.args.get("online") == "1":
        cutoff = now() - timedelta(seconds=current_app.config["PRESENCE_TIMEOUT_SECONDS"])
        q = q.filter(User.is_online.is_(True), User.last_seen >= cutoff)
    q = q.order_by(User.role.desc(), User.employee_id)
    return paginate(q, lambda u: u.to_manager_dict(), default_per_page=50)


@api_bp.route("/manager/employees/next-id")
@manager_required
def employee_next_id():
    return jsonify({"employee_id": employee_service.next_employee_id()})


@api_bp.route("/manager/employees", methods=["POST"])
@manager_required
def create_employee():
    try:
        user = employee_service.create_employee(me(), json_body())
    except EmployeeError as e:
        return error(e.message, e.status, e.field)
    return jsonify({"message": f"Employee {user.employee_id} created.", "employee": user.to_manager_dict()}), 201


@api_bp.route("/manager/employees/<int:user_id>", methods=["GET"])
@manager_required
def get_employee(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return error("Employee not found.", 404)
    return jsonify(user.to_manager_dict())


@api_bp.route("/manager/employees/<int:user_id>", methods=["PUT"])
@manager_required
def update_employee(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return error("Employee not found.", 404)
    try:
        user, changes = employee_service.update_employee(me(), user, json_body())
    except EmployeeError as e:
        return error(e.message, e.status, e.field)
    return jsonify({"message": "Employee updated." if changes else "No changes.", "changes": changes,
                    "employee": user.to_manager_dict()})


@api_bp.route("/manager/employees/<int:user_id>", methods=["DELETE"])
@manager_required
def disable_employee(user_id):
    """Accounts are never hard-deleted (audit trail); DELETE disables the account."""
    user = db.session.get(User, user_id)
    if user is None:
        return error("Employee not found.", 404)
    try:
        employee_service.set_status(me(), user, "disabled")
    except EmployeeError as e:
        return error(e.message, e.status)
    return jsonify({"message": f"{user.employee_id} disabled.", "employee": user.to_manager_dict()})


@api_bp.route("/manager/employees/<int:user_id>/status", methods=["PUT"])
@manager_required
def set_employee_status(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return error("Employee not found.", 404)
    try:
        employee_service.set_status(me(), user, clean(json_body().get("status"), 20).lower())
    except EmployeeError as e:
        return error(e.message, e.status)
    return jsonify({"message": f"{user.employee_id} is now {user.status}.", "employee": user.to_manager_dict()})


@api_bp.route("/manager/employees/<int:user_id>/reset-password", methods=["POST"])
@manager_required
def reset_employee_password(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return error("Employee not found.", 404)
    try:
        employee_service.reset_password(me(), user, json_body().get("password"))
    except EmployeeError as e:
        return error(e.message, e.status, e.field)
    return jsonify({"message": f"Password for {user.employee_id} reset. They must change it at next login."})


# ====================================================================
#  Manager: activity
# ====================================================================

@api_bp.route("/manager/activities")
@manager_required
def list_activities():
    q = ActivityLog.query
    q = employee_filter(q, ActivityLog.employee_id)
    action = clean(request.args.get("action"), 40).upper()
    if action:
        q = q.filter(ActivityLog.action == action)
    status = clean(request.args.get("status"), 10).upper()
    if status:
        q = q.filter(ActivityLog.status == status)
    role = clean(request.args.get("role"), 20).lower()
    if role in ("employee", "manager"):
        q = q.filter(ActivityLog.actor_role == role)
    if request.args.get("suspicious") == "1":
        q = q.filter(ActivityLog.risk_score > 0)
    level = clean(request.args.get("risk_level"), 10).upper()
    if level in LEVEL_BANDS:  # employee's current risk level
        ids = [uid for (uid,) in db.session.query(RiskScore.user_id).filter(RiskScore.risk_level == level).all()]
        q = q.filter(ActivityLog.user_id.in_(ids or [-1]))
    severity = clean(request.args.get("severity"), 10).upper()
    alert_status = clean(request.args.get("alert_status"), 15).upper()
    if severity or alert_status:  # activities that produced alerts of that kind
        sub = db.session.query(Alert.activity_id).filter(Alert.activity_id.isnot(None))
        if severity:
            sub = sub.filter(Alert.severity == severity)
        if alert_status:
            sub = sub.filter(Alert.status == alert_status)
        q = q.filter(ActivityLog.id.in_(sub))
    q = apply_date_range(q, ActivityLog.timestamp)
    q = q.order_by(ActivityLog.timestamp.desc(), ActivityLog.id.desc())
    return paginate(q, lambda a: a.to_manager_dict())


@api_bp.route("/manager/activities/<int:activity_id>")
@manager_required
def activity_detail(activity_id):
    activity = db.session.get(ActivityLog, activity_id)
    if activity is None:
        return error("Activity not found.", 404)
    data = activity.to_manager_dict()
    data["risk_events"] = [e.to_dict() for e in RiskEvent.query.filter_by(activity_id=activity.id).all()]
    data["alerts"] = [a.to_dict() for a in Alert.query.filter_by(activity_id=activity.id).all()]
    if activity.user:
        data["employee"] = {
            "id": activity.user.id, "employee_id": activity.user.employee_id, "name": activity.user.name,
            "department": activity.user.department, "role": activity.user.role,
            "current_risk_score": activity.user.risk.current_score if activity.user.risk else 0,
            "current_risk_level": activity.user.risk.risk_level if activity.user.risk else "LOW",
        }
    return jsonify(data)


# ====================================================================
#  Manager: alerts
# ====================================================================

@api_bp.route("/manager/alerts")
@manager_required
def list_alerts():
    q = Alert.query
    q = employee_filter(q, Alert.employee_id)
    severity = clean(request.args.get("severity"), 10).upper()
    if severity in SEVERITIES:
        q = q.filter(Alert.severity == severity)
    status = clean(request.args.get("status"), 15).upper()
    if status == "OPEN":
        q = q.filter(Alert.status != "RESOLVED")
    elif status:
        q = q.filter(Alert.status == status)
    alert_type = clean(request.args.get("alert_type"), 40).upper()
    if alert_type:
        q = q.filter(Alert.alert_type == alert_type)
    q = apply_date_range(q, Alert.timestamp)
    q = q.order_by(Alert.timestamp.desc(), Alert.id.desc())
    return paginate(q, lambda a: a.to_dict())


@api_bp.route("/manager/alerts/<int:alert_id>")
@manager_required
def alert_detail(alert_id):
    alert = db.session.get(Alert, alert_id)
    if alert is None:
        return error("Alert not found.", 404)
    data = alert.to_dict()
    data["activity"] = alert.activity.to_manager_dict() if alert.activity else None
    return jsonify(data)


def _change_alert(alert_id, operation):
    alert = db.session.get(Alert, alert_id)
    if alert is None:
        return error("Alert not found.", 404)
    try:
        if operation == "acknowledge":
            alert_service.acknowledge(alert, me())
            action, text = "ACKNOWLEDGE_ALERT", "Acknowledged"
        else:
            note = clean(json_body().get("note"), 500)
            alert_service.resolve(alert, me(), note)
            action, text = "RESOLVE_ALERT", "Resolved"
    except alert_service.AlertStateError as e:
        db.session.rollback()
        return error(str(e), 409)
    log_activity(me(), action, resource=f"alert:{alert.id}",
                 description=f"{text} {alert.severity} alert '{alert.title}' for {alert.employee_id}"
                             + (f" — note: {alert.resolution_note}" if operation == "resolve" and alert.resolution_note else ""))
    notification_service.emit_alert_update(alert)
    return jsonify({"message": f"Alert #{alert.id} {text.lower()}.", "alert": alert.to_dict()})


@api_bp.route("/manager/alerts/<int:alert_id>/acknowledge", methods=["PUT"])
@manager_required
def acknowledge_alert(alert_id):
    return _change_alert(alert_id, "acknowledge")


@api_bp.route("/manager/alerts/<int:alert_id>/resolve", methods=["PUT"])
@manager_required
def resolve_alert(alert_id):
    return _change_alert(alert_id, "resolve")


# ====================================================================
#  Manager: risk, audit, login attempts, rules
# ====================================================================

@api_bp.route("/manager/risk")
@manager_required
def risk_overview():
    data = dashboard_service.risk_groups()
    events = RiskEvent.query.order_by(RiskEvent.created_at.desc(), RiskEvent.id.desc()).limit(40).all()
    data["recent_events"] = [e.to_dict() for e in events]
    return jsonify(data)


@api_bp.route("/manager/audit")
@manager_required
def audit_log():
    q = ActivityLog.query.filter(or_(ActivityLog.actor_role == "manager", ActivityLog.action.in_(MANAGER_ACTIONS)))
    q = employee_filter(q, ActivityLog.employee_id)
    action = clean(request.args.get("action"), 40).upper()
    if action:
        q = q.filter(ActivityLog.action == action)
    q = apply_date_range(q, ActivityLog.timestamp)
    q = q.order_by(ActivityLog.timestamp.desc(), ActivityLog.id.desc())
    return paginate(q, lambda a: a.to_manager_dict())


@api_bp.route("/manager/login-attempts")
@manager_required
def login_attempts():
    q = LoginAttempt.query
    q = employee_filter(q, LoginAttempt.employee_id)
    success = request.args.get("success")
    if success in ("0", "1"):
        q = q.filter(LoginAttempt.success.is_(success == "1"))
    q = apply_date_range(q, LoginAttempt.timestamp)
    q = q.order_by(LoginAttempt.timestamp.desc(), LoginAttempt.id.desc())
    return paginate(q, lambda a: a.to_dict())


@api_bp.route("/manager/rules")
@manager_required
def list_rules():
    return jsonify([r.to_dict() for r in RiskRule.query.order_by(RiskRule.id).all()])


@api_bp.route("/manager/rules/<int:rule_id>", methods=["PUT"])
@manager_required
def update_rule(rule_id):
    rule = db.session.get(RiskRule, rule_id)
    if rule is None:
        return error("Rule not found.", 404)
    body = json_body()
    limits = {"points": (0, 100), "threshold": (1, 1000), "window_minutes": (0, 1440)}
    changes = []
    for field, (low, high) in limits.items():
        if field in body:
            value = parse_int(body[field], None)
            if value is None or not low <= value <= high:
                return error(f"{field.replace('_', ' ').title()} must be between {low} and {high}.", 400, field)
            if value != getattr(rule, field):
                changes.append(f"{field} {getattr(rule, field)} → {value}")
                setattr(rule, field, value)
    if "severity" in body:
        severity = clean(str(body["severity"]), 10).upper()
        if severity not in RULE_SEVERITIES:
            return error("Invalid severity.", 400, "severity")
        if severity != rule.severity:
            changes.append(f"severity {rule.severity} → {severity}")
            rule.severity = severity
    if "enabled" in body:
        enabled = bool(body["enabled"])
        if enabled != rule.enabled:
            changes.append("enabled" if enabled else "disabled")
            rule.enabled = enabled
    if not changes:
        return jsonify({"message": "No changes.", "rule": rule.to_dict()})
    log_activity(me(), "UPDATE_RULE", resource=f"rule:{rule.rule_key}",
                 description=f"Updated rule {rule.rule_key}: " + "; ".join(changes))
    return jsonify({"message": f"Rule '{rule.name}' updated.", "rule": rule.to_dict()})


# ====================================================================
#  Employee API (own data only)
# ====================================================================

@api_bp.route("/employee/activity")
@employee_required
def employee_activity():
    q = ActivityLog.query.filter(ActivityLog.user_id == current_user.id).order_by(
        ActivityLog.timestamp.desc(), ActivityLog.id.desc())
    return paginate(q, lambda a: a.to_employee_dict(), default_per_page=20)


@api_bp.route("/employee/profile")
@employee_required
def employee_profile():
    return jsonify(current_user.to_public_dict())
