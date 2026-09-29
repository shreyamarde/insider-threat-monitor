-- =====================================================================
--  SHRUTU Insider Threat Monitoring System — demo seed data
--
--  Run AFTER schema.sql:
--      mysql -u root -p insider_threat_system < database/seed.sql
--  (or)  python init_db.py        (runs schema + seed)
--
--  Demo credentials are documented in README.md only.
--  Timestamps are relative to NOW() so the dashboard always looks "live".
--  Every seeded risk score is fully explained by its risk_events rows,
--  exactly as the rule engine would have produced them.
-- =====================================================================
USE insider_threat_system;

SET @pw_manager  = 'scrypt:32768:8:1$8x6ytBeC6AV8iBAQ$cea5de75a8a3ce8f18af9f389f14ce03dac7d69caf05eb54d32a63ccc2e77083dcc3111ab0e32bdfa6f89b35f19a5859bdd454488536608d163cedd90f7f128c';
SET @pw_employee = 'scrypt:32768:8:1$MNPBVQJ9O4M3GGSb$e213fbf05796548b46e15e6d209ee6d25ddc9e72eac11a6b0f8eb41bde65fd8f2cd57420c9ceae48a84badcc1716941846dd92fbfb32ffefb2dfa239ccc8a704';
SET @ua_chrome = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36';
SET @ua_edge   = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36 Edg/128.0';
SET @ua_mac    = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15';
SET @ua_script = 'python-requests/2.32.3';
SET @yesterday = CURDATE() - INTERVAL 1 DAY;

-- ---------------------------------------------------------------------
-- Users (1 manager, 6 employees — one of them disabled)
-- ---------------------------------------------------------------------
INSERT INTO users (employee_id, name, email, password_hash, department, job_title, role, status,
                   must_change_password, is_online, last_login, last_login_ip, last_seen, created_at, updated_at) VALUES
('MGR1001', 'Ananya Iyer',  'ananya.iyer@shrutu.example',  @pw_manager,  'IT & Security',   'Security Manager',   'manager',  'active',   0, 0, NOW() - INTERVAL 7 HOUR,  '10.10.0.5',  NOW() - INTERVAL 7 HOUR,  NOW() - INTERVAL 60 DAY, NOW()),
('EMP1000', 'Rohan Das',    'rohan.das@shrutu.example',    @pw_employee, 'Finance',         'Accounts Assistant', 'employee', 'disabled', 0, 0, NOW() - INTERVAL 5 DAY,   '10.10.1.40', NOW() - INTERVAL 5 DAY,   NOW() - INTERVAL 45 DAY, NOW() - INTERVAL 3 DAY),
('EMP1001', 'Rahul Sharma', 'rahul.sharma@shrutu.example', @pw_employee, 'Finance',         'Financial Analyst',  'employee', 'active',   0, 0, NOW() - INTERVAL 5 HOUR,  '10.10.1.21', NOW() - INTERVAL 3 HOUR,  NOW() - INTERVAL 30 DAY, NOW()),
('EMP1002', 'Sneha Patel',  'sneha.patel@shrutu.example',  @pw_employee, 'Human Resources', 'HR Executive',       'employee', 'active',   0, 0, NOW() - INTERVAL 6 HOUR,  '10.10.2.14', NOW() - INTERVAL 4 HOUR,  NOW() - INTERVAL 30 DAY, NOW()),
('EMP1003', 'Arjun Verma',  'arjun.verma@shrutu.example',  @pw_employee, 'Engineering',     'Software Engineer',  'employee', 'active',   0, 0, TIMESTAMP(@yesterday, '23:05:12'), '10.10.3.33', TIMESTAMP(@yesterday, '23:20:40'), NOW() - INTERVAL 30 DAY, NOW()),
('EMP1004', 'Kavya Nair',   'kavya.nair@shrutu.example',   @pw_employee, 'Sales',           'Sales Associate',    'employee', 'active',   0, 0, NOW() - INTERVAL 183 MINUTE, '10.10.4.18', NOW() - INTERVAL 70 MINUTE, NOW() - INTERVAL 30 DAY, NOW()),
('EMP1005', 'Vikram Singh', 'vikram.singh@shrutu.example', @pw_employee, 'Legal',           'Legal Counsel',      'employee', 'active',   0, 0, NOW() - INTERVAL 138 MINUTE, '10.10.5.9',  NOW() - INTERVAL 60 MINUTE, NOW() - INTERVAL 30 DAY, NOW());

SET @mgr    = (SELECT id FROM users WHERE employee_id = 'MGR1001');
SET @rohan  = (SELECT id FROM users WHERE employee_id = 'EMP1000');
SET @rahul  = (SELECT id FROM users WHERE employee_id = 'EMP1001');
SET @sneha  = (SELECT id FROM users WHERE employee_id = 'EMP1002');
SET @arjun  = (SELECT id FROM users WHERE employee_id = 'EMP1003');
SET @kavya  = (SELECT id FROM users WHERE employee_id = 'EMP1004');
SET @vikram = (SELECT id FROM users WHERE employee_id = 'EMP1005');
UPDATE users SET created_by = @mgr WHERE role = 'employee';

