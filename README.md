# wizway-kintai-demo-20261121

フィック研修（2026-11-21）用の勤怠デモ。  
希望者がクローンして、Cursor / Claude Code / Codex など任意のアプリで開く。本番の勤怠（wizway_kintai）とは別リポジトリ。

完成見本は [`wizway-kintai-demo`](https://github.com/Kazuyuki-Hongo/wizway-kintai-demo)。こちらは研修当日に足す機能がまだ無い状態から始める。

## クローン（希望者）

```powershell
git clone https://github.com/Kazuyuki-Hongo/wizway-kintai-demo-20261121.git
cd wizway-kintai-demo-20261121
```

開くアプリは自由。研修中に本郷が出す指示は Zoom チャットにも貼る。同じ指示を手元でも試してよいし、見てるだけでもよい。

触らないもの:

- 本番の勤怠リポジトリ・本番 AWS
- 見本リポ `wizway-kintai-demo` の学習用 URL（画面は別）

## 動いている画面（学習用・見本とは別）

- フロント: https://d2ub54l8wsj1sg.cloudfront.net
- API: https://7p05ld5qkk.execute-api.ap-northeast-1.amazonaws.com/prod

上の URL はダミー専用。本番の勤怠データは見えない。見本（`wizway-kintai-demo`）とは別スタック・別 URL。

## このリポジトリの中身

ダミー社員の月次勤怠表と合計を返し、保存済みの日を更新できる。

**OpenSpec + Serena 導入済み。** 仕様駆動の型は次のフォルダにある。

- `docs/rules/project-rules-serena.md` と `.serena/memories/` — Serena の約束と覚え書き
- `openspec/specs/` — いまの仕様
- `openspec/changes/` — 進行中の change
- `openspec/changes/archive/` — 完了して移した change
- `.cursor/skills/openspec-apply-change/` — 実装の前に Serena へ接続するゲート

**React + TypeScript + Python Lambda + API Gateway (HTTP API) + 同梱 SQLite**

| 経路 | 役割 |
|------|------|
| `GET /employees` | ダミー社員の識別子と表示名 |
| `GET /employees/{id}/months/{ym}` | 指定月の勤怠行（`ym` は `YYYY-MM`） |
| `GET /employees/{id}/months/{ym}/summary` | 出勤日数・総実働・8時間超過・退勤なし件数 |
| `GET /months/{ym}/overview` | 指定月のダミー社員全員の合計 |
| `GET /months/{ym}/export` | 指定月の3人の全日を CSV で出す |
| `POST /login` | 表示名とパスワードでログインする |
| `POST /logout` | ログイン中のセッションを破棄する |
| `PUT /employees/{id}/months/{ym}/days/{date}` | その月の1日を保存する。行が無い日は作る。入力者はログインした人 |
| `GET /demo/error?marker=印` | 演習用。`marker` をログに出してから未処理エラーになる |

SQL 演習はデプロイ先の S3 共有 DB ではなく、リポジトリ内のローカル SQLite（`python sql/build_db.py` → `backend/data/attendance.db`）を使う。`departments` / `leave_requests` / `leave_approvals` は画面・API からは出さない演習用の表。

開いたらログインする。ログインしたあとは、その人の月の日ごとが出る。左の「自分の勤怠」で自分の月に戻る。管理者だけ「全員の勤怠」から3人の合計を開き、「日ごとを入力」でその人の日ごとへ移る。CSV は全員の勤怠から出す。

データは Lambda に同梱した SQLite が初期データ。更新は学習用アカウントの非公開 S3 にある共有ファイルへ書き、次の読み取りからも見える。2026-11-02 から 2026-11-20 の平日だけを3人ぶん入れ、土日と11月1日・21日以降は空で、その場で入力できる。DynamoDB と RDS は使わない。

## 構成

```
backend/          Python Lambda（API + 同梱 SQLite）
frontend/         React + TypeScript（Vite）
sql/              表定義・シード・合計 SELECT
template.yaml     SAM（HTTP API + Lambda + S3 + CloudFront）
docs/architecture.drawio / architecture.md  構成図（draw.io / Markdown）
docs/rules/       Serena のプロジェクトルール
openspec/         仕様と change（進行中と archive）
backend/tests/    API の pytest
tests/e2e/        画面の受け入れ確認（Playwright）
```

### 構成図

ブラウザ → CloudFront → S3（画面）  
ブラウザ → HTTP API → Lambda → 同梱 SQLite（更新は S3 共有へ）

詳細: [`docs/architecture.drawio`](docs/architecture.drawio)（draw.io）／[`docs/architecture.md`](docs/architecture.md)（Markdown・Mermaid）

## 前提（メンテ・デプロイする人）

- AWS CLI / SAM CLI / Node.js
- 学習用 AWS アカウントの Deployer（本番勤怠のアカウントには載せない）
- スタック名は `wizway-kintai-demo-20261121`（見本の `wizway-kintai-demo` と分ける）

```powershell
aws sso login --profile <自分のプロファイル名>
aws sts get-caller-identity --profile <自分のプロファイル名>
```

Account が本番勤怠と同じ箱なら、ここで止める。

## デプロイ手順

### 1. SQLite を作り直す（任意）

```powershell
python sql/build_db.py
```

### 2. API + インフラ

Windows で SAM CLI が `botocore` で落ちるときは、同じシェルで `PYTHONNOUSERSITE=1` を付けてから実行する。

```powershell
$env:PYTHONNOUSERSITE='1'
sam build
sam deploy --profile <自分のプロファイル名> --no-confirm-changeset
```

Outputs: `ApiUrl` / `FrontendBucketName` / `FrontendUrl` / `CloudFrontDistributionId`

### 3. フロント

`frontend/.env.production`:

```env
VITE_API_URL=https://xxxx.execute-api.ap-northeast-1.amazonaws.com/prod
```

```powershell
cd frontend
npm ci
npm run build
aws s3 sync dist/ s3://<FrontendBucketName>/ --delete --profile <自分のプロファイル名>
aws cloudfront create-invalidation --distribution-id <CloudFrontDistributionId> --paths "/*" --profile <自分のプロファイル名>
```

## ローカル確認

```powershell
python sql/build_db.py
python backend/local_check.py
python backend/local_server.py
```

別ターミナル:

```powershell
cd frontend
$env:VITE_API_URL='http://127.0.0.1:8080'
npm run dev
```

## テスト

API の pytest は `backend/tests/`。画面の受け入れ確認は、リポジトリ直下の Playwright と `tests/e2e/`。詳細は [tests/e2e/README.md](tests/e2e/README.md)。

```powershell
python -m pip install --user -r backend/requirements-dev.txt
npm install
npm run pw:install
cd frontend
npm install
cd ..

npm run test:api
npm run pw:test:attendance
```
