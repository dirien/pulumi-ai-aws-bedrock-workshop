#!/usr/bin/env python3
"""
Test script for deployed MCP server via AgentCore Gateway.
Uses the MCP Python client library to communicate through the gateway.
"""

import asyncio
import sys
from datetime import timedelta
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _format_exception_details(exc, level=0):
    indent = "  " * level
    lines = [f"{indent}- {type(exc).__name__}: {exc}"]
    # Python 3.11+ ExceptionGroup support
    if isinstance(exc, BaseExceptionGroup):
        for sub_exc in exc.exceptions:
            lines.extend(_format_exception_details(sub_exc, level + 1))
    return lines


async def test_mcp_server(gateway_url, bearer_token):
    """Test the deployed MCP server through the AgentCore Gateway."""

    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }

    print(f"Connecting to: {gateway_url}")
    print()

    try:
        async with streamablehttp_client(
            gateway_url, headers, timeout=timedelta(seconds=120), terminate_on_close=False
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                print("🔄 Initializing MCP session...")
                await session.initialize()
                print("✓ MCP session initialized\n")

                print("🔄 Listing available tools...")
                tool_result = await session.list_tools()

                print("\n📋 Available MCP Tools:")
                print("=" * 50)
                for tool in tool_result.tools:
                    print(f"🔧 {tool.name}: {tool.description}")

                print("\n🧪 Testing MCP Tools:")
                print("=" * 50)

                # Test add_numbers (gateway prefixes tool names with target name)
                add_tool = next(
                    (t.name for t in tool_result.tools if "add_numbers" in t.name),
                    "add_numbers",
                )
                print(f"\n➕ Testing {add_tool}(5, 3)...")
                add_result = await session.call_tool(
                    name=add_tool, arguments={"a": 5, "b": 3}
                )
                print(f"   Result: {add_result.content[0].text}")

                # Test multiply_numbers
                multiply_tool = next(
                    (t.name for t in tool_result.tools if "multiply_numbers" in t.name),
                    "multiply_numbers",
                )
                print(f"\n✖️  Testing {multiply_tool}(4, 7)...")
                multiply_result = await session.call_tool(
                    name=multiply_tool, arguments={"a": 4, "b": 7}
                )
                print(f"   Result: {multiply_result.content[0].text}")

                # Test greet_user
                greet_tool = next(
                    (t.name for t in tool_result.tools if "greet_user" in t.name),
                    "greet_user",
                )
                print(f"\n👋 Testing {greet_tool}('Alice')...")
                greet_result = await session.call_tool(
                    name=greet_tool, arguments={"name": "Alice"}
                )
                print(f"   Result: {greet_result.content[0].text}")

                print("\n✅ MCP tool testing completed!")

    except Exception as e:
        print("❌ Error while testing MCP tools:")
        for line in _format_exception_details(e):
            print(line)
        sys.exit(1)


def main():
    if len(sys.argv) < 3:
        print("Usage: python test_mcp_server.py <gateway_url> <bearer_token>")
        print("\nExample:")
        print(
            "  python test_mcp_server.py https://my-gw.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp eyJraWQiOiJ..."
        )
        sys.exit(1)

    gateway_url = sys.argv[1]
    bearer_token = sys.argv[2]

    asyncio.run(test_mcp_server(gateway_url, bearer_token))


if __name__ == "__main__":
    main()
