#!/usr/bin/env python3
import boto3
import json
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_basic_agent.py <agent_runtime_arn>")
        sys.exit(1)

    agent_arn = sys.argv[1]
    region = agent_arn.split(":")[3]

    client = boto3.client("bedrock-agentcore", region_name=region)

    print("Invoking agent...")
    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        qualifier="DEFAULT",
        payload=json.dumps({"prompt": "What is Amazon Bedrock AgentCore?"}),
    )

    content = []
    for chunk in response.get("response", []):
        content.append(chunk.decode("utf-8"))

    result = json.loads("".join(content))
    print(f"\nStatus: {result.get('status')}")
    print(f"Response: {result.get('response', result.get('error'))}")

if __name__ == "__main__":
    main()