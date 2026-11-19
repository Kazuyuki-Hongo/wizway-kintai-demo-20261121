"""勤怠デモ API。実働の合計は sql/ の SELECT。Python で同じ式を持ち直さない。"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,PUT,POST,OPTIONS",
}

YM_RE = re.compile(r"^\d{4}-\d{2}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^(\d{2}):(\d{2})$")
EMPLOYEES_PATH = re.compile(r"^/employees/?$")
DAY_PATH = re.compile(r"^/employees/([^/]+)/months/(.+?)/days/([^/]+)/?$")
# ym に 2026/11 のような不正値が来ても1セグメントとして扱う（summary を先に判定）
MONTH_PATH = re.compile(r"^/employees/([^/]+)/months/(.+?)/?$")
SUMMARY_PATH = re.compile(r"^/employees/([^/]+)/months/(.+?)/summary/?$")
OVERVIEW_PATH = re.compile(r"^/months/(.+)/overview/?$")
EXPORT_PATH = re.compile(r"^/months/(.+)/export/?$")
LOGIN_PATH = re.compile(r"^/login/?$")
LOGOUT_PATH = re.compile(r"^/logout/?$")
DEMO_ERROR_PATH = re.compile(r"^/demo/error/?$")
DEMO_UNIMPLEMENTED_PATH = re.compile(r"^/demo/unimplemented/?$")
_MARKER_UNSAFE = re.compile(r"[^\w\-]")

DEMO_PASSWORDS = {
    "テスト青空": "aozora",
    "サンプル海原": "unahara",
    "見本山辺": "yamabe",
    "デモ管理": "kanri",
}
DEMO_SALTS = {
    "テスト青空": "kintai-demo-salt-1",
    "サンプル海原": "kintai-demo-salt-2",
    "見本山辺": "kintai-demo-salt-3",
    "デモ管理": "kintai-demo-salt-admin",
}
PBKDF2_ROUNDS = 10_000
SESSION_HOURS = 8
LOGIN_REJECT = {"error": "rejected", "reason": "社員名かパスワードが違います"}
LOGIN_REQUIRED = {"error": "unauthorized", "reason": "ログインしてください"}
ADMIN_ONLY = {"error": "forbidden", "reason": "全員の勤怠は管理者だけが見られます"}

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
SEED_PATH = Path(__file__).resolve().parent / "data" / "attendance.db"
_LOCAL_RUNTIME: Path | None = None

UPDATE_FIELDS = ("category", "clock_in", "clock_out", "break_time", "note")
TIMED_CATEGORIES = ("通常出勤", "半休")
EMPTY_CATEGORIES = ("欠勤", "有休")
ALLOWED_CATEGORIES = TIMED_CATEGORIES + EMPTY_CATEGORIES

ROWS_DDL = """
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
)
"""

SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  employee_id INTEGER NOT NULL REFERENCES employees (id),
  expires_at TEXT NOT NULL
)
"""

EDITS_DDL = """
CREATE TABLE IF NOT EXISTS attendance_edits (
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
)
"""


class DemoError(Exception):
    """演習用。CloudWatch に traceback を残すために、ハンドラの外まではキャッチしない。"""


def _marker(event) -> str:
    params = event.get("queryStringParameters") or {}
    raw = str(params.get("marker") or "")
    cleaned = _MARKER_UNSAFE.sub("", raw)[:40]
    return cleaned or "demo"


def _raise_demo_error(event) -> None:
    marker = _marker(event)
    print(f"demo-error marker={marker} path=/demo/error")
    raise DemoError(f"演習用の未処理エラーです marker={marker}")


def _response(status_code: int, body: dict | list | None = None):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": "" if body is None else json.dumps(body, ensure_ascii=False),
    }


def _path(event) -> str:
    raw = event.get("rawPath") or event.get("path") or ""
    if raw.startswith("/prod/"):
        raw = raw[len("/prod") :]
    elif raw == "/prod":
        raw = "/"
    return raw


def _method(event) -> str:
    rc = event.get("requestContext") or {}
    http = rc.get("http") or {}
    return (http.get("method") or event.get("httpMethod") or "GET").upper()


_S3_CLIENT = None
_SHARED_ETAG: str | None = None
_SHARED_DB_PATH = Path("/tmp/attendance.db")


