"""
Central configuration.

Everything that is environment specific (database credentials, secret key)
comes from environment variables / the .env file. Everything that tunes the
monitoring behaviour (risk levels, working hours, lockout policy) lives here so
it is never scattered through the code base.
"""
import logging
import os
import ssl
from datetime import timedelta
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def build_mysql_uri():
    user = quote_plus(os.getenv("MYSQL_USER", "root"))
    password = quote_plus(os.getenv("MYSQL_PASSWORD", ""))
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DATABASE", "insider_threat_system")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


def mysql_ssl_context():
    """
    TLS for hosted MySQL (e.g. Aiven, which requires it).
      MYSQL_SSL_CA=/path/ca.pem  -> encrypted and the server certificate is verified
      MYSQL_SSL=1                -> encrypted, certificate not verified
      neither                    -> plain connection (local MySQL)
    """
    ca = os.getenv("MYSQL_SSL_CA")
    if ca:
        if not os.path.isabs(ca):
            ca = os.path.join(BASE_DIR, ca)  # relative paths are relative to the project folder
        if not os.path.isfile(ca):
            raise RuntimeError(f"MYSQL_SSL_CA points to {ca!r}, but that file does not exist. "
                               "Upload the database CA certificate (e.g. as a Render Secret File named ca.pem).")
        return ssl.create_default_context(cafile=ca)
    if _bool("MYSQL_SSL", False):
        logging.getLogger("itm").warning("MYSQL_SSL=1 without MYSQL_SSL_CA: connection is encrypted "
                                         "but the server certificate is not verified.")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


def _engine_options():
    options = {"pool_pre_ping": True, "pool_recycle": 280}
    ctx = mysql_ssl_context()
    if ctx is not None:
        options["connect_args"] = {"ssl": ctx}
    return options


class Config:
    # ------------------------------------------------------------------ core
    SECRET_KEY = os.getenv("SECRET_KEY") or os.urandom(32).hex()
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or build_mysql_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options()
    AUTO_INIT_DB = _bool("AUTO_INIT_DB", False)  # create tables + demo data on first start (hosting)

    # -------------------------------------------------------------- sessions
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)  # True behind HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=_int("SESSION_TIMEOUT_MINUTES", 30))
    WTF_CSRF_TIME_LIMIT = None  # token lives as long as the session

    # --------------------------------------------------------------- logging
    LOG_FILE = os.path.join(BASE_DIR, "logs", "app.log")
    TRUST_PROXY = _bool("TRUST_PROXY", False)

    # ------------------------------------------------------- login security
    LOGIN_MAX_FAILURES = _int("LOGIN_MAX_FAILURES", 5)          # per employee ID
    LOGIN_IP_MAX_FAILURES = _int("LOGIN_IP_MAX_FAILURES", 20)   # per IP address
    LOGIN_LOCKOUT_MINUTES = _int("LOGIN_LOCKOUT_MINUTES", 15)
    PASSWORD_MIN_LENGTH = 8

    # ------------------------------------------------------------ risk engine
    # Score bands (inclusive lower bound). Scores are always capped to 0..100.
    RISK_LEVELS = [
        (80, "CRITICAL"),
        (60, "HIGH"),
        (30, "MEDIUM"),
        (0, "LOW"),
    ]
    RISK_SCORE_CAP = 100
    # Scores slowly decay when an employee behaves normally, so that one bad
    # afternoon does not mark someone as critical forever.
    RISK_DECAY_PER_HOUR = _int("RISK_DECAY_PER_HOUR", 2)
    RISK_DECAY_GRACE_MINUTES = 60      # no decay within an hour of the last increase
    RISK_DECAY_INTERVAL_SECONDS = 600  # background job frequency
    WORK_HOURS_START = _int("WORK_HOURS_START", 9)   # 09:00
    WORK_HOURS_END = _int("WORK_HOURS_END", 19)      # 19:00
    WORK_DAYS = [0, 1, 2, 3, 4]                      # Monday .. Friday
    ALERT_COOLDOWN_MINUTES = 10  # same alert type for same employee is not repeated within this time
    UNUSUAL_FREQUENCY_MIN_ACTIONS = 20

    # --------------------------------------------------------------- presence
    PRESENCE_TIMEOUT_SECONDS = 120
    HEARTBEAT_SECONDS = 25

    # ---------------------------------------------------------------- testing
    TESTING = False
    START_BACKGROUND_JOBS = True


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    START_BACKGROUND_JOBS = False
