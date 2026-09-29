from models import ActivityLog, Alert, Record
from tests.conftest import login


def test_employee_blocked_from_manager_page_and_it_is_detected(employee):
    resp = employee.get("/manager/dashboard")
    assert resp.status_code == 403
    act = ActivityLog.query.filter_by(employee_id="EMP1001", action="UNAUTHORIZED_ACCESS").one()
    assert act.resource == "/manager/dashboard" and act.status == "DENIED"
    assert act.risk_score == 40  # +30 unauthorized, +10 privilege escalation
    types = {a.alert_type for a in Alert.query.filter_by(employee_id="EMP1001")}
    assert {"UNAUTHORIZED_ACCESS", "PRIVILEGE_ESCALATION"} <= types


def test_employee_blocked_from_manager_api(employee):
    for method, url in [("get", "/api/manager/employees"), ("post", "/api/manager/employees"),
                        ("get", "/api/manager/alerts"), ("put", "/api/manager/alerts/1/acknowledge"),
                        ("get", "/api/manager/risk")]:
        resp = getattr(employee, method)(url, json={})
        assert resp.status_code == 403, url
        assert resp.get_json()["error"] == "forbidden"


def test_manager_is_redirected_away_from_employee_pages(manager):
    resp = manager.get("/employee/dashboard")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/manager/dashboard")
    assert manager.get("/api/employee/activity").status_code == 403


def test_anonymous_users_are_sent_to_login(client):
    resp = client.get("/manager/employees")
    assert resp.status_code == 302 and "/?next=" in resp.headers["Location"]


def test_employee_api_returns_only_own_activity_without_risk(employee, make_client):
    other = make_client()
    login(other, "EMP1002")
    other.get("/employee/records?q=price")
    data = employee.get("/api/employee/activity").get_json()
    assert data["items"], "employee should see their own login"
    for item in data["items"]:
        assert "risk_score" not in item and "risk_reason" not in item
    assert all(i["action"] != "SEARCH" for i in data["items"])  # EMP1002's search is not visible


def test_record_permissions(employee, app):
    with app.app_context():
        own = Record.query.filter_by(record_code="FIN-0001").one().id
        restricted = Record.query.filter_by(record_code="FIN-0003").one().id
        other_dept = Record.query.filter_by(record_code="SAL-0001").one().id
        public = Record.query.filter_by(record_code="GEN-0001").one().id
    assert employee.get(f"/employee/records/{own}").status_code == 200
    assert employee.get(f"/employee/records/{public}").status_code == 200
    assert employee.get(f"/employee/records/{restricted}").status_code == 403
    assert employee.get(f"/employee/records/{other_dept}").status_code == 403
    assert employee.get(f"/employee/records/{other_dept}/edit").status_code == 403
    denied = ActivityLog.query.filter_by(employee_id="EMP1001", action="UNAUTHORIZED_ACCESS").count()
    assert denied == 3


def test_search_only_returns_permitted_records(employee):
    html = employee.get("/employee/records?q=a").get_data(as_text=True)
    assert "FIN-0001" in html and "GEN-0001" in html
    assert "FIN-0003" not in html and "SAL-0001" not in html
    assert ActivityLog.query.filter_by(employee_id="EMP1001", action="SEARCH").count() == 1


def test_employee_cannot_create_restricted_records(employee):
    resp = employee.post("/employee/records/new", data={"title": "Secret plan", "category": "Report",
                                                         "sensitivity": "RESTRICTED", "content": "hidden stuff"})
    assert resp.status_code == 400
    ok = employee.post("/employee/records/new", data={"title": "Team notes", "category": "Report",
                                                       "sensitivity": "INTERNAL", "content": "weekly notes"})
    assert ok.status_code == 302
    rec = Record.query.filter_by(title="Team notes").one()
    assert rec.department == "Finance" and rec.record_code == "FIN-0004"
    assert ActivityLog.query.filter_by(employee_id="EMP1001", action="ADD_RECORD").count() == 1
