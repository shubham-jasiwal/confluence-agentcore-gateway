# Architecture

## Confluence AgentCore Gateway

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Actions                           │
│  .github/workflows/deploy-dev.yml                               │
│                                                                  │
│  push to main ──► create_apikey_provider.py ──► cdk deploy      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                    CDK deploy (infra/app.py)
                                │
                ┌───────────────▼──────────────────┐
                │         AWS Account               │
                │                                   │
                │  ┌────────────────────────────┐   │
                │  │  SSM Parameter Store        │   │
                │  │  /confluence/gateway/*      │◄──┼── Scripts write ARNs here
                │  └──────────┬─────────────────┘   │   CDK reads from here
                │             │                      │
                │  ┌──────────▼─────────────────┐   │
                │  │  AgentCore Gateway (MCP)    │   │
                │  │  IAM Auth / SigV4           │   │
                │  │                             │   │
                │  │  ┌──────────────────────┐   │   │
                │  │  │  Gateway Target       │   │   │
                │  │  │  (Confluence API)     │   │   │
                │  │  └──────────────────────┘   │   │
                │  └─────────────────────────────┘   │
                │                                    │
                │  ┌─────────────────────────────┐   │
                │  │  API Key Credential Provider │   │
                │  │  (Bedrock AgentCore Control) │   │
                │  └─────────────────────────────┘   │
                └────────────────────────────────────┘
                                │
                     MCP / JSON-RPC calls
                                │
                ┌───────────────▼────────────────┐
                │      Confluence Cloud           │
                │   {subdomain}.atlassian.net     │
                └────────────────────────────────┘
```

## Folder Structure

```
deployment-github-actions/
├── .github/
│   └── workflows/
│       └── deploy-dev.yml          # CI/CD pipeline
├── infra/
│   ├── app.py                      # CDK entrypoint
│   └── config/
│       └── dev.py                  # Dev config (SSM-backed)
├── stacks/
│   └── agentcore_gateway/
│       ├── constructs/
│       │   └── agent_core_gateway.py   # CDK construct
│       ├── scripts/
│       │   ├── create_apikey_provider.py
│       │   └── create_oauth_provider.py
│       └── confluence_gateway_stack.py # CDK stack
├── test/
│   └── test_api_gateway.py         # Integration tests
├── architecture.md
├── setup-guide.md
└── requirements.txt
```

## SSM Parameter Map

| SSM Path | Type | Set By |
|---|---|---|
| `/confluence/gateway/aws-account-id` | String | Manual |
| `/confluence/gateway/aws-region` | String | Manual |
| `/confluence/gateway/confluence-subdomain` | String | Manual |
| `/confluence/gateway/confluence-email` | String | Manual |
| `/confluence/gateway/confluence-api-token` | SecureString | Manual |
| `/confluence/gateway/credential-provider-arn` | String | `create_apikey_provider.py` |
| `/confluence/gateway/oauth-credential-provider-arn` | String | `create_oauth_provider.py` |
| `/confluence/gateway/gateway-id` | String | GitHub Actions (post-deploy) |
| `/confluence/gateway/test-page-id` | String | Manual |

## GitHub Secrets Required

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user access key |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key |
| `CONFLUENCE_API_KEY` | `base64("email:api_token")` |