-- ---------------------------------------------------------------------
-- Business records
-- ---------------------------------------------------------------------
INSERT INTO records (record_code, title, category, department, sensitivity, content, created_by, created_at, updated_at) VALUES
('FIN-0001', 'Q2 2026 Revenue Summary', 'Report', 'Finance', 'INTERNAL', 'Consolidated Q2 revenue: INR 48.2 Cr (+11% YoY). Services grew 18%, licences flat. Detailed breakdown by region attached in the finance share.', @mgr, NOW() - INTERVAL 40 DAY, NOW() - INTERVAL 12 DAY),
('FIN-0002', 'Vendor Payment Schedule — September', 'Invoice', 'Finance', 'INTERNAL', 'Payment run dates: 5th, 15th and 25th. Vendors on net-30 terms are paid in the 25th run. Urgent payments require CFO approval.', @mgr, NOW() - INTERVAL 20 DAY, NOW() - INTERVAL 4 HOUR),
('FIN-0003', 'Invoice INV-88213 — Northwind Traders', 'Invoice', 'Finance', 'INTERNAL', 'Invoice for 1,200 units of networking equipment. Amount INR 14,40,000. Status: approved, scheduled for the 15th payment run.', @mgr, NOW() - INTERVAL 15 DAY, NOW() - INTERVAL 15 DAY),
('FIN-0004', 'Payroll Ledger — August 2026', 'Report', 'Finance', 'CONFIDENTIAL', 'Monthly payroll ledger for all 312 employees including gross pay, deductions and bank transfer references.', @mgr, NOW() - INTERVAL 28 DAY, NOW() - INTERVAL 28 DAY),
('FIN-0005', 'Corporate Bank Account Mandates', 'Policy', 'Finance', 'CONFIDENTIAL', 'Authorised signatories and transaction limits for the three corporate current accounts. Dual authorisation above INR 10 lakh.', @mgr, NOW() - INTERVAL 90 DAY, NOW() - INTERVAL 30 DAY),
('FIN-0006', 'Annual Budget Draft FY2027', 'Report', 'Finance', 'CONFIDENTIAL', 'Draft departmental budgets for FY2027. Headcount growth capped at 6%. Not for circulation outside Finance.', @mgr, NOW() - INTERVAL 10 DAY, NOW() - INTERVAL 2 DAY),
('FIN-0007', 'Expense Reimbursement Policy', 'Policy', 'Finance', 'PUBLIC', 'Claims must be submitted within 30 days with receipts. Travel is reimbursed per the company travel policy.', @mgr, NOW() - INTERVAL 200 DAY, NOW() - INTERVAL 60 DAY),
('FIN-0008', 'Invoice INV-88240 — Contoso Retail', 'Invoice', 'Finance', 'INTERNAL', 'Quarterly support contract invoice. Amount INR 3,75,000. Awaiting PO match.', @mgr, NOW() - INTERVAL 8 DAY, NOW() - INTERVAL 8 DAY),
('FIN-0009', 'Tax Filing Checklist 2026', 'Other', 'Finance', 'INTERNAL', 'GST returns due on the 20th; TDS on the 7th. Advance tax instalment due 15 December.', @mgr, NOW() - INTERVAL 50 DAY, NOW() - INTERVAL 5 DAY),
('FIN-0010', 'Board M&A Valuation — Project Falcon', 'Report', 'Finance', 'RESTRICTED', 'Board-only valuation model for a potential acquisition. Access limited to the CFO and board members.', @mgr, NOW() - INTERVAL 6 DAY, NOW() - INTERVAL 6 DAY),
('HR-0001', 'Employee Handbook 2026', 'Policy', 'Human Resources', 'PUBLIC', 'Working hours, leave, benefits, code of conduct and grievance process for all employees.', @mgr, NOW() - INTERVAL 250 DAY, NOW() - INTERVAL 100 DAY),
('HR-0002', 'Recruitment Plan Q4', 'Report', 'Human Resources', 'INTERNAL', 'Open requisitions: 4 engineers, 2 sales associates, 1 HR generalist. Campus drive planned for November.', @mgr, NOW() - INTERVAL 14 DAY, NOW() - INTERVAL 3 DAY),
('HR-0003', 'Salary Bands by Grade', 'Personnel', 'Human Resources', 'CONFIDENTIAL', 'Salary ranges for grades G1–G9 with market benchmarks. Used for offers and annual reviews only.', @mgr, NOW() - INTERVAL 120 DAY, NOW() - INTERVAL 20 DAY),
('HR-0004', 'Performance Review Summaries — Engineering', 'Personnel', 'Human Resources', 'CONFIDENTIAL', 'Mid-year review ratings and calibration notes for the Engineering department.', @mgr, NOW() - INTERVAL 25 DAY, NOW() - INTERVAL 25 DAY),
('HR-0005', 'Leave Policy', 'Policy', 'Human Resources', 'INTERNAL', '24 days annual leave, 12 sick days, carry-forward up to 10 days.', @mgr, NOW() - INTERVAL 300 DAY, NOW() - INTERVAL 90 DAY),
('HR-0006', 'Executive Compensation Package', 'Personnel', 'Human Resources', 'RESTRICTED', 'CXO compensation, ESOP grants and severance terms. Restricted to the CHRO.', @mgr, NOW() - INTERVAL 45 DAY, NOW() - INTERVAL 45 DAY),
('ENG-0001', 'Platform Architecture Overview', 'Technical', 'Engineering', 'INTERNAL', 'Service map of the customer platform: API gateway, auth service, billing service, reporting pipeline.', @mgr, NOW() - INTERVAL 180 DAY, NOW() - INTERVAL 20 DAY),
('ENG-0002', 'Release Checklist v4', 'Technical', 'Engineering', 'INTERNAL', 'Code freeze, regression suite, staging sign-off, change ticket, rollback plan.', @mgr, NOW() - INTERVAL 90 DAY, NOW() - INTERVAL 10 DAY),
('ENG-0003', 'Production Credentials Rotation Runbook', 'Technical', 'Engineering', 'CONFIDENTIAL', 'Step-by-step procedure for rotating database and API credentials in production. Requires two engineers.', @mgr, NOW() - INTERVAL 60 DAY, NOW() - INTERVAL 7 DAY),
('ENG-0004', 'API Rate Limit Design', 'Technical', 'Engineering', 'INTERNAL', 'Token-bucket limits per tenant: 100 req/s burst, 20 req/s sustained.', @mgr, NOW() - INTERVAL 30 DAY, NOW() - INTERVAL 30 DAY),
('ENG-0005', 'Customer Data Retention Design', 'Technical', 'Engineering', 'CONFIDENTIAL', 'Retention schedules and purge jobs for customer PII in line with the data protection policy.', @mgr, NOW() - INTERVAL 40 DAY, NOW() - INTERVAL 12 DAY),
('ENG-0006', 'Incident Postmortem — 14 Aug outage', 'Report', 'Engineering', 'INTERNAL', 'Root cause: expired TLS certificate on the internal load balancer. Action items: automated renewal and alerting.', @mgr, NOW() - INTERVAL 44 DAY, NOW() - INTERVAL 40 DAY),
('SEC-0001', 'Acceptable Use Policy', 'Policy', 'IT & Security', 'PUBLIC', 'Company systems are for business use. Activity is monitored. Report suspected incidents to security@.', @mgr, NOW() - INTERVAL 365 DAY, NOW() - INTERVAL 30 DAY),
('SEC-0002', 'Firewall Change Log', 'Technical', 'IT & Security', 'INTERNAL', 'Record of approved firewall rule changes for the last quarter.', @mgr, NOW() - INTERVAL 90 DAY, NOW() - INTERVAL 2 DAY),
('SEC-0003', 'Security Incident Register', 'Report', 'IT & Security', 'CONFIDENTIAL', 'Register of reported security incidents, severity, owner and status.', @mgr, NOW() - INTERVAL 120 DAY, NOW() - INTERVAL 1 DAY),
('SEC-0004', 'Penetration Test Report 2026', 'Report', 'IT & Security', 'RESTRICTED', 'External penetration test findings with exploit details. Restricted to the security team lead.', @mgr, NOW() - INTERVAL 20 DAY, NOW() - INTERVAL 20 DAY),
('SAL-0001', 'Product Price List 2026', 'Other', 'Sales', 'INTERNAL', 'List prices for all SKUs with approved discount bands (max 15% without director approval).', @mgr, NOW() - INTERVAL 100 DAY, NOW() - INTERVAL 30 DAY),
('SAL-0002', 'Key Account List — West Region', 'Customer', 'Sales', 'CONFIDENTIAL', 'Top 40 customers in the West region with contract values, renewal dates and decision makers.', @mgr, NOW() - INTERVAL 60 DAY, NOW() - INTERVAL 6 DAY),
('SAL-0003', 'Contract — Globex Corp Renewal', 'Contract', 'Sales', 'CONFIDENTIAL', 'Three-year renewal at INR 1.2 Cr per year with 5% annual uplift.', @mgr, NOW() - INTERVAL 18 DAY, NOW() - INTERVAL 4 DAY),
('SAL-0004', 'Sales Playbook', 'Policy', 'Sales', 'INTERNAL', 'Qualification framework, demo scripts and objection handling.', @mgr, NOW() - INTERVAL 150 DAY, NOW() - INTERVAL 50 DAY),
('SAL-0005', 'Q3 Pipeline Forecast', 'Report', 'Sales', 'INTERNAL', 'Weighted pipeline INR 22 Cr; commit INR 9.5 Cr.', @mgr, NOW() - INTERVAL 20 DAY, NOW() - INTERVAL 1 DAY),
('LEG-0001', 'NDA Template', 'Contract', 'Legal', 'INTERNAL', 'Standard mutual non-disclosure agreement template, version 3.2.', @mgr, NOW() - INTERVAL 400 DAY, NOW() - INTERVAL 80 DAY),
('LEG-0002', 'Litigation Hold — Case 2026-117', 'Contract', 'Legal', 'RESTRICTED', 'Legal hold notice and custodian list. Restricted to General Counsel.', @mgr, NOW() - INTERVAL 12 DAY, NOW() - INTERVAL 12 DAY),
('LEG-0003', 'Compliance Calendar 2026', 'Other', 'Legal', 'INTERNAL', 'Statutory filing and audit dates for the year.', @mgr, NOW() - INTERVAL 200 DAY, NOW() - INTERVAL 20 DAY),
('LEG-0004', 'Data Protection Impact Assessment', 'Report', 'Legal', 'CONFIDENTIAL', 'DPIA for the new customer analytics feature.', @mgr, NOW() - INTERVAL 35 DAY, NOW() - INTERVAL 10 DAY),
('GEN-0001', 'Company Holiday Calendar 2026', 'Policy', 'General', 'PUBLIC', 'List of public holidays and optional holidays for 2026.', @mgr, NOW() - INTERVAL 280 DAY, NOW() - INTERVAL 280 DAY),
('GEN-0002', 'Office Safety Guidelines', 'Policy', 'General', 'PUBLIC', 'Fire exits, first aid, visitor badges and emergency contacts.', @mgr, NOW() - INTERVAL 300 DAY, NOW() - INTERVAL 100 DAY),
('GEN-0003', 'IT Helpdesk Contacts', 'Other', 'General', 'INTERNAL', 'Helpdesk extension 4444, hours 08:00–20:00. Priority incidents via the on-call number.', @mgr, NOW() - INTERVAL 150 DAY, NOW() - INTERVAL 15 DAY),
('GEN-0004', 'Travel Policy', 'Policy', 'General', 'PUBLIC', 'Economy class for flights under 6 hours. Hotels within the approved city limits.', @mgr, NOW() - INTERVAL 220 DAY, NOW() - INTERVAL 60 DAY),
('GEN-0005', 'Code of Conduct', 'Policy', 'General', 'PUBLIC', 'Integrity, confidentiality, conflicts of interest and reporting concerns.', @mgr, NOW() - INTERVAL 365 DAY, NOW() - INTERVAL 120 DAY);

