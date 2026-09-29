"""
Explainable, rule-based risk engine.

Every activity is evaluated against the enabled rules in the `risk_rules`
table. Each rule that fires produces a Trigger with the number of points it
adds and a human readable reason. Points are added to the employee's
cumulative score (capped at 100) and every change is written to
`risk_events`, so a manager can always see *why* a score went up.

Rule thresholds, windows, points and alert severities are data, not code:
managers can tune them from Manager > Settings.
"""
from dataclasses import dataclass
from datetime import timedelta

from flask import current_app, g

from extensions import db
from models import ActivityLog, Alert, RiskEvent, RiskRule, RiskScore
from utils.helpers import now, risk_level_for

LEVEL_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

# rule_key, name, description, points, threshold, window_minutes, severity
# (kept in sync with the INSERT in database/schema.sql)
DEFAULT_RULES = [
    ("FAILED_LOGIN", "Failed login", "Each failed login attempt.", 10, 1, 0, "NONE"),
    ("REPEATED_FAILED_LOGIN", "Repeated failed logins", "Threshold failed logins for one employee ID within the window.", 20, 3, 10, "HIGH"),
    ("NEW_LOCATION", "Login from new location", "Successful login from an IP address this employee has never used before.", 10, 1, 0, "MEDIUM"),
    ("OFF_HOURS", "Outside working hours", "Activity outside configured working hours/days (counted once per window).", 15, 1, 60, "MEDIUM"),
    ("SENSITIVE_ACCESS", "Sensitive record access", "Viewing or editing a CONFIDENTIAL record.", 15, 1, 0, "MEDIUM"),
    ("UNAUTHORIZED_ACCESS", "Unauthorized access attempt", "Attempt to open a record or page outside the employee's permissions.", 30, 1, 0, "HIGH"),
    ("PRIVILEGE_ESCALATION", "Privilege escalation attempt", "Employee attempted to use a manager-only page or API.", 10, 1, 0, "HIGH"),
    ("REPEATED_UNAUTHORIZED", "Repeated unauthorized attempts", "Threshold unauthorized attempts within the window.", 25, 3, 15, "CRITICAL"),
    ("MASS_RECORD_ACCESS", "Large number of records accessed", "Threshold or more records viewed/exported within the window.", 20, 15, 5, "HIGH"),
    ("REPEATED_SEARCH", "Repeated searches", "Threshold searches within the window.", 10, 10, 5, "LOW"),
    ("RAPID_ACTIONS", "Multiple rapid actions", "Threshold actions of any kind within the window.", 15, 20, 1, "MEDIUM"),
    ("UNUSUAL_FREQUENCY", "Unusual access frequency", "Actions in the window exceed threshold x the employee's normal hourly rate (7-day baseline).", 15, 3, 60, "MEDIUM"),
    ("SUSPICIOUS_BURST", "Multiple suspicious events", "Threshold risk-scored events (excluding failed logins) within the window.", 25, 3, 10, "HIGH"),
]

DATA_ACTIONS = {"SEARCH", "VIEW_RECORD", "ADD_RECORD", "UPDATE_RECORD", "EXPORT_DATA"}
RECORD_ACCESS_ACTIONS = ("VIEW_RECORD", "EXPORT_DATA")
LOGIN_RULES = {"FAILED_LOGIN", "REPEATED_FAILED_LOGIN", "NEW_LOCATION"}
MANAGER_PATH_PREFIXES = ("/manager", "/api/manager")
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class Trigger:
    rule_key: str
    points: int
    reason: str
    severity: str  # NONE / LOW / MEDIUM / HIGH / CRITICAL


# ---------------------------------------------------------------- rule store

def ensure_default_rules():
    """Insert any default rule that is missing (never overwrites tuned values)."""
    existing = {key for (key,) in db.session.query(RiskRule.rule_key).all()}
    added = False
    for key, name, desc, points, threshold, window, severity in DEFAULT_RULES:
        if key not in existing:
            db.session.add(RiskRule(rule_key=key, name=name, description=desc, points=points,
                                    threshold=threshold, window_minutes=window, severity=severity))
            added = True
    if added:
        db.session.commit()


