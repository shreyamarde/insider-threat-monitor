"""
Adds 10 more demo employees (EMP1007–EMP1016) with realistic activity history
to an EXISTING database — nothing is deleted or reset.

    python seed_extra.py          # local (uses .env)

It is idempotent: if EMP1007 already exists it does nothing. On Render it runs
automatically at start-up (see wsgi.py). Every seeded risk score is explained
by risk_events rows exactly as the rule engine would have produced them.

Passwords: DEMO_EMPLOYEE_PASSWORD if set (live site), otherwise the README demo password.
"""
import os
from datetime import timedelta

from extensions import db
from models import ActivityLog, Alert, LoginAttempt, RiskEvent, RiskScore, User
from utils.helpers import now, risk_level_for

UA_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
UA_MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
UA_EDGE = UA_WIN + " Edg/128.0"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

RECORD_TITLES = {
    "FIN-0001": ("INTERNAL", "Q2 2026 Revenue Summary"), "FIN-0003": ("INTERNAL", "Invoice INV-88213 — Northwind Traders"),
    "FIN-0004": ("CONFIDENTIAL", "Payroll Ledger — August 2026"), "FIN-0005": ("CONFIDENTIAL", "Corporate Bank Account Mandates"),
    "FIN-0008": ("INTERNAL", "Invoice INV-88240 — Contoso Retail"), "FIN-0009": ("INTERNAL", "Tax Filing Checklist 2026"),
    "HR-0002": ("INTERNAL", "Recruitment Plan Q4"), "HR-0005": ("INTERNAL", "Leave Policy"),
    "ENG-0001": ("INTERNAL", "Platform Architecture Overview"), "ENG-0002": ("INTERNAL", "Release Checklist v4"),
    "ENG-0004": ("INTERNAL", "API Rate Limit Design"), "ENG-0006": ("INTERNAL", "Incident Postmortem — 14 Aug outage"),
    "SEC-0001": ("PUBLIC", "Acceptable Use Policy"), "SEC-0002": ("INTERNAL", "Firewall Change Log"),
    "SEC-0003": ("CONFIDENTIAL", "Security Incident Register"),
    "SAL-0001": ("INTERNAL", "Product Price List 2026"), "SAL-0003": ("CONFIDENTIAL", "Contract — Globex Corp Renewal"),
    "SAL-0005": ("INTERNAL", "Q3 Pipeline Forecast"),
    "LEG-0001": ("INTERNAL", "NDA Template"), "LEG-0003": ("INTERNAL", "Compliance Calendar 2026"),
}

# (employee_id, name, department, job title, usual IP, user agent)
EMPLOYEES = [
    ("EMP1007", "Aditi Rao", "Finance", "Accounts Executive", "10.10.1.31", UA_WIN),
    ("EMP1008", "Ishaan Gupta", "IT & Security", "Security Analyst", "10.10.6.12", UA_EDGE),
    ("EMP1009", "Neha Kulkarni", "Human Resources", "Talent Acquisition Specialist", "10.10.2.27", UA_MAC),
    ("EMP1010", "Karan Mehta", "Engineering", "DevOps Engineer", "10.10.3.41", UA_EDGE),
    ("EMP1011", "Pooja Desai", "Sales", "Account Manager", "10.10.4.22", UA_WIN),
    ("EMP1012", "Meera Joshi", "Finance", "Senior Accountant", "10.10.1.36", UA_WIN),
    ("EMP1013", "Siddharth Menon", "Engineering", "QA Engineer", "10.10.3.52", UA_MAC),
    ("EMP1014", "Ritika Bansal", "Legal", "Paralegal", "10.10.5.14", UA_WIN),
    ("EMP1015", "Aman Chauhan", "Sales", "Sales Executive", "10.10.4.37", UA_EDGE),
    ("EMP1016", "Farhan Qureshi", "IT & Security", "System Administrator", "10.10.6.19", UA_WIN),
]

