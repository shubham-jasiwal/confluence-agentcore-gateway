#!/usr/bin/env bash
# =============================================================================
# setup-ssm-params.sh
#
# One-time setup: stores all required SSM parameters for the Confluence
# AgentCore Gateway. Run this before your first CDK deploy.
#
# Usage:
#   chmod +x scripts/setup-ssm-params.sh
#   ./scripts/setup-ssm-params.sh
# =============================================================================

set -e

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   Confluence AgentCore Gateway — SSM Parameter Setup  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Verify AWS CLI is configured ─────────────────────────────────────────────
echo "🔍 Checking AWS credentials..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || {
    echo -e "${RED}❌ AWS CLI not configured. Run 'aws configure' first.${NC}"
    exit 1
}
REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")

echo -e "${GREEN}✅ Logged in as account: ${ACCOUNT_ID} | region: ${REGION}${NC}"
echo ""

# ── Prompt for values ─────────────────────────────────────────────────────────
read -p "Enter your Confluence subdomain (e.g. 'rassk97'): " SUBDOMAIN
read -p "Enter your Confluence email: " EMAIL
read -s -p "Enter your Atlassian API token: " API_TOKEN
echo ""
read -p "Enter your Confluence test page ID (leave blank to skip): " TEST_PAGE_ID
read -p "Enter AWS region [${REGION}]: " REGION_INPUT
REGION="${REGION_INPUT:-$REGION}"

echo ""
echo "────────────────────────────────────────────────────────"
echo "  About to store the following SSM parameters:"
echo "  /confluence/gateway/aws-account-id   = ${ACCOUNT_ID}"
echo "  /confluence/gateway/aws-region       = ${REGION}"
echo "  /confluence/gateway/confluence-subdomain = ${SUBDOMAIN}"
echo "  /confluence/gateway/confluence-email = ${EMAIL}"
echo "  /confluence/gateway/confluence-api-token = ******* (SecureString)"
if [ -n "$TEST_PAGE_ID" ]; then
echo "  /confluence/gateway/test-page-id     = ${TEST_PAGE_ID}"
fi
echo "────────────────────────────────────────────────────────"
echo ""
read -p "Proceed? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""

# ── Write parameters ──────────────────────────────────────────────────────────
store_param() {
    local name="$1"
    local value="$2"
    local type="${3:-String}"

    aws ssm put-parameter \
        --region "$REGION" \
        --name "$name" \
        --value "$value" \
        --type "$type" \
        --overwrite \
        --no-cli-pager > /dev/null

    echo -e "${GREEN}✅ ${name}${NC}"
}

store_param "/confluence/gateway/aws-account-id"       "$ACCOUNT_ID"
store_param "/confluence/gateway/aws-region"           "$REGION"
store_param "/confluence/gateway/confluence-subdomain" "$SUBDOMAIN"
store_param "/confluence/gateway/confluence-email"     "$EMAIL"
store_param "/confluence/gateway/confluence-api-token" "$API_TOKEN" "SecureString"

if [ -n "$TEST_PAGE_ID" ]; then
    store_param "/confluence/gateway/test-page-id" "$TEST_PAGE_ID"
fi

# ── Verify ────────────────────────────────────────────────────────────────────
echo ""
echo "📋 Stored parameters:"
aws ssm get-parameters-by-path \
    --path "/confluence/gateway/" \
    --region "$REGION" \
    --query "Parameters[].Name" \
    --output table \
    --no-cli-pager

echo ""
echo -e "${GREEN}✅ Done! You can now run: cdk --app 'python3 infra/app.py' deploy ConfluenceGatewayStack-Dev${NC}"
echo ""
