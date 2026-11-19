"""読み取り API のユニットテスト（lambda_handler を直接呼ぶ）。"""

from __future__ import annotations

import io
import json
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app import DemoError, lambda_handler  # noqa: E402

_DEFAULT_TOKEN: str | None = None
_OMIT = object()


def _ensure_db() -> None:
    db = BACKEND / "data" / "attendance.db"
    if not db.exists():
        sys.path.insert(0, str(ROOT / "sql"))
        from build_db import main as build_db

        build_db()


@pytest.fixture(autouse=True)
def runtime_db(tmp_path, monkeypatch):
    global _DEFAULT_TOKEN
    _ensure_db()
    seed = BACKEND / "data" / "attendance.db"
    before = seed.read_bytes()
    runtime = tmp_path / "attendance.db"
    shutil.copyfile(seed, runtime)
    monkeypatch.setenv("KINTAI_RUNTIME_DB", str(runtime))
    logged = lambda_handler(
        {
            "rawPath": "/login",
            "requestContext": {"http": {"method": "POST"}},
            "body": json.dumps({"display_name": "テスト青空", "password": "aozora"}),
        },
        None,
    )
    assert logged["statusCode"] == 200
    _DEFAULT_TOKEN = json.loads(logged["body"])["token"]
    yield runtime
    _DEFAULT_TOKEN = None
    assert seed.read_bytes() == before


def call(
    path: str,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict | None = None,
    token: object = _OMIT,
):
    event = {
        "rawPath": path,
        "requestContext": {"http": {"method": method}},
    }
    if headers is None:
        chosen = _DEFAULT_TOKEN if token is _OMIT else token
        if chosen:
            headers = {"authorization": f"Bearer {chosen}"}
    if headers is not None:
        event["headers"] = headers
    if payload is not None:
        event["body"] = json.dumps(payload)
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = lambda_handler(event, None)
    return result, buf.getvalue()


def body(result) -> dict:
    return json.loads(result["body"] or "{}")


def login_as(name: str, password: str) -> dict:
    global _DEFAULT_TOKEN
    logged, _ = call(
        "/login",
        "POST",
        {"display_name": name, "password": password},
        token=None,
    )
    assert logged["statusCode"] == 200, logged["body"]
    payload = body(logged)
    _DEFAULT_TOKEN = payload["token"]
    return payload


def test_list_employees_returns_three_dummy_names():
    login_as("デモ管理", "kanri")
    result, _ = call("/employees")
    assert result["statusCode"] == 200
    employees = body(result)["employees"]
    assert len(employees) == 3
    assert {e["display_name"] for e in employees} == {
        "テスト青空",
        "サンプル海原",
        "見本山辺",
    }
    assert "デモ管理" not in {e["display_name"] for e in employees}
    for emp in employees:
        assert set(emp.keys()) == {"id", "display_name"}


def test_self_employee_list_is_only_self():
    result, _ = call("/employees")
    assert result["statusCode"] == 200
    employees = body(result)["employees"]
    assert [emp["display_name"] for emp in employees] == ["テスト青空"]


def test_month_rows_include_missing_clock_out_and_absence():
    result, _ = call("/employees/1/months/2026-11")
    assert result["statusCode"] == 200
    rows = body(result)["rows"]
    assert any(r["clock_out"] == "" and r["category"] == "通常出勤" for r in rows)
    assert any(r["category"] == "欠勤" for r in rows)
    normal = next(
        r
        for r in rows
        if r["work_date"] == "2026-11-02"
    )
    assert normal["clock_in"] == "09:00"
    assert normal["clock_out"] == "18:00"
    assert normal["break_time"] == "01:00"
    assert normal["note"] == ""
    assert normal["stored"] is True
    assert len(rows) == 30
    assert [r["work_date"] for r in rows] == [
        f"2026-11-{day:02d}" for day in range(1, 31)
    ]
    empty = next(r for r in rows if r["work_date"] == "2026-11-01")
    assert empty["stored"] is False
    assert empty["category"] == ""
    assert empty["note"] == ""
    assert next(r for r in rows if r["work_date"] == "2026-11-20")["stored"] is True
    assert next(r for r in rows if r["work_date"] == "2026-11-21")["stored"] is False
    assert next(r for r in rows if r["work_date"] == "2026-11-07")["stored"] is False
    assert next(r for r in rows if r["work_date"] == "2026-11-08")["stored"] is False
    assert next(r for r in rows if r["work_date"] == "2026-11-14")["stored"] is False
    assert next(r for r in rows if r["work_date"] == "2026-11-15")["stored"] is False
    absent = next(r for r in rows if r["work_date"] == "2026-11-05")
    assert absent["stored"] is True
    assert absent["category"] == "欠勤"
    assert absent["note"] == ""


