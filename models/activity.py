from extensions import db
from utils.helpers import iso, now

BigId = db.BigInteger().with_variant(db.Integer, "sqlite")

# Actions performed by employees
EMPLOYEE_ACTIONS = (
    "LOGIN", "LOGOUT", "FAILED_LOGIN", "SEARCH", "VIEW_RECORD", "ADD_RECORD",
    "UPDATE_RECORD", "EXPORT_DATA", "UNAUTHORIZED_ACCESS", "PASSWORD_CHANGE",
)
# Actions performed by managers (audit trail)
MANAGER_ACTIONS = (
    "MANAGER_LOGIN", "CREATE_EMPLOYEE", "UPDATE_EMPLOYEE", "DISABLE_EMPLOYEE",
    "ENABLE_EMPLOYEE", "RESET_PASSWORD", "ACKNOWLEDGE_ALERT", "RESOLVE_ALERT",
    "UPDATE_RULE",
)
ACTIVITY_STATUSES = ("SUCCESS", "FAILED", "DENIED")


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(BigId, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    employee_id = db.Column(db.String(20), nullable=False, index=True)
    actor_role = db.Column(db.String(20))  # employee / manager / NULL for unknown IDs
    action = db.Column(db.String(40), nullable=False, index=True)
    resource = db.Column(db.String(255))
    description = db.Column(db.String(500))
    record_count = db.Column(db.Integer, nullable=False, default=0)
    timestamp = db.Column(db.DateTime, nullable=False, default=now, index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    status = db.Column(db.String(10), nullable=False, default="SUCCESS")
    risk_score = db.Column(db.Integer, nullable=False, default=0)
    risk_reason = db.Column(db.String(1000))

    user = db.relationship("User", lazy="joined")

    def to_feed_dict(self):
        """Compact form pushed over Socket.IO to the manager live feed."""
        return {
            "id": self.id,
            "timestamp": iso(self.timestamp),
            "employee_id": self.employee_id,
            "name": self.user.name if self.user else None,
            "actor_role": self.actor_role,
            "action": self.action,
            "resource": self.resource,
            "status": self.status,
            "risk_score": self.risk_score,
        }

    def to_manager_dict(self):
        data = self.to_feed_dict()
        data.update({
            "description": self.description,
            "record_count": self.record_count,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "risk_reason": self.risk_reason,
            "department": self.user.department if self.user else None,
        })
        return data

    def to_employee_dict(self):
        """What an employee may see about their own actions: no risk information."""
        return {
            "timestamp": iso(self.timestamp),
            "action": self.action,
            "resource": self.resource,
            "description": self.description,
            "status": self.status,
            "ip_address": self.ip_address,
        }
