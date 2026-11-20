# 設計

## 前提

見本の置き場は `C:\00_remote_git\GitHub\wizway-kintai-demo`。OpenSpec の初回化は済んでいる。アプリのコードはまだ無い。動機は proposal.md の「なぜ」。振る舞いの契約は `specs/attendance-month` と `specs/attendance-summary`。

現行勤怠の時間計算は PHP にある。この初版は、同じ意味の一部（休憩を引く、8時間超過、退勤なし、欠勤）を SQL の結果として返す。PHP のソースはコピーしない。

## 目標 / 対象外

**目標:**
- 画面、API、SQL、載せる先の対応を1リポジトリで説明できる初版にする
- デプロイ前に、向け先が本番勤怠のアカウントでないことを確認する
- 挙動を変える作業は、Serena が接続しているときだけ始める

**対象外:**
- 日次の保存、深夜、休日出勤、日付をまたぐ時刻
- 本番勤怠のリポジトリ、開発 VM、本番アカウントへの変更

## 決定事項

### 1. リポジトリと構成の対応

置き場は `wizway-kintai-demo`。中身は次で対応させる。

| 役割 | 置き場 |
|------|--------|
| 画面（社員選択、月の行、合計） | `frontend/`（React + TypeScript、Vite） |
| 読み取り API | `backend/`（Python Lambda） |
| 表定義、シード、合計の SELECT | `sql/` |
| SAM（HTTP API、Lambda、S3、CloudFront） | `template.yaml` |
| 構成図 | `docs/` の draw.io |
| Serena 必須の手順 | `.cursor/rules/openspec-serena-workflow.mdc` と `.cursor/skills/openspec-apply-change/SKILL.md`、`.cursor/skills/openspec-propose/SKILL.md` |
| Serena の起動設定 | `.cursor/mcp.json`（このリポジトリを cwd にする） |

Lambda は `sql/` から作った SQLite ファイルを同梱し、読み取りだけ行う。DynamoDB も RDS も template に足さない。

代替として本番と同じ MariaDB に繋ぐ案は取らない。接続先を誤ると実データが見える。

### 2. API の切り方

- `GET /employees` … 識別子と表示名
- `GET /employees/{id}/months/{ym}` … その月の行。`ym` は `YYYY-MM`
- `GET /employees/{id}/months/{ym}/summary` … 出勤日数、総実働、8時間超過、退勤なし件数
- `ym` が `YYYY-MM` でないときは 400。社員が無いときは 404。どちらも行も合計も返さない
- 400 のときは、年月が不正である理由をログに1行出す

画面は1枚で、社員と月を選ぶと行と合計を並べる。保存ボタンは置かない。

ダミーは3人。表示名は実在の社員と重ならない名にする。対象月は `2026-11` をシードし、通常出勤、8時間超過、退勤なし、欠勤が仕様のシナリオどおりに1件ずつ以上ある人を含める。

代替として DynamoDB に行を置く案は取らない。合計を SQL で見せるため。

### 3. 実働の計算

通常出勤で出勤と退勤がある行だけ、実働は「退勤 − 出勤 − 休憩」。8時間を超えた分だけを残業に足す。退勤が無い行と欠勤は実働に足さない。退勤が無い行は件数に数える。欠勤は出勤日数に入れない。時刻は同一日の時分で、日付をまたがない。

この計算は `sql/` の SELECT に書き、Lambda はその結果を返す。Python 側で同じ式を持ち直さない。

### 4. Serena を必須にする場所

勤怠リポジトリの apply スキルにある「接続できないなら実装を始めない」ゲートを、このリポジトリの次のファイルへ書く。

- `.cursor/skills/openspec-apply-change/SKILL.md`
- `.cursor/skills/openspec-propose/SKILL.md`（既存コードを読む propose も、接続できないなら進めない）
- `.cursor/rules/openspec-serena-workflow.mdc`（常時適用の要約）

ゲートの中身は、Serena の `initial_instructions` を呼び、失敗したら実装とコード編集を止める、までにする。PHP、開発 VM、`php -l`、給与、本番反映の文はコピーしない。編集対象は `frontend/`、`backend/`、`sql/`、`template.yaml`。

`.cursor/mcp.json` には、このリポジトリをプロジェクトルートにした Serena を書く。デプロイ用の Serverless MCP は雑メモ見本と同じ形で併記し、プロファイル名はプレースホルダのままにする。実プロファイル名とトークンは書かない。

### 5. デプロイ先の確認

載せる先は、実績づくりの学習用アカウントに作る別スタック（スタック名 `wizway-kintai-demo`）だけにする。

デプロイコマンドの前に、呼び出し元のアカウントが本番勤怠のアカウントでないことを確認する。確認できないときはデプロイしない。本番のスタック名や本番のバケットは操作しない。

公開 URL が取れたあと、README と学習パックの導入メモ（common と、ウィズウェイへ配っている版）にその URL を書く。コース本文には書かない。GitHub への push は、ユーザーが指示したときだけ行う。

## リスク / トレードオフ

- [SQLite の接続先を後から差し替える] → 接続先は同梱ファイルに固定し、環境変数で DB ホストを受け取らない
- [学習用アカウントと本番アカウントの取り違え] → デプロイタスクの最初の手順をアカウント確認にし、違うときは中止する
- [Serena 未接続だと初版の実装も止まる] → 止めるのがこのリポジトリの約束。スキルに再開手順を書く
- [Lambda の読み取り専用ファイルは更新できない] → 初版は保存しない。保存は次の change で、置き場を決めてから足す

## 移行手順

1. Serena の設定と、apply / propose スキルのゲートを先に置く
2. `sql/`、API、画面、`template.yaml` の順で初版を作る
3. ローカルで、仕様のシナリオ（09:00–18:00 休憩 1 時間、9 時間、退勤なし、欠勤、不正な年月）を確認する
4. アカウント確認のあと、学習用アカウントへデプロイする
5. README と導入メモに URL を書く
6. 戻すときはスタック `wizway-kintai-demo` だけを削除する。雑メモのスタックと本番勤怠には触らない

## 未決事項

なし。仕様、構成、タスクの分割を変える未決は残っていない。