def test_overview_returns_each_employee_summary():
    login_as("デモ管理", "kanri")
    result, _ = call("/months/2026-11/overview")
    assert result["statusCode"] == 200
    payload = body(result)
    employees = payload["employees"]
    assert [emp["id"] for emp in employees] == [1, 2, 3]
    assert [emp["display_name"] for emp in employees] == [
        "テスト青空",
        "サンプル海原",
        "見本山辺",
    ]
    for emp in employees:
        assert set(emp.keys()) == {"id", "display_name", "summary"}
        assert set(emp["summary"].keys()) == {
            "workday_count",
            "total_worked_hours",
            "overtime_hours",
            "missing_clock_out_count",
        }
    by_id = {emp["id"]: emp["summary"] for emp in employees}
    assert by_id[1] == {
        "workday_count": 14,
        "total_worked_hours": 105.0,
        "overtime_hours": 1.0,
        "missing_clock_out_count": 1,
    }
    assert by_id[2] == {
        "workday_count": 15,
        "total_worked_hours": 120.0,
        "overtime_hours": 0.0,
        "missing_clock_out_count": 0,
    }
    assert by_id[3] == {
        "workday_count": 15,
        "total_worked_hours": 112.0,
        "overtime_hours": 0.0,
        "missing_clock_out_count": 1,
    }


def test_overview_february_is_zero_for_everyone():
    login_as("デモ管理", "kanri")
    result, _ = call("/months/2026-02/overview")
    assert result["statusCode"] == 200
    employees = body(result)["employees"]
    assert len(employees) == 3
    for emp in employees:
        assert emp["summary"] == {
            "workday_count": 0,
            "total_worked_hours": 0.0,
            "overtime_hours": 0.0,
            "missing_clock_out_count": 0,
        }


def test_overview_invalid_ym_returns_400_and_logs_reason():
    login_as("デモ管理", "kanri")
    for path in ("/months/2026/11/overview", "/months/2026-13/overview"):
        result, log = call(path)
        assert result["statusCode"] == 400
        assert "employees" not in body(result)
        assert "invalid ym" in log


def test_month_summary_matches_seed_scenarios():
    result, _ = call("/employees/1/months/2026-11/summary")
    assert result["statusCode"] == 200
    summary = body(result)["summary"]
    assert summary["workday_count"] == 14
    assert summary["total_worked_hours"] == 105.0
    assert summary["overtime_hours"] == 1.0
    assert summary["missing_clock_out_count"] == 1


def test_invalid_ym_returns_400_and_logs_reason():
    result, log = call("/employees/1/months/2026/11")
    assert result["statusCode"] == 400
    payload = body(result)
    assert "rows" not in payload
    assert "summary" not in payload
    assert "invalid ym" in log

    summary_result, _ = call("/employees/1/months/2026/11/summary")
    assert summary_result["statusCode"] == 400
    assert "summary" not in body(summary_result)


def test_unknown_employee_returns_404_without_rows_or_summary():
    login_as("デモ管理", "kanri")
    result, _ = call("/employees/999/months/2026-11")
    assert result["statusCode"] == 404
    assert "rows" not in body(result)

    summary_result, _ = call("/employees/999/months/2026-11/summary")
    assert summary_result["statusCode"] == 404
    assert "summary" not in body(summary_result)


def test_february_is_all_unstored_and_summary_is_zero():
    result, _ = call("/employees/1/months/2026-02")
    assert result["statusCode"] == 200
    rows = body(result)["rows"]
    assert len(rows) == 28
    assert all(r["stored"] is False for r in rows)

    summary_result, _ = call("/employees/1/months/2026-02/summary")
    summary = body(summary_result)["summary"]
    assert summary["workday_count"] == 0
    assert summary["total_worked_hours"] == 0.0
    assert summary["overtime_hours"] == 0.0
    assert summary["missing_clock_out_count"] == 0


