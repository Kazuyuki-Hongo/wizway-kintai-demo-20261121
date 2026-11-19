# task_completion

挙動変更タスクを完了とみなす前:

1. OpenSpec `tasks.md` の該当チェックを `- [x]`（指定どおり実装済みのときだけ）
2. `python sql/build_db.py`（schema/seed を変えたとき）
3. `npm run test:api`（PYTHONNOUSERSITE を外す）
4. 画面・API 契約を変えたらローカル `npm run pw:test:attendance`（`PLAYWRIGHT_BASE_URL` 無し）
5. 理想順: ローカル E2E 緑 → 学習用 identity 確認 → sam deploy → フロント sync → CloudFront invalidate → `PLAYWRIGHT_BASE_URL` を CloudFront に向けて AWS E2E。ローカル赤のままデプロイしない
6. docs 仕様駆動案件は実装計画のチェックリストを `- [x]` に更新（`mem:docs-spec-driven`）
7. URL 変更時のみ README + 導入メモ（common/ウィズウェイ）。コース本文は触らない
8. 安定した規約が増えたら Serena memory を更新（`mem:core` から参照を辿る）

任意: プロジェクトルートで `serena memories check`
