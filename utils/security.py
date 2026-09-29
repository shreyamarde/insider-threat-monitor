"""
Role-based access control. Authorization is always enforced here on the
server; hiding buttons in the UI is only cosmetic.
"""
from functools import wraps

from flask import abort, jsonify, redirect, request, url_for
from flask_login import current_user

from extensions import login_manager
from utils.helpers import wants_json


def forbidden(message="You do not have permission to access this resource."):
    if wants_json():
        response = jsonify({"error": "forbidden", "message": message})
        response.status_code = 403
        return response
    abort(403)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        return view(*args, **kwargs)
    return wrapped


def manager_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.is_manager:
            # an employee probing manager URLs is itself a monitored event
            from services.activity_logger import log_activity
            log_activity(current_user, "UNAUTHORIZED_ACCESS", resource=request.path,
                         description=f"Blocked {request.method} to manager-only resource",
                         status="DENIED")
            return forbidden()
        return view(*args, **kwargs)
    return wrapped


def employee_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.is_manager:
            if wants_json():
                return forbidden("This endpoint is for employee accounts.")
            return redirect(url_for("manager.dashboard"))
        return view(*args, **kwargs)
    return wrapped


def home_url_for(user):
    return url_for("manager.dashboard") if user.is_manager else url_for("employee.dashboard")


def is_safe_next(target):
    return bool(target) and target.startswith("/") and not target.startswith("//") and "\\" not in target