def active_rules():
    """Enabled rules keyed by rule_key, cached for the current request."""
    if "risk_rules" not in g:
        g.risk_rules = {r.rule_key: r for r in RiskRule.query.filter_by(enabled=True).all()}
    return g.risk_rules


# ------------------------------------------------------------ query helpers

def _count_actions(employee_id, since, actions=None, extra=None):
    q = ActivityLog.query.filter(ActivityLog.employee_id == employee_id, ActivityLog.timestamp >= since)
    if actions:
        q = q.filter(ActivityLog.action.in_(actions))
    if extra is not None:
        q = q.filter(extra)
    return q.count()


def _fired_recently(user, employee_id, rule_key, since):
    """Aggregate rules fire once per window, then stay quiet until it passes."""
    if user is not None:
        return db.session.query(RiskEvent.id).filter(
            RiskEvent.user_id == user.id, RiskEvent.rule_key == rule_key,
            RiskEvent.created_at >= since).first() is not None
    return db.session.query(Alert.id).filter(
        Alert.employee_id == employee_id, Alert.alert_type == rule_key,
        Alert.timestamp >= since).first() is not None


def _is_off_hours(ts):
    cfg = current_app.config
    return ts.weekday() not in cfg["WORK_DAYS"] or not (cfg["WORK_HOURS_START"] <= ts.hour < cfg["WORK_HOURS_END"])


# ------------------------------------------------------------------ rules
# Each rule: (activity, user, context, rule) -> Trigger | None

def _failed_login(a, user, ctx, rule):
    if a.action != "FAILED_LOGIN":
        return None
    why = ctx.get("failure_reason", "invalid credentials")
    return Trigger(rule.rule_key, rule.points, f"Failed login for {a.employee_id} ({why})", rule.severity)


def _repeated_failed_login(a, user, ctx, rule):
    if a.action != "FAILED_LOGIN":
        return None
    since = a.timestamp - timedelta(minutes=rule.window_minutes)
    failures = _count_actions(a.employee_id, since, ["FAILED_LOGIN"])
    if failures < rule.threshold or _fired_recently(user, a.employee_id, rule.rule_key, since):
        return None
    return Trigger(rule.rule_key, rule.points,
                   f"{failures} failed login attempts for {a.employee_id} within {rule.window_minutes} minutes",
                   rule.severity)


def _new_location(a, user, ctx, rule):
    if a.action not in ("LOGIN", "MANAGER_LOGIN") or user is None or not a.ip_address:
        return None
    since = a.timestamp - timedelta(days=90)
    previous = db.session.query(ActivityLog.ip_address).filter(
        ActivityLog.user_id == user.id, ActivityLog.action.in_(["LOGIN", "MANAGER_LOGIN"]),
        ActivityLog.timestamp >= since, ActivityLog.id != a.id).distinct().all()
    known = {ip for (ip,) in previous if ip}
    if not known or a.ip_address in known:  # first ever login is not "unusual"
        return None
    shown = ", ".join(sorted(known)[:3])
    return Trigger(rule.rule_key, rule.points,
                   f"Login from new IP address {a.ip_address} (previously used: {shown})", rule.severity)


def _off_hours(a, user, ctx, rule):
    if a.action not in DATA_ACTIONS | {"LOGIN"} or not _is_off_hours(a.timestamp):
        return None
    since = a.timestamp - timedelta(minutes=max(rule.window_minutes, 1))
    if _fired_recently(user, a.employee_id, rule.rule_key, since):
        return None
    cfg = current_app.config
    return Trigger(rule.rule_key, rule.points,
                   f"{a.action.replace('_', ' ').title()} at {a.timestamp:%H:%M} on {DAY_NAMES[a.timestamp.weekday()]} "
                   f"is outside working hours ({cfg['WORK_HOURS_START']:02d}:00–{cfg['WORK_HOURS_END']:02d}:00, Mon–Fri)",
                   rule.severity)


def _sensitive_access(a, user, ctx, rule):
    if a.action not in ("VIEW_RECORD", "UPDATE_RECORD") or ctx.get("sensitivity") != "CONFIDENTIAL":
        return None
    verb = "Viewed" if a.action == "VIEW_RECORD" else "Modified"
    return Trigger(rule.rule_key, rule.points, f"{verb} CONFIDENTIAL record {a.resource}", rule.severity)


