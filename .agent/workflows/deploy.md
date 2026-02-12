---
description: How to deploy Kureita MVP — API to Lambda and Web to Amplify
---

# Deployment Guide — Kureita MVP

## Prerequisites (You Have All of These ✅)
- AWS CLI v2 (authenticated as `Rishav`, account `071329584603`)
- SAM CLI v1.142+
- Docker
- Region: `ap-south-1`

---

## Part 1: Deploy API (Lambda + API Gateway)

### Step 1 — Fill in production secrets

Open `apps/api/.env.prod` and replace all placeholder values with real production credentials:
- `MONGODB_URL` → your production MongoDB Atlas connection string
- `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY` → production keys
- `MONGODB_DATABASE` → set to `kureita` (or your preferred prod DB name)

### Step 2 — Get/Create an ACM Certificate (for custom domain)

You need an ACM certificate for `app-api.kureita.com`. **It must be in `ap-south-1`** (same region as your API, since we're using Regional endpoint).

```bash
# Check if you already have one:
aws acm list-certificates --region ap-south-1

# If not, request one:
aws acm request-certificate \
  --domain-name app-api.kureita.com \
  --validation-method DNS \
  --region ap-south-1
```

> **Important:** You must validate the certificate by adding the CNAME record shown in ACM to your DNS (Route 53 or wherever `kureita.com` is managed). The certificate must be in `Issued` status before deploying.

Copy the `CertificateArn` — you'll need it in Step 4.

### Step 3 — Build the Docker image via SAM

```bash
cd apps/api
sam build
```

This builds the Docker image defined in the `Dockerfile`. Takes a few minutes the first time.

### Step 4 — Deploy with SAM

```bash
sam deploy \
  --guided \
  --stack-name kureita-api \
  --region ap-south-1 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    DomainName=app-api.kureita.com \
    CertificateArn=arn:aws:acm:ap-south-1:071329584603:certificate/YOUR-CERT-ID
```

The `--guided` flag will walk you through confirmations. On subsequent deploys, drop `--guided` and use:

```bash
sam deploy --no-confirm-changeset
```

### Step 5 — Set Lambda environment variables

After the stack deploys, go to the **AWS Lambda Console** → find `kureita-api-KureitaApiFunction-*` → Configuration → Environment Variables. Add all secrets from `.env.prod`:

| Key | Value |
|-----|-------|
| `APP_ENV` | `prod` |
| `DEBUG` | `false` |
| `API_BASE_URL` | `https://app-api.kureita.com` |
| `STORAGE_TYPE` | `s3` |
| `MONGODB_URL` | *(your prod MongoDB URL)* |
| `MONGODB_DATABASE` | `kureita` |
| `OPENAI_API_KEY` | *(your key)* |
| `GEMINI_API_KEY` | *(your key)* |
| `ELEVENLABS_API_KEY` | *(your key)* |
| `CORS_ORIGINS` | `https://app.kureita.com` |

> **Alternatively**, add these to the `template.yaml` under `Globals.Function.Environment.Variables` (but keep real secrets out of source control — use AWS Systems Manager Parameter Store or Secrets Manager).

### Step 6 — Point DNS to API Gateway

After deploy, SAM outputs the API Gateway domain. Add a **CNAME** record:

```
app-api.kureita.com → <API-Gateway-domain-from-output>.execute-api.ap-south-1.amazonaws.com
```

If you set up the custom domain via the SAM template, you'll get a different target from the `ApiDomainName` resource. Check:

```bash
aws apigatewayv2 get-domain-name --domain-name app-api.kureita.com --region ap-south-1
```

The `ApiGatewayDomainName` field is what you point your DNS CNAME to.

### Step 7 — Verify API

```bash
curl https://app-api.kureita.com/health
# Expected: {"status":"healthy","version":"0.1.0"}

curl -s -o /dev/null -w "%{http_code}" https://app-api.kureita.com/docs
# Expected: 404 (docs disabled in prod)
```

---

## Part 2: Deploy Web (AWS Amplify)

### Step 1 — Push code to Git

Amplify deploys from a Git repository. Make sure your code is pushed:

```bash
git add -A
git commit -m "deployment readiness fixes"
git push origin main
```

### Step 2 — Create Amplify App

Go to **AWS Amplify Console** (https://console.aws.amazon.com/amplify/home) in `ap-south-1`:

1. Click **"Create new app"** → **"Host web app"**
2. Connect your **Git provider** (GitHub/CodeCommit/etc.)
3. Select the repo and branch (`main`)

### Step 3 — Configure Build Settings

Amplify should auto-detect Next.js. Set the **build settings**:

- **App root**: `apps/web`
- **Build command**: `npm run build`
- **Output directory**: `.next`

Or use this `amplify.yml` (create at repo root if Amplify doesn't auto-detect):

```yaml
version: 1
applications:
  - appRoot: apps/web
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - npm run build
      artifacts:
        baseDirectory: .next
        files:
          - '**/*'
      cache:
        paths:
          - node_modules/**/*
          - .next/cache/**/*
```

### Step 4 — Set Environment Variables

In Amplify Console → **Environment variables**, add:

| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_API_URL` | `https://app-api.kureita.com` |

> This is baked into the build — Amplify must have it before building.

### Step 5 — Set Custom Domain

In Amplify Console → **Domain Management**:

1. Click **"Add domain"**
2. Enter `kureita.com`
3. Set subdomain mapping: `app` → `main` branch
4. Amplify will provide DNS records — add them to your DNS provider
5. Wait for SSL certificate verification and domain activation

### Step 6 — Deploy

Trigger a build (or it auto-triggers on push). Once done:

```bash
curl https://app.kureita.com
# Should load the Next.js app
```

---

## Quick Reference

| Component | URL | Infra |
|-----------|-----|-------|
| Web UI | `https://app.kureita.com` | Amplify |
| API | `https://app-api.kureita.com` | Lambda + API Gateway |
| API Health | `https://app-api.kureita.com/health` | — |
| S3 Assets | `kureita-assets-071329584603-ap-south-1` | S3 |
| MongoDB | MongoDB Atlas | External |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `sam build` fails | Ensure Docker is running |
| API returns 502 | Check Lambda logs in CloudWatch |
| API returns 504 (timeout) | API Gateway has 29s limit — long gen calls need async pattern |
| Web shows "Network error" | Check `NEXT_PUBLIC_API_URL` env var in Amplify, rebuild |
| CORS errors | Verify `CORS_ORIGINS` in Lambda env includes `https://app.kureita.com` |
| S3 upload fails | Check Lambda IAM role has S3 access (SAM template handles this) |
