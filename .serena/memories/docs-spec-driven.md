# docs フォルダ仕様駆動（OpenSpec なし）

要件が `docs/<案件>/要件定義書.md`、手順が同フォルダ `実装計画.md` にあり、OpenSpec 対象外と明示された案件向け。
通常の OpenSpec 必須は `mem:openspec/core`。例外時だけこちら。

## 正本
- 仕様: 要件定義書のみ。再発明しない
- 手順: 実装計画の Phase / Step。編集対象・完了条件を守る
- 進捗: 実装計画のタスクチェックリスト。完了で `- [x]`
- Cursor: `.cursor/rules/docs-spec-driven.mdc`
- Rules: `docs/rules/project-rules-serena.md` の「OpenSpec なし」

## Build
1. Serena `initial_instructions`（必須）
2. OpenSpec change／specs は作らない
3. Step 順。チェックリスト更新
4. 検証理想: ローカル API → **ローカル E2E 緑** → **学習用 AWS デプロイ** → **AWS E2E**（`PLAYWRIGHT_BASE_URL`=CloudFront）
5. ローカル E2E 赤のままデプロイしない
6. AWS E2E 前（と後）: 共有 DB が汚れていたら `aws s3 cp backend/data/attendance.db s3://wizway-kintai-demo-db-655129713987/attendance.db --profile deploy-jisseki` でシードに戻す。E2E は保存で共有 DB を変えるので、合計固定のケースより前に空日を新規出勤にしない（既存日へ備考だけ等）

## 例
- `docs/日ごとの備考/`（備考 note）
