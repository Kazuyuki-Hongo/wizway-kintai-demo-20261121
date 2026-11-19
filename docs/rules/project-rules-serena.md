# wizway-kintai-demo — Serena Project Rules

Serena MCP で Spec / Plan / Build を進めるときのプロジェクト固有ルール。  
Cursor 側の一般ルールと矛盾する場合は本ドキュメントを優先する。

実装手順の正本: `.cursor/skills/openspec-apply-change/SKILL.md`  
常時ゲート要約: `.cursor/rules/openspec-serena-workflow.mdc`

---

## 1. 概要

| 項目 | 内容 |
|------|------|
| 名前 | `wizway-kintai-demo` |
| 目的 | 学習パック向け。仕様駆動（OpenSpec）＋ Serena 必須の勤怠デモ |
| 本番勤怠 | **別物**（`wizway_kintai` / `kintai.wizway.co.jp`）。ソース・DB・VM・本番 AWS に触れない |
| データ | ダミーのみ。実在社員名・給与・住所・生年月日を出さない |
| ログイン | 無し（初版） |
| 保存 | 初版は読み取りのみ。書き込みは別 OpenSpec change で設計してから |

### 技術スタック

| レイヤ | 技術 |
|--------|------|
| 画面 | React + TypeScript、Vite（`frontend/`） |
| API | Python 3.13 Lambda（`backend/app.py`） |
| 計算 | SQL（`sql/`）。Python で同じ実働式を持ち直さない |
| DB | 同梱 SQLite（`backend/data/attendance.db`）。DynamoDB / RDS 禁止 |
| 載せ方 | SAM `template.yaml`、HTTP API、S3、CloudFront |

### 公開見本（学習用アカウント）

- 画面: `https://d266q7koncqwt6.cloudfront.net`
- API: `https://335nxj9000.execute-api.ap-northeast-1.amazonaws.com/prod`
- スタック名: `wizway-kintai-demo`
- デプロイ先: 学習用 AWS のみ（例: Account `655129713987`）。本番箱 `023194178508` には出さない

---

## 2. ディレクトリと編集範囲

```
frontend/     React 画面
backend/      Lambda + 同梱 sql コピー + attendance.db
sql/          schema / seed / month_rows / month_summary / build_db.py
template.yaml SAM
docs/         構成図・本 Rules
openspec/     仕様駆動成果物
tests/e2e/    Playwright（ルートの playwright.config.ts）
```

**編集してよい:** `frontend/`、`backend/`、`sql/`、`template.yaml`、テスト、`docs/`、OpenSpec artifacts、`.cursor/` の Serena ゲート関連  
**触らない:** 本番勤怠リポジトリ、MariaDB 接続先への差し替え、DynamoDB/RDS の追加（change で明示承認がある場合のみ例外）

---

## 3. API 契約（初版）

| 経路 | 内容 |
|------|------|
| `GET /employees` | id + display_name |
| `GET /employees/{id}/months/{ym}` | 月の行。`ym` = `YYYY-MM` |
| `GET /employees/{id}/months/{ym}/summary` | 出勤日数・総実働・超過・退勤なし件数 |

- 不正な `ym` → 400。ログに `invalid ym=... reason=expected YYYY-MM` を1行
- 社員無し → 404。行も合計も返さない
- HTTP API の `/prod/...` 接頭辞は `_path` で落とす

実働: 通常出勤かつ出勤・退勤・休憩あり → `退勤 - 出勤 - 休憩`。8時間超過のみ残業。退勤なしは件数のみ。欠勤は出勤日数に入れない。

---

## 4. OpenSpec + Serena

| 作業 | OpenSpec | Serena |
|------|----------|--------|
| 挙動変更・複数ファイル | 必須 | 必須（`initial_instructions` ゲート） |
| docs フォルダ仕様駆動（要件で OpenSpec 対象外と明示） | 不要 | 必須 |
| コメント・typo・ドキュメントのみ | 不要 | 不要 |

1. セッション初回: Serena `initial_instructions`
2. 失敗したら実装しない。接続後に `/opsx-apply` をやり直す（OpenSpec 案件）
3. 既存コードは `get_symbols_overview` / `find_symbol` / `search_for_pattern` を優先
4. 行番号は Serena **0-based**
5. PHP・開発 VM・`php -l` の手順は持ち込まない

### OpenSpec なし（docs フォルダ仕様駆動）

要件・計画が `docs/<案件名>/要件定義書.md` と `実装計画.md` にあり、OpenSpec 対象外と書いてあるとき:

- 仕様の唯一ソースは要件定義書。実装手順の正本は実装計画の Phase / Step
- OpenSpec change／specs は作らない。仕様の再発明もしない
- 実装計画のタスクチェックリストを進捗の正とし、完了したら `- [x]`
- Cursor ルール: `.cursor/rules/docs-spec-driven.mdc`。Serena: `mem:docs-spec-driven`
- 例: `docs/日ごとの備考/`

---

## 5. テストと完了

| 種類 | コマンド |
|------|----------|
| API ユニット | `npm run test:api`（`python -m pytest backend/tests -q`） |
| ローカル E2E | `npm run pw:test:attendance`（`PLAYWRIGHT_BASE_URL` 無し） |
| AWS E2E | `$env:PLAYWRIGHT_BASE_URL='https://d266q7koncqwt6.cloudfront.net'; npm run pw:test:attendance` |
| DB 再生成 | `python sql/build_db.py` |

画面・API 契約を変えた案件の理想順: **ローカル E2E 緑 → 学習用 AWS デプロイ → AWS E2E パス**。ローカルが赤のままデプロイしない。

`PYTHONNOUSERSITE=1` のシェルでは user の pytest が見えないことがある。外してからユニットを回す。

---

## 6. デプロイ

1. `aws sts get-caller-identity` で学習用アカウントを確認。本番勤怠の箱なら中止
2. Windows で SAM が botocore で落ちるとき: `$env:PYTHONNOUSERSITE='1'`
3. `sam build` → `sam deploy --profile <学習用 Deployer>`
4. フロント: `frontend/.env.production` の `VITE_API_URL` → `npm run build` → S3 sync → CloudFront invalidate
5. 見本 URL の更新は README と学習パック `導入メモ.md`（common / ウィズウェイ版）のみ。コース本文には書かない

プロファイル例（このマシン）: 学習用 Deployer は `deploy-jisseki`。`deploy` は本番箱を向くことがあるので勤怠デモには使わない。
