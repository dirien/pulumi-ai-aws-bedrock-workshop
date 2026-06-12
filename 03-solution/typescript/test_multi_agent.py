#!/usr/bin/env python3
"""Invoke the orchestrator (and optionally the specialist) and print the replies.

The orchestrator speaks the plain HTTP contract from Module 2, so it takes a
{"prompt": ...} payload. The specialist speaks the A2A protocol, so calling it
directly means sending a JSON-RPC 2.0 envelope through the same data plane.

Usage:
    python test_multi_agent.py <orchestrator_arn> [specialist_arn]
"""
import json
import sys
import uuid

import boto3
from botocore.config import Config


def invoke_orchestrator(client, arn, prompt):
    print(f"\nPrompt: {prompt}")
    print("Invoking (delegated queries can take a few minutes)...")
    response = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        qualifier="DEFAULT",
        payload=json.dumps({"prompt": prompt}),
    )
    status = response["ResponseMetadata"]["HTTPStatusCode"]
    result = json.loads(response["response"].read().decode("utf-8"))
    print(f"Status: {status}")
    print(f"Response: {result.get('response', result.get('error', result))}")


def show_agent_card(client, arn):
    """Fetch the specialist's agent card - the same discovery step the
    orchestrator's A2A client performs before it sends any message."""
    response = client.get_agent_card(agentRuntimeArn=arn, qualifier="DEFAULT")
    card = response["agentCard"]
    capabilities = card.get("capabilities", {})
    print(f"\nDiscovered agent card: {card.get('name')} - {card.get('description')}")
    print(
        f"(protocol: {card.get('preferredTransport', 'JSONRPC')}, "
        f"streaming: {capabilities.get('streaming')})"
    )


def invoke_specialist_a2a(client, arn, prompt):
    """Call the A2A specialist directly: wrap the prompt in a JSON-RPC envelope."""
    print(f"\nPrompt (direct to specialist, A2A): {prompt}")
    envelope = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "text", "text": prompt}],
            }
        },
    }
    response = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        qualifier="DEFAULT",
        payload=json.dumps(envelope),
    )
    result = json.loads(response["response"].read().decode("utf-8"))
    task = result.get("result", {})
    print(f"Task state: {task.get('status', {}).get('state', 'unknown')}")
    for artifact in task.get("artifacts", []):
        for part in artifact.get("parts", []):
            if part.get("kind") == "text":
                print(f"Response: {part['text']}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_multi_agent.py <orchestrator_arn> [specialist_arn]")
        sys.exit(1)

    orchestrator_arn = sys.argv[1]
    specialist_arn = sys.argv[2] if len(sys.argv) > 2 else None
    region = orchestrator_arn.split(":")[3]

    # Delegated calls can run for minutes; bump the read timeout well past
    # boto3's 60s default so the test doesn't give up early.
    client = boto3.client(
        "bedrock-agentcore",
        region_name=region,
        config=Config(read_timeout=900, connect_timeout=30, retries={"max_attempts": 0}),
    )

    # The specialist publishes an agent card - fetch it the way any A2A
    # client (including the orchestrator) discovers an agent.
    if specialist_arn:
        show_agent_card(client, specialist_arn)

    # Simple query: the orchestrator answers directly.
    invoke_orchestrator(client, orchestrator_arn, "Hello! Can you introduce yourself?")

    # Complex query: the orchestrator delegates to the specialist over A2A.
    invoke_orchestrator(
        client,
        orchestrator_arn,
        "Ask the specialist: what is serverless computing and when should I use it?",
    )

    # Optionally hit the specialist directly to confirm it works on its own.
    if specialist_arn:
        invoke_specialist_a2a(
            client,
            specialist_arn,
            "What are the pros and cons of event-driven architecture?",
        )


if __name__ == "__main__":
    main()
