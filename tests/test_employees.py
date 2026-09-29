from models import ActivityLog, RiskScore, User
from tests.conftest import login, user

NEW = {"employee_id": "EMP1006", "name": "Test Employee", "email": "test.employee@test.example",
       "department": "Finance", "job_title": "Analyst", "role": "employee",
       "password": "TempPass123", "status": "active"}


def test_create_employee(manager, make_client):
    resp = manager.post("/api/manager/employees", json=NEW)
    assert resp.status_code == 201
    body = resp.get_json()
    assert "password" not in str(body).lower().replace("must_change_password", "")
    u = user("EMP1006")
    assert u and u.password_hash != "TempPass123" and u.password_hash.startswith("scrypt:")
    assert u.must_change_password and u.created_by == user("MGR1001").id
    assert RiskScore.query.filter_by(user_id=u.id).one().current_score == 0
    audit = ActivityLog.query.filter_by(action="CREATE_EMPLOYEE").one()
    assert audit.employee_id == "MGR1001" and audit.resource == "employee:EMP1006"
    # the new employee can log in immediately
    c = make_client()
    assert login(c, "EMP1006", "TempPass123").status_code == 302


def test_duplicate_employee_id_and_email(manager):
    assert manager.post("/api/manager/employees", json=NEW).status_code == 201
    dup_id = manager.post("/api/manager/employees", json={**NEW, "email": "other@test.example"})
    assert dup_id.status_code == 409 and dup_id.get_json()["field"] == "employee_id"
    dup_mail = manager.post("/api/manager/employees", json={**NEW, "employee_id": "EMP1007"})
    assert dup_mail.status_code == 409 and dup_mail.get_json()["field"] == "email"


def test_invalid_input_rejected(manager):
    cases = [({"employee_id": "12"}, "employee_id"), ({"email": "nope"}, "email"),
             ({"department": "Space"}, "department"), ({"password": "short"}, "password"),
             ({"name": "<script>"}, "name")]
    for patch, field in cases:
        resp = manager.post("/api/manager/employees", json={**NEW, **patch})
        assert resp.status_code == 400 and resp.get_json()["field"] == field, patch
    assert User.query.filter_by(employee_id="EMP1006").count() == 0


def test_disable_employee_invalidates_session(manager, employee):
    uid = user("EMP1001").id
    resp = manager.put(f"/api/manager/employees/{uid}/status", json={"status": "disabled"})
    assert resp.status_code == 200 and user("EMP1001").status == "disabled"
    assert ActivityLog.query.filter_by(action="DISABLE_EMPLOYEE").count() == 1
    assert employee.get("/employee/dashboard").status_code == 302  # kicked out
    # re-enable
    manager.put(f"/api/manager/employees/{uid}/status", json={"status": "active"})
    assert user("EMP1001").status == "active"
    assert ActivityLog.query.filter_by(action="ENABLE_EMPLOYEE").count() == 1


def test_delete_endpoint_soft_disables(manager):
    uid = user("EMP1002").id
    assert manager.delete(f"/api/manager/employees/{uid}").status_code == 200
    assert user("EMP1002").status == "disabled"  # never hard-deleted


def test_reset_password(manager, make_client):
    uid = user("EMP1001").id
    assert manager.post(f"/api/manager/employees/{uid}/reset-password", json={"password": "abc"}).status_code == 400
    resp = manager.post(f"/api/manager/employees/{uid}/reset-password", json={"password": "Reset12345"})
    assert resp.status_code == 200
    assert ActivityLog.query.filter_by(action="RESET_PASSWORD").count() == 1
    c = make_client()
    assert login(c, "EMP1001").status_code == 401  # old password no longer works
    assert login(c, "EMP1001", "Reset12345").headers["Location"].endswith("/change-password")


def test_manager_cannot_disable_self(manager):
    uid = user("MGR1001").id
    assert manager.put(f"/api/manager/employees/{uid}/status", json={"status": "disabled"}).status_code == 400


def test_role_change_raises_privilege_alert(manager):
    from models import Alert
    uid = user("EMP1002").id
    resp = manager.put(f"/api/manager/employees/{uid}", json={"role": "manager"})
    assert resp.status_code == 200 and user("EMP1002").role == "manager"
    assert Alert.query.filter_by(alert_type="PRIVILEGE_CHANGE", employee_id="EMP1002").count() == 1


def test_employee_list_search_and_filters(manager):
    data = manager.get("/api/manager/employees?q=rahul").get_json()
    assert [e["employee_id"] for e in data["items"]] == ["EMP1001"]
    data = manager.get("/api/manager/employees?department=Sales").get_json()
    assert [e["employee_id"] for e in data["items"]] == ["EMP1002"]
    data = manager.get("/api/manager/employees?status=disabled").get_json()
    assert data["total"] == 0
    for item in manager.get("/api/manager/employees").get_json()["items"]:
        assert "password_hash" not in item
