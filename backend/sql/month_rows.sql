-- 指定社員・月の全日。:employee_id と :ym（YYYY-MM）をバインドする。
-- 保存済みでない日は stored=0、区分と時刻は空。

WITH RECURSIVE calendar(work_date) AS (
  SELECT :ym || '-01'
  UNION ALL
  SELECT date(work_date, '+1 day')
  FROM calendar
  WHERE strftime('%Y-%m', date(work_date, '+1 day')) = :ym
)
SELECT
  calendar.work_date AS work_date,
  CASE
    WHEN attendance_rows.id IS NULL THEN ''
    ELSE attendance_rows.category
  END AS category,
  CASE
    WHEN attendance_rows.id IS NULL THEN ''
    ELSE COALESCE(attendance_rows.clock_in, '')
  END AS clock_in,
  CASE
    WHEN attendance_rows.id IS NULL THEN ''
    ELSE COALESCE(attendance_rows.clock_out, '')
  END AS clock_out,
  CASE
    WHEN attendance_rows.id IS NULL THEN ''
    ELSE COALESCE(attendance_rows.break_time, '')
  END AS break_time,
  CASE
    WHEN attendance_rows.id IS NULL THEN ''
    ELSE COALESCE(attendance_rows.note, '')
  END AS note,
  CASE
    WHEN attendance_rows.id IS NULL THEN 0
    ELSE 1
  END AS stored
FROM calendar
LEFT JOIN attendance_rows
  ON attendance_rows.employee_id = :employee_id
 AND attendance_rows.work_date = calendar.work_date
ORDER BY calendar.work_date;
