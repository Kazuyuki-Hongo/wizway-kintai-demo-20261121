-- ダミー勤怠デモ用。本番 MariaDB には繋がない。
-- departments / leave_* は SQL 演習用。画面・API からは読まない。

CREATE TABLE departments (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  parent_id INTEGER REFERENCES departments (id)
);

CREATE TABLE employees (
  id INTEGER PRIMARY KEY,
  display_name TEXT NOT NULL,
  password_hash TEXT,
  password_salt TEXT,
  is_admin INTEGER NOT NULL DEFAULT 0,
  department_id INTEGER REFERENCES departments (id)
);

CREATE TABLE sessions (
  token TEXT PRIMARY KEY,
  employee_id INTEGER NOT NULL REFERENCES employees (id),
  expires_at TEXT NOT NULL
);

CREATE TABLE attendance_rows (
  id INTEGER PRIMARY KEY,
  employee_id INTEGER NOT NULL REFERENCES employees (id),
  work_date TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('通常出勤', '半休', '有休', '欠勤')),
  clock_in TEXT,
  clock_out TEXT,
  break_time TEXT,
  note TEXT,
  UNIQUE (employee_id, work_date)
);

CREATE TABLE attendance_edits (
  id INTEGER PRIMARY KEY,
  edited_at TEXT NOT NULL,
  editor_employee_id INTEGER NOT NULL REFERENCES employees (id),
  target_employee_id INTEGER NOT NULL REFERENCES employees (id),
  work_date TEXT NOT NULL,
  before_category TEXT,
  before_clock_in TEXT,
  before_clock_out TEXT,
  before_break_time TEXT,
  before_note TEXT,
  after_category TEXT,
  after_clock_in TEXT,
  after_clock_out TEXT,
  after_break_time TEXT,
  after_note TEXT
);

CREATE TABLE leave_requests (
  id INTEGER PRIMARY KEY,
  employee_id INTEGER NOT NULL REFERENCES employees (id),
  leave_type TEXT NOT NULL CHECK (leave_type IN ('有休', '半休', '欠勤届')),
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft', 'submitted', 'approved', 'rejected')),
  requested_at TEXT NOT NULL
);

CREATE TABLE leave_approvals (
  id INTEGER PRIMARY KEY,
  leave_request_id INTEGER NOT NULL REFERENCES leave_requests (id),
  approver_employee_id INTEGER NOT NULL REFERENCES employees (id),
  decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
  decided_at TEXT NOT NULL,
  comment TEXT
);