def test_month_13_returns_400_for_rows_and_summary():
    result, log = call("/employees/1/months/2026-13")
    assert result["statusCode"] == 400
    assert "rows" not in body(result)
    assert "invalid ym" in log

    summary_result, summary_log = call("/employees/1/months/2026-13/summary")
    assert summary_result["statusCode"] == 400
    assert "summary" not in body(summary_result)
    assert "invalid ym" in summary_log


def day_payload(**overrides):
    payload = {
        "category": "通常出勤",
        "clock_in": "09:00",
        "clock_out": "18:00",
        "break_time": "01:00",
        "note": "",
    }
    payload.update(overrides)
    return payload


def nov2(path_suffix: str = ""):
    return f"/employees/1/months/2026-11/days/2026-11-02{path_suffix}"


def row_on(date: str):
    result, _ = call("/employees/1/months/2026-11")
    return next(r for r in body(result)["rows"] if r["work_date"] == date)


def test_put_updates_clocks_and_summary_uses_sql():
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(clock_in="10:00", clock_out="19:00", break_time="01:00"),
    )
    assert result["statusCode"] == 200
    saved = body(result)
    assert saved["stored"] is True
    assert saved["clock_in"] == "10:00"
    assert saved["clock_out"] == "19:00"
    updated = row_on("2026-11-02")
    assert updated["clock_in"] == "10:00"
    assert updated["clock_out"] == "19:00"

    # 11-02 を 8 時間から 9 時間にすると、総実働は 106、超過は 2。
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(clock_in="09:00", clock_out="19:00", break_time="01:00"),
    )
    assert result["statusCode"] == 200
    summary = body(call("/employees/1/months/2026-11/summary")[0])["summary"]
    assert summary["workday_count"] == 14
    assert summary["total_worked_hours"] == 106.0
    assert summary["overtime_hours"] == 2.0


def test_put_can_clear_clock_out_and_switch_to_absence():
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(clock_in="09:00", clock_out="", break_time=""),
    )
    assert result["statusCode"] == 200
    assert row_on("2026-11-02")["clock_out"] == ""

    result, _ = call(
        nov2(),
        "PUT",
        day_payload(category="欠勤", clock_in="", clock_out="", break_time=""),
    )
    assert result["statusCode"] == 200
    row = row_on("2026-11-02")
    assert row["category"] == "欠勤"
    assert row["clock_in"] == ""
    assert row["clock_out"] == ""
    assert row["break_time"] == ""


def test_put_allows_equal_clocks_and_break_equal_to_span():
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(clock_in="09:00", clock_out="09:00", break_time="00:00"),
    )
    assert result["statusCode"] == 200
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(clock_in="09:00", clock_out="18:00", break_time="09:00"),
    )
    assert result["statusCode"] == 200
    assert row_on("2026-11-02")["break_time"] == "09:00"


@pytest.mark.parametrize(
    "payload",
    [
        day_payload(clock_in="18:00", clock_out="09:00", break_time="00:00"),
        day_payload(clock_in="09:00", clock_out="18:00", break_time="10:00"),
        day_payload(clock_in="", clock_out="18:00", break_time="01:00"),
        day_payload(category="欠勤", clock_in="09:00", clock_out="", break_time=""),
        day_payload(category="有休"),
        day_payload(clock_in="9:00"),
        day_payload(clock_out="25:00"),
        day_payload(clock_out="18:60"),
    ],
)
def test_put_rejects_invalid_day_without_changing_seed_row(payload):
    result, log = call(nov2(), "PUT", payload)
    assert result["statusCode"] == 400
    assert "reason=" in log
    reason = body(result)["reason"]
    assert "break too long" not in reason
    assert "clock_out" not in reason
    row = row_on("2026-11-02")
    assert row["clock_in"] == "09:00"
    assert row["clock_out"] == "18:00"
    assert row["category"] == "通常出勤"


def test_put_rejects_missing_field_without_change():
    payload = day_payload()
    del payload["clock_out"]
    result, _ = call(nov2(), "PUT", payload)
    assert result["statusCode"] == 400
    assert row_on("2026-11-02")["clock_out"] == "18:00"


def test_put_saves_and_clears_note_including_newline():
    result, _ = call(nov2(), "PUT", day_payload(note="客先A\n二行目"))
    assert result["statusCode"] == 200
    assert body(result)["note"] == "客先A\n二行目"
    assert row_on("2026-11-02")["note"] == "客先A\n二行目"

    result, _ = call(nov2(), "PUT", day_payload(note=""))
    assert result["statusCode"] == 200
    assert body(result)["note"] == ""
    assert row_on("2026-11-02")["note"] == ""


