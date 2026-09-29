from extensions import db
from utils.helpers import iso, now

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
RULE_SEVERITIES = ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL")


class RiskScore(db.Model):
    """Current cumulative risk of one user (one row per user)."""
    __tablename__ = "risk_scores"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    current_score = db.Column(db.Integer, nullable=False, default=0)
    risk_level = db.Column(db.Enum(*RISK_LEVELS, name="risk_level"), nullable=False, default="LOW")
    last_updated = db.Column(db.DateTime, nullable=False, default=now)
    last_increase_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="risk")


class RiskEvent(db.Model):
    """Explains every change to a risk score ("why did it go up?")."""
    __tablename__ = "risk_events"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id = db.Column(db.BigInteger, db.ForeignKey("activity_logs.id", ondelete="SET NULL"))
    rule_key = db.Column(db.String(40), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    score_before = db.Column(db.Integer, nullable=False)
    score_after = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now, index=True)

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.user.employee_id if self.user else None,
            "name": self.user.name if self.user else None,
            "activity_id": self.activity_id,
            "rule_key": self.rule_key,
            "points": self.points,
            "reason": self.reason,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "created_at": iso(self.created_at),
        }


class RiskRule(db.Model):
    """Configurable detection rule: managers can tune points/thresholds in Settings."""
    __tablename__ = "risk_rules"

    id = db.Column(db.Integer, primary_key=True)
    rule_key = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    points = db.Column(db.Integer, nullable=False, default=0)
    threshold = db.Column(db.Integer, nullable=False, default=1)
    window_minutes = db.Column(db.Integer, nullable=False, default=0)
    severity = db.Column(db.Enum(*RULE_SEVERITIES, name="rule_severity"), nullable=False, default="NONE")
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    def to_dict(self):
        return {
            "id": self.id,
            "rule_key": self.rule_key,
            "name": self.name,
            "description": self.description,
            "points": self.points,
            "threshold": self.threshold,
            "window_minutes": self.window_minutes,
            "severity": self.severity,
            "enabled": self.enabled,
            "updated_at": iso(self.updated_at),
        }
