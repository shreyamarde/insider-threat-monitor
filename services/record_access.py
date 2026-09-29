"""
Record permission policy for employees.

  PUBLIC        readable by everyone
  INTERNAL      readable by the owning department (and everyone for "General" records)
  CONFIDENTIAL  readable by the owning department — every access raises risk
  RESTRICTED    never readable by employees (executive / legal hold material)

Employees can add records to their own department and edit their own
department's non-restricted records.
"""
import re

from sqlalchemy import and_, or_

from extensions import db
from models import Record
from models.record import SHARED_DEPARTMENT

DEPARTMENT_PREFIX = {
    "Finance": "FIN", "Human Resources": "HR", "Engineering": "ENG", "IT & Security": "SEC",
    "Sales": "SAL", "Legal": "LEG", SHARED_DEPARTMENT: "GEN",
}
EMPLOYEE_WRITABLE_SENSITIVITY = ("PUBLIC", "INTERNAL", "CONFIDENTIAL")


def viewable_filter(user):
    return and_(
        Record.sensitivity != "RESTRICTED",
        or_(Record.sensitivity == "PUBLIC", Record.department.in_([user.department, SHARED_DEPARTMENT])),
    )


def can_view(user, record):
    if record.sensitivity == "RESTRICTED":
        return False
    return record.sensitivity == "PUBLIC" or record.department in (user.department, SHARED_DEPARTMENT)


def can_edit(user, record):
    return record.department == user.department and record.sensitivity != "RESTRICTED"


def denial_reason(user, record):
    if record.sensitivity == "RESTRICTED":
        return f"{record.record_code} is a RESTRICTED record"
    return f"{record.record_code} belongs to the {record.department} department"


def search(user, query=None, category=None, limit=100):
    q = Record.query.filter(viewable_filter(user))
    if query:
        like = f"%{query}%"
        q = q.filter(or_(Record.title.ilike(like), Record.record_code.ilike(like), Record.content.ilike(like)))
    if category:
        q = q.filter(Record.category == category)
    return q.order_by(Record.updated_at.desc()).limit(limit).all()


def next_record_code(department):
    prefix = DEPARTMENT_PREFIX.get(department, "REC")
    codes = db.session.query(Record.record_code).filter(Record.record_code.like(f"{prefix}-%")).all()
    numbers = [int(m.group(1)) for (code,) in codes if (m := re.match(rf"^{prefix}-(\d+)$", code))]
    return f"{prefix}-{(max(numbers) + 1 if numbers else 1):04d}"
