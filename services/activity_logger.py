"""
Centralised activity logging — the single entry point of the monitoring pipeline.

    Employee action -> route -> log_activity()
        1. insert activity_logs row
        2. risk engine evaluates it
        3. risk_scores / risk_events updated
        4. alerts created if rules with a severity fired
        5. COMMIT (all of the above in one transaction)
        6. Socket.IO push to managers (only after the data is safely stored)
"""
import logging

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import ActivityLog
from services import alert_service, notification_service, risk_engine
from utils.helpers import client_ip, client_user_agent, now

log = logging.getLogger(__name__)


def log_activity(user, action, resource=None, description=None, risk_score=0, *,
                 status="SUCCESS", employee_id=None, record_count=0, context=None):
    """
    Record `action` performed by `user` (None for unknown login IDs) and run it
    through the risk pipeline. `risk_score` is an optional base score added on
    top of whatever the rules decide. Returns the stored ActivityLog.
    """
    emp_id = user.employee_id if user is not None else (employee_id or "UNKNOWN")
    activity = ActivityLog(
        user_id=user.id if user is not None else None,
        employee_id=emp_id[:20],
        actor_role=user.role if user is not None else None,
        action=action,
        resource=(resource or "")[:255] or None,
        description=(description or "")[:500] or None,
        record_count=record_count or 0,
        timestamp=now(),
        ip_address=client_ip(),
        user_agent=client_user_agent(),
        status=status,
    )
    alerts = []
    try:
        db.session.add(activity)
        db.session.flush()  # gives the activity an id so rules/alerts can reference it

        triggers = risk_engine.evaluate(activity, user, context)
        if risk_score:
            triggers.insert(0, risk_engine.Trigger("BASE_SCORE", int(risk_score),
                                                   f"Base score for {action}", "NONE"))
        cap = current_app.config["RISK_SCORE_CAP"]
        activity.risk_score = min(cap, sum(t.points for t in triggers))
        activity.risk_reason = "; ".join(f"+{t.points} {t.reason}" for t in triggers)[:1000] or None

        level_before = level_after = score = None
        if user is not None and activity.risk_score > 0:
            level_before, level_after, score = risk_engine.apply_score(user, activity, triggers)

        alerts = alert_service.generate_alerts(user, activity, triggers, level_before, level_after, score)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        log.exception("Risk pipeline failed for %s %s — storing the bare activity", emp_id, action)
        alerts = []
        activity = _store_bare(user, emp_id, action, resource, description, status, record_count)
        if activity is None:
            return None

    notification_service.emit_activity(activity)
    for alert in alerts:
        notification_service.emit_alert(alert)
    return activity


def _store_bare(user, emp_id, action, resource, description, status, record_count):
    """Fallback so an activity is never silently lost if scoring fails."""
    try:
        activity = ActivityLog(user_id=user.id if user is not None else None, employee_id=emp_id[:20],
                               actor_role=user.role if user is not None else None, action=action,
                               resource=(resource or "")[:255] or None,
                               description=(description or "")[:500] or None,
                               record_count=record_count or 0, timestamp=now(), ip_address=client_ip(),
                               user_agent=client_user_agent(), status=status)
        db.session.add(activity)
        db.session.commit()
        return activity
    except SQLAlchemyError:
        db.session.rollback()
        log.exception("Could not store activity %s for %s", action, emp_id)
        return None