def _new_s3_client():
    import boto3

    return boto3.client("s3")


def _shared_db_path() -> Path:
    return _SHARED_DB_PATH


def _remember_etag(etag: str | None) -> None:
    global _SHARED_ETAG
    _SHARED_ETAG = etag


def _not_modified(exc: Exception) -> bool:
    response = getattr(exc, "response", None) or {}
    code = str((response.get("Error") or {}).get("Code", ""))
    status = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    return code in {"304", "NotModified"} or status == 304


def _store_head_etag(client, bucket: str, key: str) -> None:
    try:
        head = client.head_object(Bucket=bucket, Key=key)
    except Exception:
        _remember_etag(None)
        return
    _remember_etag(head.get("ETag"))


def _s3():
    global _S3_CLIENT
    if _S3_CLIENT is None:
        _S3_CLIENT = _new_s3_client()
    return _S3_CLIENT


def _missing_object(exc: Exception) -> bool:
    response = getattr(exc, "response", None) or {}
    code = str((response.get("Error") or {}).get("Code", ""))
    return code in {"404", "NoSuchKey", "NotFound"}


def _prepare_shared_db(bucket: str, key: str) -> Path:
    """共有ファイルを /tmp に取り込む。変わっていないときは中身を取らない。"""
    path = _shared_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    client = _s3()
    kwargs: dict = {"Bucket": bucket, "Key": key}
    if _SHARED_ETAG and path.is_file():
        kwargs["IfNoneMatch"] = _SHARED_ETAG
    try:
        obj = client.get_object(**kwargs)
    except Exception as exc:
        if _not_modified(exc) and path.is_file():
            return path
        if not _missing_object(exc):
            raise
        shutil.copyfile(SEED_PATH, path)
        client.upload_file(str(path), bucket, key)
        _store_head_etag(client, bucket, key)
        return path
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(obj["Body"].read())
    os.replace(partial, path)
    _remember_etag(obj.get("ETag"))
    return path


def _publish_shared_db() -> None:
    if os.environ.get("KINTAI_RUNTIME_DB"):
        return
    bucket = os.environ.get("KINTAI_DB_BUCKET")
    if not bucket:
        return
    key = os.environ.get("KINTAI_DB_KEY") or "attendance.db"
    client = _s3()
    try:
        client.upload_file(str(_shared_db_path()), bucket, key)
    except Exception:
        _remember_etag(None)
        raise
    _store_head_etag(client, bucket, key)


def _runtime_db_path() -> Path:
    """初期データファイル自体は更新しない。"""
    override = os.environ.get("KINTAI_RUNTIME_DB")
    if override:
        path = Path(override)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SEED_PATH, path)
        return path

    bucket = os.environ.get("KINTAI_DB_BUCKET")
    if bucket:
        key = os.environ.get("KINTAI_DB_KEY") or "attendance.db"
        return _prepare_shared_db(bucket, key)

    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        path = Path("/tmp/attendance.db")
        if not path.exists():
            shutil.copyfile(SEED_PATH, path)
        return path

    global _LOCAL_RUNTIME
    if _LOCAL_RUNTIME is None:
        fd, name = tempfile.mkstemp(prefix="kintai-", suffix=".db")
        os.close(fd)
        shutil.copyfile(SEED_PATH, name)
        _LOCAL_RUNTIME = Path(name)
    return _LOCAL_RUNTIME


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def _password_hash(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ROUNDS,
    )
    return f"{PBKDF2_ROUNDS}${digest.hex()}"


def _fill_password_hashes(conn: sqlite3.Connection) -> None:
    for name, password in DEMO_PASSWORDS.items():
        salt = DEMO_SALTS[name]
        expected = _password_hash(password, salt)
        conn.execute(
            """
            UPDATE employees
            SET password_hash = ?, password_salt = ?
            WHERE display_name = ?
              AND (
                password_hash IS NULL
                OR password_hash = ''
                OR password_hash != ?
              )
            """,
            (expected, salt, name, expected),
        )


