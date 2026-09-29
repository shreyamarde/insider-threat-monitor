-- =====================================================================
--  SHRUTU Insider Threat Monitoring System — MySQL 8 schema
--
--  Run:   mysql -u root -p < database/schema.sql
--  (or)   python init_db.py            (reads credentials from .env)
--
--  WARNING: re-running this file drops and recreates the tables below
--  (only in the insider_threat_system database).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS insider_threat_system
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE insider_threat_system;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS risk_events;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS activity_logs;
DROP TABLE IF EXISTS login_attempts;
DROP TABLE IF EXISTS risk_scores;
DROP TABLE IF EXISTS risk_rules;
DROP TABLE IF EXISTS records;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS departments;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- Departments (lookup)
-- ---------------------------------------------------------------------
CREATE TABLE departments (
    id    INT AUTO_INCREMENT PRIMARY KEY,
    name  VARCHAR(60) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Users: employees and managers. Passwords are Werkzeug (scrypt) hashes.
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    employee_id           VARCHAR(20)  NOT NULL UNIQUE,
    name                  VARCHAR(100) NOT NULL,
    email                 VARCHAR(120) NOT NULL UNIQUE,
    password_hash         VARCHAR(255) NOT NULL,
    department            VARCHAR(60)  NOT NULL,
    job_title             VARCHAR(80)  NULL,
    role                  ENUM('employee','manager') NOT NULL DEFAULT 'employee',
    status                ENUM('active','disabled')  NOT NULL DEFAULT 'active',
    must_change_password  TINYINT(1)   NOT NULL DEFAULT 1,
    is_online             TINYINT(1)   NOT NULL DEFAULT 0,
    last_login            DATETIME     NULL,
    last_login_ip         VARCHAR(45)  NULL,
    last_seen             DATETIME     NULL,
    created_by            INT          NULL,
    created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_users_employee_id (employee_id),
    INDEX ix_users_role_status (role, status),
    CONSTRAINT fk_users_department FOREIGN KEY (department) REFERENCES departments(name) ON UPDATE CASCADE,
    CONSTRAINT fk_users_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Business records employees work with (the monitored resource)
-- ---------------------------------------------------------------------
CREATE TABLE records (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    record_code  VARCHAR(20)  NOT NULL UNIQUE,
    title        VARCHAR(150) NOT NULL,
    category     VARCHAR(30)  NOT NULL DEFAULT 'Other',
    department   VARCHAR(60)  NOT NULL,
    sensitivity  ENUM('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED') NOT NULL DEFAULT 'INTERNAL',
    content      TEXT         NOT NULL,
    created_by   INT          NULL,
    updated_by   INT          NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_records_department (department),
    CONSTRAINT fk_records_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_records_updated_by FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Activity logs: every meaningful action (employees AND managers)
-- ---------------------------------------------------------------------
CREATE TABLE activity_logs (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT          NULL,
    employee_id   VARCHAR(20)  NOT NULL,
    actor_role    VARCHAR(20)  NULL,
    action        VARCHAR(40)  NOT NULL,
    resource      VARCHAR(255) NULL,
    description   VARCHAR(500) NULL,
    record_count  INT          NOT NULL DEFAULT 0,
    timestamp     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address    VARCHAR(45)  NULL,
    user_agent    VARCHAR(255) NULL,
    status        VARCHAR(10)  NOT NULL DEFAULT 'SUCCESS',
    risk_score    INT          NOT NULL DEFAULT 0,
    risk_reason   VARCHAR(1000) NULL,
    INDEX ix_activity_user_time (user_id, timestamp),
    INDEX ix_activity_employee_time (employee_id, timestamp),
    INDEX ix_activity_action (action),
    INDEX ix_activity_timestamp (timestamp),
    CONSTRAINT fk_activity_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Alerts: never deleted, kept as an audit trail
-- ---------------------------------------------------------------------
CREATE TABLE alerts (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT          NULL,
    employee_id      VARCHAR(20)  NOT NULL,
    activity_id      BIGINT       NULL,
    alert_type       VARCHAR(40)  NOT NULL,
    severity         ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL,
    message          VARCHAR(500) NOT NULL,
    risk_score       INT          NOT NULL DEFAULT 0,
    timestamp        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status           ENUM('NEW','ACKNOWLEDGED','RESOLVED') NOT NULL DEFAULT 'NEW',
    acknowledged_by  INT          NULL,
    acknowledged_at  DATETIME     NULL,
    resolved_by      INT          NULL,
    resolved_at      DATETIME     NULL,
    resolution_note  VARCHAR(500) NULL,
    INDEX ix_alerts_user (user_id),
    INDEX ix_alerts_employee (employee_id),
    INDEX ix_alerts_status (status),
    INDEX ix_alerts_timestamp (timestamp),
    CONSTRAINT fk_alerts_user     FOREIGN KEY (user_id)         REFERENCES users(id)         ON DELETE SET NULL,
    CONSTRAINT fk_alerts_activity FOREIGN KEY (activity_id)     REFERENCES activity_logs(id) ON DELETE SET NULL,
    CONSTRAINT fk_alerts_ack_by   FOREIGN KEY (acknowledged_by) REFERENCES users(id)         ON DELETE SET NULL,
    CONSTRAINT fk_alerts_res_by   FOREIGN KEY (resolved_by)     REFERENCES users(id)         ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Current risk score per user
-- ---------------------------------------------------------------------
CREATE TABLE risk_scores (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    user_id           INT      NOT NULL UNIQUE,
    current_score     INT      NOT NULL DEFAULT 0,
    risk_level        ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'LOW',
    last_updated      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_increase_at  DATETIME NULL,
    CONSTRAINT fk_risk_scores_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Risk events: WHY a score changed (explainability)
-- ---------------------------------------------------------------------
CREATE TABLE risk_events (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT          NOT NULL,
    activity_id   BIGINT       NULL,
    rule_key      VARCHAR(40)  NOT NULL,
    points        INT          NOT NULL,
    reason        VARCHAR(500) NOT NULL,
    score_before  INT          NOT NULL,
    score_after   INT          NOT NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_risk_events_user_time (user_id, created_at),
    INDEX ix_risk_events_created (created_at),
    CONSTRAINT fk_risk_events_user     FOREIGN KEY (user_id)     REFERENCES users(id)         ON DELETE CASCADE,
    CONSTRAINT fk_risk_events_activity FOREIGN KEY (activity_id) REFERENCES activity_logs(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Login attempts (successful and failed)
-- ---------------------------------------------------------------------
CREATE TABLE login_attempts (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    employee_id  VARCHAR(20)  NOT NULL,
    user_id      INT          NULL,
    ip_address   VARCHAR(45)  NULL,
    user_agent   VARCHAR(255) NULL,
    timestamp    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    success      TINYINT(1)   NOT NULL,
    reason       VARCHAR(60)  NULL,
    INDEX ix_login_attempts_employee_time (employee_id, timestamp),
    INDEX ix_login_attempts_ip_time (ip_address, timestamp),
    INDEX ix_login_attempts_timestamp (timestamp),
    CONSTRAINT fk_login_attempts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Configurable detection rules (editable in Manager > Settings)
-- ---------------------------------------------------------------------
CREATE TABLE risk_rules (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    rule_key        VARCHAR(40)  NOT NULL UNIQUE,
    name            VARCHAR(100) NOT NULL,
    description     VARCHAR(255) NULL,
    points          INT          NOT NULL DEFAULT 0,
    threshold       INT          NOT NULL DEFAULT 1,
    window_minutes  INT          NOT NULL DEFAULT 0,
    severity        ENUM('NONE','LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'NONE',
    enabled         TINYINT(1)   NOT NULL DEFAULT 1,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- =====================================================================
--  Reference data required by the application
-- =====================================================================
INSERT INTO departments (name) VALUES
    ('Finance'), ('Human Resources'), ('Engineering'),
    ('IT & Security'), ('Sales'), ('Legal');

INSERT INTO risk_rules (rule_key, name, description, points, threshold, window_minutes, severity) VALUES
 ('FAILED_LOGIN',          'Failed login',                    'Each failed login attempt.',                                                          10,  1,  0, 'NONE'),
 ('REPEATED_FAILED_LOGIN', 'Repeated failed logins',          'Threshold failed logins for one employee ID within the window.',                     20,  3, 10, 'HIGH'),
 ('NEW_LOCATION',          'Login from new location',         'Successful login from an IP address this employee has never used before.',            10,  1,  0, 'MEDIUM'),
 ('OFF_HOURS',             'Outside working hours',           'Activity outside configured working hours/days (counted once per window).',           15,  1, 60, 'MEDIUM'),
 ('SENSITIVE_ACCESS',      'Sensitive record access',         'Viewing or editing a CONFIDENTIAL record.',                                          15,  1,  0, 'MEDIUM'),
 ('UNAUTHORIZED_ACCESS',   'Unauthorized access attempt',     'Attempt to open a record or page outside the employee''s permissions.',              30,  1,  0, 'HIGH'),
 ('PRIVILEGE_ESCALATION',  'Privilege escalation attempt',    'Employee attempted to use a manager-only page or API.',                              10,  1,  0, 'HIGH'),
 ('REPEATED_UNAUTHORIZED', 'Repeated unauthorized attempts',  'Threshold unauthorized attempts within the window.',                                  25,  3, 15, 'CRITICAL'),
 ('MASS_RECORD_ACCESS',    'Large number of records accessed','Threshold or more records viewed/exported within the window.',                       20, 15,  5, 'HIGH'),
 ('REPEATED_SEARCH',       'Repeated searches',               'Threshold searches within the window.',                                              10, 10,  5, 'LOW'),
 ('RAPID_ACTIONS',         'Multiple rapid actions',          'Threshold actions of any kind within the window.',                                   15, 20,  1, 'MEDIUM'),
 ('UNUSUAL_FREQUENCY',     'Unusual access frequency',        'Actions in the window exceed threshold x the employee''s normal hourly rate (7-day baseline).', 15, 3, 60, 'MEDIUM'),
 ('SUSPICIOUS_BURST',      'Multiple suspicious events',      'Threshold risk-scored events (excluding failed logins) within the window.',          25,  3, 10, 'HIGH');
