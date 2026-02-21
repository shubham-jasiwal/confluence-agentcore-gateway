# Setup Guide — Confluence AgentCore Gateway

## Prerequisites

- AWS CLI configured (`aws configure`)
- Python 3.11+
- Node.js 20+ (`npm install -g aws-cdk`)
- GitHub repository with Actions enabled

---

## Step 1 — Create SSM Parameters

Run these once in your terminal (replace values with your own):

```bash
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Account & Region
aws ssm put-parameter --region $REGION --name "/confluence/gateway/aws-account-id" \
  --value "$ACCOUNT_ID" --type String --overwrite

aws ssm put-parameter --region $REGION --name "/confluence/gateway/aws-region" \
  --value "$REGION" --type String --overwrite

# Confluence details
aws ssm put-parameter --region $REGION --name "/confluence/gateway/confluence-subdomain" \
  --value "YOUR_ATLASSIAN_SUBDOMAIN" --type String --overwrite

aws ssm put-parameter --region $REGION --name "/confluence/gateway/confluence-email" \
  --value "your@email.com" --type String --overwrite

# SecureString for API token
aws ssm put-parameter --region $REGION --name "/confluence/gateway/confluence-api-token" \
  --value "YOUR_ATLASSIAN_API_TOKEN" --type SecureString --overwrite

# Test page ID (any Confluence page ID)
aws ssm put-parameter --region $REGION --name "/confluence/gateway/test-page-id" \
  --value "622593" --type String --overwrite
```

---

## Step 2 — Create API Key Credential Provider

```bash
cd deployment-github-actions

# Base64 encode "email:api_token"
export CONFLUENCE_API_KEY=$(echo -n "your@email.com:YOUR_ATLASSIAN_API_TOKEN" | base64)

python3 stacks/agentcore_gateway/scripts/create_apikey_provider.py
```

This will store the provider ARN in SSM at `/confluence/gateway/credential-provider-arn`.

---

## Step 3 — Install Dependencies & Bootstrap CDK

```bash
cd deployment-github-actions
pip install -r requirements.txt
cdk bootstrap aws://$ACCOUNT_ID/$REGION
```

---

## Step 4 — Deploy via CDK (Local)

```bash
cdk --app "python3 infra/app.py" synth      # dry-run
cdk --app "python3 infra/app.py" deploy ConfluenceGatewayStack-Dev --require-approval never
```

After deploy, store the Gateway ID from the CloudFormation outputs:

```bash
aws ssm put-parameter --region $REGION --name "/confluence/gateway/gateway-id" \
  --value "YOUR_GATEWAY_ID_FROM_OUTPUT" --type String --overwrite
```

---

## Step 5 — Attach Confluence Target (Manual)

In the [AWS Bedrock Console](https://console.aws.amazon.com/bedrock):
1. Go to **AgentCore → Gateways**
2. Select your gateway → **Targets → Add Target**
3. Set endpoint: `https://api.atlassian.com`
4. Select your API Key credential provider
5. Upload/paste the Confluence OpenAPI schema

---

## Step 6 — Configure GitHub Actions (CI/CD)

Add these secrets to your GitHub repository (**Settings → Secrets → Actions**):

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user access key ID |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret access key |
| `CONFLUENCE_API_KEY` | `base64("your@email.com:your_api_token")` |

Push to the `main` branch — the pipeline runs automatically.

---

## Step 7 — Run Tests

```bash
python3 test/test_api_gateway.py
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `SSM parameter not found` | Run Step 1 again for the missing parameter |
| `CDK bootstrap required` | Run `cdk bootstrap aws://ACCOUNT/REGION` |
| `403 from Gateway` | Check IAM permissions on the caller identity |
| `No tools found` | Confirm Confluence target is attached (Step 5) |
| `CONFLUENCE_API_KEY not set` | Export/set the env var before running the script |
