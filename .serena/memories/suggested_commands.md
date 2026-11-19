# suggested_commands (Windows PowerShell)

## Data / API local
- `python sql/build_db.py`
- `python backend/local_check.py`
- `python backend/local_server.py` → http://127.0.0.1:8080

## Frontend local
- `cd frontend; $env:VITE_API_URL='http://127.0.0.1:8080'; npm run dev`

## Tests
- `npm run test:api` — pytest。`PYTHONNOUSERSITE=1` だと user の pytest を見失う → 外す
- `npm run pw:install` / ローカル E2E: `npm run pw:test:attendance`（`PLAYWRIGHT_BASE_URL` 無し）
- 理想: ローカル E2E 緑 → AWS デプロイ → AWS E2E: `$env:PLAYWRIGHT_BASE_URL='https://d266q7koncqwt6.cloudfront.net'; npm run pw:test:attendance`

## Deploy (学習用のみ)
- `aws sts get-caller-identity --profile deploy-jisseki` — Account 655129713987 を確認。`deploy` は本番箱のことがある
- `$env:PYTHONNOUSERSITE='1'; sam build; sam deploy --profile deploy-jisseki --no-confirm-changeset`
- フロント: `frontend/.env.production` の VITE_API_URL → `npm run build` → `aws s3 sync dist/ s3://wizway-kintai-demo-frontend-655129713987/ --delete --profile deploy-jisseki` → CloudFront invalidate `E1N0VGUC7GMMK5`

## OpenSpec
- `openspec list --json` / `openspec instructions apply --change "<name>" --json`
