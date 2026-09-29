"""Socket.IO: the manager receives employee activity and alerts without refreshing."""
from datetime import timedelta

from extensions import db, socketio
from models import Record
from tests.conftest import login, user


def events(sock, name=None):
    received = sock.get_received()
    return [e for e in received if name is None or e["name"] == name]


def test_anonymous_socket_rejected(app, client):
    sock = socketio.test_client(app, flask_test_client=client)
    assert not sock.is_connected()


def test_manager_receives_live_activity_and_alert(app, manager_socket, make_client):
    emp = make_client()
    login(emp, "EMP1001")
    got = events(manager_socket)
    login_events = [e for e in got if e["name"] == "activity:new"]
    assert login_events and login_events[-1]["args"][0]["action"] == "LOGIN"
    assert any(e["name"] == "presence" and e["args"][0]["employee_id"] == "EMP1001" for e in got)

    rid = Record.query.filter_by(record_code="FIN-0003").one().id
    emp.get(f"/employee/records/{rid}")
    got = events(manager_socket)
    activity = [e["args"][0] for e in got if e["name"] == "activity:new"]
    alerts = [e["args"][0] for e in got if e["name"] == "alert:new"]
    assert activity[-1]["action"] == "UNAUTHORIZED_ACCESS" and activity[-1]["risk_score"] == 30
    assert alerts and alerts[0]["employee_id"] == "EMP1001" and alerts[0]["severity"] == "HIGH"
    assert alerts[0]["id"] and alerts[0]["activity_id"] == activity[-1]["id"]  # stored in DB first


def test_alert_update_broadcast(app, manager, manager_socket, make_client):
    emp = make_client()
    login(emp, "EMP1001")
    rid = Record.query.filter_by(record_code="FIN-0003").one().id
    emp.get(f"/employee/records/{rid}")
    alert_id = [e for e in events(manager_socket, "alert:new")][0]["args"][0]["id"]
    manager.put(f"/api/manager/alerts/{alert_id}/acknowledge")
    updates = events(manager_socket, "alert:updated")
    assert updates and updates[0]["args"][0]["status"] == "ACKNOWLEDGED"


def test_employee_socket_gets_no_manager_events(app, make_client):
    emp = make_client()
    login(emp, "EMP1001")
    emp_sock = socketio.test_client(app, flask_test_client=emp)
    assert emp_sock.is_connected()
    emp_sock.get_received()
    other = make_client()
    login(other, "EMP1002")
    other.get("/employee/records?q=price")
    assert emp_sock.get_received() == []


def test_heartbeat_keeps_presence(app, make_client):
    emp = make_client()
    login(emp, "EMP1001")
    u = user("EMP1001")
    u.last_seen = u.last_seen - timedelta(minutes=10)
    db.session.commit()
    assert not user("EMP1001").online
    sock = socketio.test_client(app, flask_test_client=emp)
    ack = sock.emit("heartbeat", {}, callback=True)
    assert ack["ok"] is True
    db.session.expire_all()
    assert user("EMP1001").online


def test_disabled_account_notified(app, manager, make_client):
    emp = make_client()
    login(emp, "EMP1002")
    emp_sock = socketio.test_client(app, flask_test_client=emp)
    emp_sock.get_received()
    manager.put(f"/api/manager/employees/{user('EMP1002').id}/status", json={"status": "disabled"})
    assert any(e["name"] == "account:disabled" for e in emp_sock.get_received())