-- ---------------------------------------------------------------------
-- Risk score rows for every user (seeded scores are explained below)
-- ---------------------------------------------------------------------
INSERT INTO risk_scores (user_id, current_score, risk_level, last_updated, last_increase_at) VALUES
(@mgr,    0,  'LOW',      NOW(), NULL),
(@rohan,  10, 'LOW',      NOW(), NOW() - INTERVAL 4 HOUR),
(@rahul,  0,  'LOW',      NOW(), NULL),
(@sneha,  45, 'MEDIUM',   NOW(), NOW() - INTERVAL 340 MINUTE),
(@arjun,  70, 'HIGH',     NOW(), TIMESTAMP(@yesterday, '23:11:30')),
(@kavya,  95, 'CRITICAL', NOW(), NOW() - INTERVAL 75 MINUTE),
(@vikram, 20, 'LOW',      NOW(), NOW() - INTERVAL 139 MINUTE);

-- =====================================================================
-- Manager audit trail
-- =====================================================================
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status) VALUES
(@mgr, 'MGR1001', 'manager', 'CREATE_EMPLOYEE', 'employee:EMP1000', 'Created employee account EMP1000 (Rohan Das, Finance, status active)', NOW() - INTERVAL 45 DAY, '10.10.0.5', @ua_chrome, 'SUCCESS'),
(@mgr, 'MGR1001', 'manager', 'CREATE_EMPLOYEE', 'employee:EMP1001', 'Created employee account EMP1001 (Rahul Sharma, Finance, status active)', NOW() - INTERVAL 30 DAY, '10.10.0.5', @ua_chrome, 'SUCCESS'),
(@mgr, 'MGR1001', 'manager', 'CREATE_EMPLOYEE', 'employee:EMP1002', 'Created employee account EMP1002 (Sneha Patel, Human Resources, status active)', NOW() - INTERVAL 30 DAY, '10.10.0.5', @ua_chrome, 'SUCCESS'),
(@mgr, 'MGR1001', 'manager', 'CREATE_EMPLOYEE', 'employee:EMP1003', 'Created employee account EMP1003 (Arjun Verma, Engineering, status active)', NOW() - INTERVAL 30 DAY, '10.10.0.5', @ua_chrome, 'SUCCESS'),
(@mgr, 'MGR1001', 'manager', 'CREATE_EMPLOYEE', 'employee:EMP1004', 'Created employee account EMP1004 (Kavya Nair, Sales, status active)', NOW() - INTERVAL 30 DAY, '10.10.0.5', @ua_chrome, 'SUCCESS'),
(@mgr, 'MGR1001', 'manager', 'CREATE_EMPLOYEE', 'employee:EMP1005', 'Created employee account EMP1005 (Vikram Singh, Legal, status active)', NOW() - INTERVAL 30 DAY, '10.10.0.5', @ua_chrome, 'SUCCESS'),
(@mgr, 'MGR1001', 'manager', 'DISABLE_EMPLOYEE', 'employee:EMP1000', 'Disabled account EMP1000 (Rohan Das) — resigned, last working day', NOW() - INTERVAL 3 DAY, '10.10.0.5', @ua_chrome, 'SUCCESS'),
(@mgr, 'MGR1001', 'manager', 'MANAGER_LOGIN', '/login', 'Signed in', NOW() - INTERVAL 7 HOUR, '10.10.0.5', @ua_chrome, 'SUCCESS');
INSERT INTO login_attempts (employee_id, user_id, ip_address, user_agent, timestamp, success, reason) VALUES
('MGR1001', @mgr, '10.10.0.5', @ua_chrome, NOW() - INTERVAL 7 HOUR, 1, 'SUCCESS');