def _ensure_login_schema(conn: sqlite3.Connection) -> None:
    """勤怠行を残したまま、パスワード列とセッション表を足す。"""
    conn.execute(SESSIONS_DDL)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(employees)")
    }
    if "password_hash" not in columns:
        conn.execute("ALTER TABLE employees ADD COLUMN password_hash TEXT")
    if "password_salt" not in columns:
        conn.execute("ALTER TABLE employees ADD COLUMN password_salt TEXT")
    _ensure_admin(conn)


def _ensure_admin(conn: sqlite3.Connection) -> None:
    """勤怠行を残したまま、管理者を1人足す。"""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(employees)")}
    if "is_admin" not in columns:
        conn.execute(
            "ALTER TABLE employees ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
        )
    conn.execute(
        """
        INSERT INTO employees (id, display_name, is_admin)
        SELECT 4, 'デモ管理', 1
        WHERE NOT EXISTS (
          SELECT 1 FROM employees WHERE display_name = 'デモ管理'
        )
        """
    )
    _fill_password_hashes(conn)


def _ensure_note_columns(conn: sqlite3.Connection) -> None:
    """既存 DB に備考列が無ければ足す。"""
    names = _table_names(conn)
    if "attendance_rows" in names:
        row_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(attendance_rows)")
        }
        if "note" not in row_columns:
            conn.execute("ALTER TABLE attendance_rows ADD COLUMN note TEXT")
    if "attendance_edits" in names:
        edit_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(attendance_edits)")
        }
        if "before_note" not in edit_columns:
            conn.execute("ALTER TABLE attendance_edits ADD COLUMN before_note TEXT")
        if "after_note" not in edit_columns:
            conn.execute("ALTER TABLE attendance_edits ADD COLUMN after_note TEXT")


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """古い区分制約のファイルでも、行を残したまま半休と有休を許す。"""
    _ensure_login_schema(conn)
    conn.execute(EDITS_DDL)
    names = _table_names(conn)
    if "attendance_rows" in names:
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'attendance_rows'"
        ).fetchone()[0]
        if "半休" in ddl and "有休" in ddl:
            if "attendance_rows_old" in names:
                conn.execute("DROP TABLE attendance_rows_old")
            _ensure_note_columns(conn)
            return
        conn.execute("ALTER TABLE attendance_rows RENAME TO attendance_rows_old")
    elif "attendance_rows_old" not in names:
        _ensure_note_columns(conn)
        return
    old_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(attendance_rows_old)")
    }
    conn.execute(ROWS_DDL)
    if "note" in old_columns:
        conn.execute(
            """
            INSERT INTO attendance_rows (
              id, employee_id, work_date, category, clock_in, clock_out, break_time, note
            )
            SELECT id, employee_id, work_date, category, clock_in, clock_out, break_time, note
            FROM attendance_rows_old
            """
        )
    else:
        conn.execute(
            """
            INSERT INTO attendance_rows (
              id, employee_id, work_date, category, clock_in, clock_out, break_time
            )
            SELECT id, employee_id, work_date, category, clock_in, clock_out, break_time
            FROM attendance_rows_old
            """
        )
    conn.execute("DROP TABLE attendance_rows_old")
    _ensure_note_columns(conn)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_runtime_db_path())
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _load_sql(name: str) -> str:
    local = Path(__file__).resolve().parent / "sql" / name
    path = local if local.exists() else SQL_DIR / name
    return path.read_text(encoding="utf-8")


def _parse_employee_id(raw: str) -> int | None:
    try:
        return int(raw)
    except ValueError:
        return None


def _invalid_ym(ym: str) -> bool:
    if YM_RE.match(ym) is None:
        return True
    month = int(ym[5:7])
    return month < 1 or month > 12


def _log_invalid_ym(ym: str) -> None:
    print(f"invalid ym={ym!r} reason=expected YYYY-MM with month 01-12")


def _employee_exists(conn: sqlite3.Connection, employee_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 AS ok FROM employees WHERE id = ?", (employee_id,)
    ).fetchone()
    return row is not None


def _list_employees(conn: sqlite3.Connection, actor) -> list[dict]:
    if actor["is_admin"]:
        rows = conn.execute(
            """
            SELECT id, display_name FROM employees
            WHERE is_admin = 0
            ORDER BY id
            """
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, display_name FROM employees WHERE id = ? ORDER BY id",
            (int(actor["id"]),),
        ).fetchall()
    return [{"id": r["id"], "display_name": r["display_name"]} for r in rows]


