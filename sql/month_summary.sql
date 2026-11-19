-- 月の合計。実働は SQL で計算する（Python で同じ式を持ち直さない）。
-- :employee_id と :ym（YYYY-MM）をバインドする。
--
-- 時刻 HH:MM → 分: CAST(substr(t,1,2) AS INT) * 60 + CAST(substr(t,4,2) AS INT)
-- 通常出勤と半休で出勤・退勤がある行だけ実働 = 退勤 - 出勤 - 休憩
-- 8時間超過 = max(0, 実働 - 480分)
-- 退勤なしは件数のみ。欠勤と有休は出勤日数に入れない。

WITH month_rows AS (
  SELECT *
  FROM attendance_rows
  WHERE employee_id = :employee_id
    AND substr(work_date, 1, 7) = :ym
),
calc AS (
  SELECT
    category,
    clock_in,
    clock_out,
    break_time,
    CASE
      WHEN category IN ('通常出勤', '半休')
        AND clock_in IS NOT NULL
        AND clock_out IS NOT NULL
        AND break_time IS NOT NULL
      THEN
        (
          CAST(substr(clock_out, 1, 2) AS INTEGER) * 60
          + CAST(substr(clock_out, 4, 2) AS INTEGER)
        )
        - (
          CAST(substr(clock_in, 1, 2) AS INTEGER) * 60
          + CAST(substr(clock_in, 4, 2) AS INTEGER)
        )
        - (
          CAST(substr(break_time, 1, 2) AS INTEGER) * 60
          + CAST(substr(break_time, 4, 2) AS INTEGER)
        )
      ELSE NULL
    END AS worked_minutes
  FROM month_rows
)
SELECT
  COALESCE(
    SUM(CASE WHEN category IN ('通常出勤', '半休') AND clock_in IS NOT NULL THEN 1 ELSE 0 END),
    0
  ) AS workday_count,
  ROUND(COALESCE(SUM(worked_minutes), 0) / 60.0, 2) AS total_worked_hours,
  ROUND(
    COALESCE(
      SUM(
        CASE
          WHEN worked_minutes IS NOT NULL AND worked_minutes > 480
          THEN worked_minutes - 480
          ELSE 0
        END
      ),
      0
    ) / 60.0,
    2
  ) AS overtime_hours,
  COALESCE(
    SUM(
      CASE
        WHEN category IN ('通常出勤', '半休')
          AND clock_in IS NOT NULL
          AND clock_out IS NULL
        THEN 1
        ELSE 0
      END
    ),
    0
  ) AS missing_clock_out_count
FROM calc;
