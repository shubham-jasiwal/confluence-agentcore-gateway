"""
stacks/agentcore_gateway/confluence_gateway_stack.py

Main CDK Stack for the Confluence AgentCore Gateway.
All configuration values are supplied by infra/config/dev.py (SSM-backed).
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_iam as iam,
)
from constructs import Construct
from typing import Any

from stacks.agentcore_gateway.constructs.agent_core_gateway import AgentCoreGateway


class ConfluenceGatewayStack(Stack):
    """
    Top-level CDK stack.

    Creates:
      - AgentCoreGateway construct (IAM-authenticated MCP gateway)
      - CloudFormation Outputs for Gateway URL, ID, and Role ARN
    """

    def __init__(self, scope: Construct, stack_id: str, *, config: Any, **kwargs):
        super().__init__(scope, stack_id, **kwargs)

        # ── Create the Gateway ────────────────────────────────────────────────
        self.gateway_construct = AgentCoreGateway(
            self,
            "ConfluenceGateway",
            name=config.GATEWAY_NAME,
            description=config.GATEWAY_DESCRIPTION,
            inbound_identity_config={"type": "IAM"},
            tags=config.TAGS,
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(
            self,
            "GatewayURL",
            value=self.gateway_construct.gateway_url,
            description="AgentCore Gateway MCP endpoint URL",
            export_name=f"{stack_id}-GatewayURL",
        )

        CfnOutput(
            self,
            "GatewayID",
            value=self.gateway_construct.gateway_id,
            description="AgentCore Gateway ID",
            export_name=f"{stack_id}-GatewayID",
        )

        CfnOutput(
            self,
            "GatewayRoleArn",
            value=self.gateway_construct.gateway_role.role_arn,
            description="Execution role ARN for the AgentCore Gateway",
            export_name=f"{stack_id}-GatewayRoleArn",
        )

        CfnOutput(
            self,
            "CredentialProviderArn",
            value=config.CREDENTIAL_PROVIDER_ARN or "NOT_SET_YET",
            description="API Key Credential Provider ARN (from SSM)",
        )
