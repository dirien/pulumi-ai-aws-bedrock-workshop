#!/usr/bin/env python3
"""Invoke the orchestrator (and optionally the specialist) and print the replies.

Usage:
    python test_multi_agent.py <orchestrator_arn> [specialist_arn]
"""
import json
import sys

import boto3
from botocore.config import Config


def invoke(client, arn, prompt):
    print(f"\nPrompt: {prompt}")
    print("Invoking (A2A flows can take a few minutes)...")
    response = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        qualifier="DEFAULT",
        payload=json.dumps({"prompt": prompt}),
    )
    status = response["ResponseMetadata"]["HTTPStatusCode"]
    result = json.loads(response["response"].read().decode("utf-8"))
    print(f"Status: {status}")
    print(f"Response: {result.get('response', result.get('error', result))}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_multi_agent.py <orchestrator_arn> [specialist_arn]")
        sys.exit(1)

    orchestrator_arn = sys.argv[1]
    specialist_arn = sys.argv[2] if len(sys.argv) > 2 else None
    region = orchestrator_arn.split(":")[3]

    # A2A calls in the orchestrator can run for minutes; bump the read timeout
    # well past boto3's 60s default so the test doesn't give up early.
    client = boto3.client(
        "bedrock-agentcore",
        region_name=region,
        config=Config(read_timeout=900, connect_timeout=30, retries={"max_attempts": 0}),
    )

    # Simple query: the orchestrator answers directly.
    invoke(client, orchestrator_arn, "Hello! Can you introduce yourself?")

    # Complex query: the orchestrator delegates to the specialist (A2A).
    invoke(
        client,
        orchestrator_arn,
        "Ask the specialist: what is serverless computing and when should I use it?",
    )

    # Optionally hit the specialist directly to confirm it works on its own.
    if specialist_arn:
        invoke(
            client,
            specialist_arn,
            "What are the pros and cons of event-driven architecture?",
        )


if __name__ == "__main__":
    main()