def _unauthorized(a, user, ctx, rule):
    if a.action != "UNAUTHORIZED_ACCESS":
        return None
    return Trigger(rule.rule_key, rule.points,
                   f"Attempted to access {a.resource} without permission", rule.severity)


def _privilege_escalation(a, user, ctx, rule):
    if a.action != "UNAUTHORIZED_ACCESS" or not (a.resource or "").startswith(MANAGER_PATH_PREFIXES):
        return None
    return Trigger(rule.rule_key, rule.points,
                   f"Employee tried to open manager-only resource {a.resource}", rule.severity)


def _repeated_unauthorized(a, user, ctx, rule):
    if a.action != "UNAUTHORIZED_ACCESS":
        return None
    since = a.timestamp - timedelta(minutes=rule.window_minutes)
    attempts = _count_actions(a.employee_id, since, ["UNAUTHORIZED_ACCESS"])
    if attempts < rule.threshold or _fired_recently(user, a.employee_id, rule.rule_key, since):
        return None
    return Trigger(rule.rule_key, rule.points,
                   f"{attempts} unauthorized access attempts within {rule.window_minutes} minutes", rule.severity)


def _mass_record_access(a, user, ctx, rule):
    if a.action not in RECORD_ACCESS_ACTIONS:
        return None
    since = a.timestamp - timedelta(minutes=rule.window_minutes)
    total = db.session.query(db.func.coalesce(db.func.sum(ActivityLog.record_count), 0)).filter(
        ActivityLog.employee_id == a.employee_id, ActivityLog.timestamp >= since,
        ActivityLog.action.in_(RECORD_ACCESS_ACTIONS), ActivityLog.status == "SUCCESS").scalar()
    if total < rule.threshold or _fired_recently(user, a.employee_id, rule.rule_key, since):
        return None
    return Trigger(rule.rule_key, rule.points,
                   f"Accessed {int(total)} records within {rule.window_minutes} minutes", rule.severity)


def _repeated_search(a, user, ctx, rule):
    if a.action != "SEARCH":
        return None
    since = a.timestamp - timedelta(minutes=rule.window_minutes)
    searches = _count_actions(a.employee_id, since, ["SEARCH"])
    if searches < rule.threshold or _fired_recently(user, a.employee_id, rule.rule_key, since):
        return None
    return Trigger(rule.rule_key, rule.points,
                   f"{searches} searches within {rule.window_minutes} minutes", rule.severity)


def _rapid_actions(a, user, ctx, rule):
    since = a.timestamp - timedelta(minutes=max(rule.window_minutes, 1))
    actions = _count_actions(a.employee_id, since)
    if actions < rule.threshold or _fired_recently(user, a.employee_id, rule.rule_key, since):
        return None
    return Trigger(rule.rule_key, rule.points,
                   f"{actions} actions within {max(rule.window_minutes, 1)} minute(s)", rule.severity)


def _unusual_frequency(a, user, ctx, rule):
    window = max(rule.window_minutes, 1)
    since = a.timestamp - timedelta(minutes=window)
    recent = _count_actions(a.employee_id, since)
    if recent < current_app.config["UNUSUAL_FREQUENCY_MIN_ACTIONS"]:
        return None
    baseline_rows = db.session.query(ActivityLog.timestamp).filter(
        ActivityLog.employee_id == a.employee_id,
        ActivityLog.timestamp >= a.timestamp - timedelta(days=7),
        ActivityLog.timestamp < since).all()
    if not baseline_rows:
        return None  # no history yet, nothing to compare against
    active_hours = {ts.replace(minute=0, second=0) for (ts,) in baseline_rows}
    normal_rate = len(baseline_rows) / len(active_hours) * (window / 60)
    if recent <= rule.threshold * normal_rate or _fired_recently(user, a.employee_id, rule.rule_key, since):
        return None
    return Trigger(rule.rule_key, rule.points,
                   f"{recent} actions in the last {window} minutes vs a normal rate of ~{normal_rate:.0f}",
                   rule.severity)


