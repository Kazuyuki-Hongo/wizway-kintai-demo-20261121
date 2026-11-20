# 設計

## 前提

見本の置き場は `C:\00_remote_git\GitHub\wizway-kintai-demo`。動機は proposal.md の「なぜ」。振る舞いの契約は `specs/attendance-day-update`、`specs/attendance-month`、`specs/attendance-summary`。

いまの読み取りは `backend/app.py` の GET と、`file:{seed}?mode=ro` の SQLite。月の行は `sql/month_rows.sql` が `attendance_rows` だけを返す。合計の式は `sql/month_summary.sql`。画面は `frontend/src/App.tsx` の1枚で、保存操作は無い。Lambda の配置物は `template.yaml` の `CodeUri: backend/`。`sql/` と同じ SELECT が `backend/sql/` にもある。

## 目標 / 対象外

**目標:**
- 同梱の SQLite を初期データにしたまま、実行環境のコピーへ更新を書く
- 月の読み取りはカレンダーの全日を返し、保存済みかどうかを区別する
- 合計の式は SQL のままにする
- デプロイ前に、向け先が本番勤怠のアカウントでないことを確認する

**対象外:**
- 保存済みでない日への INSERT、行の削除
- データファイルの正本を S3、DynamoDB、RDS に移すこと
- Serena の接続ゲート自体の変更。ゲートは既に `.cursor/skills/openspec-apply-change/SKILL.md`、`.cursor/skills/openspec-propose/SKILL.md`、`.cursor/rules/openspec-serena-workflow.mdc` にある

## 決定事項

### 1. 書き込みは実行環境のコピーだけ

初期データは `backend/data/attendance.db` のまま開かない。プロセスは、そのファイルを読み取り専用でコピーし、コピーを読み書きする。

| 実行 | コピー先 |
|------|----------|
| Lambda（`AWS_LAMBDA_FUNCTION_NAME` がある） | `/tmp/attendance.db`。ファイルが既にあるときはコピーしない |
| ローカルの API プロセス | 起動のたびに一時ファイルへコピーする |
| pytest | テストが渡す一時ファイル。環境変数 `KINTAI_RUNTIME_DB` でパスを指定する |

パスは import 時に固定しない。接続のたびに決める。初期データファイルへ `UPDATE` しない。

代替として配置物の SQLite を直接開く案は取らない。Lambda の配置物は更新できない。S3 にファイルを置く案は、この change では取らない。公開 URL の保存は、同じ実行環境が生きているあいだだけ見える。

### 2. API

- `PUT /employees/{id}/months/{ym}/days/{date}`
- JSON は `category`、`clock_in`、`clock_out`、`break_time` の4キー。空文字は空。キーが無いときは 400 で更新しない
- 成功は 200。返した日は `stored: true` と、保存した区分・時刻
- 検証拒否、年月の形が違う、月が 01〜12 でない、日付がその月に無い、は 400。理由を JSON の `reason` とログ1行に出す
- 社員が無い、その日が保存済みでない、は 404。行は作らない
- 日のパスは、月のパスより先に判定する。いまの月の正規表現が `/days/...` を年月として吸い込まないようにする
- CORS と `template.yaml` の HTTP API に PUT を足す。GET の3本は残す

検証は Python で、`UPDATE` の前に行う。空文字は DB では NULL。通常出勤は出勤が必須。退勤が空の行は残せる。退勤があるときは、退勤の分が出勤の分以上であり、休憩の分は（退勤−出勤）以下である。欠勤は3つの時刻がすべて空。区分は `通常出勤` と `欠勤` だけ。時刻は `HH:MM` かつ 00:00〜23:59。

実働と8時間超過は、更新後の `GET .../summary` が既存の `month_summary.sql` を読んだ結果だけにする。Python に同じ式を持たない。

### 3. 月の行

`sql/month_rows.sql` を、その月の各日を再帰 CTE で作り、`attendance_rows` を左結合する SELECT に変える。保存済みでない日は区分と時刻を空にし、`stored` を偽にする。保存済みの日は `stored` を真にする。`backend/sql/month_rows.sql` も同じ内容にする。Lambda は `backend/sql/` を読む。

`month_summary.sql` の式は変えない。保存済みでない日は `attendance_rows` に無いので合計に入らない。

年月の 01〜12 判定は、月の GET、合計の GET、日の PUT で同じ関数を使う。`2026-13` は 400。

### 4. 画面

`frontend/src/App.tsx` の表は、返った日をすべて出す。保存済みの行だけ、区分の選択、時刻の入力、その日の保存ができる。保存済みでない行は空のまま入力できない。保存の成功後に、月の行と合計を読み直す。API の `reason` を画面のエラーに出す。見出しの「読み取り専用」と「保存操作はありません」は、実行環境のコピーに保存することと、やり直すと初期データに戻ることを書く文に変える。

### 5. テストとデプロイ先

pytest は一時コピーに対して更新と拒否を確認し、`backend/data/attendance.db` のバイト列が変わらないことを確認する。Playwright は 2026-11 の空日が表示されること、保存済みの日を変えると合計が変わること、拒否が画面に出ることを確認する。

載せる先はスタック `wizway-kintai-demo` だけ。デプロイコマンドの前に、呼び出し元のアカウントが本番勤怠のアカウントでないことを確認する。確認できないときはデプロイしない。見本 URL が同じなら、導入メモは変えない。

## リスク / トレードオフ

- [公開 URL では別の実行環境に当たると保存が見えない] → 画面に、保存は実行環境のあいだだけ残り、やり直すと初期データに戻る、と書く。ローカルと pytest は一時コピーで仕様の Scenario を確認する
- [温かい Lambda の `/tmp` が保存を持ち続ける] → 実行環境が新しいときだけ初期データからコピーする。戻す操作は、この change では付けない
- [`sql/` と `backend/sql/` がずれる] → 変える SELECT は両方に同じ内容を置く
- [学習用アカウントと本番アカウントの取り違え] → デプロイタスクの最初の手順をアカウント確認にし、違うときは中止する

## 移行手順

1. SQL、API、画面、`template.yaml`、テストの順で足す
2. ローカルで、更新の成功、拒否、2026-11 の30日、2026-02 の28日、合計の再計算を確認する
3. アカウント確認のあと、学習用アカウントのスタック `wizway-kintai-demo` を更新する
4. 載った URL で、空日と、保存済みの日の更新が見えることを確認する
5. 戻すときは、この change の前の配置にスタック `wizway-kintai-demo` だけを戻す。実行環境のコピーは、実行環境が終われば消える
