# Design

## Context

動機は proposal.md の Why。要件は `specs/attendance-overview/spec.md`。

このリポジトリ `wizway-kintai-demo` の中で完結する。画面は `frontend/` の React + TypeScript。API は `backend/` の Python Lambda。合計の式は `sql/month_summary.sql`。載せ方は `template.yaml` の SAM、API Gateway、S3、CloudFront。データは共有の SQLite。

挙動を変える実装は、OpenSpec の apply と Serena を使う。Serena の手順は `.cursor/skills/openspec-apply-change/SKILL.md`。接続とシンボルの見方は `docs/rules/project-rules-serena.md`。

## Goals / Non-Goals

**Goals:**

- 指定月の3人の合計を、1回の GET で返す
- 画面を開くと一覧が先に出る。行を選ぶと、その人の日ごとの入力になる
- 合計は既存の `month_summary.sql` の結果を使う

**Non-Goals:**

- 日ごとの保存、区分、時刻検証の変更
- 新しいテーブル、DynamoDB、RDS

## Decisions

### 1. 読み取りは `GET /months/{ym}/overview`

`backend/app.py` に、社員を指定しないパスを足す。年月の検証は、既存の月読み取りと同じにする。不正なら 400 と、年月が不正であるログ1行。成功時はダミー社員を id 順に返し、各人の合計は既存の `_month_summary` を呼ぶ。Python で実働の式を書き直さない。この GET は共有ファイルを読むだけで、書き戻さない。

`template.yaml` に、そのパスの GET を足す。既存の `/employees/...` はそのままにする。

代替として、画面から1人ずつの合計を3回読む案は取らない。仕様は1回の読み取りである。

### 2. 画面は一覧と日ごとの切り替え

`frontend/src/App.tsx` は、開いた直後に一覧を出す。月の入力は一覧と日ごとで同じ値を使う。行を選ぶと、その識別子の日ごとの入力を出す。一覧へ戻る操作を置く。一覧には保存ボタンを出さない。日ごとの保存は今の PUT のまま。

### 3. デプロイ先は学習用アカウントだけ

実装後のデプロイは、プロファイル `deploy-jisseki` のアカウントが `655129713987` であることを確認してから行う。スタック名は `wizway-kintai-demo`。プロファイル `deploy` と、アカウント `023194178508` には出さない。本番勤怠のリポジトリ、本番 DB、開発 VM は触らない。

## Risks / Trade-offs

- [パスの判定順を誤ると、既存の月読み取りが壊れる] → `/months/{ym}/overview` は `/employees` の外に置き、既存の正規表現より前には既存パスを通す
- [一覧と1人分の合計で式がずれる] → 同じ `_month_summary` を使う。社員1の 18 / 137 / 1 / 1 を両方で確認する

## Migration Plan

1. API の GET と画面の切り替えを足す
2. pytest と Playwright を通す
3. アカウントを確認してから、学習用アカウントのスタックと画面を更新する
4. 公開 URL が変わらなければ、導入メモは更新しない
5. 戻すときは、追加した GET と画面の一覧を外す。共有ファイルの中身は変えない