-- =====================================================================
-- EMP1001 Rahul Sharma (Finance) — normal behaviour, LOW (0)
-- =====================================================================
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, record_count, timestamp, ip_address, user_agent, status) VALUES
(@rahul, 'EMP1001', 'employee', 'LOGIN',         '/login',          'Signed in',                                   0, TIMESTAMP(@yesterday, '09:58:10'), '10.10.1.21', @ua_chrome, 'SUCCESS'),
(@rahul, 'EMP1001', 'employee', 'SEARCH',        'records',         'Searched "budget" — 2 result(s)',             0, TIMESTAMP(@yesterday, '10:04:31'), '10.10.1.21', @ua_chrome, 'SUCCESS'),
(@rahul, 'EMP1001', 'employee', 'VIEW_RECORD',   'record:FIN-0001', 'Viewed INTERNAL record ''Q2 2026 Revenue Summary''', 1, TIMESTAMP(@yesterday, '10:05:02'), '10.10.1.21', @ua_chrome, 'SUCCESS'),
(@rahul, 'EMP1001', 'employee', 'LOGOUT',        '/logout',         'Signed out',                                  0, TIMESTAMP(@yesterday, '17:42:55'), '10.10.1.21', @ua_chrome, 'SUCCESS'),
(@rahul, 'EMP1001', 'employee', 'LOGIN',         '/login',          'Signed in',                                   0, NOW() - INTERVAL 300 MINUTE, '10.10.1.21', @ua_chrome, 'SUCCESS'),
(@rahul, 'EMP1001', 'employee', 'SEARCH',        'records',         'Searched "invoice" — 3 result(s)',            0, NOW() - INTERVAL 295 MINUTE, '10.10.1.21', @ua_chrome, 'SUCCESS'),
(@rahul, 'EMP1001', 'employee', 'VIEW_RECORD',   'record:FIN-0003', 'Viewed INTERNAL record ''Invoice INV-88213 — Northwind Traders''', 1, NOW() - INTERVAL 293 MINUTE, '10.10.1.21', @ua_chrome, 'SUCCESS'),
(@rahul, 'EMP1001', 'employee', 'VIEW_RECORD',   'record:FIN-0008', 'Viewed INTERNAL record ''Invoice INV-88240 — Contoso Retail''', 1, NOW() - INTERVAL 290 MINUTE, '10.10.1.21', @ua_chrome, 'SUCCESS'),
(@rahul, 'EMP1001', 'employee', 'UPDATE_RECORD', 'record:FIN-0002', 'Updated record ''Vendor Payment Schedule — September''', 1, NOW() - INTERVAL 240 MINUTE, '10.10.1.21', @ua_chrome, 'SUCCESS'),
(@rahul, 'EMP1001', 'employee', 'LOGOUT',        '/logout',         'Signed out',                                  0, NOW() - INTERVAL 180 MINUTE, '10.10.1.21', @ua_chrome, 'SUCCESS');
UPDATE records SET updated_by = @rahul WHERE record_code = 'FIN-0002';
INSERT INTO login_attempts (employee_id, user_id, ip_address, user_agent, timestamp, success, reason) VALUES
('EMP1001', @rahul, '10.10.1.21', @ua_chrome, TIMESTAMP(@yesterday, '09:58:10'), 1, 'SUCCESS'),
('EMP1001', @rahul, '10.10.1.21', @ua_chrome, NOW() - INTERVAL 300 MINUTE, 1, 'SUCCESS');

-- =====================================================================
-- EMP1002 Sneha Patel (HR) — off-hours login + confidential access, MEDIUM (45)
-- =====================================================================
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@sneha, 'EMP1002', 'employee', 'LOGIN', '/login', 'Signed in', TIMESTAMP(@yesterday, '21:47:05'), '10.10.2.14', @ua_mac, 'SUCCESS', 15,
 CONCAT('+15 Login at 21:47 on ', DAYNAME(@yesterday), ' is outside working hours (09:00–19:00, Mon–Fri)'));
