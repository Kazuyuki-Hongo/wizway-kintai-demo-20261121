import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const SESSION_KEY = 'kintai-demo-session'
const DEMO_ACCOUNTS = [
  { name: 'テスト青空', role: '本人', password: 'aozora' },
  { name: 'サンプル海原', role: '本人', password: 'unahara' },
  { name: '見本山辺', role: '本人', password: 'yamabe' },
  { name: 'デモ管理', role: '管理者', password: 'kanri' },
]

type Employee = {
  id: number
  display_name: string
  is_admin?: boolean
}

type AttendanceRow = {
  work_date: string
  category: string
  clock_in: string
  clock_out: string
  break_time: string
  note: string
  stored: boolean
}

type Summary = {
  workday_count: number
  total_worked_hours: number
  overtime_hours: number
  missing_clock_out_count: number
}

type OverviewEmployee = Employee & {
  summary: Summary
}

type Draft = {
  category: string
  clock_in: string
  clock_out: string
  break_time: string
  note: string
}

type Session = {
  token: string
  employee: Employee
}

type Edit = {
  id: number
  edited_at: string
  editor_name: string
  work_date: string
  before_category: string
  before_clock_in: string
  before_clock_out: string
  before_break_time: string
  before_note: string
  after_category: string
  after_clock_in: string
  after_clock_out: string
  after_break_time: string
  after_note: string
}

const SAVE_ERROR: Record<string, string> = {
  'category not allowed': '区分は通常出勤か欠勤にしてください',
  'absence must have empty times': '欠勤のときは、出勤・退勤・休憩を空にしてください',
  'clock_in required': '通常出勤のときは、出勤を入れてください',
  'invalid time': '時刻は 09:00 のように、00:00 から 23:59 までで入れてください',
  'clock_out before clock_in': '退勤は出勤より前にはできません',
  'break required when clock_out is set':
    '退勤を入れるときは、休憩も入れてください。1時間なら 01:00 です',
  'break too long':
    '休憩は時刻ではなく長さです。出勤から退勤までより長くできません。1時間なら 01:00 です',
  'date not in month': 'その日付は、この月にありません',
  'invalid json': '送信内容を読めませんでした',
  'missing field': '区分、出勤、退勤、休憩、備考をすべて送ってください',
  'invalid field': '入力の形式が正しくありません',
  'invalid ym': '年月は 2026-11 のように入れてください',
}

function saveError(reason: string | undefined, status: number) {
  if (!reason) return `保存できませんでした（${status}）`
  if (SAVE_ERROR[reason]) return SAVE_ERROR[reason]
  if (/[A-Za-z]/.test(reason)) return '保存できませんでした'
  return reason
}

function editText(edit: Edit) {
  const beforeTimes = edit.before_category
    ? `${edit.before_category} ${edit.before_clock_in} ${edit.before_clock_out} ${edit.before_break_time}`
    : '空'
  const afterTimes = `${edit.after_category} ${edit.after_clock_in} ${edit.after_clock_out} ${edit.after_break_time}`
  const beforeNote = edit.before_note || '（備考なし）'
  const afterNote = edit.after_note || '（備考なし）'
  return `${edit.editor_name} が ${beforeTimes}／備考 ${beforeNote} を ${afterTimes}／備考 ${afterNote} にしました`
}

function draftsFrom(rows: AttendanceRow[]): Record<string, Draft> {
  const next: Record<string, Draft> = {}
  for (const row of rows) {
    next[row.work_date] = row.stored
      ? {
          category: row.category,
          clock_in: row.clock_in,
          clock_out: row.clock_out,
          break_time: row.break_time,
          note: row.note,
        }
      : {
          category: '通常出勤',
          clock_in: '',
          clock_out: '',
          break_time: '',
          note: '',
        }
  }
  return next
}

function readSession(): Session | null {
  const raw = sessionStorage.getItem(SESSION_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Session
    if (!parsed.token || !parsed.employee?.display_name) return null
    return parsed
  } catch {
    return null
  }
}

function authHeaders(token: string, json = false): HeadersInit {
  if (json) {
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    }
  }
  return { Authorization: `Bearer ${token}` }
}

