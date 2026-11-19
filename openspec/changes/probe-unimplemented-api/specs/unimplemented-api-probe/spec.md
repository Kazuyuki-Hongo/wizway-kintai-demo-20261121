## ADDED Requirements

### Requirement: 未実装の仮 API

システムは `GET /demo/unimplemented` を提供し、501 と日本語の `reason`（この機能はまだ実装されていません）を返す SHALL。未処理例外は送出しない。

#### Scenario: 未実装を JSON で返す

- **WHEN** `GET /demo/unimplemented` を呼ぶ
- **THEN** 応答は 501 で、本文の `reason` は「この機能はまだ実装されていません」である

### Requirement: 画面からの未実装プローブ

ログイン後の勤怠画面は、見た目を抑えたボタン「未実装の機能を試す」を提供し、押すと `GET /demo/unimplemented` を呼び、返った `reason`（または呼べないとき日本語の失敗文）を `role="alert"` のエラーとして表示する SHALL。

#### Scenario: 隠しボタンでエラーが出る

- **WHEN** ログイン後に「未実装の機能を試す」を押す
- **THEN** 画面に「この機能はまだ実装されていません」が表示される
