## 1. API

- [x] 1.1 `backend/app.py` に `GET /demo/unimplemented` を追加し、501 と日本語 `reason` を返す
- [x] 1.2 `template.yaml` に `/demo/unimplemented` ルートを追加する
- [x] 1.3 `backend/tests/test_api.py` に 501／`reason` のテストを追加する

## 2. 画面

- [x] 2.1 ログイン後に「未実装の機能を試す」ボタンを置き、`GET /demo/unimplemented` を呼んでエラーを `role="alert"` で表示する

## 3. E2E

- [x] 3.1 「わざと失敗して録画を残す」を、ログイン→ボタン→エラー確認→成功文言の誤期待、に差し替える