# Event: (when, action, target, extra)  — when = minutes ago (int) or "Y22:20" (yesterday at 22:20)
# target = record code / search text; extra may hold risk triggers, alerts, status, ip, record_count.
V, S = "VIEW_RECORD", "SEARCH"
SCENARIOS = {
    "EMP1007": [(280, "LOGIN", None, {}), (275, S, "invoice", {"results": 3}), (272, V, "FIN-0003", {}),
                (268, V, "FIN-0008", {}), (240, "UPDATE_RECORD", "FIN-0009", {}), (200, "LOGOUT", None, {})],
    "EMP1008": [(200, "FAILED_LOGIN", None, {"risk": [("FAILED_LOGIN", 10, "Failed login for EMP1008 (invalid password)")]}),
                (199, "LOGIN", None, {"ip": "49.207.44.10",
                                      "risk": [("NEW_LOCATION", 10, "Login from new IP address 49.207.44.10 (previously used: 10.10.6.12)")],
                                      "alerts": [("NEW_LOCATION", "MEDIUM", "NEW")]}),
                (170, V, "SEC-0003", {"ip": "49.207.44.10",
                                      "risk": [("SENSITIVE_ACCESS", 15, "Viewed CONFIDENTIAL record record:SEC-0003")],
                                      "alerts": [("SENSITIVE_ACCESS", "MEDIUM", "NEW")]}),
                (120, V, "SEC-0002", {"ip": "49.207.44.10"}), (100, S, "firewall", {"ip": "49.207.44.10", "results": 1}),
                (40, "LOGOUT", None, {"ip": "49.207.44.10"})],
    "EMP1009": [(230, "LOGIN", None, {}), (226, S, "recruitment", {"results": 1}), (224, V, "HR-0002", {}),
                (205, V, "HR-0005", {}), (150, "LOGOUT", None, {})],
    "EMP1010": [(130, "FAILED_LOGIN", None, {"risk": [("FAILED_LOGIN", 10, "Failed login for EMP1010 (invalid password)")]}),
                (129, "LOGIN", None, {}), (120, S, "deploy", {"results": 1}), (118, V, "ENG-0002", {}),
                (110, V, "ENG-0004", {}), (30, "LOGOUT", None, {})],
    "EMP1011": [(260, "LOGIN", None, {}), (255, V, "SAL-0001", {}), (250, V, "SAL-0005", {}),
                (245, S, "pipeline", {"results": 1}), (170, "LOGOUT", None, {})],
    "EMP1012": [("Y22:20", "LOGIN", None, {"risk": [("OFF_HOURS", 15, "Login at 22:20 on {yday} is outside working hours (09:00–19:00, Mon–Fri)")],
                                          "alerts": [("OFF_HOURS", "MEDIUM", "NEW")]}),
                ("Y22:31", V, "FIN-0004", {"risk": [("SENSITIVE_ACCESS", 15, "Viewed CONFIDENTIAL record record:FIN-0004")],
                                           "alerts": [("SENSITIVE_ACCESS", "MEDIUM", "NEW")]}),
                ("Y22:36", V, "FIN-0005", {"risk": [("SENSITIVE_ACCESS", 15, "Viewed CONFIDENTIAL record record:FIN-0005")]}),
                ("Y22:44", "EXPORT_DATA", None, {"record_count": 16,
                                                 "risk": [("MASS_RECORD_ACCESS", 20, "Accessed 16 records within 5 minutes")],
                                                 "alerts": [("MASS_RECORD_ACCESS", "HIGH", "NEW"), ("RISK_LEVEL_ESCALATION", "HIGH", "NEW")]}),
                ("Y22:52", "LOGOUT", None, {}),
                (150, "LOGIN", None, {}), (146, S, "revenue", {"results": 1}), (144, V, "FIN-0001", {}), (60, "LOGOUT", None, {})],
    "EMP1013": [(190, "LOGIN", None, {}), (185, V, "ENG-0006", {}), (160, V, "ENG-0001", {}),
                (140, S, "release", {"results": 1}), (95, "LOGOUT", None, {})],
    "EMP1014": [(210, "LOGIN", None, {}), (204, V, "LEG-0001", {}), (180, V, "LEG-0003", {}), (140, "LOGOUT", None, {})],
    "EMP1015": [(240, "LOGIN", None, {}), (236, S, "globex", {"results": 1}),
                (235, V, "SAL-0003", {"risk": [("SENSITIVE_ACCESS", 15, "Viewed CONFIDENTIAL record record:SAL-0003")],
                                      "alerts": [("SENSITIVE_ACCESS", "MEDIUM", "ACKNOWLEDGED")]}),
                (160, "LOGOUT", None, {})],
    "EMP1016": [(175, "LOGIN", None, {}), (171, V, "SEC-0002", {}), (160, S, "firewall", {"results": 1}),
                (150, V, "SEC-0001", {}), (80, "LOGOUT", None, {})],
}


def _when(spec, current):
    if isinstance(spec, int):
        return current - timedelta(minutes=spec)
    hour, minute = map(int, spec[1:].split(":"))
    return (current - timedelta(days=1)).replace(hour=hour, minute=minute, second=0)