export default function App() {
  const [session, setSession] = useState<Session | null>(() => readSession())
  const [loginName, setLoginName] = useState(DEMO_ACCOUNTS[0].name)
  const [loginPassword, setLoginPassword] = useState('')
  const [employees, setEmployees] = useState<Employee[]>([])
  const [overview, setOverview] = useState<OverviewEmployee[]>([])
  const [view, setView] = useState<'overview' | 'days'>('days')
  const [employeeId, setEmployeeId] = useState<number | ''>(() => {
    const saved = readSession()
    if (!saved || saved.employee.is_admin) return ''
    return saved.employee.id
  })
  const [ym, setYm] = useState('2026-11')
  const [rows, setRows] = useState<AttendanceRow[]>([])
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [edits, setEdits] = useState<Edit[]>([])
  const [savedDate, setSavedDate] = useState('')
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState('')
  const [loginBusy, setLoginBusy] = useState(false)
  const [loading, setLoading] = useState(() => readSession() !== null)
  const [savingDate, setSavingDate] = useState('')
  const [csvBusy, setCsvBusy] = useState(false)
  const loadSeq = useRef(0)
  const loginLock = useRef(false)
  const saveLock = useRef('')
  const csvLock = useRef(false)
  const screenRef = useRef({
    view: 'days' as 'overview' | 'days',
    employeeId: '' as number | '',
    ym: '2026-11',
  })
  const token = session?.token ?? ''
  screenRef.current = { view, employeeId, ym }

  function clearSession() {
    loadSeq.current += 1
    sessionStorage.removeItem(SESSION_KEY)
    setSession(null)
    setOverview([])
    setEmployees([])
    setRows([])
    setDrafts({})
    setEdits([])
    setSummary(null)
    setEmployeeId('')
    setView('days')
    setLoginPassword('')
    setLoginBusy(false)
    setLoading(false)
    setSavingDate('')
    setCsvBusy(false)
    loginLock.current = false
    saveLock.current = ''
    csvLock.current = false
  }

  const loadOverview = useCallback(async () => {
    if (!API_URL) {
      setLoading(false)
      setError('API の URL が未設定です')
      return
    }
    if (!token) return
    const seq = ++loadSeq.current
    const requestedYm = ym
    setLoading(true)
    setError('')
    setOverview([])
    try {
      const res = await fetch(
        `${API_URL}/months/${encodeURIComponent(requestedYm)}/overview`,
        { headers: authHeaders(token) },
      )
      if (loadSeq.current !== seq) return
      if (res.status === 401) {
        clearSession()
        setError('ログインしてください')
        return
      }
      if (!res.ok) throw new Error('一覧を取得できませんでした')
      const data = (await res.json()) as { employees: OverviewEmployee[] }
      if (loadSeq.current !== seq) return
      const next = data.employees || []
      setOverview(next)
      setEmployees(next.map(({ id, display_name }) => ({ id, display_name })))
      setLoading(false)
    } catch {
      if (loadSeq.current !== seq) return
      setOverview([])
      setLoading(false)
      setError('一覧を取得できませんでした')
    }
  }, [ym, token])

  const loadMonth = useCallback(async (quiet = false) => {
    if (!API_URL || employeeId === '' || !token) return false
    const seq = quiet ? loadSeq.current : ++loadSeq.current
    const requestedId = employeeId
    const requestedYm = ym
    const sameScreen = () =>
      screenRef.current.view === 'days' &&
      screenRef.current.employeeId === requestedId &&
      screenRef.current.ym === requestedYm
    if (!quiet) {
      setLoading(true)
      setError('')
      setRows([])
      setDrafts({})
      setEdits([])
      setSummary(null)
      setSavedDate('')
    }
    try {
      const [rowsRes, summaryRes] = await Promise.all([
        fetch(`${API_URL}/employees/${requestedId}/months/${requestedYm}`, {
          headers: authHeaders(token),
        }),
        fetch(`${API_URL}/employees/${requestedId}/months/${requestedYm}/summary`, {
          headers: authHeaders(token),
        }),
      ])
      if (loadSeq.current !== seq || !sameScreen()) return false
      if (rowsRes.status === 401 || summaryRes.status === 401) {
        clearSession()
        setError('ログインしてください')
        return false
      }
      if (!rowsRes.ok) throw new Error('勤怠を取得できませんでした')
      if (!summaryRes.ok) throw new Error('合計を取得できませんでした')
      const rowsBody = (await rowsRes.json()) as {
        rows: AttendanceRow[]
        edits?: Edit[]
      }
      const summaryBody = (await summaryRes.json()) as { summary: Summary }
      if (loadSeq.current !== seq || !sameScreen()) return false
      const nextRows = rowsBody.rows || []
      setRows(nextRows)
      setDrafts(draftsFrom(nextRows))
      setEdits(rowsBody.edits || [])
      setSummary(summaryBody.summary)
      if (!quiet) setLoading(false)
      return true
    } catch {
      if (loadSeq.current !== seq || !sameScreen()) return false
      setRows([])
      setDrafts({})
      setEdits([])
      setSummary(null)
      if (!quiet) setLoading(false)
      setError('勤怠を取得できませんでした')
      return false
    }
  }, [employeeId, ym, token])

  useEffect(() => {
    if (!session) return
    if (view === 'overview') {
      loadOverview()
      return
    }
    loadMonth()
  }, [session, view, loadOverview, loadMonth])

  useEffect(() => {
    if (!session?.employee.is_admin || !token || !API_URL) return
    let cancelled = false
    ;(async () => {
      const res = await fetch(`${API_URL}/employees`, { headers: authHeaders(token) })
      if (!res.ok || cancelled) {
        if (!cancelled && !res.ok) {
          setLoading(false)
          setError('社員を取得できませんでした')
        }
        return
      }
      const data = (await res.json()) as { employees?: Employee[] }
      if (cancelled) return
      const next = data.employees || []
      setEmployees(next)
      setEmployeeId((current) => {
        if (typeof current === 'number' && next.some((emp) => emp.id === current)) return current
        return next[0]?.id ?? ''
      })
      if (next.length === 0) setLoading(false)
    })()
    return () => {
      cancelled = true
    }
  }, [session, token])

  function forgetDays() {
    setRows([])
    setDrafts({})
    setEdits([])
    setSummary(null)
    setSavedDate('')
  }

  function openDays(id: number) {
    setLoading(true)
    forgetDays()
    setEmployeeId(id)
    setView('days')
  }

  function updateDraft(workDate: string, patch: Partial<Draft>) {
    setSavedDate((current) => (current === workDate ? '' : current))
    setDrafts((current) => {
      const prev = current[workDate]
      if (!prev) return current
      const next = { ...prev, ...patch }
      if (patch.category === '欠勤' || patch.category === '有休') {
        next.clock_in = ''
        next.clock_out = ''
        next.break_time = ''
      }
      return { ...current, [workDate]: next }
    })
  }

  async function login(event: FormEvent) {
    event.preventDefault()
    if (loginLock.current) return
    if (!API_URL) {
      setError('API の URL が未設定です')
      return
    }
    loginLock.current = true
    setLoginBusy(true)
    setError('')
    try {
      const res = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: loginName,
          password: loginPassword,
        }),
      })
      const payload = (await res.json().catch(() => ({}))) as {
        token?: string
        employee?: Employee
        reason?: string
      }
      if (!res.ok || !payload.token || !payload.employee) {
        setError(payload.reason || '社員名かパスワードが違います')
        return
      }
      const next = { token: payload.token, employee: payload.employee }
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(next))
      setLoginPassword('')
      setLoading(true)
      setEmployeeId(payload.employee.is_admin ? '' : payload.employee.id)
      setYm('2026-11')
      setView('days')
      setSession(next)
    } catch {
      setError('ログインできませんでした')
    } finally {
      loginLock.current = false
      setLoginBusy(false)
    }
  }

  async function logout() {
    if (API_URL && token) {
      await fetch(`${API_URL}/logout`, {
        method: 'POST',
        headers: authHeaders(token),
      }).catch(() => undefined)
    }
    clearSession()
  }

  async function saveDay(workDate: string) {
    const draft = drafts[workDate]
    if (!API_URL || employeeId === '' || !draft || !token || saveLock.current || loading) return
    setError('')
    setSavedDate('')
    saveLock.current = workDate
    setSavingDate(workDate)
    try {
      const res = await fetch(
        `${API_URL}/employees/${employeeId}/months/${ym}/days/${workDate}`,
        {
          method: 'PUT',
          headers: authHeaders(token, true),
          body: JSON.stringify(draft),
        },
      )
      const payload = (await res.json().catch(() => ({}))) as { reason?: string }
      if (res.status === 401) {
        clearSession()
        setError('ログインしてください')
        return
      }
      if (!res.ok) {
        setSavedDate('')
        setError(saveError(payload.reason, res.status))
        await loadMonth(true)
        return
      }
      const applied = await loadMonth(true)
      if (applied) {
        setSavedDate(workDate)
        setError('')
      }
    } catch {
      setSavedDate('')
      setError('保存できませんでした')
    } finally {
      saveLock.current = ''
      setSavingDate('')
    }
  }

  async function probeUnimplemented() {
    if (!API_URL) {
      setError('API の URL が未設定です')
      return
    }
    setError('')
    try {
      const res = await fetch(`${API_URL}/demo/unimplemented`)
      const payload = (await res.json().catch(() => ({}))) as { reason?: string }
      setError(payload.reason || '未実装の機能を呼べませんでした')
    } catch {
      setError('未実装の機能を呼べませんでした')
    }
  }

  async function downloadCsv() {
    if (csvLock.current) return
    if (!API_URL) {
      setError('API の URL が未設定です')
      return
    }
    if (!token) return
    csvLock.current = true
    setCsvBusy(true)
    setError('')
    try {
      const res = await fetch(`${API_URL}/months/${encodeURIComponent(ym)}/export`, {
        headers: authHeaders(token),
      })
      if (res.status === 401) {
        clearSession()
        setError('ログインしてください')
        return
      }
      if (!res.ok) throw new Error('csv')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `kintai-${ym}.csv`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch {
      setError('CSVを出せませんでした')
    } finally {
      csvLock.current = false
      setCsvBusy(false)
    }
  }

  if (!session) {
    return (
      <main>
        <h1>勤怠デモ</h1>
        <p className="note">
          社員名を選び、表のパスワードを入れてログインします。役割が管理者の人は、ログイン後に全員の勤怠を開けます。本人は自分の月だけです。
        </p>
        <table className="accounts">
          <caption>デモ用のパスワード</caption>
          <thead>
            <tr>
              <th>社員名</th>
              <th>役割</th>
              <th>パスワード</th>
            </tr>
          </thead>
          <tbody>
            {DEMO_ACCOUNTS.map((account) => (
              <tr key={account.name}>
                <td>{account.name}</td>
                <td>{account.role}</td>
                <td>{account.password}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <form className="controls" onSubmit={login}>
          <label>
            社員名
            <select
              aria-label="社員名"
              value={loginName}
              onChange={(e) => setLoginName(e.target.value)}
            >
              {DEMO_ACCOUNTS.map((account) => (
                <option key={account.name} value={account.name}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            パスワード
            <input
              aria-label="パスワード"
              type="text"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              autoComplete="off"
            />
          </label>
          <button type="submit" disabled={loginBusy}>
            {loginBusy ? 'ログインしています' : 'ログイン'}
          </button>
        </form>
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}
      </main>
    )
  }

  return (
    <main>
      <h1>勤怠デモ</h1>
      <div className="shell">
        {session.employee.is_admin ? (
          <nav className="menu" aria-label="勤怠メニュー">
            <button
              type="button"
              aria-current={view === 'days' ? 'page' : undefined}
              onClick={() => {
                if (view === 'days') return
                setLoading(true)
                forgetDays()
                setView('days')
              }}
            >
              個別の勤怠
            </button>
            <button
              type="button"
              aria-current={view === 'overview' ? 'page' : undefined}
              onClick={() => {
                setLoading(true)
                setOverview([])
                setView('overview')
              }}
            >
              全員の勤怠
            </button>
          </nav>
        ) : null}
        <div className="content">
          <p className="who">
            <span>ログイン中: {session.employee.display_name}</span>
            <button type="button" onClick={() => logout()}>
              ログアウト
            </button>
            <button type="button" className="probe" onClick={() => probeUnimplemented()}>
              未実装の機能を試す
            </button>
          </p>
          {view === 'overview' ? (
            <p className="note">
              選んだ月の3人の合計です。「日ごとを入力」を押すと、その人の日ごとを入力できます。
            </p>
          ) : (
            <p className="note">
              11月2日から20日までは初期データです。1日と21日以降は空なので、その場で入力できます。保存した内容は、このデモを開いている人のあいだで共有されます。半休の実働は、入れた時刻から計算します。
            </p>
          )}

          <div className="controls">
            {view === 'days' && session.employee.is_admin ? (
              <label>
                社員
                <select
                  value={employeeId === '' ? '' : String(employeeId)}
                  onChange={(e) => {
                    setLoading(true)
                    forgetDays()
                    setEmployeeId(e.target.value ? Number(e.target.value) : '')
                  }}
                >
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.display_name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label>
              月
              <input
                type="month"
                value={ym}
                onChange={(e) => {
                  setLoading(true)
                  forgetDays()
                  setOverview([])
                  setYm(e.target.value)
                }}
              />
            </label>
            {view === 'overview' ? (
              <button type="button" disabled={csvBusy} onClick={() => downloadCsv()}>
                {csvBusy ? '出しています' : 'この月をCSVで出す'}
              </button>
            ) : null}
          </div>

          {error ? (
            <p className="error" role="alert">
              {error}
            </p>
          ) : null}
          {loading ? <p className="note">読み込んでいます</p> : null}

          {view === 'overview' ? (
            <table>
              <thead>
                <tr>
                  <th>表示名</th>
                  <th>出勤日数</th>
                  <th>総実働（時間）</th>
                  <th>8時間超過（時間）</th>
                  <th>退勤なし件数</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {overview.map((emp) => (
                  <tr key={emp.id}>
                    <td>{emp.display_name}</td>
                    <td>{emp.summary.workday_count}</td>
                    <td>{emp.summary.total_worked_hours}</td>
                    <td>{emp.summary.overtime_hours}</td>
                    <td>{emp.summary.missing_clock_out_count}</td>
                    <td>
                      <button type="button" onClick={() => openDays(emp.id)}>
                        日ごとを入力
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}

      {view === 'days' ? (
      <>
      {summary ? (
        <dl className="summary">
          <div>
            <dt>出勤日数</dt>
            <dd>{summary.workday_count}</dd>
          </div>
          <div>
            <dt>総実働（時間）</dt>
            <dd>{summary.total_worked_hours}</dd>
          </div>
          <div>
            <dt>8時間超過（時間）</dt>
            <dd>{summary.overtime_hours}</dd>
          </div>
          <div>
            <dt>退勤なし件数</dt>
            <dd>{summary.missing_clock_out_count}</dd>
          </div>
        </dl>
      ) : null}

      <table>
        <thead>
          <tr>
            <th>日付</th>
            <th>区分</th>
            <th>出勤</th>
            <th>退勤</th>
            <th>休憩</th>
            <th>備考</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const draft = drafts[row.work_date]
            if (!draft) return null
            return (
              <tr key={row.work_date}>
                <td>{row.work_date}</td>
                <td>
                  <select
                    aria-label={`${row.work_date} 区分`}
                    value={draft.category}
                    onChange={(e) =>
                      updateDraft(row.work_date, { category: e.target.value })
                    }
                  >
                    <option value="通常出勤">通常出勤</option>
                    <option value="半休">半休</option>
                    <option value="有休">有休</option>
                    <option value="欠勤">欠勤</option>
                  </select>
                </td>
                <td>
                  <input
                    aria-label={`${row.work_date} 出勤`}
                    value={draft.clock_in}
                    onChange={(e) =>
                      updateDraft(row.work_date, { clock_in: e.target.value })
                    }
                  />
                </td>
                <td>
                  <input
                    aria-label={`${row.work_date} 退勤`}
                    value={draft.clock_out}
                    onChange={(e) =>
                      updateDraft(row.work_date, { clock_out: e.target.value })
                    }
                  />
                </td>
                <td>
                  <input
                    aria-label={`${row.work_date} 休憩`}
                    value={draft.break_time}
                    onChange={(e) =>
                      updateDraft(row.work_date, { break_time: e.target.value })
                    }
                  />
                </td>
                <td>
                  <input
                    aria-label={`${row.work_date} 備考`}
                    value={draft.note}
                    onChange={(e) =>
                      updateDraft(row.work_date, { note: e.target.value })
                    }
                  />
                </td>
                <td>
                  {loading ? null : (
                    <button
                      type="button"
                      disabled={savingDate !== ''}
                      onClick={() => saveDay(row.work_date)}
                    >
                      {savingDate === row.work_date ? '保存しています' : `${row.work_date} を保存`}
                    </button>
                  )}
                  {savedDate === row.work_date && savingDate !== row.work_date ? (
                    <p className="saved">保存しました</p>
                  ) : null}
                  <ul className="edits">
                    {edits
                      .filter((edit) => edit.work_date === row.work_date)
                      .map((edit) => (
                        <li key={edit.id}>{editText(edit)}</li>
                      ))}
                  </ul>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      </>
      ) : null}
        </div>
      </div>
    </main>
  )
}
