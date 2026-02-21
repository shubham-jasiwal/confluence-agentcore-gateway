#!/usr/bin/env python3
"""
test/test_api_gateway.py

Integration test for the AgentCore Gateway with API Key Authentication.
All configuration is read from SSM Parameter Store — no hardcoded values.

Usage:
    python3 test/test_api_gateway.py

Prerequisites:
    - AWS credentials configured (env vars or ~/.aws/credentials)
    - SSM parameters set (see setup-guide.md)
    - Gateway deployed and Confluence target attached
"""

import boto3
import requests
import json
import sys
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError

# ─── Load config from SSM ─────────────────────────────────────────────────────
REGION       = __import__("os").environ.get("AWS_REGION", "us-east-1")
SERVICE_NAME = "bedrock-agentcore"


def _ssm_get(name: str, default: str = "") -> str:
    try:
        ssm = boto3.client("ssm", region_name=REGION)
        return ssm.get_parameter(Name=name)["Parameter"]["Value"]
    except ClientError:
        if default:
            return default
        print(f"❌ SSM parameter '{name}' not found. Run setup-guide.md steps first.")
        sys.exit(1)


GATEWAY_ID           = _ssm_get("/confluence/gateway/gateway-id")
CONFLUENCE_SUBDOMAIN = _ssm_get("/confluence/gateway/confluence-subdomain", "rassk97")
TEST_PAGE_ID         = _ssm_get("/confluence/gateway/test-page-id", "622593")

GATEWAY_URL = (
    f"https://{GATEWAY_ID}.gateway.bedrock-agentcore.{REGION}.amazonaws.com/mcp"
)

# ─── SigV4 signing ───────────────────────────────────────────────────────────

def sign_request(method: str, url: str, body: str) -> dict:
    """Sign request with AWS SigV4."""
    headers = {"Content-Type": "application/json"}
    req = AWSRequest(method=method, url=url, data=body, headers=headers)
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    SigV4Auth(creds, SERVICE_NAME, REGION).add_auth(req)
    return dict(req.headers)


def mcp_call(method: str, params: dict = None, call_id: int = 1) -> dict:
    """Make an MCP JSON-RPC call to the gateway."""
    payload = {"jsonrpc": "2.0", "id": call_id, "method": method}
    if params:
        payload["params"] = params
    body = json.dumps(payload)
    headers = sign_request("POST", GATEWAY_URL, body)
    resp = requests.post(GATEWAY_URL, headers=headers, data=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ─── Test cases ──────────────────────────────────────────────────────────────

def test_list_tools() -> list:
    print("=" * 70)
    print("TEST: List Gateway Tools")
    print("=" * 70)
    print(f"Gateway ID  : {GATEWAY_ID}")
    print(f"Gateway URL : {GATEWAY_URL}")
    print(f"Confluence  : {CONFLUENCE_SUBDOMAIN}.atlassian.net\n")

    result = mcp_call("tools/list")

    if "result" in result and "tools" in result["result"]:
        tools = result["result"]["tools"]
        print(f"✅ Gateway accessible — {len(tools)} tool(s) found:")
        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool['name']}")
        return tools
    else:
        print("❌ Error response:")
        print(json.dumps(result, indent=2))
        return []


def test_search_pages(tool_name: str):
    print("\n" + "=" * 70)
    print(f"TEST: Search Confluence Pages  [{tool_name}]")
    print("=" * 70)

    result = mcp_call(
        "tools/call",
        params={
            "name": tool_name,
            "arguments": {
                "cql": "type=page",
                "sub-domain": CONFLUENCE_SUBDOMAIN,
                "limit": 3,
            },
        },
        call_id=2,
    )

    if "result" in result and not result["result"].get("isError"):
        data = json.loads(result["result"]["content"][0]["text"])
        print(f"✅ SUCCESS — {data.get('totalSize', 0)} page(s) found:")
        for page in data.get("results", [])[:3]:
            print(f"  📄 {page['title']} (ID: {page['id']})")
    else:
        print("❌ Error:")
        print(json.dumps(result, indent=2))


def test_get_page(tool_name: str, page_id: str = TEST_PAGE_ID):
    print("\n" + "=" * 70)
    print(f"TEST: Get Page by ID [{page_id}]  [{tool_name}]")
    print("=" * 70)

    result = mcp_call(
        "tools/call",
        params={
            "name": tool_name,
            "arguments": {
                "id": int(page_id),
                "sub-domain": CONFLUENCE_SUBDOMAIN,
            },
        },
        call_id=3,
    )

    if "result" in result and not result["result"].get("isError"):
        data = json.loads(result["result"]["content"][0]["text"])
        print(f"✅ SUCCESS:")
        print(f"  📄 Title  : {data.get('title')}")
        print(f"     ID     : {data.get('id')}")
        print(f"     Status : {data.get('status')}")
    else:
        print("❌ Error:")
        print(json.dumps(result, indent=2))


def test_get_spaces(tool_name: str):
    print("\n" + "=" * 70)
    print(f"TEST: List Confluence Spaces  [{tool_name}]")
    print("=" * 70)

    result = mcp_call(
        "tools/call",
        params={
            "name": tool_name,
            "arguments": {
                "sub-domain": CONFLUENCE_SUBDOMAIN,
                "limit": 5,
            },
        },
        call_id=4,
    )

    if "result" in result and not result["result"].get("isError"):
        data = json.loads(result["result"]["content"][0]["text"])
        print(f"✅ SUCCESS — {data.get('totalSize', 0)} space(s):")
        for space in data.get("results", []):
            print(f"  📁 {space.get('name')} (Key: {space.get('key')})")
    else:
        print("❌ Error:")
        print(json.dumps(result, indent=2))


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tools = test_list_tools()

    if not tools:
        print("\n⚠️  No tools found. Attach a Confluence target to the gateway first.")
        sys.exit(1)

    def find_tool(keyword: str):
        return next((t for t in tools if keyword in t.get("name", "")), None)

    search_tool    = find_tool("searchByCQL")
    get_page_tool  = find_tool("getPageById")
    get_space_tool = find_tool("getSpaces")

    if search_tool:
        test_search_pages(search_tool["name"])
    if get_page_tool:
        test_get_page(get_page_tool["name"])
    if get_space_tool:
        test_get_spaces(get_space_tool["name"])

    print("\n" + "=" * 70)
    print("✅ ALL TESTS COMPLETE")
    print("=" * 70)