SET @s1 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status) VALUES
(@sneha, 'EMP1002', 'employee', 'LOGOUT', '/logout', 'Signed out', TIMESTAMP(@yesterday, '21:58:40'), '10.10.2.14', @ua_mac, 'SUCCESS'),
(@sneha, 'EMP1002', 'employee', 'LOGIN',  '/login',  'Signed in',  NOW() - INTERVAL 360 MINUTE, '10.10.2.14', @ua_mac, 'SUCCESS');
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, record_count, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@sneha, 'EMP1002', 'employee', 'VIEW_RECORD', 'record:HR-0003', 'Viewed CONFIDENTIAL record ''Salary Bands by Grade''', 1, NOW() - INTERVAL 350 MINUTE, '10.10.2.14', @ua_mac, 'SUCCESS', 15,
 '+15 Viewed CONFIDENTIAL record record:HR-0003');
SET @s2 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, record_count, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@sneha, 'EMP1002', 'employee', 'VIEW_RECORD', 'record:HR-0004', 'Viewed CONFIDENTIAL record ''Performance Review Summaries — Engineering''', 1, NOW() - INTERVAL 340 MINUTE, '10.10.2.14', @ua_mac, 'SUCCESS', 15,
 '+15 Viewed CONFIDENTIAL record record:HR-0004');
SET @s3 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status) VALUES
(@sneha, 'EMP1002', 'employee', 'LOGOUT', '/logout', 'Signed out', NOW() - INTERVAL 240 MINUTE, '10.10.2.14', @ua_mac, 'SUCCESS');
INSERT INTO login_attempts (employee_id, user_id, ip_address, user_agent, timestamp, success, reason) VALUES
('EMP1002', @sneha, '10.10.2.14', @ua_mac, TIMESTAMP(@yesterday, '21:47:05'), 1, 'SUCCESS'),
('EMP1002', @sneha, '10.10.2.14', @ua_mac, NOW() - INTERVAL 360 MINUTE, 1, 'SUCCESS');
INSERT INTO risk_events (user_id, activity_id, rule_key, points, reason, score_before, score_after, created_at) VALUES
(@sneha, @s1, 'OFF_HOURS', 15, CONCAT('Login at 21:47 on ', DAYNAME(@yesterday), ' is outside working hours (09:00–19:00, Mon–Fri)'), 0, 15, TIMESTAMP(@yesterday, '21:47:05')),
(@sneha, @s2, 'SENSITIVE_ACCESS', 15, 'Viewed CONFIDENTIAL record record:HR-0003', 15, 30, NOW() - INTERVAL 350 MINUTE),
(@sneha, @s3, 'SENSITIVE_ACCESS', 15, 'Viewed CONFIDENTIAL record record:HR-0004', 30, 45, NOW() - INTERVAL 340 MINUTE);
INSERT INTO alerts (user_id, employee_id, activity_id, alert_type, severity, message, risk_score, timestamp, status, acknowledged_by, acknowledged_at, resolved_by, resolved_at, resolution_note) VALUES
(@sneha, 'EMP1002', @s1, 'OFF_HOURS', 'MEDIUM', CONCAT('Login at 21:47 on ', DAYNAME(@yesterday), ' is outside working hours (09:00–19:00, Mon–Fri)'), 15, TIMESTAMP(@yesterday, '21:47:05'), 'NEW', NULL, NULL, NULL, NULL, NULL),
(@sneha, 'EMP1002', @s2, 'SENSITIVE_ACCESS', 'MEDIUM', 'Viewed CONFIDENTIAL record record:HR-0003', 30, NOW() - INTERVAL 350 MINUTE, 'RESOLVED', @mgr, NOW() - INTERVAL 320 MINUTE, @mgr, NOW() - INTERVAL 300 MINUTE, 'Approved: annual compensation review requested by the HR head.'),
(@sneha, 'EMP1002', @s3, 'SENSITIVE_ACCESS', 'MEDIUM', 'Viewed CONFIDENTIAL record record:HR-0004', 45, NOW() - INTERVAL 340 MINUTE, 'ACKNOWLEDGED', @mgr, NOW() - INTERVAL 320 MINUTE, NULL, NULL, NULL);
SET @alert_sneha = (SELECT id FROM alerts WHERE activity_id = @s2);
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status) VALUES
(@mgr, 'MGR1001', 'manager', 'ACKNOWLEDGE_ALERT', CONCAT('alert:', (SELECT id FROM alerts WHERE activity_id = @s3)), 'Acknowledged MEDIUM alert ''Sensitive record accessed'' for EMP1002', NOW() - INTERVAL 320 MINUTE, '10.10.0.5', @ua_chrome, 'SUCCESS'),
(@mgr, 'MGR1001', 'manager', 'RESOLVE_ALERT', CONCAT('alert:', @alert_sneha), 'Resolved MEDIUM alert ''Sensitive record accessed'' for EMP1002 — note: Approved: annual compensation review requested by the HR head.', NOW() - INTERVAL 300 MINUTE, '10.10.0.5', @ua_chrome, 'SUCCESS');

-- =====================================================================
-- EMP1003 Arjun Verma (Engineering) — late-night search burst + bulk export, HIGH (70)
-- =====================================================================
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@arjun, 'EMP1003', 'employee', 'LOGIN', '/login', 'Signed in', TIMESTAMP(@yesterday, '23:05:12'), '10.10.3.33', @ua_edge, 'SUCCESS', 15,
 CONCAT('+15 Login at 23:05 on ', DAYNAME(@yesterday), ' is outside working hours (09:00–19:00, Mon–Fri)'));
