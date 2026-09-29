"""Read-side queries for the manager dashboard. Every number comes from MySQL."""
from collections import Counter, OrderedDict
from datetime import timedelta

from flask import current_app

from extensions import db
from models import ActivityLog, Alert, LoginAttempt, RiskEvent, RiskScore, User
from models.alert import SEVERITIES
from utils.helpers import iso, now

LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def _start_of_day():
    return now().replace(hour=0, minute=0, second=0)


def _online_cutoff():
    return now() - timedelta(seconds=current_app.config["PRESENCE_TIMEOUT_SECONDS"])


def stats():
    today = _start_of_day()
    employees = User.query.filter(User.role == "employee")
    return {
        "total_employees": employees.count(),
        "active_accounts": employees.filter(User.status == "active").count(),
        "online_now": employees.filter(User.status == "active", User.is_online.is_(True),
                                       User.last_seen >= _online_cutoff()).count(),
        "activities_today": ActivityLog.query.filter(ActivityLog.timestamp >= today).count(),
        "suspicious_today": ActivityLog.query.filter(ActivityLog.timestamp >= today,
                                                     ActivityLog.risk_score > 0).count(),
        "new_alerts": Alert.query.filter(Alert.status == "NEW").count(),
        "high_critical_open": Alert.query.filter(Alert.status != "RESOLVED",
                                                 Alert.severity.in_(["HIGH", "CRITICAL"])).count(),
        "employees_at_risk": (RiskScore.query.join(User, RiskScore.user_id == User.id)
                              .filter(User.role == "employee", RiskScore.risk_level.in_(["HIGH", "CRITICAL"]))
                              .count()),
        "failed_logins_today": LoginAttempt.query.filter(LoginAttempt.timestamp >= today,
                                                         LoginAttempt.success.is_(False)).count(),
    }


def charts():
    current = now()
    # ---- activity & alerts over the last 24 hours, hourly buckets
    start = (current - timedelta(hours=23)).replace(minute=0, second=0)
    buckets = OrderedDict(((start + timedelta(hours=i)), [0, 0, 0]) for i in range(24))
    rows = db.session.query(ActivityLog.timestamp, ActivityLog.risk_score).filter(
        ActivityLog.timestamp >= start).all()
    for ts, risk in rows:
        key = ts.replace(minute=0, second=0)
        if key in buckets:
            buckets[key][0] += 1
            if risk > 0:
                buckets[key][1] += 1
    for (ts,) in db.session.query(Alert.timestamp).filter(Alert.timestamp >= start).all():
        key = ts.replace(minute=0, second=0)
        if key in buckets:
            buckets[key][2] += 1
    timeline = {
        "labels": [k.strftime("%H:00") for k in buckets],
        "activities": [v[0] for v in buckets.values()],
        "suspicious": [v[1] for v in buckets.values()],
        "alerts": [v[2] for v in buckets.values()],
    }

    # ---- alerts per day by severity (7 days)
    day0 = _start_of_day() - timedelta(days=6)
    days = [day0 + timedelta(days=i) for i in range(7)]
    per_day = {s: [0] * 7 for s in SEVERITIES}
    for ts, sev in db.session.query(Alert.timestamp, Alert.severity).filter(Alert.timestamp >= day0).all():
        idx = (ts.date() - day0.date()).days
        if 0 <= idx < 7:
            per_day[sev][idx] += 1
    alerts_by_day = {"labels": [d.strftime("%a %d") for d in days], "series": per_day}

    # ---- activity types and most active employees today
    today = _start_of_day()
    types = (db.session.query(ActivityLog.action, db.func.count(ActivityLog.id))
             .filter(ActivityLog.timestamp >= today).group_by(ActivityLog.action)
             .order_by(db.func.count(ActivityLog.id).desc()).all())
    top = (db.session.query(ActivityLog.employee_id, db.func.count(ActivityLog.id))
           .filter(ActivityLog.timestamp >= today, ActivityLog.actor_role == "employee")
           .group_by(ActivityLog.employee_id).order_by(db.func.count(ActivityLog.id).desc()).limit(8).all())
    return {
        "timeline": timeline,
        "alerts_by_day": alerts_by_day,
        "action_types": {"labels": [a for a, _ in types], "values": [c for _, c in types]},
        "top_employees": {"labels": [e for e, _ in top], "values": [c for _, c in top]},
    }


def risk_groups():
    groups = {level: [] for level in LEVELS}
    employees = (User.query.filter(User.role == "employee")
                 .outerjoin(RiskScore, RiskScore.user_id == User.id)
                 .order_by(RiskScore.current_score.desc(), User.employee_id).all())
    latest_reason = {}
    for user_id, reason in (db.session.query(RiskEvent.user_id, RiskEvent.reason)
                            .order_by(RiskEvent.created_at.desc(), RiskEvent.id.desc()).limit(300).all()):
        latest_reason.setdefault(user_id, reason)
    for u in employees:
        level = u.risk.risk_level if u.risk else "LOW"
        groups[level].append({
            "id": u.id, "employee_id": u.employee_id, "name": u.name, "department": u.department,
            "status": u.status, "score": u.risk.current_score if u.risk else 0,
            "last_reason": latest_reason.get(u.id), "online": u.online,
        })
    return {"groups": groups, "counts": {k: len(v) for k, v in groups.items()}}


def presence():
    users = User.query.filter(User.role == "employee").order_by(User.last_seen.desc()).all()
    rows = [{
        "id": u.id, "employee_id": u.employee_id, "name": u.name, "department": u.department,
        "status": u.status, "online": u.online, "last_seen": iso(u.last_seen), "last_login": iso(u.last_login),
    } for u in users]
    rows.sort(key=lambda r: (not r["online"], r["status"] != "active"))
    return rows


def recent_logins(limit=8):
    ok = (LoginAttempt.query.filter(LoginAttempt.success.is_(True))
          .order_by(LoginAttempt.timestamp.desc()).limit(limit).all())
    failed = (LoginAttempt.query.filter(LoginAttempt.success.is_(False))
              .order_by(LoginAttempt.timestamp.desc()).limit(limit).all())
    return [a.to_dict() for a in ok], [a.to_dict() for a in failed]


def dashboard_payload():
    ok, failed = recent_logins()
    feed = ActivityLog.query.order_by(ActivityLog.timestamp.desc(), ActivityLog.id.desc()).limit(30).all()
    alerts = Alert.query.order_by(Alert.timestamp.desc(), Alert.id.desc()).limit(8).all()
    return {
        "stats": stats(),
        "charts": charts(),
        "feed": [a.to_feed_dict() for a in feed],
        "alerts": [a.to_dict() for a in alerts],
        "risk": risk_groups(),
        "presence": presence(),
        "recent_logins": ok,
        "failed_logins": failed,
        "generated_at": iso(now()),
    }


def action_counter(user_id, days=7):
    since = now() - timedelta(days=days)
    rows = db.session.query(ActivityLog.action).filter(ActivityLog.user_id == user_id,
                                                       ActivityLog.timestamp >= since).all()
    return Counter(a for (a,) in rows).most_common()
