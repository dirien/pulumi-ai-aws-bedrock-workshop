#!/usr/bin/env python3
"""Invoke a deployed AgentCore runtime and print its response.

Usage:
    python test_basic_agent.py <agent_runtime_arn>
"""
import json
import sys

import boto3


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

    status = response["ResponseMetadata"]["HTTPStatusCode"]
    body = response["response"].read().decode("utf-8")
    result = json.loads(body)

    print(f"Status: {status}")
    print(f"Response: {result.get('response', result.get('error'))}")


if __name__ == "__main__":
    main()