SET @a1 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status) VALUES
(@arjun, 'EMP1003', 'employee', 'SEARCH', 'records', 'Searched "credentials" — 1 result(s)', TIMESTAMP(@yesterday, '23:06:01'), '10.10.3.33', @ua_edge, 'SUCCESS'),
(@arjun, 'EMP1003', 'employee', 'SEARCH', 'records', 'Searched "password" — 0 result(s)',    TIMESTAMP(@yesterday, '23:06:20'), '10.10.3.33', @ua_edge, 'SUCCESS'),
(@arjun, 'EMP1003', 'employee', 'SEARCH', 'records', 'Searched "salary" — 0 result(s)',      TIMESTAMP(@yesterday, '23:06:44'), '10.10.3.33', @ua_edge, 'SUCCESS'),
(@arjun, 'EMP1003', 'employee', 'SEARCH', 'records', 'Searched "customer" — 1 result(s)',    TIMESTAMP(@yesterday, '23:07:02'), '10.10.3.33', @ua_edge, 'SUCCESS'),
(@arjun, 'EMP1003', 'employee', 'SEARCH', 'records', 'Searched "export" — 0 result(s)',      TIMESTAMP(@yesterday, '23:07:25'), '10.10.3.33', @ua_edge, 'SUCCESS'),
(@arjun, 'EMP1003', 'employee', 'SEARCH', 'records', 'Searched "database" — 1 result(s)',    TIMESTAMP(@yesterday, '23:07:48'), '10.10.3.33', @ua_edge, 'SUCCESS'),
(@arjun, 'EMP1003', 'employee', 'SEARCH', 'records', 'Searched "backup" — 0 result(s)',      TIMESTAMP(@yesterday, '23:08:05'), '10.10.3.33', @ua_edge, 'SUCCESS'),
(@arjun, 'EMP1003', 'employee', 'SEARCH', 'records', 'Searched "contract" — 0 result(s)',    TIMESTAMP(@yesterday, '23:08:31'), '10.10.3.33', @ua_edge, 'SUCCESS'),
(@arjun, 'EMP1003', 'employee', 'SEARCH', 'records', 'Searched "keys" — 0 result(s)',        TIMESTAMP(@yesterday, '23:08:52'), '10.10.3.33', @ua_edge, 'SUCCESS');
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@arjun, 'EMP1003', 'employee', 'SEARCH', 'records', 'Searched "prod" — 1 result(s)', TIMESTAMP(@yesterday, '23:09:10'), '10.10.3.33', @ua_edge, 'SUCCESS', 10, '+10 10 searches within 5 minutes');
SET @a2 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, record_count, timestamp, ip_address, user_agent, status) VALUES
(@arjun, 'EMP1003', 'employee', 'VIEW_RECORD', 'record:ENG-0002', 'Viewed INTERNAL record ''Release Checklist v4''', 1, TIMESTAMP(@yesterday, '23:10:02'), '10.10.3.33', @ua_edge, 'SUCCESS'),
(@arjun, 'EMP1003', 'employee', 'VIEW_RECORD', 'record:ENG-0004', 'Viewed INTERNAL record ''API Rate Limit Design''', 1, TIMESTAMP(@yesterday, '23:10:25'), '10.10.3.33', @ua_edge, 'SUCCESS'),
(@arjun, 'EMP1003', 'employee', 'VIEW_RECORD', 'record:ENG-0006', 'Viewed INTERNAL record ''Incident Postmortem — 14 Aug outage''', 1, TIMESTAMP(@yesterday, '23:10:51'), '10.10.3.33', @ua_edge, 'SUCCESS');
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, record_count, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@arjun, 'EMP1003', 'employee', 'EXPORT_DATA', 'records.csv', 'Exported 14 record(s) for search ""', 14, TIMESTAMP(@yesterday, '23:11:30'), '10.10.3.33', @ua_edge, 'SUCCESS', 45,
 '+20 Accessed 17 records within 5 minutes; +25 3 suspicious events within 10 minutes');
SET @a3 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status) VALUES
(@arjun, 'EMP1003', 'employee', 'LOGOUT', '/logout', 'Signed out', TIMESTAMP(@yesterday, '23:20:40'), '10.10.3.33', @ua_edge, 'SUCCESS');
INSERT INTO login_attempts (employee_id, user_id, ip_address, user_agent, timestamp, success, reason) VALUES
('EMP1003', @arjun, '10.10.3.33', @ua_edge, TIMESTAMP(@yesterday, '23:05:12'), 1, 'SUCCESS');
INSERT INTO risk_events (user_id, activity_id, rule_key, points, reason, score_before, score_after, created_at) VALUES
(@arjun, @a1, 'OFF_HOURS', 15, CONCAT('Login at 23:05 on ', DAYNAME(@yesterday), ' is outside working hours (09:00–19:00, Mon–Fri)'), 0, 15, TIMESTAMP(@yesterday, '23:05:12')),
(@arjun, @a2, 'REPEATED_SEARCH', 10, '10 searches within 5 minutes', 15, 25, TIMESTAMP(@yesterday, '23:09:10')),
(@arjun, @a3, 'MASS_RECORD_ACCESS', 20, 'Accessed 17 records within 5 minutes', 25, 45, TIMESTAMP(@yesterday, '23:11:30')),
(@arjun, @a3, 'SUSPICIOUS_BURST', 25, '3 suspicious events within 10 minutes', 45, 70, TIMESTAMP(@yesterday, '23:11:30'));
INSERT INTO alerts (user_id, employee_id, activity_id, alert_type, severity, message, risk_score, timestamp, status, acknowledged_by, acknowledged_at) VALUES
(@arjun, 'EMP1003', @a1, 'OFF_HOURS', 'MEDIUM', CONCAT('Login at 23:05 on ', DAYNAME(@yesterday), ' is outside working hours (09:00–19:00, Mon–Fri)'), 15, TIMESTAMP(@yesterday, '23:05:12'), 'ACKNOWLEDGED', @mgr, NOW() - INTERVAL 410 MINUTE),
(@arjun, 'EMP1003', @a2, 'REPEATED_SEARCH', 'LOW', '10 searches within 5 minutes', 25, TIMESTAMP(@yesterday, '23:09:10'), 'NEW', NULL, NULL),
(@arjun, 'EMP1003', @a3, 'MASS_RECORD_ACCESS', 'HIGH', 'Accessed 17 records within 5 minutes', 70, TIMESTAMP(@yesterday, '23:11:30'), 'NEW', NULL, NULL),
(@arjun, 'EMP1003', @a3, 'SUSPICIOUS_BURST', 'HIGH', '3 suspicious events within 10 minutes', 70, TIMESTAMP(@yesterday, '23:11:30'), 'NEW', NULL, NULL),
(@arjun, 'EMP1003', @a3, 'RISK_LEVEL_ESCALATION', 'HIGH', 'Risk level rose from MEDIUM to HIGH (score 70). Latest: 3 suspicious events within 10 minutes', 70, TIMESTAMP(@yesterday, '23:11:30'), 'NEW', NULL, NULL);
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status) VALUES
(@mgr, 'MGR1001', 'manager', 'ACKNOWLEDGE_ALERT', CONCAT('alert:', (SELECT id FROM alerts WHERE activity_id = @a1 AND alert_type = 'OFF_HOURS')),
 'Acknowledged MEDIUM alert ''Access outside working hours'' for EMP1003', NOW() - INTERVAL 410 MINUTE, '10.10.0.5', @ua_chrome, 'SUCCESS');

