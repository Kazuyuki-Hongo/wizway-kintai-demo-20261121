# Design

## Context

- 既存 `GET /demo/error` は `DemoError` を raise して 500／traceback 用。通常画面からはリンクしない。
- 今回は録画で「未実装」が読めるように、JSON の `reason` を画面に出す経路が要る。

## Goals / Non-Goals

**Goals**

- 501 + 日本語 `reason` の仮 API
- ログイン後の隠しボタンから呼び、アラートとして表示
- 意図的失敗 E2E でエラーが見えたあと成功文言を誤期待し、録画を残す

**Non-Goals**

- `/demo/error` の契約変更
- 本番勤怠・本番 AWS・DynamoDB／RDS
- 仮 API の本実装

## Decisions

1. Path は `/demo/unimplemented`。`/demo/error` と分離する。
2. 応答は `_response(501, {"reason": "この機能はまだ実装されていません"})`。raise しない（ローカルサーバーが落ちない）。
3. 認証は必須にしない（プローブ用。既存の demo-error と同様に session 前でも可）。画面からはログイン後だけ見せる。
4. ボタン文言は「未実装の機能を試す」。`aria-label` 同名。見た目は小さめ／控えめ（`className` で note 寄り）。
5. ログイン後の既存エラー枠に `role="alert"` を付ける（ログイン画面と揃える）。
6. E2E「わざと失敗して録画を残す」は、エラー表示を確認したあと「処理が完了しました」を期待して落とす。

## Risks / Trade-offs

- 隠しボタンが学習者に見つかる → 文言で未実装と明示し、本機能ではないことが分かるようにする。
- template.yaml に Path を足さないとデプロイ先で 404 → SAM にも載せる。

## Migration Plan

なし（デモ専用の追加）。

## Open Questions

なし。