def test_put_rejects_note_over_100_without_change():
    before = row_on("2026-11-02")
    result, _ = call(nov2(), "PUT", day_payload(note="あ" * 101))
    assert result["statusCode"] == 400
    assert body(result)["reason"] == "備考は100文字以内にしてください"
    after = row_on("2026-11-02")
    assert after["note"] == before["note"]
    assert after["clock_in"] == before["clock_in"]


def test_put_rejects_missing_note_without_change():
    payload = day_payload()
    del payload["note"]
    result, _ = call(nov2(), "PUT", payload)
    assert result["statusCode"] == 400
    assert "備考" in body(result)["reason"]
    assert row_on("2026-11-02")["clock_out"] == "18:00"


def test_put_rejects_non_string_note_without_change():
    payload = day_payload()
    payload["note"] = 1
    result, _ = call(nov2(), "PUT", payload)
    assert result["statusCode"] == 400
    assert body(result)["reason"] == "入力の形式が正しくありません"
    assert row_on("2026-11-02")["note"] == ""


def test_note_change_is_recorded_in_edits():
    call(nov2(), "PUT", day_payload(note="客先A"))
    result, _ = call(nov2(), "PUT", day_payload(note="客先B"))
    assert result["statusCode"] == 200
    edit = edits_for("2026-11-02")[0]
    assert edit["before_note"] == "客先A"
    assert edit["after_note"] == "客先B"


def test_forbidden_put_does_not_write_note():
    login_as("サンプル海原", "unahara")
    result, _ = call(
        "/employees/1/months/2026-11/days/2026-11-02",
        "PUT",
        day_payload(note="他人の備考"),
    )
    assert result["statusCode"] == 403
    login_as("テスト青空", "aozora")
    assert row_on("2026-11-02")["note"] == ""


def test_put_rejects_bad_target_without_creating_a_row(runtime_db):
    login_as("デモ管理", "kanri")
    before = sqlite_count(runtime_db)
    result, log = call(
        "/employees/1/months/2026/11/days/2026-11-02",
        "PUT",
        day_payload(),
    )
    assert result["statusCode"] == 400
    assert "invalid ym" in log

    result, log = call(
        "/employees/1/months/2026-13/days/2026-13-01",
        "PUT",
        day_payload(),
    )
    assert result["statusCode"] == 400
    assert "invalid ym" in log

    result, _ = call("/employees/999/months/2026-11/days/2026-11-02", "PUT", day_payload())
    assert result["statusCode"] == 404

    result, _ = call("/employees/1/months/2026-11/days/2026-11-31", "PUT", day_payload())
    assert result["statusCode"] == 400
    assert sqlite_count(runtime_db) == before


def test_put_creates_empty_day_and_keeps_other_employee(runtime_db):
    before = sqlite_count(runtime_db)
    result, _ = call(
        "/employees/1/months/2026-11/days/2026-11-21",
        "PUT",
        day_payload(),
    )
    assert result["statusCode"] == 200
    assert body(result)["stored"] is True
    assert row_on("2026-11-21")["clock_in"] == "09:00"
    assert sqlite_count(runtime_db) == before + 1

    login_as("デモ管理", "kanri")
    others, _ = call("/employees/2/months/2026-11")
    other = next(r for r in body(others)["rows"] if r["work_date"] == "2026-11-02")
    assert other["stored"] is True
    assert other["clock_in"] == "09:00"
    assert other["clock_out"] == "18:00"
    later = next(r for r in body(others)["rows"] if r["work_date"] == "2026-11-21")
    assert later["stored"] is False


def test_fresh_runtime_db_drops_updates(runtime_db, tmp_path, monkeypatch):
    call(nov2(), "PUT", day_payload(clock_in="10:00"))
    assert row_on("2026-11-02")["clock_in"] == "10:00"
    fresh = tmp_path / "fresh.db"
    shutil.copyfile(BACKEND / "data" / "attendance.db", fresh)
    monkeypatch.setenv("KINTAI_RUNTIME_DB", str(fresh))
    global _DEFAULT_TOKEN
    logged, _ = call(
        "/login",
        "POST",
        {"display_name": "テスト青空", "password": "aozora"},
        token=None,
    )
    assert logged["statusCode"] == 200
    _DEFAULT_TOKEN = body(logged)["token"]
    assert row_on("2026-11-02")["clock_in"] == "09:00"
    assert runtime_db.exists()