def _workers(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, display_name FROM employees
        WHERE is_admin = 0
        ORDER BY id
        """
    ).fetchall()
    return [{"id": r["id"], "display_name": r["display_name"]} for r in rows]


def _month_rows(conn: sqlite3.Connection, employee_id: int, ym: str) -> list[dict]:
    sql = _load_sql("month_rows.sql")
    rows = conn.execute(sql, {"employee_id": employee_id, "ym": ym}).fetchall()
    return [
        {
            "work_date": r["work_date"],
            "category": r["category"],
            "clock_in": r["clock_in"],
            "clock_out": r["clock_out"],
            "break_time": r["break_time"],
            "note": r["note"],
            "stored": bool(r["stored"]),
        }
        for r in rows
    ]


def _month_summary(conn: sqlite3.Connection, employee_id: int, ym: str) -> dict:
    sql = _load_sql("month_summary.sql")
    row = conn.execute(sql, {"employee_id": employee_id, "ym": ym}).fetchone()
    return {
        "workday_count": int(row["workday_count"]),
        "total_worked_hours": float(row["total_worked_hours"]),
        "overtime_hours": float(row["overtime_hours"]),
        "missing_clock_out_count": int(row["missing_clock_out_count"]),
    }


def _read_month(employee_id: int | None, ym: str, summary: bool, event):
    if employee_id is None:
        return _response(404, {"error": "employee not found"})
    if _invalid_ym(ym):
        _log_invalid_ym(ym)
        return _response(400, {"error": "invalid ym", "reason": "年月は 2026-11 のように入れてください"})
    with _connect() as conn:
        actor = _session_actor(conn, _bearer(event) or "")
        if actor is None:
            return _response(401, LOGIN_REQUIRED)
        if int(actor["id"]) != employee_id and not actor["is_admin"]:
            return _response(403, ADMIN_ONLY)
        if not _employee_exists(conn, employee_id):
            return _response(404, {"error": "employee not found"})
        if summary:
            return _response(
                200,
                {
                    "employee_id": employee_id,
                    "ym": ym,
                    "summary": _month_summary(conn, employee_id, ym),
                },
            )
        return _response(
            200,
            {
                "employee_id": employee_id,
                "ym": ym,
                "rows": _month_rows(conn, employee_id, ym),
                "edits": _month_edits(conn, employee_id, ym),
            },
        )


def _csv_response(text: str, filename: str):
    headers = dict(CORS_HEADERS)
    headers["Content-Type"] = "text/csv; charset=utf-8"
    headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return {"statusCode": 200, "headers": headers, "body": text}


def _read_export(ym: str, event):
    if _invalid_ym(ym):
        _log_invalid_ym(ym)
        return _response(400, {"error": "invalid ym", "reason": "年月は 2026-11 のように入れてください"})
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["社員名", "日付", "区分", "出勤", "退勤", "休憩"])
    with _connect() as conn:
        actor = _session_actor(conn, _bearer(event) or "")
        if actor is None or not actor["is_admin"]:
            return _response(403, ADMIN_ONLY)
        for emp in _workers(conn):
            for row in _month_rows(conn, emp["id"], ym):
                writer.writerow(
                    [
                        emp["display_name"],
                        row["work_date"],
                        row["category"],
                        row["clock_in"],
                        row["clock_out"],
                        row["break_time"],
                    ]
                )
    return _csv_response("\ufeff" + buffer.getvalue(), f"kintai-{ym}.csv")


def _read_overview(ym: str, event):
    if _invalid_ym(ym):
        _log_invalid_ym(ym)
        return _response(400, {"error": "invalid ym", "reason": "年月は 2026-11 のように入れてください"})
    with _connect() as conn:
        actor = _session_actor(conn, _bearer(event) or "")
        if actor is None or not actor["is_admin"]:
            return _response(403, ADMIN_ONLY)
        employees = [
            {
                "id": emp["id"],
                "display_name": emp["display_name"],
                "summary": _month_summary(conn, emp["id"], ym),
            }
            for emp in _workers(conn)
        ]
    return _response(200, {"ym": ym, "employees": employees})


def _event_body(event) -> dict | None:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded") and raw:
        import base64

        raw = base64.b64decode(raw).decode("utf-8")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _minutes(value: str) -> int | None:
    match = TIME_RE.fullmatch(value)
    if match is None:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def _reject(reason: str):
    print(f"reject update reason={reason}")
    return _response(400, {"error": "rejected", "reason": reason})


def _validate_fields(fields: dict[str, str]) -> str | None:
    category = fields["category"]
    clock_in = fields["clock_in"]
    clock_out = fields["clock_out"]
    break_time = fields["break_time"]
    if category not in ALLOWED_CATEGORIES:
        return "区分は通常出勤、半休、有休、欠勤のいずれかにしてください"
    if category in EMPTY_CATEGORIES:
        if clock_in or clock_out or break_time:
            return f"{category}のときは、出勤・退勤・休憩を空にしてください"
        return None
    if not clock_in:
        return f"{category}のときは、出勤を入れてください"
    in_minutes = _minutes(clock_in)
    if in_minutes is None:
        return "時刻は 09:00 のように、00:00 から 23:59 までで入れてください"
    if clock_out == "":
        if break_time and _minutes(break_time) is None:
            return "時刻は 09:00 のように、00:00 から 23:59 までで入れてください"
        return None
    out_minutes = _minutes(clock_out)
    if out_minutes is None:
        return "時刻は 09:00 のように、00:00 から 23:59 までで入れてください"
    if out_minutes < in_minutes:
        return "退勤は出勤より前にはできません"
    if break_time == "":
        return "退勤を入れるときは、休憩も入れてください。1時間なら 01:00 です"
    break_minutes = _minutes(break_time)
    if break_minutes is None:
        return "時刻は 09:00 のように、00:00 から 23:59 までで入れてください"
    if break_minutes > out_minutes - in_minutes:
        return "休憩は時刻ではなく長さです。出勤から退勤までより長くできません。1時間なら 01:00 です"
    return None


def _blank_to_null(value: str) -> str | None:
    return value if value else None


def _date_in_month(ym: str, work_date: str) -> bool:
    if DATE_RE.fullmatch(work_date) is None or not work_date.startswith(ym + "-"):
        return False
    try:
        datetime.strptime(work_date, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _row_exists(conn: sqlite3.Connection, employee_id: int, work_date: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 AS ok
        FROM attendance_rows
        WHERE employee_id = ? AND work_date = ?
        """,
        (employee_id, work_date),
    ).fetchone()
    return row is not None


