"""
Production entry point (Render, Railway, any Linux host):

    gunicorn --worker-class gthread -w 1 --threads 100 --timeout 120 wsgi:app

Exactly ONE worker: Socket.IO keeps its rooms in memory, so all clients must
talk to the same process (scaling out would need a Redis message queue).
"""
import logging

from app import create_app, start_background_jobs

log = logging.getLogger("itm")

app = create_app()

if app.config.get("AUTO_INIT_DB"):
    # First start on a fresh hosted database: create tables + demo data once.
    import init_db
    try:
        if not init_db.is_initialized():
            log.info("Empty database detected — creating schema and demo data ...")
            counts = init_db.initialize(seed=True, log=log.info)
            log.info("Database ready: %s", counts)
        with app.app_context():
            from services.risk_engine import ensure_default_rules
            ensure_default_rules()
    except Exception:
        log.exception("Automatic database setup failed — check the MYSQL_* environment variables")

start_background_jobs(app)
