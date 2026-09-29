"""
Alert generation and lifecycle (NEW -> ACKNOWLEDGED -> RESOLVED).
Alerts are never deleted: they form part of the audit trail.
"""
from datetime import timedelta

from flask import current_app

from extensions import db
from models import Alert
from services.risk_engine import LEVEL_ORDER
from utils.helpers import now


def _in_cooldown(employee_id, alert_type, at):
    since = at - timedelta(minutes=current_app.config["ALERT_COOLDOWN_MINUTES"])
    return db.session.query(Alert.id).filter(
        Alert.employee_id == employee_id, Alert.alert_type == alert_type,
        Alert.status != "RESOLVED", Alert.timestamp >= since).first() is not None


def generate_alerts(user, activity, triggers, level_before=None, level_after=None, score=None):
    """Create alerts for triggered rules that carry a severity. Returns new Alert objects (not committed)."""
    employee_id = activity.employee_id
    risk_score = score if score is not None else (user.risk.current_score if user and user.risk else activity.risk_score)
    created = []
    for t in triggers:
        if t.severity == "NONE" or _in_cooldown(employee_id, t.rule_key, activity.timestamp):
            continue
        alert = Alert(user_id=user.id if user else None, employee_id=employee_id, activity_id=activity.id,
                      alert_type=t.rule_key, severity=t.severity, message=t.reason[:500],
                      risk_score=risk_score, timestamp=activity.timestamp, status="NEW")
        db.session.add(alert)
        created.append(alert)

    escalated = (user is not None and level_before and level_after
                 and LEVEL_ORDER[level_after] > LEVEL_ORDER[level_before]
                 and level_after in ("HIGH", "CRITICAL"))
    if escalated:
        latest = triggers[-1].reason if triggers else activity.action
        alert = Alert(user_id=user.id, employee_id=employee_id, activity_id=activity.id,
                      alert_type="RISK_LEVEL_ESCALATION", severity=level_after,
                      message=f"Risk level rose from {level_before} to {level_after} (score {risk_score}). "
                              f"Latest: {latest}"[:500],
                      risk_score=risk_score, timestamp=activity.timestamp, status="NEW")
        db.session.add(alert)
        created.append(alert)
    return created


def raise_alert(user, alert_type, severity, message, activity=None):
    """Create a single alert outside the rule engine (e.g. privilege changes)."""
    alert = Alert(user_id=user.id, employee_id=user.employee_id,
                  activity_id=activity.id if activity else None, alert_type=alert_type,
                  severity=severity, message=message[:500],
                  risk_score=user.risk.current_score if user.risk else 0,
                  timestamp=now(), status="NEW")
    db.session.add(alert)
    return alert


class AlertStateError(ValueError):
    pass


def acknowledge(alert, manager):
    if alert.status != "NEW":
        raise AlertStateError(f"Alert is already {alert.status.lower()}.")
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_by = manager.id
    alert.acknowledged_at = now()


def resolve(alert, manager, note=None):
    if alert.status == "RESOLVED":
        raise AlertStateError("Alert is already resolved.")
    if alert.status == "NEW":  # resolving implies it was seen
        alert.acknowledged_by = manager.id
        alert.acknowledged_at = now()
    alert.status = "RESOLVED"
    alert.resolved_by = manager.id
    alert.resolved_at = now()
    alert.resolution_note = (note or "").strip()[:500] or None
