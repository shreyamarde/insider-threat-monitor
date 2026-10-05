# SHRUTU — Insider Threat Monitoring System

A working, end-to-end insider-threat monitoring web application built with **Flask, MySQL 8 and Socket.IO**.

Employees do their normal work (searching, viewing, adding and editing business records). Every meaningful action is logged automatically, scored by an **explainable rule-based risk engine**, and — when something looks suspicious — turned into an **alert that is pushed to the manager's dashboard in real time**, without a page refresh.

```
Employee action ─► Flask route ─► log_activity() ─► MySQL (activity_logs)
                                      │
                                      ├─► Risk engine (rules from risk_rules)
                                      │      └─► risk_scores + risk_events (why the score changed)
                                      ├─► Alert generator ─► MySQL (alerts)
                                      │        (all of the above in ONE transaction)
                                      └─► COMMIT ─► Socket.IO emit ─► Manager dashboard (live)
```

---

## Contents
1. [Features](#features)
2. [Technology stack](#technology-stack)
3. [Architecture & project structure](#architecture--project-structure)
4. [Database schema](#database-schema)
5. [Installation & MySQL setup](#installation--mysql-setup)
6. [Environment variables](#environment-variables)
7. [Running the application](#running-the-application)
8. [Demo credentials](#demo-credentials)
9. [Demonstration walkthrough](#demonstration-walkthrough)
10. [Manager workflow](#manager-workflow)
11. [Employee workflow](#employee-workflow)
12. [Real-time notification architecture](#real-time-notification-architecture)
13. [Risk scoring explained](#risk-scoring-explained)
14. [Security measures](#security-measures)
15. [API endpoints](#api-endpoints)
16. [Testing](#testing)
17. [Future improvements](#future-improvements)

---

## Features

**Employee portal**
- Log in with employee ID + password (forced password change on first login / after a reset)
- Dashboard with name, employee ID, department, login status and recent own activity
- Records: search, open by code, add, edit (department-scoped), CSV export
- My Activity history and Profile (no risk scores or security data are ever shown to employees)

**Manager console**
- Dashboard with KPIs (total employees, online now, activities today, new alerts, high/critical alerts, employees at risk), a **live activity feed**, security alerts, risk overview, online/offline presence, recent sign-ins, failed logins and Chart.js charts
- **Real-time alert notifications** (toast + bell counter + tab title) with *View activity* and *Acknowledge* actions
- Employee management: create accounts, edit details/role/department, enable/disable, reset passwords, search & filter
- Live Activity log with filters (employee, date range, action, result, employee risk level, alert severity, alert status, risk-scored only) and a full detail view (IP, user agent, risk reason…)
- Alert queue: acknowledge / resolve with notes — alerts are never deleted
- Risk Monitoring: employees grouped LOW / MEDIUM / HIGH / CRITICAL and an explained history of every score change
- Audit Logs: every manager action + every login attempt
- Settings: tune each detection rule (points, threshold, window, alert severity, on/off) — changes are audited

## Technology stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+ (tested on 3.14), Flask 3, Flask-SQLAlchemy 3 / SQLAlchemy 2, Flask-Login, Flask-WTF (CSRF), Flask-SocketIO 5 (threading mode + simple-websocket) |
| Database | MySQL 8 via PyMySQL |
| Security | Werkzeug `generate_password_hash` / `check_password_hash` (scrypt), CSRF tokens, session protection, CSP headers |
| Frontend | HTML (Jinja2), custom CSS design system (dark/light), vanilla JavaScript, Chart.js 4, Socket.IO client 4 (both from jsDelivr CDN) |
| Tests | pytest (54 tests, in-memory SQLite + Flask/Socket.IO test clients) |

## Architecture & project structure

```
insider-threat-monitor/
├── app.py                  # application factory, error handling, security headers, entry point
├── config.py               # all configuration (env vars + monitoring policy)
├── extensions.py           # db, login_manager, csrf, socketio singletons
├── init_db.py              # creates the database from schema.sql and loads seed.sql
├── requirements.txt
├── .env.example            # copy to .env
├── models/                 # SQLAlchemy models (mirror database/schema.sql)
│   ├── user.py             # User, Department, LoginAttempt
│   ├── activity.py         # ActivityLog
│   ├── alert.py            # Alert
│   ├── risk.py             # RiskScore, RiskEvent, RiskRule
│   └── record.py           # Record (business data employees work with)
├── routes/
│   ├── auth.py             # login (lockout), logout, change password
│   ├── employee.py         # employee pages: dashboard, records, activity, profile
│   ├── manager.py          # manager pages (data comes from the API)
│   └── api.py              # JSON REST API (manager + employee)
├── services/
│   ├── activity_logger.py  # log_activity(): the single entry point of the pipeline
│   ├── risk_engine.py      # explainable rules, scoring, cap, decay
│   ├── alert_service.py    # alert creation, cooldown, acknowledge/resolve
│   ├── notification_service.py  # Socket.IO rooms, events, presence heartbeat
│   ├── employee_service.py # create/update/disable/reset (audited)
│   ├── record_access.py    # record permission policy
│   └── dashboard_service.py# dashboard aggregations
├── utils/
│   ├── security.py         # @login_required, @manager_required, @employee_required
│   ├── validators.py       # input validation
│   └── helpers.py          # time, IP, risk level helpers
├── templates/              # login, layout, employee/*, manager/*, errors/*
├── static/css, static/js, static/images
├── database/
│   ├── schema.sql          # MySQL 8 schema + departments + default rules
│   └── seed.sql            # demo data
├── tests/                  # pytest suite
└── _legacy/                # the original prototype, kept for reference (git-ignored)
```

**Design principles**
- *Thin routes, fat services*: routes validate input and call services; all business rules live in `services/`.
- *One pipeline*: every action goes through `log_activity()` — nothing duplicates logging, scoring or alerting logic.
- *Server-side authorization*: decorators enforce roles; the UI hiding a button is never the protection.
- *Everything real*: every number on every dashboard is a MySQL query; every alert shown is a row in `alerts`.

## Database schema

| Table | Purpose | Key columns |
|---|---|---|
| `departments` | lookup for departments | `name` |
| `users` | employees **and** managers | `employee_id` (unique), `name`, `email` (unique), `password_hash`, `department`, `job_title`, `role` (employee/manager), `status` (active/disabled), `must_change_password`, `is_online`, `last_login`, `last_login_ip`, `last_seen`, `created_by`, `created_at`, `updated_at` |
| `records` | business records employees work with | `record_code`, `title`, `category`, `department`, `sensitivity` (PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED), `content` |
| `activity_logs` | every action (employees and managers) | `user_id`, `employee_id`, `actor_role`, `action`, `resource`, `description`, `record_count`, `timestamp`, `ip_address`, `user_agent`, `status` (SUCCESS/FAILED/DENIED), `risk_score`, `risk_reason` |
| `alerts` | suspicious events (never deleted) | `user_id`, `employee_id`, `activity_id`, `alert_type`, `severity` (LOW…CRITICAL), `message`, `risk_score`, `timestamp`, `status` (NEW/ACKNOWLEDGED/RESOLVED), `acknowledged_by`, `acknowledged_at`, `resolved_by`, `resolved_at`, `resolution_note` |
| `risk_scores` | current score per user | `user_id` (unique), `current_score` (0–100), `risk_level`, `last_updated`, `last_increase_at` |
| `risk_events` | **why** a score changed | `user_id`, `activity_id`, `rule_key`, `points`, `reason`, `score_before`, `score_after`, `created_at` |
| `login_attempts` | every authentication attempt | `employee_id`, `user_id`, `ip_address`, `user_agent`, `timestamp`, `success`, `reason` |
| `risk_rules` | configurable detection rules | `rule_key`, `name`, `points`, `threshold`, `window_minutes`, `severity`, `enabled` |

Foreign keys use `ON DELETE SET NULL` for history tables so the audit trail survives. Full DDL: [`database/schema.sql`](database/schema.sql).

## Installation & MySQL setup

Prerequisites: **Python 3.10+** and **MySQL 8** running locally.

```bash
# 1. create a virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

# 2. configure
copy .env.example .env            # macOS/Linux: cp .env.example .env
#    then edit .env: MYSQL_PASSWORD and SECRET_KEY

# 3. create the database + demo data
python init_db.py
```

`init_db.py` creates the `insider_threat_system` database, runs `schema.sql` and `seed.sql`, and prints the row counts. Use `python init_db.py --no-seed` for an empty system (departments and rules only; create the first manager with SQL).

**Manual alternative (MySQL CLI):**

```bash
mysql -u root -p < database/schema.sql
mysql -u root -p insider_threat_system < database/seed.sql
```

> Re-running either command **drops and recreates** the application tables — use it to reset the demo.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MYSQL_HOST` / `MYSQL_PORT` | `localhost` / `3306` | MySQL server |
| `MYSQL_USER` / `MYSQL_PASSWORD` | `root` / – | MySQL credentials |
| `MYSQL_DATABASE` | `insider_threat_system` | database name |
| `SECRET_KEY` | random per start | Flask session signing key — **set it** (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | where the server listens |
| `SESSION_TIMEOUT_MINUTES` | `30` | idle session lifetime |
| `SESSION_COOKIE_SECURE` | `0` | set `1` behind HTTPS |
| `TRUST_PROXY` | `0` | set `1` only behind a reverse proxy (trust `X-Forwarded-For`) |
| `WORK_HOURS_START` / `WORK_HOURS_END` | `9` / `19` | working hours for the off-hours rule |
| `RISK_DECAY_PER_HOUR` | `2` | points removed per hour of normal behaviour |
| `LOGIN_MAX_FAILURES` / `LOGIN_IP_MAX_FAILURES` / `LOGIN_LOCKOUT_MINUTES` | `5` / `20` / `15` | brute-force lockout policy |

`.env` is git-ignored. Never commit real passwords or keys.

## Running the application

```bash
python app.py
```

Open **http://127.0.0.1:5000**. The server runs Flask-SocketIO (WebSockets included) and a background job that applies risk-score decay every 10 minutes.

## Deploying online (Render + Aiven, free)

The live setup is **Render** (runs the Flask/Socket.IO app, free HTTPS link) + **Aiven** (free managed MySQL 8). Free-tier behaviour: the app sleeps after 15 minutes without visitors and the first visit then takes about a minute to wake up; Aiven may power off a free database after a long period of inactivity (power it back on from the Aiven console).

Deployment files in this repo: `wsgi.py` (production entry point), `render.yaml` (Render Blueprint), `.python-version`, `gunicorn` in `requirements.txt`.

1. **Aiven — create the database**
   - Sign up at aiven.io → *Create service* → **MySQL** → **Free plan** → pick the region closest to Singapore → create.
   - When it is *Running*, open its **Overview** page and note **Host, Port, User** (`avnadmin`) and **Password**.
   - Copy the **CA certificate** from the same page into `certs/aiven-ca.pem` (it is public, not a secret) and update the host/port in `render.yaml`.
2. **GitHub — push the code** (a *private* repository is recommended)
   ```bash
   git remote add origin https://github.com/<your-user>/insider-threat-monitor.git
   git push -u origin main
   ```
3. **Render — create the web service**
   - Sign up at render.com with GitHub → **New → Blueprint** → select the repository. Render reads `render.yaml`.
   - Fill in the three secrets Render asks for: `MYSQL_PASSWORD` (from Aiven) and **your own** `DEMO_MANAGER_PASSWORD` / `DEMO_EMPLOYEE_PASSWORD` for the public demo accounts.
   - Deploy. On the first start the app creates all tables and demo data automatically (`AUTO_INIT_DB=1`) — watch the **Logs** tab for `Database ready`.
4. Open `https://<service-name>.onrender.com` and sign in as `MGR1001` with your `DEMO_MANAGER_PASSWORD`.

**Resetting the live demo data**: from your own computer, with the Aiven values set as environment variables (PowerShell):
```powershell
$env:MYSQL_HOST="<aiven-host>"; $env:MYSQL_PORT="<port>"; $env:MYSQL_USER="avnadmin"; $env:MYSQL_PASSWORD="<password>"
$env:MYSQL_SSL_CA="certs\aiven-ca.pem"; $env:DEMO_MANAGER_PASSWORD="<yours>"; $env:DEMO_EMPLOYEE_PASSWORD="<yours>"
.venv\Scripts\python.exe init_db.py
```

**Production notes**: exactly one gunicorn worker (Socket.IO rooms are in memory); `TRUST_PROXY=1` so real client IPs are recorded; `SESSION_COOKIE_SECURE=1` because Render serves HTTPS; `TZ=Asia/Kolkata` so working-hours rules use Indian time.

## Demo credentials

| Role | Employee ID | Password | Notes |
|---|---|---|---|
| Manager | `MGR1001` | `Manager@123` | Ananya Iyer, IT & Security |
| Employee | `EMP1001` | `Employee@123` | Rahul Sharma, Finance — normal behaviour (LOW) |
| Employee | `EMP1002` | `Employee@123` | Sneha Patel, HR — off-hours + confidential access (MEDIUM 45) |
| Employee | `EMP1003` | `Employee@123` | Arjun Verma, Engineering — late-night search burst + bulk export (HIGH 70) |
| Employee | `EMP1004` | `Employee@123` | Kavya Nair, Sales — restricted record + manager page probing (CRITICAL 95) |
| Employee | `EMP1005` | `Employee@123` | Vikram Singh, Legal — two mistyped passwords (LOW 20) |
| Employee | `EMP1000` | `Employee@123` | Rohan Das — **disabled** account (login is refused) |
| Employees | `EMP1007`–`EMP1016` | `Employee@123` | 10 more staff across all departments (from `seed_extra.py`): mostly normal work; `EMP1008` Ishaan Gupta — new-location login + confidential access (MEDIUM 35); `EMP1012` Meera Joshi — late-night confidential access + bulk export (HIGH 65); `EMP1010`, `EMP1015` — LOW with explained points |

`seed_extra.py` adds `EMP1007`–`EMP1016` to an **existing** database without deleting anything (run `python seed_extra.py`; it runs automatically in `init_db.py` and on Render start-up, and does nothing if they already exist). On the live site the employees use your `DEMO_EMPLOYEE_PASSWORD`.

These are demo-only credentials seeded by `database/seed.sql` (as Werkzeug hashes). Change or remove them for any real deployment.

> Seeded employees normally worked from `10.10.x.x` addresses, so logging in as them from your machine (`127.0.0.1`) correctly triggers the **"Login from a new location"** rule.

## Demonstration walkthrough

Use **two different browser sessions** so the manager and employee cookies don't collide — e.g. a normal window + an incognito window, two different browsers, or `http://localhost:5000` in one tab and `http://127.0.0.1:5000` in another.

1. **Browser A** → sign in as `MGR1001`. The Security Dashboard appears; the badge top-right shows **● Live** (Socket.IO connected).
2. Employees → **New employee** → Employee ID `EMP1006` (pre-filled), Name `Test Employee`, email, Department `Finance`, temporary password (or *Generate*) → **Create employee**. The row appears immediately; the account exists in MySQL (`users`) and `CREATE_EMPLOYEE` is in the audit log.
3. **Browser B** → sign in as `EMP1006` with the temporary password → you are asked to set a new password (logged as `PASSWORD_CHANGE`).
4. As the employee: **Records** → search `invoice` → open a record → search `revenue` → open another. In Browser A the **Live Activity Feed** shows `LOGIN`, `SEARCH`, `VIEW_RECORD`… as they happen, and *Online Now* becomes 1 — no refresh.
5. Suspicious behaviour, as the employee:
   - *Open a record by code* `FIN-0010` (RESTRICTED) → 403 "Access denied"
   - open `SAL-0002` (another department) → 403
   - type `http://…/manager/employees` in the address bar → 403
   *(or sign out and enter a wrong password 3 times for a failed-login alert)*
6. The backend logs each attempt as `UNAUTHORIZED_ACCESS`, the risk engine adds points (30 → 60 → 100), and alerts are inserted into MySQL.
7. **Browser A, without refreshing:** a toast appears — *🚨 NEW CRITICAL-RISK ALERT · Employee EMP1006 · Repeated unauthorized access attempts · Risk 100 CRITICAL* — the bell counter and the Alerts table update.
8. Click **View activity** (or open Alerts and click the row): full details — employee, action, resource, description, timestamp, IP address, user agent, risk score and the point-by-point **risk reason**.
9. Click **Acknowledge** (or **Resolve** with a note). The alert's `status`, `acknowledged_by` and `acknowledged_at` are updated in MySQL, `ACKNOWLEDGE_ALERT` is written to the audit log, and every open manager tab updates.

To reset the demo: `python init_db.py`.

### Running the demo on two laptops

Only the laptop that runs the app needs Python and MySQL; the other laptop just needs a browser.

1. Connect both laptops to the **same Wi-Fi** (a phone hotspot is the most reliable — many college/office networks block laptop-to-laptop traffic).
2. On the server laptop, start the app listening on the network (PowerShell):
   ```powershell
   $env:HOST = "0.0.0.0"; .venv\Scripts\python.exe app.py
   ```
   The console prints `Other devices on this network can open: http://<ip>:5000`.
3. If Windows Firewall asks, allow Python — and tick **Private** (and **Public** if Windows labels your network as public).
4. Manager laptop: open `http://<ip>:5000` (the server laptop can also use `http://127.0.0.1:5000`). Employee laptop: open `http://<ip>:5000`.
5. Stop the server (Ctrl+C) when you're done — it is a development server and should not stay exposed on shared networks.

Bonus: because the employee now logs in from a genuinely different IP address, the *new location* rule fires with a real address.

## Manager workflow

| Task | Where |
|---|---|
| See what is happening right now | Dashboard (KPIs, live feed, alerts, presence) or **Live Activity** |
| Investigate an alert | Alerts → click the row → *View activity* → employee page (`/manager/employees/<id>`) shows the full risk explanation, activity, alerts and login attempts |
| Close an alert | Acknowledge (investigating) → Resolve with a note (closed) |
| Onboard / offboard | Employees → New employee / Disable (disabled users are signed out immediately and cannot log in) |
| Help a locked-out employee | Employees → Reset (temporary password; they must change it at next login) |
| Review who did what | Audit Logs (manager actions, login attempts) |
| Tune detection | Settings → edit a rule → Save |

## Employee workflow

| Task | Where |
|---|---|
| Sign in | `/` with employee ID and password |
| Work with records | Records: search, open, add, edit, export CSV |
| Open a record by code | Dashboard → *Open a record by code* |
| Review own history | My Activity (own actions only, no risk data) |
| Profile / password | Profile → Change password |

Employees can see `PUBLIC` records of any department, `INTERNAL` and `CONFIDENTIAL` records of their own department (and company-wide `General` records), and never `RESTRICTED` records. Every denied attempt is recorded and scored.

## Real-time notification architecture

- **Server**: Flask-SocketIO in `threading` mode (works on Windows/macOS/Linux without eventlet), WebSocket transport via `simple-websocket`.
- **Authentication**: the Socket.IO `connect` handler uses the same Flask-Login session cookie. Anonymous connections are rejected.
- **Rooms**: every socket joins `user:<id>`; managers additionally join `managers`. Rooms are assigned only by the server, so an employee can never subscribe to manager events.
- **Events (server → client)**:
  | Event | Room | Payload |
  |---|---|---|
  | `activity:new` | managers | activity row (time, employee, action, resource, status, risk score) |
  | `alert:new` | managers | full alert (severity, message, risk score/level, activity id) |
  | `alert:updated` | managers | alert after acknowledge / resolve |
  | `presence` | managers | employee online/offline + last seen |
  | `account:disabled` | user:<id> | tells a disabled user's open tabs to sign out |
- **Ordering guarantee**: events are emitted **only after the database transaction commits**, so every notification corresponds to a row that already exists in MySQL.
- **Presence**: login sets `is_online`, logout clears it; each open tab sends a `heartbeat` every 25 s which updates `last_seen`. An employee is *online* if `is_online` and `last_seen` is within 120 s (closing the browser without logging out makes them go offline automatically).
- **Resilience**: the client auto-reconnects (status badge shows *Reconnecting…*), and after reconnecting every page re-fetches its data so nothing is missed. A failed emit is logged but never breaks the HTTP request.

## Risk scoring explained

Every activity is evaluated against the enabled rules in `risk_rules` (editable in **Settings**):

| Rule | Points | Fires when | Alert severity |
|---|---|---|---|
| `FAILED_LOGIN` | +10 | any failed login | – |
| `REPEATED_FAILED_LOGIN` | +20 | ≥ 3 failed logins for one ID in 10 min | HIGH |
| `NEW_LOCATION` | +10 | successful login from an IP never used by this employee before | MEDIUM |
| `OFF_HOURS` | +15 | login/data access outside 09:00–19:00 Mon–Fri (once per 60 min) | MEDIUM |
| `SENSITIVE_ACCESS` | +15 | viewing or editing a CONFIDENTIAL record | MEDIUM |
| `UNAUTHORIZED_ACCESS` | +30 | opening a record/page outside the employee's permissions | HIGH |
| `PRIVILEGE_ESCALATION` | +10 | an employee tries a manager-only page or API | HIGH |
| `REPEATED_UNAUTHORIZED` | +25 | ≥ 3 unauthorized attempts in 15 min | CRITICAL |
| `MASS_RECORD_ACCESS` | +20 | ≥ 15 records viewed/exported in 5 min | HIGH |
| `REPEATED_SEARCH` | +10 | ≥ 10 searches in 5 min | LOW |
| `RAPID_ACTIONS` | +15 | ≥ 20 actions in 1 min | MEDIUM |
| `UNUSUAL_FREQUENCY` | +15 | actions in the last hour > 3× the employee's normal hourly rate (7-day baseline, min 20 actions) | MEDIUM |
| `SUSPICIOUS_BURST` | +25 | ≥ 3 risk-scored events (excluding failed logins) in 10 min | HIGH |

**Levels**: `0–29 LOW`, `30–59 MEDIUM`, `60–79 HIGH`, `80–100 CRITICAL` (in `config.py`).

**Keeping scores sane**
- Scores are **capped at 100**.
- Aggregate rules fire **once per window**, so a burst is counted once, not on every click.
- The same alert type for the same employee is not repeated within a **10-minute cooldown**.
- Scores **decay** by 2 points per hour once an employee has been quiet for an hour.
- Crossing into HIGH or CRITICAL raises a separate `RISK_LEVEL_ESCALATION` alert.

**Explainability**: each point is stored in `risk_events` with a human-readable reason, e.g.
> Risk increased by 20 because: Accessed 17 records within 5 minutes (score 25 → 45)

These explanations are shown on the activity detail modal, the employee page and the Risk Monitoring page.

## Security measures

- Passwords hashed with Werkzeug scrypt (`generate_password_hash` / `check_password_hash`); never returned by any API or rendered in HTML.
- Temporary passwords must be changed at first login.
- **Strong password policy** — enforced on the server (`utils/validators.py`) for creating an employee, resetting a password and changing your own password, and shown as a live ✓ checklist in each form: at least 8 characters (max 128), an uppercase letter, a lowercase letter, a number and a special character; no spaces; no character repeated 3+ times in a row; no common words such as `password`, `qwerty` or `123456`; must not contain the account's employee ID or name. The *Generate* button always produces a 12-character password that meets every rule.
- Role-based access control with `@login_required`, `@manager_required`, `@employee_required` on every route and API. Employees probing manager URLs get **403** *and* an alert.
- Login rate limiting: 5 failures per employee ID or 20 per IP in 15 min → temporary lockout. Generic error messages (no user enumeration).
- CSRF protection on every form and on API writes (`X-CSRFToken` header); logout is POST-only.
- Session protection (`strong`), HttpOnly + SameSite cookies, 30-minute idle timeout, session cleared on login (fixation) and logout; disabled accounts lose their session immediately.
- SQL injection protection: all queries through SQLAlchemy parameter binding.
- Input validation for every field (IDs, names, emails, departments, record fields, rule limits).
- Security headers: Content-Security-Policy (no inline scripts), X-Frame-Options DENY, nosniff, Referrer-Policy, `Cache-Control: no-store` on authenticated pages.
- Friendly error pages / JSON errors — raw Python or database errors are never shown; details go to `logs/app.log`.
- Database outages return a 503 page instead of crashing; `/api/health` reports DB status.
- Suspicious activity handling is transactional: activity + risk score + risk events + alerts commit together or not at all (with a fallback that still stores the bare activity).

## API endpoints

All endpoints return JSON. Writes require the `X-CSRFToken` header (taken from the page's `<meta name="csrf-token">`).

| Method | Endpoint | Role | Description |
|---|---|---|---|
| POST | `/login` | public | form login (employee ID + password) |
| POST | `/logout` | any | sign out |
| GET | `/api/health` | public | database status |
| GET | `/api/manager/dashboard` | manager | stats, charts, feed, alerts, risk groups, presence, logins |
| GET | `/api/manager/stats` | manager | KPI numbers |
| GET | `/api/manager/presence` | manager | online/offline status |
| GET | `/api/manager/employees` | manager | list (`q`, `department`, `status`, `role`, `risk_level`, `online`, `page`) |
| POST | `/api/manager/employees` | manager | create employee |
| GET | `/api/manager/employees/<id>` | manager | employee details |
| PUT | `/api/manager/employees/<id>` | manager | update name/email/department/job title/role/status |
| DELETE | `/api/manager/employees/<id>` | manager | **disable** (soft delete — history is kept) |
| PUT | `/api/manager/employees/<id>/status` | manager | `{"status": "active" \| "disabled"}` |
| POST | `/api/manager/employees/<id>/reset-password` | manager | `{"password": "..."}` |
| GET | `/api/manager/employees/next-id` | manager | next free employee ID |
| GET | `/api/manager/activities` | manager | filters: `employee`, `action`, `status`, `role`, `suspicious`, `risk_level`, `severity`, `alert_status`, `date_from`, `date_to`, `page` |
| GET | `/api/manager/activities/<id>` | manager | full activity + risk events + alerts |
| GET | `/api/manager/alerts` | manager | filters: `employee`, `severity`, `status` (`OPEN`/`NEW`/…), `alert_type`, dates |
| GET | `/api/manager/alerts/<id>` | manager | alert + triggering activity |
| PUT | `/api/manager/alerts/<id>/acknowledge` | manager | acknowledge |
| PUT | `/api/manager/alerts/<id>/resolve` | manager | resolve, `{"note": "..."}` |
| GET | `/api/manager/risk` | manager | employees by level + recent risk events |
| GET | `/api/manager/audit` | manager | manager actions |
| GET | `/api/manager/login-attempts` | manager | login attempts (`success=0/1`) |
| GET | `/api/manager/rules` | manager | detection rules |
| PUT | `/api/manager/rules/<id>` | manager | update points/threshold/window/severity/enabled |
| GET | `/api/employee/activity` | employee | own activity (no risk data) |
| GET | `/api/employee/profile` | employee | own profile |

## Testing

```bash
python -m pytest -q
```

51 automated tests (in-memory SQLite, no MySQL needed) cover:

- **Authentication** — manager/employee login, invalid password, unknown ID, disabled account, lockout, POST-only logout, expired session (401), forced password change
- **Authorization** — employee → manager pages/APIs (403 + alert), manager → employee pages, anonymous access, own-data-only employee API, record permissions
- **Employee management** — create, duplicate ID/email (409), invalid input, disable (session invalidated), soft delete, reset password, self-protection, privilege-change alert, search/filter
- **Risk engine** — normal (0), medium, high (escalation alert), critical (capped at 100), repeated failed logins, mass export, new location, off-hours, decay, configurable rules
- **Alerts & API** — acknowledge/resolve (audited, not deletable), filters, activity detail fields, dashboard numbers equal database counts
- **Real-time** — anonymous sockets rejected, manager receives `activity:new` / `alert:new` / `alert:updated`, employees receive no manager events, heartbeat presence, disabled-account notification

The full demonstration flow (steps 1–9 above) was also run end-to-end against MySQL 8 in two browser sessions.

## Future improvements

- Per-employee behavioural baselines and an optional ML anomaly model on top of the explainable rules
- Geo-IP lookup for real "unusual location" detection; device fingerprinting
- Email / Slack / SMS escalation for CRITICAL alerts; on-call routing
- Case management (assign alerts, comments, attachments)
- Multi-factor authentication for managers
- Separate read-only "auditor" role; fine-grained department managers
- Production deployment: gunicorn + eventlet/gevent or uvicorn, Redis message queue for multiple Socket.IO workers, HTTPS, Alembic migrations
- Data retention policies and archiving for `activity_logs`