RULES = [
    ("FAILED_LOGIN", _failed_login),
    ("REPEATED_FAILED_LOGIN", _repeated_failed_login),
    ("NEW_LOCATION", _new_location),
    ("OFF_HOURS", _off_hours),
    ("SENSITIVE_ACCESS", _sensitive_access),
    ("UNAUTHORIZED_ACCESS", _unauthorized),
    ("PRIVILEGE_ESCALATION", _privilege_escalation),
    ("REPEATED_UNAUTHORIZED", _repeated_unauthorized),
    ("MASS_RECORD_ACCESS", _mass_record_access),
    ("REPEATED_SEARCH", _repeated_search),
    ("RAPID_ACTIONS", _rapid_actions),
    ("UNUSUAL_FREQUENCY", _unusual_frequency),
]


# --------------------------------------------------------------- evaluation

def evaluate(activity, user, context=None):
    """Return the list of Triggers fired by this (already flushed) activity."""
    ctx = context or {}
    rules = active_rules()
    is_employee = user is not None and user.role == "employee"
    triggers = []
    for key, check in RULES:
        rule = rules.get(key)
        if rule is None:
            continue
        if not is_employee and key not in LOGIN_RULES:
            continue  # managers / unknown IDs are only evaluated for login behaviour
        trig = check(activity, user, ctx, rule)
        if trig:
            triggers.append(trig)

    # Failed logins escalate through their own rule, so typos never count as a "burst".
    burst = rules.get("SUSPICIOUS_BURST")
    if (burst and is_employee and activity.action != "FAILED_LOGIN"
            and any(t.points > 0 for t in triggers)):
        since = activity.timestamp - timedelta(minutes=burst.window_minutes)
        earlier = _count_actions(activity.employee_id, since,
                                 extra=db.and_(ActivityLog.risk_score > 0, ActivityLog.id != activity.id,
                                               ActivityLog.action != "FAILED_LOGIN"))
        if earlier + 1 >= burst.threshold and not _fired_recently(user, activity.employee_id, burst.rule_key, since):
            triggers.append(Trigger(burst.rule_key, burst.points,
                                    f"{earlier + 1} suspicious events within {burst.window_minutes} minutes",
                                    burst.severity))
    return triggers


def get_or_create_score(user):
    if user.risk is None:
        user.risk = RiskScore(user_id=user.id, current_score=0, risk_level="LOW", last_updated=now())
        db.session.add(user.risk)
    return user.risk


def apply_score(user, activity, triggers):
    """Add trigger points to the user's score and record why. Returns (level_before, level_after, score)."""
    cap = current_app.config["RISK_SCORE_CAP"]
    rs = get_or_create_score(user)
    level_before = rs.risk_level
    score = rs.current_score
    for t in triggers:
        if t.points <= 0:
            continue
        after = min(cap, score + t.points)
        db.session.add(RiskEvent(user_id=user.id, activity_id=activity.id, rule_key=t.rule_key,
                                 points=t.points, reason=t.reason, score_before=score, score_after=after,
                                 created_at=activity.timestamp))
        score = after
    if score != rs.current_score:
        rs.current_score = score
        rs.risk_level = risk_level_for(score)
        rs.last_updated = activity.timestamp
        rs.last_increase_at = activity.timestamp
    return level_before, rs.risk_level, score


def apply_decay():
    """Slowly lower scores of employees with no recent risky behaviour."""
    cfg = current_app.config
    per_hour = cfg["RISK_DECAY_PER_HOUR"]
    if per_hour <= 0:
        return 0
    current = now()
    grace = current - timedelta(minutes=cfg["RISK_DECAY_GRACE_MINUTES"])
    changed = 0
    for rs in RiskScore.query.filter(RiskScore.current_score > 0).all():
        if rs.last_increase_at and rs.last_increase_at > grace:
            continue
        hours = (current - rs.last_updated).total_seconds() / 3600
        decrease = int(hours * per_hour)
        if decrease < 1:
            continue
        rs.current_score = max(0, rs.current_score - decrease)
        rs.risk_level = risk_level_for(rs.current_score)
        rs.last_updated = rs.last_updated + timedelta(hours=decrease / per_hour)
        changed += 1
    if changed:
        db.session.commit()
    return changed