def sqlite_count(db: Path) -> int:
    import sqlite3

    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM attendance_rows").fetchone()[0]
    finally:
        conn.close()


def test_prod_prefix_path_is_accepted():
    login_as("デモ管理", "kanri")
    result, _ = call("/prod/employees")
    assert result["statusCode"] == 200
    assert len(body(result)["employees"]) == 3


def _summary():
    result, _ = call("/employees/1/months/2026-11/summary")
    assert result["statusCode"] == 200
    return body(result)["summary"]


def test_paid_leave_drops_that_day_from_the_summary():
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(category="有休", clock_in="", clock_out="", break_time=""),
    )
    assert result["statusCode"] == 200
    row = row_on("2026-11-02")
    assert row["category"] == "有休"
    assert row["clock_in"] == ""
    assert row["clock_out"] == ""
    assert row["break_time"] == ""
    summary = _summary()
    assert summary["workday_count"] == 13
    assert summary["total_worked_hours"] == 97.0
    assert summary["overtime_hours"] == 1.0
    assert summary["missing_clock_out_count"] == 1


def test_half_day_counts_actual_hours():
    result, _ = call(
        "/employees/1/months/2026-11/days/2026-11-21",
        "PUT",
        day_payload(category="半休", clock_in="09:00", clock_out="13:00", break_time="00:00"),
    )
    assert result["statusCode"] == 200
    summary = _summary()
    assert summary["workday_count"] == 15
    assert summary["total_worked_hours"] == 109.0
    assert summary["overtime_hours"] == 1.0
    assert summary["missing_clock_out_count"] == 1


def test_half_day_without_clock_out_adds_a_missing_day():
    result, _ = call(
        "/employees/1/months/2026-11/days/2026-11-21",
        "PUT",
        day_payload(category="半休", clock_in="09:00", clock_out="", break_time=""),
    )
    assert result["statusCode"] == 200
    summary = _summary()
    assert summary["workday_count"] == 15
    assert summary["total_worked_hours"] == 105.0
    assert summary["overtime_hours"] == 1.0
    assert summary["missing_clock_out_count"] == 2


def test_unknown_category_is_rejected():
    result, log = call(nov2(), "PUT", day_payload(category="出張"))
    assert result["statusCode"] == 400
    assert "reason=" in log
    assert "通常出勤、半休、有休、欠勤" in body(result)["reason"]
    row = row_on("2026-11-02")
    assert row["category"] == "通常出勤"
    assert row["clock_in"] == "09:00"
    assert row["clock_out"] == "18:00"