-- =====================================================================
-- EMP1004 Kavya Nair (Sales) — restricted record + manager page probing, CRITICAL (95)
-- =====================================================================
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@kavya, 'EMP1004', 'employee', 'FAILED_LOGIN', '/login', 'Incorrect password', NOW() - INTERVAL 185 MINUTE, '10.10.4.18', @ua_chrome, 'FAILED', 10, '+10 Failed login for EMP1004 (invalid password)');
SET @k1 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status) VALUES
(@kavya, 'EMP1004', 'employee', 'LOGIN', '/login', 'Signed in', NOW() - INTERVAL 183 MINUTE, '10.10.4.18', @ua_chrome, 'SUCCESS'),
(@kavya, 'EMP1004', 'employee', 'SEARCH', 'records', 'Searched "account" — 1 result(s)', NOW() - INTERVAL 125 MINUTE, '10.10.4.18', @ua_chrome, 'SUCCESS');
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, record_count, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@kavya, 'EMP1004', 'employee', 'VIEW_RECORD', 'record:SAL-0002', 'Viewed CONFIDENTIAL record ''Key Account List — West Region''', 1, NOW() - INTERVAL 120 MINUTE, '10.10.4.18', @ua_chrome, 'SUCCESS', 15,
 '+15 Viewed CONFIDENTIAL record record:SAL-0002');
SET @k2 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@kavya, 'EMP1004', 'employee', 'UNAUTHORIZED_ACCESS', 'record:FIN-0010', 'Denied open: FIN-0010 is a RESTRICTED record', NOW() - INTERVAL 90 MINUTE, '10.10.4.18', @ua_chrome, 'DENIED', 30,
 '+30 Attempted to access record:FIN-0010 without permission');
SET @k3 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@kavya, 'EMP1004', 'employee', 'UNAUTHORIZED_ACCESS', '/manager/employees', 'Blocked GET to manager-only resource', NOW() - INTERVAL 75 MINUTE, '10.10.4.18', @ua_chrome, 'DENIED', 40,
 '+30 Attempted to access /manager/employees without permission; +10 Employee tried to open manager-only resource /manager/employees');
SET @k4 = LAST_INSERT_ID();
INSERT INTO login_attempts (employee_id, user_id, ip_address, user_agent, timestamp, success, reason) VALUES
('EMP1004', @kavya, '10.10.4.18', @ua_chrome, NOW() - INTERVAL 185 MINUTE, 0, 'INVALID_PASSWORD'),
('EMP1004', @kavya, '10.10.4.18', @ua_chrome, NOW() - INTERVAL 183 MINUTE, 1, 'SUCCESS');
INSERT INTO risk_events (user_id, activity_id, rule_key, points, reason, score_before, score_after, created_at) VALUES
(@kavya, @k1, 'FAILED_LOGIN', 10, 'Failed login for EMP1004 (invalid password)', 0, 10, NOW() - INTERVAL 185 MINUTE),
(@kavya, @k2, 'SENSITIVE_ACCESS', 15, 'Viewed CONFIDENTIAL record record:SAL-0002', 10, 25, NOW() - INTERVAL 120 MINUTE),
(@kavya, @k3, 'UNAUTHORIZED_ACCESS', 30, 'Attempted to access record:FIN-0010 without permission', 25, 55, NOW() - INTERVAL 90 MINUTE),
(@kavya, @k4, 'UNAUTHORIZED_ACCESS', 30, 'Attempted to access /manager/employees without permission', 55, 85, NOW() - INTERVAL 75 MINUTE),
(@kavya, @k4, 'PRIVILEGE_ESCALATION', 10, 'Employee tried to open manager-only resource /manager/employees', 85, 95, NOW() - INTERVAL 75 MINUTE);
INSERT INTO alerts (user_id, employee_id, activity_id, alert_type, severity, message, risk_score, timestamp, status) VALUES
(@kavya, 'EMP1004', @k2, 'SENSITIVE_ACCESS', 'MEDIUM', 'Viewed CONFIDENTIAL record record:SAL-0002', 25, NOW() - INTERVAL 120 MINUTE, 'NEW'),
(@kavya, 'EMP1004', @k3, 'UNAUTHORIZED_ACCESS', 'HIGH', 'Attempted to access record:FIN-0010 without permission', 55, NOW() - INTERVAL 90 MINUTE, 'NEW'),
(@kavya, 'EMP1004', @k4, 'UNAUTHORIZED_ACCESS', 'HIGH', 'Attempted to access /manager/employees without permission', 95, NOW() - INTERVAL 75 MINUTE, 'NEW'),
(@kavya, 'EMP1004', @k4, 'PRIVILEGE_ESCALATION', 'HIGH', 'Employee tried to open manager-only resource /manager/employees', 95, NOW() - INTERVAL 75 MINUTE, 'NEW'),
(@kavya, 'EMP1004', @k4, 'RISK_LEVEL_ESCALATION', 'CRITICAL', 'Risk level rose from MEDIUM to CRITICAL (score 95). Latest: Employee tried to open manager-only resource /manager/employees', 95, NOW() - INTERVAL 75 MINUTE, 'NEW');

