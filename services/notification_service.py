"""
Real-time layer (Flask-SocketIO).

Rooms
  managers        every connected manager browser tab
  user:<id>       every tab of one specific user

Server -> client events
  activity:new    new activity row            (managers)
  alert:new       new alert                   (managers)
  alert:updated   alert acknowledged/resolved (managers)
  presence        employee went online/offline (managers)
  account:disabled  the account was disabled  (that user)

Client -> server events
  heartbeat       keeps users.last_seen fresh for online/offline tracking
"""
import logging

from flask import current_app
from flask_login import current_user
from flask_socketio import join_room

from extensions import db, socketio
from utils.helpers import iso, now

log = logging.getLogger(__name__)
MANAGERS_ROOM = "managers"


def _emit(event, payload, room):
    try:
        socketio.emit(event, payload, to=room)
    except Exception:  # a broken socket must never break the HTTP request
        log.exception("Socket.IO emit failed for %s", event)


def emit_activity(activity):
    _emit("activity:new", activity.to_feed_dict(), MANAGERS_ROOM)


def emit_alert(alert):
    _emit("alert:new", alert.to_dict(), MANAGERS_ROOM)


def emit_alert_update(alert):
    _emit("alert:updated", alert.to_dict(), MANAGERS_ROOM)


def emit_presence(user):
    _emit("presence", {
        "user_id": user.id,
        "employee_id": user.employee_id,
        "name": user.name,
        "online": user.online,
        "last_seen": iso(user.last_seen),
        "last_login": iso(user.last_login),
    }, MANAGERS_ROOM)


def notify_user(user_id, event, payload=None):
    _emit(event, payload or {}, f"user:{user_id}")


def touch_presence(user, commit=True):
    user.last_seen = now()
    if commit:
        db.session.commit()


# Handlers are registered once on the global SocketIO object and bound to
# the app by socketio.init_app().

@socketio.on("connect")
def on_connect(auth=None):
    if not current_user.is_authenticated:
        return False  # reject anonymous sockets
    join_room(f"user:{current_user.id}")
    if current_user.is_manager:
        join_room(MANAGERS_ROOM)
    try:
        touch_presence(current_user)
    except Exception:
        db.session.rollback()
        log.exception("Presence update failed on connect")
    return True


@socketio.on("heartbeat")
def on_heartbeat(data=None):
    if not current_user.is_authenticated:
        return {"ok": False}
    try:
        was_online = current_user.online
        touch_presence(current_user)
        if not was_online and current_user.is_online:
            emit_presence(current_user)  # came back after a timeout
    except Exception:
        db.session.rollback()
        log.exception("Heartbeat failed")
        return {"ok": False}
    return {"ok": True, "interval": current_app.config["HEARTBEAT_SECONDS"]}
