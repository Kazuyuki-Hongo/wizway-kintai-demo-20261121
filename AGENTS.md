# AGENTS.md

- 画面は React ＋ TypeScript（`.tsx`）。Vite の `react-ts` に合わせる
- API は Python Lambda。データは同梱 SQLite（`backend/data/attendance.db`）
- SAM の `template.yaml` を勝手に大きくしない。DynamoDB・RDS・コンテナ常時起動は足さない
- 本番の勤怠（wizway_kintai）とは別。実在社員名・給与・住所・生年月日は使わない
- Serena ルール正本: `docs/rules/project-rules-serena.md`。挙動変更は OpenSpec + Serena 必須（例外: `docs/<案件>/` で OpenSpec 対象外と明示 → `.cursor/rules/docs-spec-driven.mdc`）
- 画面・API 契約変更の検証理想: ローカル E2E 緑 → 学習用 AWS デプロイ → CloudFront 向け AWS E2E
