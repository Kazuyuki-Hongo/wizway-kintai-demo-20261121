# Proposal

## Why

E2E の失敗録画で「何がダメか」が画面上に残るようにしたい。ログイン後にまだ無い仮 API を叩き、未実装であることが分かる日本語エラーを出す経路が必要。既存の `GET /demo/error` は traceback／ログ演習用で、通常画面からはリンクしない契約のままにする。

## What Changes

- 仮 API `GET /demo/unimplemented` を追加し、501 と日本語の `reason` を返す（未処理例外は投げない）
- ログイン後の画面に、見た目を抑えた隠しボタンを置き、その仮 API を呼んでエラー文言を表示する
- 意図的に失敗する E2E を、エラーが見えたあとに成功文言を誤って期待する形に差し替える
- 本番勤怠リポジトリ・本番 AWS・共有本番 DB は変更しない

## Capabilities

### New Capabilities

- `unimplemented-api-probe`: 未実装の仮 API を試し、画面に未実装であることが分かるエラーを出す経路

### Modified Capabilities

- （なし。`demo-error` の「通常画面からリンクしない」は維持する）

## Impact

- `backend/app.py`（新ルート）
- `template.yaml`（HTTP API Path）
- `frontend/src/App.tsx`（隠しボタンと呼び出し）
- `backend/tests/test_api.py`（501 応答）
- `tests/e2e/attendance.spec.ts`（意図的失敗の差し替え）
- 本番勤怠・本番 AWS アカウントには影響しない