def add_extra_employees(log=print):
    """Insert the extra employees if they are not there yet. Returns the number added."""
    if User.query.filter_by(employee_id="EMP1007").first():
        log("Extra demo employees already present — nothing to do.")
        return 0
    manager = User.query.filter_by(role="manager").order_by(User.id).first()
    password = (os.getenv("DEMO_EMPLOYEE_PASSWORD") or "").strip() or "Employee@123"
    current = now()
    yesterday = current - timedelta(days=1)
    yday_name = DAYS[yesterday.weekday()]

    for emp_id, name, dept, title, ip, ua in EMPLOYEES:
        user = User(employee_id=emp_id, name=name, email=f"{name.lower().replace(' ', '.')}@shrutu.example",
                    department=dept, job_title=title, role="employee", status="active",
                    must_change_password=False, is_online=False, created_by=manager.id if manager else None,
                    created_at=current - timedelta(days=20), updated_at=current)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        if manager:
            db.session.add(ActivityLog(user_id=manager.id, employee_id=manager.employee_id, actor_role="manager",
                                       action="CREATE_EMPLOYEE", resource=f"employee:{emp_id}",
                                       description=f"Created employee account {emp_id} ({name}, {dept}, status active)",
                                       timestamp=current - timedelta(days=20), ip_address="10.10.0.5",
                                       user_agent=UA_WIN, status="SUCCESS"))

        # a normal working day yesterday = the employee's baseline (and known IP)
        events = [("Y09:5%d" % (len(emp_id) % 10), "LOGIN", None, {}), ("Y17:4%d" % (int(emp_id[-1]) % 10), "LOGOUT", None, {})]
        events += SCENARIOS[emp_id]
        events.sort(key=lambda e: _when(e[0], current))

        score, level, last_increase, last_ip, last_login = 0, "LOW", None, ip, None
        for spec, action, target, extra in events:
            ts = _when(spec, current)
            event_ip = extra.get("ip", ip)
            status = "FAILED" if action == "FAILED_LOGIN" else "SUCCESS"
            record_count, resource, description = 0, None, None
            if action in ("LOGIN", "FAILED_LOGIN"):
                resource, description = "/login", ("Signed in" if action == "LOGIN" else "Incorrect password")
            elif action == "LOGOUT":
                resource, description = "/logout", "Signed out"
            elif action == S:
                resource, description = "records", f'Searched "{target}" — {extra.get("results", 0)} result(s)'
            elif action in (V, "UPDATE_RECORD"):
                sensitivity, rtitle = RECORD_TITLES[target]
                resource, record_count = f"record:{target}", 1
                description = (f"Viewed {sensitivity} record '{rtitle}'" if action == V else f"Updated record '{rtitle}'")
            elif action == "EXPORT_DATA":
                record_count = extra["record_count"]
                resource, description = "records.csv", f'Exported {record_count} record(s) for search ""'

            triggers = [(k, p, r.format(yday=yday_name)) for k, p, r in extra.get("risk", [])]
            activity = ActivityLog(user_id=user.id, employee_id=emp_id, actor_role="employee", action=action,
                                   resource=resource, description=description, record_count=record_count,
                                   timestamp=ts, ip_address=event_ip, user_agent=ua, status=status,
                                   risk_score=sum(p for _, p, _ in triggers),
                                   risk_reason="; ".join(f"+{p} {r}" for _, p, r in triggers) or None)
            db.session.add(activity)
            db.session.flush()

            level_before = level
            for key, points, reason in triggers:
                after = min(100, score + points)
                db.session.add(RiskEvent(user_id=user.id, activity_id=activity.id, rule_key=key, points=points,
                                         reason=reason, score_before=score, score_after=after, created_at=ts))
                score, last_increase = after, ts
            level = risk_level_for(score)

            for alert_type, severity, status_ in extra.get("alerts", []):
                if alert_type == "RISK_LEVEL_ESCALATION":
                    message = f"Risk level rose from {level_before} to {level} (score {score}). Latest: {triggers[-1][2]}"
                else:
                    message = next(r for k, _, r in triggers if k == alert_type)
                alert = Alert(user_id=user.id, employee_id=emp_id, activity_id=activity.id, alert_type=alert_type,
                              severity=severity, message=message, risk_score=score, timestamp=ts, status=status_)
                if status_ == "ACKNOWLEDGED" and manager:
                    alert.acknowledged_by, alert.acknowledged_at = manager.id, ts + timedelta(minutes=25)
                db.session.add(alert)
                if status_ == "ACKNOWLEDGED" and manager:
                    db.session.flush()
                    db.session.add(ActivityLog(user_id=manager.id, employee_id=manager.employee_id, actor_role="manager",
                                               action="ACKNOWLEDGE_ALERT", resource=f"alert:{alert.id}",
                                               description=f"Acknowledged {severity} alert '{alert.title}' for {emp_id}",
                                               timestamp=alert.acknowledged_at, ip_address="10.10.0.5",
                                               user_agent=UA_WIN, status="SUCCESS"))

            if action in ("LOGIN", "FAILED_LOGIN"):
                db.session.add(LoginAttempt(employee_id=emp_id, user_id=user.id, ip_address=event_ip, user_agent=ua,
                                            timestamp=ts, success=action == "LOGIN",
                                            reason="SUCCESS" if action == "LOGIN" else "INVALID_PASSWORD"))
                if action == "LOGIN":
                    last_login, last_ip = ts, event_ip

        user.last_login, user.last_login_ip = last_login, last_ip
        user.last_seen = _when(events[-1][0], current)
        db.session.add(RiskScore(user_id=user.id, current_score=score, risk_level=level,
                                 last_updated=current, last_increase_at=last_increase))

    db.session.commit()
    log(f"Added {len(EMPLOYEES)} demo employees (EMP1007–EMP1016).")
    return len(EMPLOYEES)


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        add_extra_employees()
