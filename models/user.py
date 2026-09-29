from flask import current_app
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from utils.helpers import iso, now

ROLES = ("employee", "manager")
ACCOUNT_STATUSES = ("active", "disabled")


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(60), db.ForeignKey("departments.name"), nullable=False)
    job_title = db.Column(db.String(80))
    role = db.Column(db.Enum(*ROLES, name="user_role"), nullable=False, default="employee")
    status = db.Column(db.Enum(*ACCOUNT_STATUSES, name="account_status"), nullable=False, default="active")
    must_change_password = db.Column(db.Boolean, nullable=False, default=True)
    is_online = db.Column(db.Boolean, nullable=False, default=False)
    last_login = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))
    last_seen = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    risk = db.relationship("RiskScore", uselist=False, back_populates="user", lazy="joined")

    # ------------------------------------------------------------ passwords
    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    # -------------------------------------------------------------- helpers
    @property
    def is_manager(self):
        return self.role == "manager"

    @property
    def is_active(self):  # used by Flask-Login: disabled accounts cannot hold a session
        return self.status == "active"

    @property
    def online(self):
        if not self.is_online or not self.last_seen:
            return False
        timeout = current_app.config["PRESENCE_TIMEOUT_SECONDS"]
        return (now() - self.last_seen).total_seconds() <= timeout

    @property
    def initials(self):
        parts = [p for p in self.name.split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "?"

    def to_public_dict(self):
        """Safe for the employee themself (no risk data, never the password hash)."""
        return {
            "employee_id": self.employee_id,
            "name": self.name,
            "email": self.email,
            "department": self.department,
            "job_title": self.job_title,
            "role": self.role,
            "status": self.status,
            "last_login": iso(self.last_login),
            "created_at": iso(self.created_at),
        }

    def to_manager_dict(self):
        """Full monitoring view for managers (still never the password hash)."""
        data = self.to_public_dict()
        data.update({
            "id": self.id,
            "online": self.online,
            "last_seen": iso(self.last_seen),
            "last_login_ip": self.last_login_ip,
            "must_change_password": self.must_change_password,
            "updated_at": iso(self.updated_at),
            "risk_score": self.risk.current_score if self.risk else 0,
            "risk_level": self.risk.risk_level if self.risk else "LOW",
        })
        return data


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    employee_id = db.Column(db.String(20), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, nullable=False, default=now, index=True)
    success = db.Column(db.Boolean, nullable=False)
    reason = db.Column(db.String(60))

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": iso(self.timestamp),
            "success": self.success,
            "reason": self.reason,
        }
