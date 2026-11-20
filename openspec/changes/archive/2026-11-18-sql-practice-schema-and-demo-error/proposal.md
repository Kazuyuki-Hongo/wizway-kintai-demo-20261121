# 変更提案

## なぜ

学習パックの「現場でよく使う型」を、架空 EC スキーマではなく本リポジトリのローカル SQLite で通す。  
複雑 SQL・seed・ログ切り分けの演習土台を、勤怠ドメインに揃える。

## 変更内容

- 画面なしで、勤怠管理向けの表とデモ用データを SQLite に足す（部署・休暇申請・承認履歴など）
- 既存の勤怠画面・API の挙動は変えない（新表は API から読まない）
- 学習用の意図的 ERROR 経路 `GET /demo/error` を足す（CloudWatch／ログ演習用）
- HTTP API に `/demo/error` を載せる
- 本番勤怠リポジトリ・本番 AWS アカウントは変更しない

## 対象能力

### 新規の能力

- `attendance-sql-practice`: ローカル SQLite 上の演習用スキーマとデモデータ（画面・API 非公開）
- `demo-error`: 学習用に意図的に 500 と traceback を出す経路

### 変更する能力

- （なし）既存の勤怠画面・読み書き API の要件は変えない

## 影響範囲

- `sql/schema.sql` / `sql/seed.sql` / `sql/build_db.py`（必要なら検証スクリプト）
- `backend/data/attendance.db`（build し直し）
- `backend/app.py`（`GET /demo/error`）
- `template.yaml`（`/demo/error` ルート）
- `backend/tests/`（ERROR 経路のテスト）
- README（ローカル SQLite 演習・ERROR 経路の一行）
- フロントエンドの画面変更はしない
