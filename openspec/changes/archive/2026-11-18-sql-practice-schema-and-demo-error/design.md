# 設計

## 前提

現状の SQLite は `employees` / `sessions` / `attendance_rows` / `attendance_edits`。JOIN はあるが、窓関数・承認履歴・部署階層の演習には薄い。  
動機は proposal.md の「なぜ」。学習パック `08` はリポジトリ内のローカル DB（`backend/data/attendance.db`）を使う。S3 共有ファイルは演習に使わない。

## 目標 / 対象外

**目標:**
- JOIN／CTE／窓関数が自然に書ける勤怠ドメインの表＋seed
- `GET /demo/error` でログ演習ができること
- 既存画面・API の入出力を変えないこと

**対象外:**
- 部署・休暇申請の画面や API を作ること
- 架空 EC スキーマ（users/orders）を本リポに持ち込むこと
- 本番勤怠・MariaDB・本番 AWS への接続

## 決定事項

1. **表の追加（画面なし）**  
   - `departments`（`parent_id` で親子）  
   - `employees.department_id`（既存社員に紐付け）  
   - `leave_requests`（draft/submitted/approved/rejected）  
   - `leave_approvals`（同一申請に複数行可 → 最新1件の窓関数向け）  
   代替: 別ファイル DB を演習専用にする → 却下。一本のローカル DB の方が「接続を探す」演習と一致する。

2. **API は新表を読まない**  
   既存の SELECT 列指定のまま。`department_id` が増えても応答 JSON は変えない。

3. **ERROR 経路**  
   `lambda_handler` 先頭付近で `GET /demo/error` を判定し、`DemoError`（仮）を raise。`marker` をメッセージに含める。HTTP API に Path `/demo/error` を追加。  
   代替: 故意に壊した JSON のみ → traceback が出ないためログ演習に不足。

4. **seed**  
   実在名禁止。既存3人＋部署2〜3＋申請の境界ケース。`attendance_edits` も1件以上残す／足す。

## リスク / トレードオフ

- [Risk] build_db し直しでローカル変更が消える → Mitigation: README に「演習前に `python sql/build_db.py`」と書く  
- [Risk] デプロイ済み共有 DB とローカル schema がずれる → Mitigation: 演習はローカル DB 前提。新表は API 非公開なので画面デプロイは ERROR 経路だけでよい  
- [Risk] `employees` 列追加で既存テストが壊れる → Mitigation: 列指定 SELECT を確認し、必要ならテストだけ直す

## 移行手順

1. schema / seed 更新 → `python sql/build_db.py`  
2. `/demo/error` 実装とテスト  
3. `template.yaml` にルート追加（学習用アカウントへ載せるとき）  
4. ロールバック: 当該 change の schema/seed/app/template を戻し DB を作り直す
