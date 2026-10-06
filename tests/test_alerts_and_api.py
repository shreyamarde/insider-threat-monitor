from extensions import db
from models import ActivityLog, Alert, Record
from tests.conftest import user


def trigger_alert(employee):
    rid = Record.query.filter_by(record_code="FIN-0003").one().id
    employee.get(f"/employee/records/{rid}")
    return Alert.query.filter_by(alert_type="UNAUTHORIZED_ACCESS").one()


def test_acknowledge_and_resolve_alert(manager, employee):
    alert = trigger_alert(employee)
    resp = manager.put(f"/api/manager/alerts/{alert.id}/acknowledge")
    assert resp.status_code == 200
    alert = db.session.get(Alert, alert.id)
    assert alert.status == "ACKNOWLEDGED" and alert.acknowledged_by == user("MGR1001").id
    assert alert.acknowledged_at is not None
    assert manager.put(f"/api/manager/alerts/{alert.id}/acknowledge").status_code == 409

    resp = manager.put(f"/api/manager/alerts/{alert.id}/resolve", json={"note": "Spoke to employee; mistyped code."})
    assert resp.status_code == 200
    alert = db.session.get(Alert, alert.id)
    assert alert.status == "RESOLVED" and alert.resolution_note.startswith("Spoke")
    assert alert.resolved_by == user("MGR1001").id and alert.resolved_at is not None
    audit = [a.action for a in ActivityLog.query.filter_by(employee_id="MGR1001")]
    assert "ACKNOWLEDGE_ALERT" in audit and "RESOLVE_ALERT" in audit
    # alerts cannot be deleted
    assert manager.delete(f"/api/manager/alerts/{alert.id}").status_code == 405


def test_alert_filters(manager, employee):
    trigger_alert(employee)
    assert manager.get("/api/manager/alerts?severity=HIGH").get_json()["total"] >= 1
    assert manager.get("/api/manager/alerts?severity=LOW").get_json()["total"] == 0
    assert manager.get("/api/manager/alerts?status=RESOLVED").get_json()["total"] == 0
    assert manager.get("/api/manager/alerts?employee=rahul").get_json()["total"] >= 1


def test_alert_and_activity_detail(manager, employee):
    alert = trigger_alert(employee)
    detail = manager.get(f"/api/manager/alerts/{alert.id}").get_json()
    assert detail["activity"]["action"] == "UNAUTHORIZED_ACCESS"
    act = manager.get(f"/api/manager/activities/{alert.activity_id}").get_json()
    for key in ("employee_id", "name", "action", "resource", "description", "timestamp", "ip_address",
                "user_agent", "risk_score", "risk_reason", "status"):
        assert key in act
    assert act["risk_events"][0]["rule_key"] == "UNAUTHORIZED_ACCESS"
    assert act["employee"]["current_risk_score"] == 30
    assert manager.get("/api/manager/activities/999999").status_code == 404


def test_activity_filters(manager, employee):
    trigger_alert(employee)
    employee.get("/employee/records?q=revenue")
    get = lambda q: manager.get("/api/manager/activities" + q).get_json()["total"]  # noqa: E731
    assert get("?action=SEARCH") == 1
    assert get("?suspicious=1") == 1
    assert get("?severity=HIGH") == 1
    assert get("?alert_status=NEW") == 1
    assert get("?employee=EMP1001&action=LOGIN") == 1
    assert get("?role=manager") >= 1
    assert get("?risk_level=MEDIUM") >= 1  # EMP1001 now at 30


def test_dashboard_numbers_come_from_database(manager, employee):
    trigger_alert(employee)
    data = manager.get("/api/manager/dashboard").get_json()
    stats = data["stats"]
    assert stats["total_employees"] == 2
    assert stats["online_now"] == 1  # EMP1001 is logged in
    assert stats["activities_today"] == ActivityLog.query.count()
    assert stats["new_alerts"] == Alert.query.filter_by(status="NEW").count()
    assert data["risk"]["counts"]["MEDIUM"] == 1
    assert data["feed"][0]["action"] == "UNAUTHORIZED_ACCESS"
    assert sum(data["charts"]["timeline"]["activities"]) == ActivityLog.query.count()


def test_dashboard_30_day_highlights(manager, employee):
    from datetime import timedelta
    from utils.helpers import now
    # one blocked action 40 days ago belongs to the *previous* 30-day period
    db.session.add(ActivityLog(user_id=user("EMP1001").id, employee_id="EMP1001", actor_role="employee",
                               action="UNAUTHORIZED_ACCESS", status="DENIED", timestamp=now() - timedelta(days=40)))
    db.session.commit()
    alert = trigger_alert(employee)
    manager.put(f"/api/manager/alerts/{alert.id}/acknowledge")

    h = manager.get("/api/manager/dashboard").get_json()["highlights"]
    recent = ActivityLog.query.count() - 1  # everything except the 40-day-old row
    assert h["days"] == 30 and len(h["daily"]["labels"]) == 30
    assert h["current"]["activities"] == recent == sum(h["daily"]["activities"])
    assert h["current"]["alerts"] == Alert.query.count() == sum(h["daily"]["alerts"])
    assert h["current"]["blocked"] == 1 and h["previous"]["blocked"] == 1
    assert h["previous"]["activities"] == 1 and h["previous"]["alerts"] == 0
    assert h["top_employees"][0]["employee_id"] == "EMP1001" and h["top_employees"][0]["points"] > 0
    assert h["top_departments"][0]["department"] == "Finance"
    assert h["top_alert_types"][0]["count"] >= 1
    assert h["avg_ack_minutes"] == 0 and h["busiest_day"]["activities"] == max(h["daily"]["activities"])


def test_audit_and_login_attempt_endpoints(manager, client):
    client.post("/login", data={"employee_id": "EMP1002", "password": "nope-nope1"})
    audit = manager.get("/api/manager/audit").get_json()
    assert all(i["actor_role"] == "manager" for i in audit["items"])
    failed = manager.get("/api/manager/login-attempts?success=0").get_json()
    assert failed["total"] == 1 and failed["items"][0]["employee_id"] == "EMP1002"


def test_health_endpoint(client):
    assert client.get("/api/health").get_json()["database"] == "up"
