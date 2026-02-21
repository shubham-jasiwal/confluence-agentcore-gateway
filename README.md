# Confluence AgentCore Gateway — CDK Deployment

Deploys an **AWS Bedrock AgentCore Gateway** that connects your Bedrock agents to **Confluence Cloud** via the MCP protocol. Deployment is fully automated through **GitHub Actions** with no hardcoded secrets — all configuration lives in **AWS SSM Parameter Store**.

---

## Architecture

```
GitHub Actions (push to main)
        │
        ├─► create_apikey_provider.py  →  stores ARN in SSM
        └─► cdk deploy (infra/app.py)  →  deploys AgentCore Gateway
                                               │
                              AWS Bedrock AgentCore Gateway (MCP / IAM auth)
                                               │
                                      Confluence Cloud API
                                   ({subdomain}.atlassian.net)
```

See [architecture.md](./architecture.md) for full diagrams and SSM parameter map.

---

## Project Structure

```
deployment-github-actions/
├── .github/workflows/
│   └── deploy-dev.yml              # CI/CD pipeline (auto-deploy on push to main)
├── infra/
│   ├── app.py                      # CDK entrypoint
│   └── config/
│       └── dev.py                  # Dev config — reads everything from SSM
├── stacks/
│   └── agentcore_gateway/
│       ├── constructs/
│       │   └── agent_core_gateway.py   # CDK Construct for the Gateway
│       ├── scripts/
│       │   ├── create_apikey_provider.py   # One-time: creates API Key provider
│       │   └── create_oauth_provider.py    # One-time: creates OAuth provider
│       └── confluence_gateway_stack.py     # Main CDK Stack
├── test/
│   └── test_api_gateway.py         # Integration tests
├── architecture.md
├── setup-guide.md
└── requirements.txt
```

---

## Quick Start

### 1. Prerequisites

```bash
brew install awscli node python@3.11
npm install -g aws-cdk
pip install -r requirements.txt
aws configure   # set your AWS credentials
```

### 2. Store SSM Parameters (one-time)

```bash
REGION="us-east-1"

aws ssm put-parameter --region $REGION --name "/confluence/gateway/aws-account-id" \
  --value "$(aws sts get-caller-identity --query Account --output text)" --type String --overwrite

aws ssm put-parameter --region $REGION --name "/confluence/gateway/aws-region" \
  --value "$REGION" --type String --overwrite

aws ssm put-parameter --region $REGION --name "/confluence/gateway/confluence-subdomain" \
  --value "YOUR_SUBDOMAIN" --type String --overwrite

aws ssm put-parameter --region $REGION --name "/confluence/gateway/confluence-email" \
  --value "your@email.com" --type String --overwrite

aws ssm put-parameter --region $REGION --name "/confluence/gateway/confluence-api-token" \
  --value "YOUR_ATLASSIAN_API_TOKEN" --type SecureString --overwrite
```

### 3. Create the API Key Credential Provider

```bash
export CONFLUENCE_API_KEY=$(echo -n "your@email.com:YOUR_ATLASSIAN_API_TOKEN" | base64)
python3 stacks/agentcore_gateway/scripts/create_apikey_provider.py
```

### 4. Deploy

```bash
cdk --app "python3 infra/app.py" deploy ConfluenceGatewayStack-Dev --require-approval never
```

### 5. Test

```bash
python3 test/test_api_gateway.py
```

---

## GitHub Actions Setup

The pipeline (`.github/workflows/deploy-dev.yml`) runs automatically on every push to `main`.

### Required GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | Your IAM user access key |
| `AWS_SECRET_ACCESS_KEY` | Your IAM user secret key |
| `CONFLUENCE_API_KEY` | `base64("your@email.com:your_api_token")` |

> **SSM vs GitHub Secrets:**
> - **GitHub Secrets** = credentials needed *by the pipeline itself* to authenticate to AWS
> - **AWS SSM** = configuration values read *by CDK & scripts at deploy time* (account ID, subdomain, etc.)

### Pipeline Steps

1. Checkout code
2. Install Python + CDK
3. Configure AWS credentials (from GitHub Secrets)
4. Run `create_apikey_provider.py` → writes credential provider ARN to SSM
5. `cdk bootstrap` (safe to run repeatedly)
6. `cdk synth` (validation)
7. `cdk deploy` → outputs Gateway URL, ID, Role ARN
8. Stores Gateway ID in SSM for test scripts

---

## SSM Parameter Reference

| Parameter Path | Type | Set By |
|---|---|---|
| `/confluence/gateway/aws-account-id` | String | Manual (Step 2) |
| `/confluence/gateway/aws-region` | String | Manual (Step 2) |
| `/confluence/gateway/confluence-subdomain` | String | Manual (Step 2) |
| `/confluence/gateway/confluence-email` | String | Manual (Step 2) |
| `/confluence/gateway/confluence-api-token` | SecureString | Manual (Step 2) |
| `/confluence/gateway/credential-provider-arn` | String | `create_apikey_provider.py` |
| `/confluence/gateway/gateway-id` | String | GitHub Actions (post-deploy) |
| `/confluence/gateway/test-page-id` | String | Manual (optional) |

---

## After Deployment

Once the stack is deployed, you need to **attach a Confluence target** manually in the AWS Console:

1. Go to **AWS Bedrock → AgentCore → Gateways**
2. Select your gateway → **Targets → Add Target**
3. Set the API endpoint to `https://api.atlassian.com`
4. Select the API Key credential provider
5. Upload the Confluence OpenAPI schema

See [setup-guide.md](./setup-guide.md) for detailed steps and troubleshooting.

---

## Local Development

```bash
# Validate without deploying
cdk --app "python3 infra/app.py" synth

# Check SSM parameters are all set
aws ssm get-parameters-by-path --path "/confluence/gateway/" \
  --region us-east-1 --query "Parameters[].Name" --output table
```