def _blank(value) -> str:
    return value or ""


def _insert_edit(conn, editor_id: int, employee_id: int, work_date: str, before, fields: dict[str, str]) -> None:
    if before is None:
        before_values = (None, None, None, None, None)
    else:
        before_values = (
            before["category"],
            before["clock_in"],
            before["clock_out"],
            before["break_time"],
            before["note"],
        )
    conn.execute(
        """
        INSERT INTO attendance_edits (
          edited_at, editor_employee_id, target_employee_id, work_date,
          before_category, before_clock_in, before_clock_out, before_break_time, before_note,
          after_category, after_clock_in, after_clock_out, after_break_time, after_note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().astimezone().isoformat(timespec="seconds"),
            editor_id,
            employee_id,
            work_date,
            *before_values,
            fields["category"],
            _blank_to_null(fields["clock_in"]),
            _blank_to_null(fields["clock_out"]),
            _blank_to_null(fields["break_time"]),
            _blank_to_null(fields["note"]),
        ),
    )


def _month_edits(conn: sqlite3.Connection, employee_id: int, ym: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
          e.id,
          e.edited_at,
          e.editor_employee_id,
          editor.display_name AS editor_name,
          e.work_date,
          e.before_category,
          e.before_clock_in,
          e.before_clock_out,
          e.before_break_time,
          e.before_note,
          e.after_category,
          e.after_clock_in,
          e.after_clock_out,
          e.after_break_time,
          e.after_note
        FROM attendance_edits AS e
        JOIN employees AS editor ON editor.id = e.editor_employee_id
        WHERE e.target_employee_id = ?
          AND substr(e.work_date, 1, 7) = ?
        ORDER BY e.id DESC
        """,
        (employee_id, ym),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "edited_at": row["edited_at"],
            "editor_id": row["editor_employee_id"],
            "editor_name": row["editor_name"],
            "work_date": row["work_date"],
            "before_category": _blank(row["before_category"]),
            "before_clock_in": _blank(row["before_clock_in"]),
            "before_clock_out": _blank(row["before_clock_out"]),
            "before_break_time": _blank(row["before_break_time"]),
            "before_note": _blank(row["before_note"]),
            "after_category": _blank(row["after_category"]),
            "after_clock_in": _blank(row["after_clock_in"]),
            "after_clock_out": _blank(row["after_clock_out"]),
            "after_break_time": _blank(row["after_break_time"]),
            "after_note": _blank(row["after_note"]),
        }
        for row in rows
    ]


