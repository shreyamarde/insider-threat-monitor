"""Input validation shared by forms and JSON APIs."""
import re
from datetime import datetime

EMPLOYEE_ID_RE = re.compile(r"^[A-Z]{3}\d{4}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,99}$")


class ValidationError(ValueError):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, dict) else {"_": str(errors)}
        super().__init__("; ".join(self.errors.values()))


def clean(value, max_len=255):
    return (value or "").strip()[:max_len] if isinstance(value, str) else ""


def normalize_employee_id(value):
    return clean(value, 20).upper()


def password_problems(password, min_length=8):
    problems = []
    if len(password or "") < min_length:
        problems.append(f"at least {min_length} characters")
    if not re.search(r"[A-Za-z]", password or ""):
        problems.append("a letter")
    if not re.search(r"\d", password or ""):
        problems.append("a number")
    return problems


def validate_password(password, min_length=8):
    problems = password_problems(password, min_length)
    if problems:
        return "Password must contain " + ", ".join(problems) + "."
    return None


def validate_employee_payload(data, departments, partial=False, min_password=8):
    """Validate create/update employee data. Returns a dict of cleaned values."""
    errors, out = {}, {}

    def present(key):
        return key in data and data.get(key) not in (None, "")

    if not partial or present("employee_id"):
        emp_id = normalize_employee_id(data.get("employee_id"))
        if not EMPLOYEE_ID_RE.match(emp_id):
            errors["employee_id"] = "Employee ID must look like EMP1006 (3 letters + 4 digits)."
        out["employee_id"] = emp_id
    if not partial or present("name"):
        name = clean(data.get("name"), 100)
        if not NAME_RE.match(name):
            errors["name"] = "Enter a valid full name (letters, spaces, . ' -)."
        out["name"] = name
    if not partial or present("email"):
        email = clean(data.get("email"), 120).lower()
        if not EMAIL_RE.match(email):
            errors["email"] = "Enter a valid email address."
        out["email"] = email
    if not partial or present("department"):
        dept = clean(data.get("department"), 60)
        if dept not in departments:
            errors["department"] = "Choose a valid department."
        out["department"] = dept
    if not partial or present("role"):
        role = clean(data.get("role"), 20).lower() or "employee"
        if role not in ("employee", "manager"):
            errors["role"] = "Role must be employee or manager."
        out["role"] = role
    if present("job_title") or not partial:
        out["job_title"] = clean(data.get("job_title"), 80) or None
    if not partial or present("status"):
        status = clean(data.get("status"), 20).lower() or "active"
        if status not in ("active", "disabled"):
            errors["status"] = "Status must be active or disabled."
        out["status"] = status
    if not partial:
        pw_error = validate_password(data.get("password") or "", min_password)
        if pw_error:
            errors["password"] = pw_error
        out["password"] = data.get("password") or ""

    if errors:
        raise ValidationError(errors)
    return out


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d") if value else None
    except ValueError:
        return None


def parse_int(value, default, minimum=None, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number
