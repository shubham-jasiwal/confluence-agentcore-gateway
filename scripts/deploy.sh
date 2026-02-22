#!/usr/bin/env bash
# =============================================================================
# scripts/deploy.sh
#
# Single entrypoint for deploying the Confluence AgentCore Gateway.
# Handles everything in order:
#   1. Check / create / update API Key credential provider
#   2. CDK bootstrap (idempotent)
#   3. CDK synth (validate templates)
#   4. CDK deploy
#   5. Store Gateway ID in SSM
#   6. Run integration tests (optional, pass --test to enable)
#
# Usage:
#   ./scripts/deploy.sh              # deploy only
#   ./scripts/deploy.sh --test       # deploy + run integration tests
#   ./scripts/deploy.sh --dry-run    # synth only, no deploy
#
# Required env vars (set from GitHub Secrets in CI):
#   CONFLUENCE_API_KEY   base64("email:api_token")
#   AWS_REGION           (default: us-east-1)
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}ℹ  $*${NC}"; }
success() { echo -e "${GREEN}✅ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠️  $*${NC}"; }
error()   { echo -e "${RED}❌ $*${NC}"; exit 1; }

# ── Args ─────────────────────────────────────────────────────────────────────
RUN_TESTS=false
DRY_RUN=false
for arg in "$@"; do
  case $arg in
    --test)    RUN_TESTS=true ;;
    --dry-run) DRY_RUN=true ;;
  esac
done

# ── Config ───────────────────────────────────────────────────────────────────
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="ConfluenceGatewayStack-Dev"
CDK_APP="python3 infra/app.py"
OUTPUTS_FILE="cdk-outputs.json"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     Confluence AgentCore Gateway — Deploy Script      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Step 0: Verify AWS credentials ───────────────────────────────────────────
info "Verifying AWS credentials..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) \
  || error "AWS credentials not configured. Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY."
success "Authenticated as account: ${ACCOUNT_ID} | region: ${REGION}"
echo ""

# ── Step 1: API Key Credential Provider ──────────────────────────────────────
echo "━━━ Step 1: API Key Credential Provider ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -z "${CONFLUENCE_API_KEY:-}" ]; then
  warn "CONFLUENCE_API_KEY is not set — skipping credential provider step."
  warn "Set it as: export CONFLUENCE_API_KEY=\$(echo -n 'email:token' | base64)"
  warn "The pipeline will fail if the provider ARN is not already in SSM."
else
  info "Running create_apikey_provider.py (creates or updates)..."
  python3 stacks/agentcore_gateway/scripts/create_apikey_provider.py
  success "Credential provider ready."
fi
echo ""

# ── Step 2: CDK Bootstrap ─────────────────────────────────────────────────────
echo "━━━ Step 2: CDK Bootstrap ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Bootstrapping CDK environment (safe to run repeatedly)..."
cdk bootstrap \
  --app "$CDK_APP" \
  "aws://${ACCOUNT_ID}/${REGION}" \
  --require-approval never 2>&1 | tail -5
success "Bootstrap complete."
echo ""

# ── Step 3: CDK Synth ────────────────────────────────────────────────────────
echo "━━━ Step 3: CDK Synth (validate templates) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Synthesizing CloudFormation templates..."
cdk --app "$CDK_APP" synth --quiet
success "Synth passed — templates are valid."
echo ""

if [ "$DRY_RUN" = true ]; then
  warn "Dry run mode — stopping before deploy."
  exit 0
fi

# ── Step 4: CDK Deploy ───────────────────────────────────────────────────────
echo "━━━ Step 4: CDK Deploy ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Deploying ${STACK_NAME}..."
cdk --app "$CDK_APP" deploy "$STACK_NAME" \
  --require-approval never \
  --outputs-file "$OUTPUTS_FILE"
success "Stack deployed."
echo ""

# ── Step 5: Store Gateway ID in SSM ──────────────────────────────────────────
echo "━━━ Step 5: Store Gateway ID in SSM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "$OUTPUTS_FILE" ]; then
  GATEWAY_ID=$(python3 -c "
import json, sys
outputs = json.load(open('${OUTPUTS_FILE}'))
stack = list(outputs.keys())[0]
print(outputs[stack].get('GatewayID', ''))
" 2>/dev/null || echo "")

  if [ -n "$GATEWAY_ID" ]; then
    aws ssm put-parameter \
      --name "/confluence/gateway/gateway-id" \
      --value "$GATEWAY_ID" \
      --type String \
      --overwrite \
      --region "$REGION" \
      --no-cli-pager
    success "Gateway ID stored in SSM: ${GATEWAY_ID}"
  else
    warn "No GatewayID found in CDK outputs — skipping SSM write."
  fi

  echo ""
  info "Deployment outputs:"
  python3 -m json.tool "$OUTPUTS_FILE" 2>/dev/null || true
else
  warn "No outputs file found — skipping SSM write."
fi
echo ""

# ── Step 6: Integration Tests (optional) ─────────────────────────────────────
if [ "$RUN_TESTS" = true ]; then
  echo "━━━ Step 6: Integration Tests ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  info "Running integration tests..."
  python3 test/test_api_gateway.py
  success "All tests passed."
  echo ""
else
  info "Skipping integration tests (pass --test to enable)."
  echo ""
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════╗"
echo -e "║  ${GREEN}✅ Deployment complete!${NC}                               ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Stack:   ${STACK_NAME}"
echo "  Account: ${ACCOUNT_ID}"
echo "  Region:  ${REGION}"
echo ""
echo "  Next: Attach the Confluence target in AWS Console"
echo "  → Bedrock → AgentCore → Gateways → Targets → Add Target"
echo ""
