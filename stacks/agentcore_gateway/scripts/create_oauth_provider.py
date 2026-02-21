#!/usr/bin/env python3
"""
stacks/agentcore_gateway/scripts/create_oauth_provider.py

One-time setup script: creates an OAuth 2.0 credential provider in Bedrock
AgentCore and stores the resulting ARN in SSM Parameter Store.

Reads all credentials from environment variables — no secrets are hardcoded.

Usage:
    export OAUTH_CLIENT_ID="your_atlassian_oauth_client_id"
    export OAUTH_CLIENT_SECRET="your_atlassian_oauth_client_secret"
    python3 stacks/agentcore_gateway/scripts/create_oauth_provider.py

Environment variables:
    OAUTH_CLIENT_ID      - Atlassian OAuth 2.0 client ID
    OAUTH_CLIENT_SECRET  - Atlassian OAuth 2.0 client secret
    AWS_REGION           - AWS region (default: us-east-1, or from SSM)

Atlassian OAuth 2.0 app configuration:
    Authorization URL : https://auth.atlassian.com/authorize
    Token URL         : https://auth.atlassian.com/oauth/token
    Scopes            : read:confluence-content.all offline_access
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError

# ─── Config ───────────────────────────────────────────────────────────────────
REGION        = os.environ.get("AWS_REGION", "us-east-1")
PROVIDER_NAME = "confluence-oauth-provider"
SSM_PARAM_ARN = "/confluence/gateway/oauth-credential-provider-arn"

# Atlassian OAuth endpoints
AUTHORIZATION_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL         = "https://auth.atlassian.com/oauth/token"
SCOPES            = ["read:confluence-content.all", "offline_access"]

# From environment / GitHub Secrets
CLIENT_ID     = os.environ.get("OAUTH_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
# ─────────────────────────────────────────────────────────────────────────────


def get_region_from_ssm() -> str:
    try:
        ssm = boto3.client("ssm", region_name=REGION)
        resp = ssm.get_parameter(Name="/confluence/gateway/aws-region")
        return resp["Parameter"]["Value"]
    except Exception:
        return REGION


def create_or_get_provider(region: str) -> str:
    agentcore = boto3.client("bedrock-agentcore-control", region_name=region)
    print(f"\n🔐 Creating OAuth credential provider: {PROVIDER_NAME}")

    try:
        resp = agentcore.create_oauth2_credential_provider(
            name=PROVIDER_NAME,
            credentialProviderVendor="CUSTOM",
            oauth2ProviderConfigInput={
                "customOauth2ProviderConfig": {
                    "oauthDiscovery": {
                        "authorizationServerMetadata": {
                            "issuer": "https://auth.atlassian.com",
                            "authorizationEndpoint": AUTHORIZATION_URL,
                            "tokenEndpoint": TOKEN_URL,
                            "responseTypesSupported": ["code"],
                        }
                    },
                    "clientId": CLIENT_ID,
                    "clientSecret": CLIENT_SECRET,
                    "oauthScopes": SCOPES,
                }
            },
        )
        arn = resp.get("credentialProviderArn")
        print(f"✅ Created!  ARN: {arn}")
        return arn

    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg  = e.response["Error"]["Message"]

        if "ConflictException" in code or "already exists" in msg:
            print("⚠️  Provider already exists — fetching existing ARN...")
            providers = agentcore.list_oauth2_credential_providers()
            for p in providers.get("items", []):
                if p.get("name") == PROVIDER_NAME:
                    arn = p.get("credentialProviderArn") or p.get("arn")
                    print(f"   Existing ARN: {arn}")
                    return arn
            print("❌ Could not find existing provider.")
            sys.exit(1)
        else:
            print(f"❌ Error ({code}): {msg}")
            sys.exit(1)


def write_arn_to_ssm(arn: str, region: str):
    ssm = boto3.client("ssm", region_name=region)
    ssm.put_parameter(
        Name=SSM_PARAM_ARN,
        Value=arn,
        Type="String",
        Description="ARN of Confluence OAuth 2.0 credential provider in AgentCore",
        Overwrite=True,
    )
    print(f"\n📦 ARN stored in SSM: {SSM_PARAM_ARN}")
    print("   → CDK stack will read this automatically on next deploy")


if __name__ == "__main__":
    missing = [v for v in ["OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET"] if not os.environ.get(v)]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("   Set these via GitHub Secrets or export them locally.")
        sys.exit(1)

    resolved_region = get_region_from_ssm()
    print(f"🌍 Using region: {resolved_region}")

    arn = create_or_get_provider(resolved_region)
    write_arn_to_ssm(arn, resolved_region)

    print("\n✅ Done.")
    print("   Next: Complete OAuth authorization in the AWS Bedrock Console.")
    print("   Then run: cdk --app 'python3 infra/app.py' deploy ConfluenceGatewayStack-Dev")