def test_legacy_check_constraint_still_accepts_paid_leave(tmp_path, monkeypatch):
    import sqlite3

    legacy = tmp_path / "legacy.db"
    conn = sqlite3.connect(legacy)
    conn.executescript(
        """
        CREATE TABLE employees (
          id INTEGER PRIMARY KEY,
          display_name TEXT NOT NULL
        );
        INSERT INTO employees (id, display_name) VALUES
          (1, 'テスト青空'),
          (2, 'サンプル海原');
        CREATE TABLE attendance_rows (
          id INTEGER PRIMARY KEY,
          employee_id INTEGER NOT NULL,
          work_date TEXT NOT NULL,
          category TEXT NOT NULL CHECK (category IN ('通常出勤', '欠勤')),
          clock_in TEXT,
          clock_out TEXT,
          break_time TEXT,
          UNIQUE (employee_id, work_date)
        );
        INSERT INTO attendance_rows (
          employee_id, work_date, category, clock_in, clock_out, break_time
        ) VALUES
          (1, '2026-11-02', '通常出勤', '09:00', '18:00', '01:00'),
          (2, '2026-11-02', '通常出勤', '09:00', '18:00', '01:00');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("KINTAI_RUNTIME_DB", str(legacy))
    global _DEFAULT_TOKEN
    logged, _ = call(
        "/login",
        "POST",
        {"display_name": "テスト青空", "password": "aozora"},
        token=None,
    )
    assert logged["statusCode"] == 200
    _DEFAULT_TOKEN = body(logged)["token"]
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(category="有休", clock_in="", clock_out="", break_time=""),
    )
    assert result["statusCode"] == 200
    assert row_on("2026-11-02")["category"] == "有休"
    login_as("デモ管理", "kanri")
    others, _ = call("/employees/2/months/2026-11")
    other = next(r for r in body(others)["rows"] if r["work_date"] == "2026-11-02")
    assert other["category"] == "通常出勤"
    assert other["clock_in"] == "09:00"
    assert other["clock_out"] == "18:00"
    assert sqlite_count(legacy) == 2


def edits_for(date: str):
    result, _ = call("/employees/1/months/2026-11")
    return [item for item in body(result)["edits"] if item["work_date"] == date]


def test_successful_save_records_editor_and_before_after():
    login_as("デモ管理", "kanri")
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(category="有休", clock_in="", clock_out="", break_time="", editor_id=2),
    )
    assert result["statusCode"] == 200
    edits = edits_for("2026-11-02")
    assert len(edits) == 1
    edit = edits[0]
    assert edit["editor_id"] == 4
    assert edit["editor_name"] == "デモ管理"
    assert edit["before_category"] == "通常出勤"
    assert edit["before_clock_in"] == "09:00"
    assert edit["before_clock_out"] == "18:00"
    assert edit["before_break_time"] == "01:00"
    assert edit["before_note"] == ""
    assert edit["after_category"] == "有休"
    assert edit["after_clock_in"] == ""
    assert edit["after_clock_out"] == ""
    assert edit["after_break_time"] == ""
    assert edit["after_note"] == ""


def test_new_day_edit_has_empty_before():
    result, _ = call(
        "/employees/1/months/2026-11/days/2026-11-21",
        "PUT",
        day_payload(editor_id=1),
    )
    assert result["statusCode"] == 200
    edits = edits_for("2026-11-21")
    assert len(edits) == 1
    edit = edits[0]
    assert edit["before_category"] == ""
    assert edit["before_clock_in"] == ""
    assert edit["before_clock_out"] == ""
    assert edit["before_break_time"] == ""
    assert edit["before_note"] == ""
    assert edit["after_category"] == "通常出勤"
    assert edit["after_clock_in"] == "09:00"
    assert edit["after_note"] == ""


def test_missing_editor_is_the_target_employee():
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(clock_in="10:00", clock_out="19:00"),
    )
    assert result["statusCode"] == 200
    edits = edits_for("2026-11-02")
    assert len(edits) == 1
    assert edits[0]["editor_id"] == 1


def test_rejected_save_does_not_record_an_edit():
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(clock_in="18:00", clock_out="09:00", break_time="00:00", editor_id=2),
    )
    assert result["statusCode"] == 400
    assert edits_for("2026-11-02") == []
    row = row_on("2026-11-02")
    assert row["clock_in"] == "09:00"
    assert row["clock_out"] == "18:00"


def test_sent_editor_is_ignored():
    login_as("デモ管理", "kanri")
    result, _ = call(
        nov2(),
        "PUT",
        day_payload(clock_in="10:00", clock_out="19:00", editor_id=3),
    )
    assert result["statusCode"] == 200
    edits = edits_for("2026-11-02")
    assert len(edits) == 1
    assert edits[0]["editor_id"] == 4
    assert edits[0]["editor_name"] == "デモ管理"


def test_no_session_rejects_overview_and_update():
    overview, _ = call("/months/2026-11/overview", token=None)
    assert overview["statusCode"] == 401
    assert body(overview)["reason"] == "ログインしてください"
    assert "employees" not in body(overview)
    result, _ = call(nov2(), "PUT", day_payload(clock_out="19:00"), token=None)
    assert result["statusCode"] == 401
    assert body(result)["reason"] == "ログインしてください"
    assert row_on("2026-11-02")["clock_out"] == "18:00"


def _csv_rows(result) -> list[list[str]]:
    import csv

    text = result["body"]
    assert text.startswith("\ufeff")
    return list(csv.reader(io.StringIO(text[1:])))


def test_export_november_includes_stored_and_empty_days(runtime_db):
    login_as("デモ管理", "kanri")
    before = sqlite_count(runtime_db)
    result, _ = call("/months/2026-11/export")
    assert result["statusCode"] == 200
    assert 'filename="kintai-2026-11.csv"' in result["headers"]["Content-Disposition"]
    rows = _csv_rows(result)
    assert rows[0] == ["社員名", "日付", "区分", "出勤", "退勤", "休憩"]
    assert "給与" not in rows[0]
    data = rows[1:]
    assert len(data) == 90
    by_key = {(row[0], row[1]): row for row in data}
    assert by_key[("テスト青空", "2026-11-01")][2:] == ["", "", "", ""]
    assert by_key[("テスト青空", "2026-11-02")][2:] == ["通常出勤", "09:00", "18:00", "01:00"]
    assert by_key[("テスト青空", "2026-11-05")][2:] == ["欠勤", "", "", ""]
    assert by_key[("見本山辺", "2026-11-02")][2:] == ["通常出勤", "10:00", "19:00", "01:00"]
    assert by_key[("見本山辺", "2026-11-04")][2] == "通常出勤"
    assert by_key[("見本山辺", "2026-11-04")][3] == "09:00"
    assert by_key[("見本山辺", "2026-11-04")][4] == ""
    assert row_on("2026-11-02")["clock_in"] == "09:00"
    assert sqlite_count(runtime_db) == before


def test_export_february_is_empty_days():
    login_as("デモ管理", "kanri")
    result, _ = call("/months/2026-02/export")
    assert result["statusCode"] == 200
    data = _csv_rows(result)[1:]
    assert len(data) == 84
    assert all(row[2:] == ["", "", "", ""] for row in data)


def test_export_invalid_ym_returns_no_csv():
    login_as("デモ管理", "kanri")
    result, log = call("/months/2026/11/export")
    assert result["statusCode"] == 400
    assert not result["body"].startswith("\ufeff")
    assert "invalid ym" in log

    result, log = call("/months/2026-13/export")
    assert result["statusCode"] == 400
    assert not result["body"].startswith("\ufeff")
    assert "invalid ym" in log


def _clock_in(db: Path) -> str:
    import sqlite3

    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            """
            SELECT clock_in FROM attendance_rows
            WHERE employee_id = 1 AND work_date = '2026-11-02'
            """
        ).fetchone()[0]
    finally:
        conn.close()


def test_login_kanri_omits_password_and_marks_admin():
    result, _ = call(
        "/login",
        "POST",
        {"display_name": "デモ管理", "password": "kanri"},
    )
    assert result["statusCode"] == 200
    payload = body(result)
    assert payload["employee"]["display_name"] == "デモ管理"
    assert payload["employee"]["is_admin"] is True
    assert "kanri" not in result["body"]


def test_unahara_cannot_change_aozora_clock_out(runtime_db):
    login_as("サンプル海原", "unahara")
    result, _ = call(nov2(), "PUT", day_payload(clock_out="19:00"))
    assert result["statusCode"] == 403
    assert body(result)["reason"] == "全員の勤怠は管理者だけが見られます"
    import sqlite3

    conn = sqlite3.connect(runtime_db)
    try:
        clock_out = conn.execute(
            """
            SELECT clock_out FROM attendance_rows
            WHERE employee_id = 1 AND work_date = '2026-11-02'
            """
        ).fetchone()[0]
    finally:
        conn.close()
    assert clock_out == "18:00"


def test_aozora_cannot_read_overview_or_other_month():
    overview, _ = call("/months/2026-11/overview")
    assert overview["statusCode"] == 403
    assert body(overview)["reason"] == "全員の勤怠は管理者だけが見られます"
    exported, _ = call("/months/2026-11/export")
    assert exported["statusCode"] == 403
    other, _ = call("/employees/2/months/2026-11")
    assert other["statusCode"] == 403
    own, _ = call("/employees/1/months/2026-11/summary")
    assert own["statusCode"] == 200
    assert body(own)["summary"]["workday_count"] == 14


def test_unahara_own_november_is_fifteen_weekdays():
    login_as("サンプル海原", "unahara")
    result, _ = call("/employees/2/months/2026-11/summary")
    assert result["statusCode"] == 200
    summary = body(result)["summary"]
    assert summary["workday_count"] == 15
    assert summary["total_worked_hours"] == 120


def test_admin_own_november_has_no_workdays():
    login_as("デモ管理", "kanri")
    result, _ = call("/employees/4/months/2026-11/summary")
    assert result["statusCode"] == 200
    assert body(result)["summary"]["workday_count"] == 0


def test_login_unahara_omits_password():
    result, _ = call(
        "/login",
        "POST",
        {"display_name": "サンプル海原", "password": "unahara"},
    )
    assert result["statusCode"] == 200
    payload = body(result)
    assert payload["employee"]["display_name"] == "サンプル海原"
    assert payload["employee"]["id"] == 2
    assert "unahara" not in result["body"]
    assert "password" not in payload


def test_login_aozora_and_yamabe():
    for name, password in (("テスト青空", "aozora"), ("見本山辺", "yamabe")):
        result, _ = call("/login", "POST", {"display_name": name, "password": password})
        assert result["statusCode"] == 200
        assert body(result)["employee"]["display_name"] == name


def test_login_wrong_password_keeps_clock_in(runtime_db):
    result, _ = call(
        "/login",
        "POST",
        {"display_name": "テスト青空", "password": "wrong"},
    )
    assert result["statusCode"] == 401
    assert body(result)["reason"] == "社員名かパスワードが違います"
    assert _clock_in(runtime_db) == "09:00"


def test_login_unknown_name_is_rejected():
    result, _ = call(
        "/login",
        "POST",
        {"display_name": "出張太郎", "password": "aozora"},
    )
    assert result["statusCode"] == 401
    assert body(result)["reason"] == "社員名かパスワードが違います"


def test_logout_and_expired_session_hide_november(runtime_db):
    import sqlite3

    logged_in, _ = call(
        "/login",
        "POST",
        {"display_name": "サンプル海原", "password": "unahara"},
    )
    token = body(logged_in)["token"]
    headers = {"authorization": f"Bearer {token}"}
    logged_out, _ = call("/logout", "POST", headers=headers)
    assert logged_out["statusCode"] == 200
    hidden, _ = call("/months/2026-11/overview", headers=headers)
    assert hidden["statusCode"] == 401
    assert "employees" not in body(hidden)

    again, _ = call(
        "/login",
        "POST",
        {"display_name": "テスト青空", "password": "aozora"},
    )
    expired_token = body(again)["token"]
    conn = sqlite3.connect(runtime_db)
    try:
        conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE token = ?",
            ("2000-01-01T00:00:00+09:00", expired_token),
        )
        conn.commit()
    finally:
        conn.close()
    expired, _ = call(
        "/months/2026-11/overview",
        headers={"authorization": f"Bearer {expired_token}"},
    )
    assert expired["statusCode"] == 401
    assert "employees" not in body(expired)


def test_old_employees_table_keeps_attendance_rows(runtime_db):
    import sqlite3

    before = sqlite_count(runtime_db)
    conn = sqlite3.connect(runtime_db)
    try:
        conn.execute("DROP TABLE sessions")
        conn.execute("ALTER TABLE employees RENAME TO employees_old")
        conn.execute(
            """
            CREATE TABLE employees (
              id INTEGER PRIMARY KEY,
              display_name TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO employees (id, display_name)
            SELECT id, display_name FROM employees_old
            """
        )
        conn.execute("DROP TABLE employees_old")
        conn.commit()
    finally:
        conn.close()

    global _DEFAULT_TOKEN
    logged, _ = call(
        "/login",
        "POST",
        {"display_name": "テスト青空", "password": "aozora"},
        token=None,
    )
    assert logged["statusCode"] == 200
    _DEFAULT_TOKEN = body(logged)["token"]
    result, _ = call("/employees")
    assert result["statusCode"] == 200
    assert _clock_in(runtime_db) == "09:00"
    assert sqlite_count(runtime_db) == before
    conn = sqlite3.connect(runtime_db)
    try:
        hashes = conn.execute("SELECT password_hash FROM employees ORDER BY id").fetchall()
    finally:
        conn.close()
    assert all(row[0] for row in hashes)


def test_demo_unimplemented_returns_501_with_japanese_reason():
    result, _ = call("/demo/unimplemented")
    assert result["statusCode"] == 501
    assert body(result)["reason"] == "この機能はまだ実装されていません"


def test_demo_error_raises_with_marker():
    with pytest.raises(DemoError, match="lesson1"):
        lambda_handler(
            {
                "rawPath": "/demo/error",
                "queryStringParameters": {"marker": "lesson1"},
                "requestContext": {"http": {"method": "GET"}},
            },
            None,
        )


def test_demo_error_raises_without_marker():
    with pytest.raises(DemoError, match="marker=demo"):
        lambda_handler(
            {
                "rawPath": "/demo/error",
                "requestContext": {"http": {"method": "GET"}},
            },
            None,
        )
