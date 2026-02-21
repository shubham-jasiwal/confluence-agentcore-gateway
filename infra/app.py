#!/usr/bin/env python3
"""
infra/app.py

CDK application entrypoint.
Reads all config from SSM (via infra/config/dev.py) — no hardcoded values.

Usage:
    cdk --app "python3 infra/app.py" synth
    cdk --app "python3 infra/app.py" deploy ConfluenceGatewayStack-Dev
"""

import sys
import os

# Add project root to path so stacks/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aws_cdk as cdk
from infra.config import dev as config
from stacks.agentcore_gateway.confluence_gateway_stack import ConfluenceGatewayStack

app = cdk.App()

# ─── Dev stack ────────────────────────────────────────────────────────────────
stack = ConfluenceGatewayStack(
    app,
    config.STACK_NAME,
    config=config,
    env=cdk.Environment(
        account=config.AWS_ACCOUNT,
        region=config.AWS_REGION,
    ),
    tags=config.TAGS,
)

# ─── Apply tags to all resources in the stack ─────────────────────────────────
for key, value in config.TAGS.items():
    cdk.Tags.of(stack).add(key, value)

app.synth()
