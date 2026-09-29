"""
Create (or re-create) the MySQL database from database/schema.sql and load
the demo data from database/seed.sql, using the credentials in .env.

    python init_db.py             # schema + demo data
    python init_db.py --no-seed   # empty system (schema, departments, rules only)

WARNING: this drops and recreates the application's tables.

Optional environment variables (recommended for a public deployment):
    DEMO_MANAGER_PASSWORD   replaces the documented demo password of MGR1001
    DEMO_EMPLOYEE_PASSWORD  replaces the documented demo password of all seeded employees
"""
import os
import re
import sys
from datetime import datetime

import pymysql
from pymysql.constants import CLIENT
from werkzeug.security import generate_password_hash

from config import BASE_DIR, mysql_ssl_context

DEFAULT_DB = "insider_threat_system"


def database_name():
    name = os.getenv("MYSQL_DATABASE", DEFAULT_DB)
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("MYSQL_DATABASE may only contain letters, digits and underscores.")
    return name


def read_sql(filename, database):
    with open(os.path.join(BASE_DIR, "database", filename), encoding="utf-8") as fh:
        sql = fh.read()
    return re.sub(rf"\b{DEFAULT_DB}\b", database, sql)  # allow a custom database name


def connect(database=None):
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "").strip(),
        database=database,
        charset="utf8mb4",
        client_flag=CLIENT.MULTI_STATEMENTS,
        ssl=mysql_ssl_context(),
        autocommit=False,
    )


def _run(cursor, sql):
    cursor.execute(sql)
    while cursor.nextset():
        pass


def _align_clock(cursor):
    """Seed timestamps use MySQL NOW(); make it match the app's clock (hosted MySQL is usually UTC)."""
    offset = datetime.now().astimezone().utcoffset()
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    cursor.execute(f"SET time_zone = '{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}'")


def _apply_demo_passwords(cursor, database):
    manager_pw = (os.getenv("DEMO_MANAGER_PASSWORD") or "").strip()
    employee_pw = (os.getenv("DEMO_EMPLOYEE_PASSWORD") or "").strip()
    if manager_pw:
        cursor.execute(f"UPDATE `{database}`.users SET password_hash=%s WHERE role='manager'",
                       (generate_password_hash(manager_pw),))
    if employee_pw:
        cursor.execute(f"UPDATE `{database}`.users SET password_hash=%s WHERE role='employee'",
                       (generate_password_hash(employee_pw),))
    return bool(manager_pw or employee_pw)


def initialize(seed=True, log=print):
    """Drop + create the schema and (optionally) load demo data. Returns row counts."""
    database = database_name()
    conn = connect()
    try:
        with conn.cursor() as cur:
            _align_clock(cur)
            log(f"Creating schema in `{database}` ...")
            _run(cur, read_sql("schema.sql", database))
            conn.commit()
            if seed:
                log("Loading demo data ...")
                _run(cur, read_sql("seed.sql", database))
                if _apply_demo_passwords(cur, database):
                    log("Demo passwords replaced from DEMO_*_PASSWORD environment variables.")
                conn.commit()
            counts = {}
            for table in ("users", "records", "activity_logs", "alerts", "risk_scores", "risk_events",
                          "login_attempts", "risk_rules"):
                cur.execute(f"SELECT COUNT(*) FROM `{database}`.{table}")
                counts[table] = cur.fetchone()[0]
            return counts
    except pymysql.MySQLError:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_initialized():
    """True if the application tables already exist (used for first-start auto setup)."""
    database = database_name()
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name='users'",
                        (database,))
            return cur.fetchone()[0] > 0
    finally:
        conn.close()


def main():
    try:
        counts = initialize(seed="--no-seed" not in sys.argv)
    except ValueError as exc:
        sys.exit(str(exc))
    except pymysql.MySQLError as exc:
        sys.exit(f"Database initialisation failed: {exc}\n"
                 "Check MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD (and MYSQL_SSL for hosted MySQL).")
    for table, count in counts.items():
        print(f"  {table:<15} {count:>5} rows")
    if "--no-seed" not in sys.argv:
        from app import create_app
        from seed_extra import add_extra_employees
        with create_app().app_context():
            add_extra_employees()  # + EMP1007–EMP1016 with activity history
    print("Done. Start the app with:  python app.py")


if __name__ == "__main__":
    main()
