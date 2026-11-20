# タスク

## 1. 演習用スキーマと seed

- [x] 1.1 `sql/schema.sql` に `departments` / `employees.department_id` / `leave_requests` / `leave_approvals` を追加し、`python sql/build_db.py` が成功することを確認する
- [x] 1.2 `sql/seed.sql` に部署・社員紐付け・休暇申請の境界ケース（draft/submitted/approved/rejected、承認あり／なし、同一申請に承認2行以上）を入れ、表件数を SQL で確認する
- [x] 1.3 既存の月次読み取りテスト（または `local_check`）が通ることを確認する

## 2. 意図的 ERROR 経路

- [x] 2.1 `backend/app.py` に `GET /demo/error` を追加し、`marker` を含む例外で 500 になることをローカル呼び出しで確認する
- [x] 2.2 `template.yaml` に `/demo/error` ルートを追加する（ファイルに Path があること）
- [x] 2.3 `backend/tests/` に 500 と marker 伝播のテストを足し、`npm run test:api`（または同等）で通す

## 3. ドキュメント

- [x] 3.1 README に、ローカル SQLite での SQL 演習と `GET /demo/error` の一行を足す

## 作業後の続き

- 学習パック `0.共通/08.現場でよく使う型.md` を勤怠デモのローカル SQLite 前提に書き換える（本リポの archive 外）
- 変更を archive するときは `/opsx-archive` を使う
