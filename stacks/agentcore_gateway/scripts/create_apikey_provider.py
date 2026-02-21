#!/usr/bin/env python3
"""
stacks/agentcore_gateway/scripts/create_apikey_provider.py

One-time setup script: creates an API Key credential provider in Bedrock AgentCore
and stores the resulting ARN in SSM Parameter Store.

Reads credentials from environment variables — no secrets are hardcoded.

Usage:
    export CONFLUENCE_API_KEY="base64(email:api_token)"
    python3 stacks/agentcore_gateway/scripts/create_apikey_provider.py

Environment variables:
    CONFLUENCE_API_KEY   - Atlassian API token (base64-encoded "email:api_token")
    AWS_REGION           - AWS region (default: us-east-1, or from SSM)
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError

# ─── Config ───────────────────────────────────────────────────────────────────
REGION        = os.environ.get("AWS_REGION", "us-east-1")
PROVIDER_NAME = "confluence-apikey-provider"
SSM_PARAM_ARN = "/confluence/gateway/credential-provider-arn"

# Supplied via environment variable / GitHub Secret — never hardcoded
API_KEY = os.environ.get("CONFLUENCE_API_KEY", "")
# ─────────────────────────────────────────────────────────────────────────────


def get_region_from_ssm() -> str:
    """Try to read the canonical region from SSM, fall back to env var."""
    try:
        ssm = boto3.client("ssm", region_name=REGION)
        resp = ssm.get_parameter(Name="/confluence/gateway/aws-region")
        return resp["Parameter"]["Value"]
    except Exception:
        return REGION


def create_or_get_provider(region: str) -> str:
    agentcore = boto3.client("bedrock-agentcore-control", region_name=region)
    print(f"\n🔑 Creating API Key credential provider: {PROVIDER_NAME}")

    try:
        resp = agentcore.create_api_key_credential_provider(
            name=PROVIDER_NAME,
            apiKey=API_KEY,
        )
        arn = resp.get("credentialProviderArn")
        print(f"✅ Created!  ARN: {arn}")
        return arn

    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg  = e.response["Error"]["Message"]

        if "ConflictException" in code or "already exists" in msg.lower():
            print("⚠️  Provider already exists — updating API key and fetching ARN...")
            try:
                update_resp = agentcore.update_api_key_credential_provider(
                    name=PROVIDER_NAME,
                    apiKey=API_KEY,
                )
                arn = update_resp.get("credentialProviderArn") or update_resp.get("arn")
                print(f"✅ Updated!  ARN: {arn}")
                return arn
            except Exception as update_err:
                # update failed — try listing as a last resort
                print(f"⚠️  Update failed ({update_err}), trying list...")
                try:
                    providers_resp = agentcore.list_api_key_credential_providers()
                    # API may return 'items', 'credentialProviders', or similar
                    items = (
                        providers_resp.get("items")
                        or providers_resp.get("credentialProviders")
                        or []
                    )
                    for p in items:
                        if p.get("name") == PROVIDER_NAME:
                            arn = p.get("credentialProviderArn") or p.get("arn")
                            print(f"   Found ARN via list: {arn}")
                            return arn
                except Exception as list_err:
                    print(f"⚠️  List also failed: {list_err}")
                print("❌ Could not retrieve existing provider ARN.")
                sys.exit(1)
        else:
            print(f"❌ Error: {code} — {msg}")
            sys.exit(1)


def write_arn_to_ssm(arn: str, region: str):
    ssm = boto3.client("ssm", region_name=region)
    ssm.put_parameter(
        Name=SSM_PARAM_ARN,
        Value=arn,
        Type="String",
        Description="ARN of Confluence API Key credential provider in AgentCore",
        Overwrite=True,
    )
    print(f"\n📦 ARN stored in SSM: {SSM_PARAM_ARN}")
    print("   → CDK stack will read this automatically on next deploy")


if __name__ == "__main__":
    if not API_KEY:
        print(
            "❌ CONFLUENCE_API_KEY env var is not set.\n"
            "   Format: base64('your_email@example.com:your_api_token')\n"
            "   In GitHub Actions this comes from the CONFLUENCE_API_KEY secret."
        )
        sys.exit(1)

    resolved_region = get_region_from_ssm()
    print(f"🌍 Using region: {resolved_region}")

    arn = create_or_get_provider(resolved_region)
    write_arn_to_ssm(arn, resolved_region)

    print("\n✅ Done.")
    print("   Next: cdk --app 'python3 infra/app.py' deploy ConfluenceGatewayStack-Dev")