def _update_day(employee_raw: str, ym: str, work_date: str, event):
    if _invalid_ym(ym):
        _log_invalid_ym(ym)
        return _response(400, {"error": "invalid ym", "reason": "年月は 2026-11 のように入れてください"})
    if not _date_in_month(ym, work_date):
        return _reject("その日付は、この月にありません")
    employee_id = _parse_employee_id(employee_raw)
    if employee_id is None:
        return _response(404, {"error": "employee not found"})

    token = _bearer(event)
    with _connect() as conn:
        actor = _session_actor(conn, token) if token else None
        editor_id = int(actor["id"]) if actor is not None else None
        if editor_id is None:
            return _response(401, LOGIN_REQUIRED)
        if editor_id != employee_id and not actor["is_admin"]:
            return _response(403, ADMIN_ONLY)
        if not _employee_exists(conn, employee_id):
            return _response(404, {"error": "employee not found"})
        data = _event_body(event)
        if data is None:
            return _reject("送信内容を読めませんでした")
        if any(key not in data for key in UPDATE_FIELDS):
            return _reject("区分、出勤、退勤、休憩、備考をすべて送ってください")
        fields: dict[str, str] = {}
        for key in UPDATE_FIELDS:
            value = data[key]
            if value is None:
                value = ""
            if not isinstance(value, str):
                return _reject("入力の形式が正しくありません")
            fields[key] = value
        if len(fields["note"]) > 100:
            return _reject("備考は100文字以内にしてください")
        reason = _validate_fields(fields)
        if reason:
            return _reject(reason)

        before = conn.execute(
            """
            SELECT category, clock_in, clock_out, break_time, note
            FROM attendance_rows
            WHERE employee_id = ? AND work_date = ?
            """,
            (employee_id, work_date),
        ).fetchone()
        values = (
            fields["category"],
            _blank_to_null(fields["clock_in"]),
            _blank_to_null(fields["clock_out"]),
            _blank_to_null(fields["break_time"]),
            _blank_to_null(fields["note"]),
            employee_id,
            work_date,
        )
        if _row_exists(conn, employee_id, work_date):
            conn.execute(
                """
                UPDATE attendance_rows
                SET category = ?, clock_in = ?, clock_out = ?, break_time = ?, note = ?
                WHERE employee_id = ? AND work_date = ?
                """,
                values,
            )
        else:
            conn.execute(
                """
                INSERT INTO attendance_rows (
                  employee_id, work_date, category, clock_in, clock_out, break_time, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    employee_id,
                    work_date,
                    values[0],
                    values[1],
                    values[2],
                    values[3],
                    values[4],
                ),
            )
        _insert_edit(conn, editor_id, employee_id, work_date, before, fields)
        conn.commit()
    _publish_shared_db()
    return _response(
        200,
        {
            "employee_id": employee_id,
            "ym": ym,
            "work_date": work_date,
            "category": fields["category"],
            "clock_in": fields["clock_in"],
            "clock_out": fields["clock_out"],
            "break_time": fields["break_time"],
            "note": fields["note"],
            "stored": True,
        },
    )


def _event_headers(event) -> dict[str, str]:
    raw = event.get("headers") or {}
    return {str(key).lower(): "" if value is None else str(value) for key, value in raw.items()}


def _bearer(event) -> str | None:
    value = _event_headers(event).get("authorization", "")
    if not value.lower().startswith("bearer "):
        return None
    token = value[7:].strip()
    return token or None


def _session_actor(conn: sqlite3.Connection, token: str):
    row = conn.execute(
        """
        SELECT
          employees.id AS id,
          employees.display_name AS display_name,
          COALESCE(employees.is_admin, 0) AS is_admin,
          sessions.expires_at AS expires_at
        FROM sessions
        JOIN employees ON employees.id = sessions.employee_id
        WHERE sessions.token = ?
        """,
        (token,),
    ).fetchone()
    if row is None:
        return None
    expires = datetime.fromisoformat(row["expires_at"])
    now = datetime.now(expires.tzinfo)
    if now >= expires:
        return None
    return row


def _session_employee_id(conn: sqlite3.Connection, token: str) -> int | None:
    actor = _session_actor(conn, token)
    if actor is None:
        return None
    return int(actor["id"])


def _session_rejected(event):
    token = _bearer(event)
    if token is None:
        return _response(401, LOGIN_REQUIRED)
    with _connect() as conn:
        employee_id = _session_employee_id(conn, token)
    if employee_id is None:
        return _response(401, LOGIN_REQUIRED)
    return None


def _login(event):
    data = _event_body(event)
    name = data.get("display_name") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(name, str) or not isinstance(password, str):
        return _response(401, LOGIN_REJECT)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, display_name, password_hash, password_salt, is_admin
            FROM employees
            WHERE display_name = ?
            """,
            (name,),
        ).fetchone()
        if row is None or not row["password_hash"] or not row["password_salt"]:
            return _response(401, LOGIN_REJECT)
        digest = _password_hash(password, row["password_salt"])
        if not hmac.compare_digest(digest, row["password_hash"]):
            return _response(401, LOGIN_REJECT)
        token = secrets.token_urlsafe(32)
        expires = datetime.now().astimezone() + timedelta(hours=SESSION_HOURS)
        conn.execute(
            "INSERT INTO sessions (token, employee_id, expires_at) VALUES (?, ?, ?)",
            (token, row["id"], expires.isoformat(timespec="seconds")),
        )
        conn.commit()
        payload = {
            "token": token,
            "employee": {
                "id": row["id"],
                "display_name": row["display_name"],
                "is_admin": bool(row["is_admin"]),
            },
        }
    _publish_shared_db()
    return _response(200, payload)


