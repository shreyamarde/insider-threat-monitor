"""Flask extension singletons, created here to avoid circular imports."""
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
# threading mode works on every OS without eventlet/gevent; simple-websocket
# gives it real WebSocket support.
socketio = SocketIO(async_mode="threading")
