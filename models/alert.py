from extensions import db
from utils.helpers import iso, now

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
ALERT_STATUSES = ("NEW", "ACKNOWLEDGED", "RESOLVED")

ALERT_TITLES = {
    "REPEATED_FAILED_LOGIN": "Multiple failed login attempts",
    "NEW_LOCATION": "Login from a new location",
    "OFF_HOURS": "Access outside working hours",
    "SENSITIVE_ACCESS": "Sensitive record accessed",
    "UNAUTHORIZED_ACCESS": "Unauthorized access attempt",
    "PRIVILEGE_ESCALATION": "Privilege escalation attempt",
    "REPEATED_UNAUTHORIZED": "Repeated unauthorized access attempts",
    "MASS_RECORD_ACCESS": "Large number of records accessed",
    "REPEATED_SEARCH": "Repeated searches",
    "RAPID_ACTIONS": "Multiple rapid actions",
    "UNUSUAL_FREQUENCY": "Unusual access frequency",
    "SUSPICIOUS_BURST": "Multiple suspicious events",
    "RISK_LEVEL_ESCALATION": "Risk level escalated",
    "PRIVILEGE_CHANGE": "Account privileges changed",
}


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    employee_id = db.Column(db.String(20), nullable=False, index=True)
    activity_id = db.Column(db.BigInteger, db.ForeignKey("activity_logs.id", ondelete="SET NULL"))
    alert_type = db.Column(db.String(40), nullable=False)
    severity = db.Column(db.Enum(*SEVERITIES, name="alert_severity"), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    risk_score = db.Column(db.Integer, nullable=False, default=0)
    timestamp = db.Column(db.DateTime, nullable=False, default=now, index=True)
    status = db.Column(db.Enum(*ALERT_STATUSES, name="alert_status"), nullable=False, default="NEW", index=True)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at = db.Column(db.DateTime)
    resolution_note = db.Column(db.String(500))

    user = db.relationship("User", foreign_keys=[user_id], lazy="joined")
    acknowledger = db.relationship("User", foreign_keys=[acknowledged_by])
    resolver = db.relationship("User", foreign_keys=[resolved_by])
    activity = db.relationship("ActivityLog")

    @property
    def title(self):
        return ALERT_TITLES.get(self.alert_type, self.alert_type.replace("_", " ").title())

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "name": self.user.name if self.user else None,
            "department": self.user.department if self.user else None,
            "activity_id": self.activity_id,
            "alert_type": self.alert_type,
            "title": self.title,
            "severity": self.severity,
            "message": self.message,
            "risk_score": self.risk_score,
            "risk_level": self.user.risk.risk_level if self.user and self.user.risk else None,
            "timestamp": iso(self.timestamp),
            "status": self.status,
            "acknowledged_by": self.acknowledger.employee_id if self.acknowledger else None,
            "acknowledged_at": iso(self.acknowledged_at),
            "resolved_by": self.resolver.employee_id if self.resolver else None,
            "resolved_at": iso(self.resolved_at),
            "resolution_note": self.resolution_note,
        }
