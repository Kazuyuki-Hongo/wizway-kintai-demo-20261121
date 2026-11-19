# wizway-kintai-demo core

学習パック向け勤怠デモ。本番 `wizway_kintai` / `kintai.wizway.co.jp` とは別リポ。ソース・DB・VM・本番 AWS に触らない。
ダミー SQLite のみ。実在社員名・給与・住所・生年月日禁止。秘密を成果物に書かない。

## Source map
- `frontend/` — React+TS 画面（社員・月選択、行と合計。保存ボタン無し）
- `backend/app.py` — Lambda 読み取り API。`backend/data/attendance.db` + `backend/sql/`
- `sql/` — schema/seed/month_rows/month_summary。実働計算はここ。Python で同じ式を持ち直さない
- `template.yaml` — HTTP API + Lambda + S3 + CloudFront。DynamoDB/RDS 禁止
- `docs/rules/project-rules-serena.md` — Serena Rules 正本
- `openspec/` — 仕様駆動。schema `spec-driven`
- `tests/e2e/` + ルート Playwright — ログイン無し E2E
- `backend/tests/` — pytest（lambda_handler 直叩き）

## Invariants
- 挙動変更は OpenSpec change + Serena（`initial_instructions` ゲート）。編集範囲: frontend/backend/sql/template.yaml
- 例外: `docs/<案件>/` で OpenSpec 対象外と明示 → `mem:docs-spec-driven`（Serena は必須のまま）
- 学習用 AWS のみデプロイ。本番箱（例: 023194178508）なら中止。スタック名 `wizway-kintai-demo`
- 見本 URL は README と学習パック導入メモのみ。コース本文に書かない
- 利用者に見える文は日本語。詳細は `mem:user-facing-language`
- HTTP API stage `/prod` は `_path` で strip

## Further
- スタック・コマンド: `mem:tech_stack` / `mem:suggested_commands`
- 作法・完了条件: `mem:conventions` / `mem:task_completion`
- 画面: `mem:frontend/core`
- API/SQL: `mem:backend/core`
- OpenSpec: `mem:openspec/core`
- OpenSpec なし（docs 仕様駆動）: `mem:docs-spec-driven`
