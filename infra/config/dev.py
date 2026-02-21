"""
infra/config/dev.py

Development environment configuration.
All values are read from AWS SSM Parameter Store — no secrets are hardcoded.

Required SSM Parameters (create these once manually or via setup-guide.md):
  /confluence/gateway/aws-account-id        → AWS account ID
  /confluence/gateway/aws-region            → AWS region (e.g. us-east-1)
  /confluence/gateway/confluence-subdomain  → Atlassian subdomain (e.g. rassk97)
  /confluence/gateway/credential-provider-arn → Created by create_apikey_provider.py
"""

import boto3
import os
from botocore.exceptions import ClientError

# ─── Region ───────────────────────────────────────────────────────────────────
# Allow override via environment variable (GitHub Actions sets AWS_REGION)
_REGION = os.environ.get("AWS_REGION", "us-east-1")


def _get_ssm(name: str, default: str = "") -> str:
    """
    Fetch a plain-string SSM parameter.
    Falls back to `default` if the parameter is missing (useful for first-time bootstrap).
    """
    try:
        ssm = boto3.client("ssm", region_name=_REGION)
        resp = ssm.get_parameter(Name=name)
        return resp["Parameter"]["Value"]
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ParameterNotFound":
            if default:
                print(f"⚠️  SSM param '{name}' not found — using default: '{default}'")
                return default
            raise RuntimeError(
                f"Required SSM parameter '{name}' not found in region '{_REGION}'.\n"
                f"Run setup-guide.md steps to create it."
            ) from e
        raise


def _get_ssm_secure(name: str) -> str:
    """Fetch a SecureString SSM parameter (decrypted)."""
    try:
        ssm = boto3.client("ssm", region_name=_REGION)
        resp = ssm.get_parameter(Name=name, WithDecryption=True)
        return resp["Parameter"]["Value"]
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ParameterNotFound":
            raise RuntimeError(
                f"Required SSM SecureString parameter '{name}' not found.\n"
                f"Run setup-guide.md steps to create it."
            ) from e
        raise


# ─── Environment tag ──────────────────────────────────────────────────────────
ENV = "dev"

# ─── AWS Account & Region ─────────────────────────────────────────────────────
AWS_ACCOUNT = _get_ssm(
    "/confluence/gateway/aws-account-id",
    default=os.environ.get("CDK_DEFAULT_ACCOUNT", "")
)
AWS_REGION = _get_ssm(
    "/confluence/gateway/aws-region",
    default=_REGION
)

# ─── CDK Stack name ───────────────────────────────────────────────────────────
STACK_NAME = f"ConfluenceGatewayStack-{ENV.capitalize()}"

# ─── Gateway config ───────────────────────────────────────────────────────────
GATEWAY_NAME = f"confluence-gateway-{ENV}"
GATEWAY_DESCRIPTION = "AgentCore Gateway for Confluence integration (dev)"

# ─── Credential Provider ARN (set by create_apikey_provider.py) ───────────────
CREDENTIAL_PROVIDER_ARN = _get_ssm(
    "/confluence/gateway/credential-provider-arn",
    default=""   # empty until the script is run
)

# ─── Confluence config (informational — used in tests) ────────────────────────
CONFLUENCE_SUBDOMAIN = _get_ssm(
    "/confluence/gateway/confluence-subdomain",
    default="rassk97"
)

# ─── Tags applied to all CDK resources ────────────────────────────────────────
TAGS = {
    "Environment": ENV,
    "Project": "ConfluenceGateway",
    "ManagedBy": "CDK",
}
