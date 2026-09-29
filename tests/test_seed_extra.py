from extensions import db
from models import ActivityLog, Alert, RiskEvent, RiskScore, User
from seed_extra import EMPLOYEES, add_extra_employees
from tests.conftest import login


def test_extra_employees_are_consistent_and_idempotent(app, make_client):
    assert add_extra_employees(log=lambda *_: None) == len(EMPLOYEES)
    assert add_extra_employees(log=lambda *_: None) == 0  # second run changes nothing

    for emp_id, *_ in EMPLOYEES:
        user = User.query.filter_by(employee_id=emp_id).one()
        rs = RiskScore.query.filter_by(user_id=user.id).one()
        events = RiskEvent.query.filter_by(user_id=user.id).all()
        assert rs.current_score == sum(e.points for e in events), emp_id  # every point explained
        acts = ActivityLog.query.filter_by(user_id=user.id).all()
        assert sum(a.risk_score for a in acts) == rs.current_score, emp_id
        assert user.last_login is not None and any(a.action == "LOGIN" for a in acts)

    levels = {u.employee_id: u.risk.risk_level for u in User.query.filter(User.employee_id.in_(["EMP1008", "EMP1012"]))}
    assert levels == {"EMP1008": "MEDIUM", "EMP1012": "HIGH"}
    assert Alert.query.filter_by(employee_id="EMP1012", alert_type="RISK_LEVEL_ESCALATION").one().severity == "HIGH"

    c = make_client()
    assert login(c, "EMP1011").headers["Location"].endswith("/employee/dashboard")  # can sign in
    db.session.remove()