def _logout(event):
    token = _bearer(event)
    if token is None:
        return _response(401, LOGIN_REQUIRED)
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    _publish_shared_db()
    return _response(200, {"logged_out": True})


def lambda_handler(event, context):
    method = _method(event)
    path = _path(event)

    if method == "OPTIONS":
        return _response(204)

    if method == "GET" and DEMO_ERROR_PATH.match(path):
        _raise_demo_error(event)

    if method == "GET" and DEMO_UNIMPLEMENTED_PATH.match(path):
        return _response(501, {"reason": "この機能はまだ実装されていません"})

    if method == "POST" and LOGIN_PATH.match(path):
        return _login(event)
    if method == "POST" and LOGOUT_PATH.match(path):
        return _logout(event)

    rejected = _session_rejected(event)
    if rejected is not None:
        return rejected

    day_match = DAY_PATH.match(path)
    if day_match:
        if method != "PUT":
            return _response(405, {"error": "method not allowed"})
        return _update_day(
            day_match.group(1), day_match.group(2), day_match.group(3), event
        )

    if method != "GET":
        return _response(405, {"error": "method not allowed"})

    if EMPLOYEES_PATH.match(path):
        with _connect() as conn:
            actor = _session_actor(conn, _bearer(event) or "")
            if actor is None:
                return _response(401, LOGIN_REQUIRED)
            return _response(200, {"employees": _list_employees(conn, actor)})

    export_match = EXPORT_PATH.match(path)
    if export_match:
        return _read_export(export_match.group(1), event)

    overview_match = OVERVIEW_PATH.match(path)
    if overview_match:
        return _read_overview(overview_match.group(1), event)

    summary_match = SUMMARY_PATH.match(path)
    month_match = MONTH_PATH.match(path) if summary_match is None else None

    if summary_match or month_match:
        matched = summary_match or month_match
        assert matched is not None
        return _read_month(
            _parse_employee_id(matched.group(1)),
            matched.group(2),
            summary_match is not None,
            event,
        )

    return _response(404, {"error": "not found", "path": path, "method": method})
