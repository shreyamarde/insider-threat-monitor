"""Small shared helpers."""
from datetime import datetime

from flask import current_app, has_request_context, request


def now():
    """Server-local, second-precision timestamp used for every stored time."""
    return datetime.now().replace(microsecond=0)


def iso(value):
    return value.isoformat(timespec="seconds") if value else None


def client_ip():
    if not has_request_context():
        return None
    return (request.remote_addr or "unknown")[:45]


def client_user_agent():
    if not has_request_context():
        return None
    return (request.headers.get("User-Agent") or "")[:255]


def wants_json():
    """True for API calls (and fetch() requests) so errors are returned as JSON."""
    if not has_request_context():
        return False
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def risk_level_for(score):
    for lower_bound, level in current_app.config["RISK_LEVELS"]:
        if score >= lower_bound:
            return level
    return "LOW"
