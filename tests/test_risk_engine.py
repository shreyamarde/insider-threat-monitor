from datetime import datetime, timedelta

from extensions import db
from models import ActivityLog, Alert, Record, RiskEvent, RiskScore
from services import activity_logger, risk_engine
from tests.conftest import login, user
from utils.helpers import now, risk_level_for


def score(employee_id):
    return RiskScore.query.filter_by(user_id=user(employee_id).id).one()


def record_id(code):
    return Record.query.filter_by(record_code=code).one().id


def alert_types(employee_id):
    return [a.alert_type for a in Alert.query.filter_by(employee_id=employee_id).order_by(Alert.id)]


def test_level_thresholds(app):
    assert [risk_level_for(s) for s in (0, 29, 30, 59, 60, 79, 80, 100)] == \
        ["LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH", "HIGH", "CRITICAL", "CRITICAL"]


def test_normal_activity_adds_no_risk(employee):
    employee.get("/employee/records?q=revenue")
    employee.get(f"/employee/records/{record_id('FIN-0001')}")
    rs = score("EMP1001")
    assert rs.current_score == 0 and rs.risk_level == "LOW"
    assert Alert.query.count() == 0
    assert ActivityLog.query.filter(ActivityLog.risk_score > 0).count() == 0


def test_sensitive_access_is_medium_risk_and_explained(employee):
    employee.get(f"/employee/records/{record_id('FIN-0002')}")
    employee.get(f"/employee/records/{record_id('FIN-0002')}")
    rs = score("EMP1001")
    assert rs.current_score == 30 and rs.risk_level == "MEDIUM"
    events = RiskEvent.query.filter_by(user_id=user("EMP1001").id).order_by(RiskEvent.id).all()
    assert [(e.rule_key, e.points, e.score_before, e.score_after) for e in events] == [
        ("SENSITIVE_ACCESS", 15, 0, 15), ("SENSITIVE_ACCESS", 15, 15, 30)]
    assert "CONFIDENTIAL record record:FIN-0002" in events[0].reason
    # same alert type is not repeated inside the cooldown window
    assert alert_types("EMP1001") == ["SENSITIVE_ACCESS"]


def test_unauthorized_access_reaches_high_with_escalation_alert(employee):
    employee.get(f"/employee/records/{record_id('FIN-0003')}")   # restricted
    employee.get(f"/employee/records/{record_id('SAL-0001')}")   # other department
    rs = score("EMP1001")
    assert rs.current_score == 60 and rs.risk_level == "HIGH"
    assert "RISK_LEVEL_ESCALATION" in alert_types("EMP1001")
    escalation = Alert.query.filter_by(alert_type="RISK_LEVEL_ESCALATION").one()
    assert escalation.severity == "HIGH" and escalation.risk_score == 60


def test_repeated_unauthorized_is_critical_and_capped(employee):
    for code in ("FIN-0003", "SAL-0001", "FIN-0003", "SAL-0001"):
        employee.get(f"/employee/records/{record_id(code)}")
    rs = score("EMP1001")
    assert rs.risk_level == "CRITICAL" and rs.current_score == 100  # capped, never above 100
    types = alert_types("EMP1001")
    assert "REPEATED_UNAUTHORIZED" in types and "SUSPICIOUS_BURST" in types
    critical = Alert.query.filter_by(alert_type="REPEATED_UNAUTHORIZED").one()
    assert critical.severity == "CRITICAL"
    assert RiskEvent.query.filter(RiskEvent.score_after > 100).count() == 0


def test_repeated_failed_logins_alert_for_known_and_unknown_ids(client):
    for _ in range(3):
        login(client, "EMP1002", "bad-password1")
        login(client, "EMP4040", "bad-password1")
    assert "REPEATED_FAILED_LOGIN" in alert_types("EMP1002")
    unknown = Alert.query.filter_by(employee_id="EMP4040").one()
    assert unknown.alert_type == "REPEATED_FAILED_LOGIN" and unknown.user_id is None
    rs = score("EMP1002")
    assert rs.current_score == 50 and rs.risk_level == "MEDIUM"  # 3 x 10 + 20, no burst for typos


def test_mass_export_detected(employee, app):
    with app.app_context():
        for i in range(5, 20):
            db.session.add(Record(record_code=f"FIN-{i:04d}", title=f"Invoice {i}", category="Invoice",
                                  department="Finance", sensitivity="INTERNAL", content="invoice data"))
        db.session.commit()
    resp = employee.get("/employee/records/export?q=")
    assert resp.status_code == 200 and resp.mimetype == "text/csv"
    export = ActivityLog.query.filter_by(action="EXPORT_DATA").one()
    assert export.record_count >= 15
    assert "MASS_RECORD_ACCESS" in alert_types("EMP1001")
    assert "Accessed" in export.risk_reason


def test_new_location_login(client, app):
    login(client, "EMP1001")
    client.post("/logout")
    # pretend the next login comes from another network
    login_env = {"REMOTE_ADDR": "203.0.113.9"}
    client.post("/login", data={"employee_id": "EMP1001", "password": "Employee@123"}, environ_base=login_env)
    assert "NEW_LOCATION" in alert_types("EMP1001")


def test_off_hours_rule(app, employee, monkeypatch):
    app.config.update(WORK_HOURS_START=9, WORK_HOURS_END=19, WORK_DAYS=[0, 1, 2, 3, 4])
    sunday_night = datetime(2026, 9, 27, 23, 15, 0)
    monkeypatch.setattr(activity_logger, "now", lambda: sunday_night)
    employee.get("/employee/records?q=revenue")
    employee.get("/employee/records?q=invoice")  # counted once per window
    events = RiskEvent.query.filter_by(rule_key="OFF_HOURS").all()
    assert len(events) == 1 and "23:15 on Sunday" in events[0].reason


def test_decay_lowers_scores_after_quiet_period(app):
    rs = score("EMP1002")
    rs.current_score, rs.risk_level = 70, "HIGH"
    rs.last_updated = rs.last_increase_at = now() - timedelta(hours=5)
    db.session.commit()
    assert risk_engine.apply_decay() == 1
    rs = score("EMP1002")
    assert rs.current_score == 60 and rs.risk_level == "HIGH"  # 5 h x 2 points


def test_rules_are_configurable(manager, employee):
    rule = manager.get("/api/manager/rules").get_json()
    sensitive = next(r for r in rule if r["rule_key"] == "SENSITIVE_ACCESS")
    resp = manager.put(f"/api/manager/rules/{sensitive['id']}", json={"points": 40, "severity": "HIGH"})
    assert resp.status_code == 200
    assert manager.put(f"/api/manager/rules/{sensitive['id']}", json={"points": 500}).status_code == 400
    employee.get(f"/employee/records/{record_id('FIN-0002')}")
    assert score("EMP1001").current_score == 40
    assert Alert.query.filter_by(alert_type="SENSITIVE_ACCESS").one().severity == "HIGH"
    assert ActivityLog.query.filter_by(action="UPDATE_RULE").count() == 1
