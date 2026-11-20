# タスク

## 1. Serena を必須にする

- [x] 1.1 `.cursor/mcp.json` に、このリポジトリをプロジェクトルートにした Serena と、雑メモ見本と同じ形の Serverless MCP を書く。プロファイル名はプレースホルダのままにし、ファイルに実名とトークンが無いことを確認する
- [x] 1.2 `.cursor/skills/openspec-apply-change/SKILL.md` と `.cursor/skills/openspec-propose/SKILL.md` に、Serena の `initial_instructions` が失敗したら実装を始めないゲートを書く。PHP、開発 VM、`php -l` の手順が残っていないことを確認する
- [x] 1.3 `.cursor/rules/openspec-serena-workflow.mdc` に、挙動変更は OpenSpec と Serena が必須であることを常時適用で書く。編集対象が `frontend/`、`backend/`、`sql/`、`template.yaml` になっていることを確認する

## 2. SQL と合計

- [x] 2.1 `sql/` に表定義と、ダミー3人・`2026-11` のシードを置く。通常出勤、8時間超過、退勤なし、欠勤が各1件以上あり、表示名に実在社員が無いことを SELECT で確認する
- [x] 2.2 月の合計 SELECT を `sql/` に置き、09:00–18:00 休憩 1 時間が実働 8 時間・超過 0、実働 9 時間が超過 1 時間、退勤なしは件数のみ、欠勤は出勤日数に入らないことを、ローカルの SQLite で確認する

## 3. 読み取り API

- [x] 3.1 `GET /employees`、`GET /employees/{id}/months/{ym}`、`GET /employees/{id}/months/{ym}/summary` を `backend/` に実装し、2.2 と同じ行が JSON で返ることをローカル起動で確認する
- [x] 3.2 `ym` が `2026/11` のとき 400 で行も合計も返さず、ログに理由が1行残ることを確認する。ダミーに無い社員は 404 で行も合計も返さないことを確認する

## 4. 画面

- [x] 4.1 `frontend/` に、社員と月を選ぶと行と合計を1画面に出す React + TypeScript を置く。保存操作が無いことを画面で確認する
- [x] 4.2 ダミーの `2026-11` で、退勤が空の行と、合計の出勤日数・総実働・超過・退勤なし件数が API と一致することを画面で確認する

## 5. SAM

- [x] 5.1 `template.yaml` に HTTP API、Lambda、S3、CloudFront を書く。DynamoDB と RDS が無く、Lambda が `sql/` 由来の SQLite を同梱していることを template とパッケージ内容で確認する
- [x] 5.2 `docs/` に、ブラウザ、CloudFront、API、Lambda、SQLite の draw.io を1枚置く。図の箱が template のリソースと一致することを目視で確認する

## 6. デプロイ

- [x] 6.1 デプロイ前に呼び出し元アカウントを確認し、本番勤怠のアカウントなら中止する。学習用アカウントのときだけスタック `wizway-kintai-demo` を載せる。載った URL で社員一覧と `2026-11` の行・合計がローカルと同じことを確認する

## 7. 見本 URL

- [x] 7.1 README に載った URL と、ダミー専用であることを書く。学習パックの導入メモ（common と、ウィズウェイへ配っている版）に同じ URL を1行足し、コース本文に URL が無いことを確認する

## 作業後の続き

- ソースの GitHub への push は、ユーザーが指示してから行う
- レビューが済んだらこの change を archive する