-- =====================================================================
-- EMP1005 Vikram Singh (Legal) — two mistyped passwords, LOW (20)
-- =====================================================================
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@vikram, 'EMP1005', 'employee', 'FAILED_LOGIN', '/login', 'Incorrect password', NOW() - INTERVAL 140 MINUTE, '10.10.5.9', @ua_edge, 'FAILED', 10, '+10 Failed login for EMP1005 (invalid password)');
SET @v1 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@vikram, 'EMP1005', 'employee', 'FAILED_LOGIN', '/login', 'Incorrect password', NOW() - INTERVAL 139 MINUTE, '10.10.5.9', @ua_edge, 'FAILED', 10, '+10 Failed login for EMP1005 (invalid password)');
SET @v2 = LAST_INSERT_ID();
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, record_count, timestamp, ip_address, user_agent, status) VALUES
(@vikram, 'EMP1005', 'employee', 'LOGIN',       '/login',          'Signed in', 0, NOW() - INTERVAL 138 MINUTE, '10.10.5.9', @ua_edge, 'SUCCESS'),
(@vikram, 'EMP1005', 'employee', 'SEARCH',      'records',         'Searched "NDA" — 1 result(s)', 0, NOW() - INTERVAL 130 MINUTE, '10.10.5.9', @ua_edge, 'SUCCESS'),
(@vikram, 'EMP1005', 'employee', 'VIEW_RECORD', 'record:LEG-0001', 'Viewed INTERNAL record ''NDA Template''', 1, NOW() - INTERVAL 129 MINUTE, '10.10.5.9', @ua_edge, 'SUCCESS'),
(@vikram, 'EMP1005', 'employee', 'VIEW_RECORD', 'record:LEG-0003', 'Viewed INTERNAL record ''Compliance Calendar 2026''', 1, NOW() - INTERVAL 100 MINUTE, '10.10.5.9', @ua_edge, 'SUCCESS'),
(@vikram, 'EMP1005', 'employee', 'LOGOUT',      '/logout',         'Signed out', 0, NOW() - INTERVAL 60 MINUTE, '10.10.5.9', @ua_edge, 'SUCCESS');
INSERT INTO login_attempts (employee_id, user_id, ip_address, user_agent, timestamp, success, reason) VALUES
('EMP1005', @vikram, '10.10.5.9', @ua_edge, NOW() - INTERVAL 140 MINUTE, 0, 'INVALID_PASSWORD'),
('EMP1005', @vikram, '10.10.5.9', @ua_edge, NOW() - INTERVAL 139 MINUTE, 0, 'INVALID_PASSWORD'),
('EMP1005', @vikram, '10.10.5.9', @ua_edge, NOW() - INTERVAL 138 MINUTE, 1, 'SUCCESS');
INSERT INTO risk_events (user_id, activity_id, rule_key, points, reason, score_before, score_after, created_at) VALUES
(@vikram, @v1, 'FAILED_LOGIN', 10, 'Failed login for EMP1005 (invalid password)', 0, 10, NOW() - INTERVAL 140 MINUTE),
(@vikram, @v2, 'FAILED_LOGIN', 10, 'Failed login for EMP1005 (invalid password)', 10, 20, NOW() - INTERVAL 139 MINUTE);

-- =====================================================================
-- EMP1000 Rohan Das (disabled) — tried to log in after leaving
-- =====================================================================
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(@rohan, 'EMP1000', 'employee', 'FAILED_LOGIN', '/login', 'Login attempt on a disabled account', NOW() - INTERVAL 240 MINUTE, '49.36.120.7', @ua_chrome, 'FAILED', 10, '+10 Failed login for EMP1000 (account disabled)');
SET @r1 = LAST_INSERT_ID();
INSERT INTO login_attempts (employee_id, user_id, ip_address, user_agent, timestamp, success, reason) VALUES
('EMP1000', @rohan, '49.36.120.7', @ua_chrome, NOW() - INTERVAL 240 MINUTE, 0, 'ACCOUNT_DISABLED');
INSERT INTO risk_events (user_id, activity_id, rule_key, points, reason, score_before, score_after, created_at) VALUES
(@rohan, @r1, 'FAILED_LOGIN', 10, 'Failed login for EMP1000 (account disabled)', 0, 10, NOW() - INTERVAL 240 MINUTE);

-- =====================================================================
-- Unknown ID EMP9999 — scripted password guessing from an external IP
-- =====================================================================
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(NULL, 'EMP9999', NULL, 'FAILED_LOGIN', '/login', 'Login with unknown employee ID', NOW() - INTERVAL 50 MINUTE, '185.220.101.4', @ua_script, 'FAILED', 10, '+10 Failed login for EMP9999 (unknown employee id)'),
(NULL, 'EMP9999', NULL, 'FAILED_LOGIN', '/login', 'Login with unknown employee ID', NOW() - INTERVAL 49 MINUTE, '185.220.101.4', @ua_script, 'FAILED', 10, '+10 Failed login for EMP9999 (unknown employee id)');
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status, risk_score, risk_reason) VALUES
(NULL, 'EMP9999', NULL, 'FAILED_LOGIN', '/login', 'Login with unknown employee ID', NOW() - INTERVAL 48 MINUTE, '185.220.101.4', @ua_script, 'FAILED', 30,
 '+10 Failed login for EMP9999 (unknown employee id); +20 3 failed login attempts for EMP9999 within 10 minutes');
SET @u3 = LAST_INSERT_ID();
INSERT INTO login_attempts (employee_id, user_id, ip_address, user_agent, timestamp, success, reason) VALUES
('EMP9999', NULL, '185.220.101.4', @ua_script, NOW() - INTERVAL 50 MINUTE, 0, 'UNKNOWN_EMPLOYEE_ID'),
('EMP9999', NULL, '185.220.101.4', @ua_script, NOW() - INTERVAL 49 MINUTE, 0, 'UNKNOWN_EMPLOYEE_ID'),
('EMP9999', NULL, '185.220.101.4', @ua_script, NOW() - INTERVAL 48 MINUTE, 0, 'UNKNOWN_EMPLOYEE_ID');
INSERT INTO alerts (user_id, employee_id, activity_id, alert_type, severity, message, risk_score, timestamp, status, acknowledged_by, acknowledged_at) VALUES
(NULL, 'EMP9999', @u3, 'REPEATED_FAILED_LOGIN', 'HIGH', '3 failed login attempts for EMP9999 within 10 minutes', 30, NOW() - INTERVAL 48 MINUTE, 'ACKNOWLEDGED', @mgr, NOW() - INTERVAL 40 MINUTE);
INSERT INTO activity_logs (user_id, employee_id, actor_role, action, resource, description, timestamp, ip_address, user_agent, status) VALUES
(@mgr, 'MGR1001', 'manager', 'ACKNOWLEDGE_ALERT', CONCAT('alert:', (SELECT id FROM alerts WHERE activity_id = @u3)),
 'Acknowledged HIGH alert ''Multiple failed login attempts'' for EMP9999', NOW() - INTERVAL 40 MINUTE, '10.10.0.5', @ua_chrome, 'SUCCESS');
