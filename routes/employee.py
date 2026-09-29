"""Employee interface: dashboard, records (normal work), own activity, profile."""
import csv
import io

from flask import (Blueprint, Response, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from extensions import db
from models import ActivityLog, Record
from models.record import RECORD_CATEGORIES
from services import record_access
from services.activity_logger import log_activity
from utils.helpers import now
from utils.security import employee_required
from utils.validators import clean, parse_int

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")


def _me():
    return current_user._get_current_object()


def _deny(record, action_label):
    reason = record_access.denial_reason(_me(), record)
    log_activity(_me(), "UNAUTHORIZED_ACCESS", resource=f"record:{record.record_code}",
                 description=f"Denied {action_label}: {reason}", status="DENIED")
    return render_template("errors/error.html", code=403, title="Access denied",
                           message=f"You are not permitted to {action_label} {record.record_code}. "
                                   "This attempt has been logged and reported to your manager."), 403


def _get_record_or_404(record_id):
    record = db.session.get(Record, record_id)
    if record is None:
        log_activity(_me(), "VIEW_RECORD", resource=f"record:#{record_id}",
                     description="Requested record does not exist", status="FAILED")
        abort(404)
    return record


# ------------------------------------------------------------------ pages

@employee_bp.route("/dashboard")
@employee_required
def dashboard():
    recent = (ActivityLog.query.filter_by(user_id=current_user.id)
              .order_by(ActivityLog.timestamp.desc()).limit(8).all())
    start_of_day = now().replace(hour=0, minute=0, second=0)
    stats = {
        "available_records": Record.query.filter(record_access.viewable_filter(current_user)).count(),
        "my_records": Record.query.filter_by(created_by=current_user.id).count(),
        "actions_today": ActivityLog.query.filter(ActivityLog.user_id == current_user.id,
                                                  ActivityLog.timestamp >= start_of_day).count(),
    }
    latest = (Record.query.filter(record_access.viewable_filter(current_user))
              .order_by(Record.updated_at.desc()).limit(5).all())
    return render_template("employee/dashboard.html", recent=recent, stats=stats, latest=latest)


@employee_bp.route("/records")
@employee_required
def records():
    query = clean(request.args.get("q"), 100)
    category = clean(request.args.get("category"), 30)
    if category and category not in RECORD_CATEGORIES:
        category = ""
    searched = bool(query or category)
    results = record_access.search(_me(), query or None, category or None, limit=100 if searched else 25)
    if searched:
        log_activity(_me(), "SEARCH", resource="records",
                     description=f'Searched "{query}"' + (f" in {category}" if category else "")
                                 + f" — {len(results)} result(s)")
    return render_template("employee/records.html", results=results, query=query, category=category,
                           categories=RECORD_CATEGORIES, searched=searched)


@employee_bp.route("/records/lookup")
@employee_required
def lookup():
    code = clean(request.args.get("code"), 20).upper()
    if not code:
        return redirect(url_for("employee.records"))
    record = Record.query.filter_by(record_code=code).first()
    if record is None:
        log_activity(_me(), "VIEW_RECORD", resource=f"record:{code}",
                     description="Lookup of a record code that does not exist", status="FAILED")
        flash(f"No record with code {code} exists.", "warning")
        return redirect(url_for("employee.records"))
    return redirect(url_for("employee.view_record", record_id=record.id))


@employee_bp.route("/records/<int:record_id>")
@employee_required
def view_record(record_id):
    record = _get_record_or_404(record_id)
    if not record_access.can_view(_me(), record):
        return _deny(record, "open")
    log_activity(_me(), "VIEW_RECORD", resource=f"record:{record.record_code}",
                 description=f"Viewed {record.sensitivity} record '{record.title}'", record_count=1,
                 context={"sensitivity": record.sensitivity})
    return render_template("employee/record_view.html", record=record,
                           can_edit=record_access.can_edit(_me(), record))


@employee_bp.route("/records/new", methods=["GET", "POST"])
@employee_required
def add_record():
    if request.method == "POST":
        data, errors = _read_record_form()
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("employee/record_form.html", record=None, form=data,
                                   categories=RECORD_CATEGORIES,
                                   sensitivities=record_access.EMPLOYEE_WRITABLE_SENSITIVITY), 400
        record = Record(record_code=record_access.next_record_code(current_user.department),
                        department=current_user.department, created_by=current_user.id,
                        updated_by=current_user.id, **data)
        db.session.add(record)
        db.session.flush()
        log_activity(_me(), "ADD_RECORD", resource=f"record:{record.record_code}",
                     description=f"Added {record.sensitivity} record '{record.title}'", record_count=1)
        flash(f"Record {record.record_code} created.", "success")
        return redirect(url_for("employee.view_record", record_id=record.id))
    return render_template("employee/record_form.html", record=None, form={},
                           categories=RECORD_CATEGORIES, sensitivities=record_access.EMPLOYEE_WRITABLE_SENSITIVITY)


@employee_bp.route("/records/<int:record_id>/edit", methods=["GET", "POST"])
@employee_required
def edit_record(record_id):
    record = _get_record_or_404(record_id)
    if not record_access.can_edit(_me(), record):
        return _deny(record, "edit")
    if request.method == "POST":
        data, errors = _read_record_form()
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("employee/record_form.html", record=record, form=data,
                                   categories=RECORD_CATEGORIES,
                                   sensitivities=record_access.EMPLOYEE_WRITABLE_SENSITIVITY), 400
        old_sensitivity = record.sensitivity
        for key, value in data.items():
            setattr(record, key, value)
        record.updated_by = current_user.id
        change = f" (sensitivity {old_sensitivity} → {record.sensitivity})" if old_sensitivity != record.sensitivity else ""
        log_activity(_me(), "UPDATE_RECORD", resource=f"record:{record.record_code}",
                     description=f"Updated record '{record.title}'{change}", record_count=1,
                     context={"sensitivity": "CONFIDENTIAL" if "CONFIDENTIAL" in (old_sensitivity, record.sensitivity)
                              else record.sensitivity})
        flash(f"Record {record.record_code} updated.", "success")
        return redirect(url_for("employee.view_record", record_id=record.id))
    return render_template("employee/record_form.html", record=record, form=record.to_dict(),
                           categories=RECORD_CATEGORIES, sensitivities=record_access.EMPLOYEE_WRITABLE_SENSITIVITY)


@employee_bp.route("/records/export")
@employee_required
def export_records():
    query = clean(request.args.get("q"), 100)
    category = clean(request.args.get("category"), 30)
    results = record_access.search(_me(), query or None, category or None, limit=200)
    log_activity(_me(), "EXPORT_DATA", resource="records.csv",
                 description=f'Exported {len(results)} record(s) for search "{query}"'
                             + (f" in {category}" if category else ""),
                 record_count=len(results))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["record_code", "title", "category", "department", "sensitivity", "updated_at"])
    for r in results:
        writer.writerow([r.record_code, r.title, r.category, r.department, r.sensitivity, r.updated_at])
    return Response(buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=records_export.csv"})


@employee_bp.route("/activity")
@employee_required
def my_activity():
    page = parse_int(request.args.get("page"), 1, minimum=1)
    pagination = (ActivityLog.query.filter_by(user_id=current_user.id)
                  .order_by(ActivityLog.timestamp.desc())
                  .paginate(page=page, per_page=20, error_out=False))
    return render_template("employee/activity.html", pagination=pagination)


@employee_bp.route("/profile")
@employee_required
def profile():
    return render_template("employee/profile.html", user=current_user)


# ------------------------------------------------------------------ helpers

def _read_record_form():
    data = {
        "title": clean(request.form.get("title"), 150),
        "category": clean(request.form.get("category"), 30),
        "sensitivity": clean(request.form.get("sensitivity"), 20).upper(),
        "content": clean(request.form.get("content"), 5000),
    }
    errors = []
    if len(data["title"]) < 3:
        errors.append("Title must be at least 3 characters.")
    if data["category"] not in RECORD_CATEGORIES:
        errors.append("Choose a valid category.")
    if data["sensitivity"] not in record_access.EMPLOYEE_WRITABLE_SENSITIVITY:
        errors.append("Employees can only create PUBLIC, INTERNAL or CONFIDENTIAL records.")
    if len(data["content"]) < 5:
        errors.append("Content must be at least 5 characters.")
    return data, errors
