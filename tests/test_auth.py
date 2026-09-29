from models import ActivityLog, LoginAttempt
from tests.conftest import EMPLOYEE_PW, login, user


def last_activity(employee_id):
    return ActivityLog.query.filter_by(employee_id=employee_id).order_by(ActivityLog.id.desc()).first()


def test_manager_login_redirects_to_manager_dashboard(client):
    resp = login(client, "MGR1001")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/manager/dashboard")
    assert last_activity("MGR1001").action == "MANAGER_LOGIN"
    assert LoginAttempt.query.filter_by(employee_id="MGR1001", success=True).count() == 1


def test_employee_login_records_activity_and_presence(client):
    resp = login(client, "EMP1001")
    assert resp.headers["Location"].endswith("/employee/dashboard")
    u = user("EMP1001")
    assert u.is_online and u.last_login is not None and u.online
    assert last_activity("EMP1001").action == "LOGIN"
    assert client.get("/employee/dashboard").status_code == 200


def test_invalid_password_is_logged_with_generic_message(client):
    resp = login(client, "EMP1001", "wrong-password1")
    assert resp.status_code == 401
    assert b"Invalid employee ID or password" in resp.data
    act = last_activity("EMP1001")
    assert act.action == "FAILED_LOGIN" and act.status == "FAILED" and act.risk_score == 10
    attempt = LoginAttempt.query.filter_by(employee_id="EMP1001").one()
    assert attempt.success is False and attempt.reason == "INVALID_PASSWORD"


def test_unknown_employee_id_is_logged_without_user(client):
    resp = login(client, "EMP9999", "whatever1")
    assert resp.status_code == 401
    act = last_activity("EMP9999")
    assert act.user_id is None and act.action == "FAILED_LOGIN"


def test_disabled_account_cannot_log_in(app, client):
    from extensions import db
    u = user("EMP1002")
    u.status = "disabled"
    db.session.commit()
    resp = login(client, "EMP1002")
    assert resp.status_code == 403 and b"disabled" in resp.data
    assert LoginAttempt.query.filter_by(employee_id="EMP1002").one().reason == "ACCOUNT_DISABLED"


def test_lockout_after_repeated_failures(client):
    for _ in range(5):
        login(client, "EMP1001", "bad-password1")
    resp = login(client, "EMP1001", EMPLOYEE_PW)  # correct password, still locked
    assert resp.status_code == 429
    assert LoginAttempt.query.filter_by(employee_id="EMP1001", reason="LOCKED_OUT").count() == 1


def test_logout_is_post_only_and_clears_session(client):
    login(client, "EMP1001")
    assert client.get("/logout").status_code == 405
    resp = client.post("/logout")
    assert resp.status_code == 302
    assert last_activity("EMP1001").action == "LOGOUT"
    assert user("EMP1001").is_online is False
    assert client.get("/employee/dashboard").status_code == 302  # back to login


def test_expired_session_api_returns_401(client):
    resp = client.get("/api/manager/stats")
    assert resp.status_code == 401 and resp.get_json()["error"] == "unauthorized"


def test_forced_password_change_for_new_accounts(manager, make_client):
    manager.post("/api/manager/employees", json={
        "employee_id": "EMP1006", "name": "Test Employee", "email": "test.employee@test.example",
        "department": "Finance", "role": "employee", "password": "TempPass123", "status": "active"})
    c = make_client()
    resp = login(c, "EMP1006", "TempPass123")
    assert resp.headers["Location"].endswith("/change-password")
    assert c.get("/employee/dashboard").status_code == 302
    assert c.get("/api/employee/activity").status_code == 403
    resp = c.post("/change-password", data={"current_password": "TempPass123",
                                            "new_password": "MyNewPass456", "confirm_password": "MyNewPass456"})
    assert resp.status_code == 302
    assert c.get("/employee/dashboard").status_code == 200
    assert last_activity("EMP1006").action == "PASSWORD_CHANGE"
    assert user("EMP1006").check_password("MyNewPass456")


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
