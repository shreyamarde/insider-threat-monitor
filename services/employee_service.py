"""Employee account management performed by managers (every change is audited)."""
import re

from flask import current_app
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Department, RiskScore, User
from services import alert_service, notification_service
from services.activity_logger import log_activity
from utils.helpers import now
from utils.validators import ValidationError, validate_employee_payload, validate_password


class EmployeeError(Exception):
    def __init__(self, message, status=400, field=None):
        super().__init__(message)
        self.message, self.status, self.field = message, status, field


def department_names():
    return [d.name for d in Department.query.order_by(Department.name).all()]


def next_employee_id(prefix="EMP"):
    ids = db.session.query(User.employee_id).filter(User.employee_id.like(f"{prefix}%")).all()
    numbers = [int(m.group(1)) for (eid,) in ids if (m := re.match(rf"^{prefix}(\d{{4}})$", eid))]
    return f"{prefix}{(max(numbers) + 1 if numbers else 1001):04d}"


def _check_unique(employee_id=None, email=None, exclude_id=None):
    if employee_id:
        q = User.query.filter(User.employee_id == employee_id)
        if exclude_id:
            q = q.filter(User.id != exclude_id)
        if q.first():
            raise EmployeeError(f"Employee ID {employee_id} already exists.", 409, "employee_id")
    if email:
        q = User.query.filter(db.func.lower(User.email) == email.lower())
        if exclude_id:
            q = q.filter(User.id != exclude_id)
        if q.first():
            raise EmployeeError(f"Email {email} is already used by another account.", 409, "email")


def _privilege_alert(target, manager, message, activity):
    alert = alert_service.raise_alert(target, "PRIVILEGE_CHANGE", "MEDIUM", message, activity)
    db.session.commit()
    notification_service.emit_alert(alert)


def create_employee(manager, payload):
    try:
        data = validate_employee_payload(payload, department_names(),
                                         min_password=current_app.config["PASSWORD_MIN_LENGTH"])
    except ValidationError as e:
        raise EmployeeError(next(iter(e.errors.values())), 400, next(iter(e.errors.keys())))
    _check_unique(data["employee_id"], data["email"])

    user = User(employee_id=data["employee_id"], name=data["name"], email=data["email"],
                department=data["department"], job_title=data["job_title"], role=data["role"],
                status=data["status"], must_change_password=True, created_by=manager.id,
                created_at=now(), updated_at=now())
    user.set_password(data["password"])
    try:
        db.session.add(user)
        db.session.flush()
        db.session.add(RiskScore(user_id=user.id, current_score=0, risk_level="LOW", last_updated=now()))
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        raise EmployeeError("An account with this employee ID or email already exists.", 409)

    activity = log_activity(manager, "CREATE_EMPLOYEE", resource=f"employee:{user.employee_id}",
                            description=f"Created {user.role} account {user.employee_id} ({user.name}, "
                                        f"{user.department}, status {user.status})")
    if user.role == "manager":
        _privilege_alert(user, manager, f"Manager account {user.employee_id} created by {manager.employee_id}", activity)
    return user


def update_employee(manager, user, payload):
    try:
        data = validate_employee_payload(payload, department_names(), partial=True)
    except ValidationError as e:
        raise EmployeeError(next(iter(e.errors.values())), 400, next(iter(e.errors.keys())))
    data.pop("employee_id", None)  # IDs are permanent
    data.pop("password", None)
    if user.id == manager.id and (data.get("role", "manager") != "manager" or data.get("status", "active") != "active"):
        raise EmployeeError("You cannot change your own role or disable your own account.", 400)
    if "email" in data:
        _check_unique(email=data["email"], exclude_id=user.id)

    changes = []
    for key, value in data.items():
        if getattr(user, key) != value:
            changes.append(f"{key}: {getattr(user, key)} → {value}")
            setattr(user, key, value)
    if not changes:
        return user, []

    old_role = next((c for c in changes if c.startswith("role:")), None)
    status_change = next((c for c in changes if c.startswith("status:")), None)
    if status_change:
        user.is_online = False if user.status == "disabled" else user.is_online
    action = "UPDATE_EMPLOYEE"
    if status_change and len(changes) == 1:
        action = "DISABLE_EMPLOYEE" if user.status == "disabled" else "ENABLE_EMPLOYEE"
    activity = log_activity(manager, action, resource=f"employee:{user.employee_id}",
                            description=f"Updated {user.employee_id}: " + "; ".join(changes))
    if old_role:
        _privilege_alert(user, manager, f"Role of {user.employee_id} changed ({old_role}) by {manager.employee_id}",
                         activity)
    if user.status == "disabled":
        notification_service.notify_user(user.id, "account:disabled", {"message": "Your account has been disabled."})
        notification_service.emit_presence(user)
    return user, changes


def set_status(manager, user, status):
    if status not in ("active", "disabled"):
        raise EmployeeError("Status must be active or disabled.")
    if user.id == manager.id:
        raise EmployeeError("You cannot disable your own account.")
    if user.status == status:
        return user
    user.status = status
    if status == "disabled":
        user.is_online = False
    action = "DISABLE_EMPLOYEE" if status == "disabled" else "ENABLE_EMPLOYEE"
    log_activity(manager, action, resource=f"employee:{user.employee_id}",
                 description=f"{'Disabled' if status == 'disabled' else 'Re-enabled'} account {user.employee_id} ({user.name})")
    if status == "disabled":
        notification_service.notify_user(user.id, "account:disabled", {"message": "Your account has been disabled."})
    notification_service.emit_presence(user)
    return user


def reset_password(manager, user, new_password):
    error = validate_password(new_password or "", current_app.config["PASSWORD_MIN_LENGTH"],
                              employee_id=user.employee_id, name=user.name)
    if error:
        raise EmployeeError(error, 400, "password")
    user.set_password(new_password)
    user.must_change_password = True
    log_activity(manager, "RESET_PASSWORD", resource=f"employee:{user.employee_id}",
                 description=f"Reset password for {user.employee_id}; change required at next login")
    return user
