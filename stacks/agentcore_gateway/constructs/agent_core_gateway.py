"""
stacks/agentcore_gateway/constructs/agent_core_gateway.py

CDK Construct for AWS Bedrock AgentCore Gateway.
Refactored from root-level agent_core_gateway.py into the proper package structure.
"""

from aws_cdk import (
    Stack,
    CfnOutput,
    aws_iam as iam,
    aws_bedrockagentcore as bedrock,
)
from constructs import Construct
from typing import Optional, Any, Dict


class AgentCoreGateway(Construct):
    """
    Reusable CDK construct that creates a Bedrock AgentCore Gateway (MCP protocol).

    Supports two inbound identity types:
      - IAM   : AWS SigV4-authenticated callers
      - Cognito: Custom JWT via a Cognito User Pool
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        name: str,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        inbound_identity_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(scope, id)

        # ── 1. Gateway Execution Role ─────────────────────────────────────────
        self.gateway_role = iam.Role(
            self,
            "GatewayExecutionRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description=f"Execution role for AgentCore Gateway '{name}'",
        )

        # Grant minimum permissions: read SSM parameters for credential provider ARN
        self.gateway_role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadSSMParameters",
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/confluence/*"
                ],
            )
        )

        # Grant permission to use the Bedrock AgentCore credential providers
        self.gateway_role.add_to_policy(
            iam.PolicyStatement(
                sid="UseCredentialProviders",
                actions=[
                    "bedrock-agentcore:GetCredentialProvider",
                    "bedrock-agentcore:GetCredential",       # read secret from token vault at runtime
                    "bedrock-agentcore:InvokeGateway",
                ],
                resources=["*"],
            )
        )

        # ── 2. Authorizer config ──────────────────────────────────────────────
        authorizer_type = None
        authorizer_config = None

        if inbound_identity_config:
            identity_type = inbound_identity_config.get("type")

            if identity_type == "IAM":
                authorizer_type = "AWS_IAM"
                # No additional authorizer_config needed for IAM

            elif identity_type == "Cognito":
                authorizer_type = "CUSTOM_JWT"
                pool_id = inbound_identity_config.get("user_pool_id")
                region = Stack.of(self).region

                if not pool_id:
                    user_pool_arn = inbound_identity_config.get("user_pool_arn", "")
                    pool_id = user_pool_arn.split("/")[-1] if user_pool_arn else "placeholder"

                issuer_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
                client_ids = inbound_identity_config.get("client_ids", [])

                authorizer_config = bedrock.CfnGateway.AuthorizerConfigurationProperty(
                    custom_jwt_authorizer=bedrock.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                        discovery_url=f"{issuer_url}/.well-known/openid-configuration",
                        allowed_audience=client_ids,
                        allowed_clients=client_ids,
                    )
                )

        # ── 3. Create Gateway resource ────────────────────────────────────────
        self.gateway = bedrock.CfnGateway(
            self,
            "Resource",
            name=name,
            description=description,
            role_arn=self.gateway_role.role_arn,
            protocol_type="MCP",
            protocol_configuration=None,
            authorizer_type=authorizer_type,
            authorizer_configuration=authorizer_config,
            tags=tags,
        )

        # Friendly accessors
        self.gateway_id: str = self.gateway.ref
        self.gateway_arn: str = self.gateway.get_att("Arn").to_string()
        self.gateway_url: str = self.gateway.get_att("GatewayUrl").to_string()
