import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from extensions import db, socketio  # noqa: E402
from models import Department, Record, RiskScore, User  # noqa: E402
from services.risk_engine import ensure_default_rules  # noqa: E402
from utils.helpers import now  # noqa: E402

MANAGER_PW = "Manager@123"
EMPLOYEE_PW = "Employee@123"


class Config(TestConfig):
    # Neutralise the working-hours rule so results don't depend on when tests run;
    # the off-hours test switches it back on explicitly.
    WORK_HOURS_START = 0
    WORK_HOURS_END = 24
    WORK_DAYS = list(range(7))


def _user(employee_id, name, dept, role="employee", must_change=False, status="active"):
    u = User(employee_id=employee_id, name=name, email=f"{employee_id.lower()}@test.example",
             department=dept, job_title="Tester", role=role, status=status,
             must_change_password=must_change, created_at=now(), updated_at=now())
    u.set_password(MANAGER_PW if role == "manager" else EMPLOYEE_PW)
    db.session.add(u)
    db.session.flush()
    db.session.add(RiskScore(user_id=u.id, current_score=0, risk_level="LOW", last_updated=now()))
    return u


@pytest.fixture
def app():
    app = create_app(Config)

    # Tests keep one app context open (so they can query the DB), which makes
    # Flask reuse `g` between requests. In production every request gets a fresh
    # context; emulate that so cached users/rules never leak between clients.
    def fresh_g():
        from flask import g
        g.__dict__.clear()
    app.before_request_funcs.setdefault(None, []).insert(0, fresh_g)

    with app.app_context():
        db.create_all()
        for name in ("Finance", "Sales", "Human Resources", "Engineering", "IT & Security", "Legal"):
            db.session.add(Department(name=name))
        db.session.flush()
        ensure_default_rules()
        _user("MGR1001", "Maya Manager", "IT & Security", role="manager")
        _user("EMP1001", "Rahul Sharma", "Finance")
        _user("EMP1002", "Kavya Nair", "Sales")
        records = [
            ("FIN-0001", "Revenue summary", "Finance", "INTERNAL"),
            ("FIN-0002", "Payroll ledger", "Finance", "CONFIDENTIAL"),
            ("FIN-0003", "Board valuation", "Finance", "RESTRICTED"),
            ("SAL-0001", "Price list", "Sales", "INTERNAL"),
            ("GEN-0001", "Holiday calendar", "General", "PUBLIC"),
        ]
        for code, title, dept, sens in records:
            db.session.add(Record(record_code=code, title=title, category="Report", department=dept,
                                  sensitivity=sens, content=f"Content of {title}"))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_client(app):
    return lambda: app.test_client()


def login(client, employee_id, password=None):
    password = password or (MANAGER_PW if employee_id.startswith("MGR") else EMPLOYEE_PW)
    return client.post("/login", data={"employee_id": employee_id, "password": password})


@pytest.fixture
def manager(client):
    login(client, "MGR1001")
    return client


@pytest.fixture
def employee(make_client):
    c = make_client()
    login(c, "EMP1001")
    return c


@pytest.fixture
def manager_socket(app, manager):
    sock = socketio.test_client(app, flask_test_client=manager)
    assert sock.is_connected()
    sock.get_received()  # drain connect noise
    yield sock
    if sock.is_connected():
        sock.disconnect()


def user(employee_id):
    return User.query.filter_by(employee_id=employee_id).first()
