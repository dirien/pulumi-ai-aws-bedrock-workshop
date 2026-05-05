#!/usr/bin/env python3
import argparse
import sys
import time
import uuid

import boto3
from botocore.exceptions import ClientError


MAX_ATTEMPTS = 20
WAIT_SECONDS = 3


def _is_transient_state_error(exc: ClientError) -> bool:
    message = str(exc)
    return (
        "in Updating state" in message
        or "in Deleting state" in message
    )


def _find_target_by_name(client, gateway_id: str, target_name: str):
    next_token = None
    while True:
        kwargs = {"gatewayIdentifier": gateway_id, "maxResults": 100}
        if next_token:
            kwargs["nextToken"] = next_token
        response = client.list_gateway_targets(**kwargs)
        for item in response.get("items", []):
            if item.get("name") == target_name:
                return item
        next_token = response.get("nextToken")
        if not next_token:
            return None


def _upsert_target(
    client,
    region: str,
    gateway_id: str,
    target_name: str,
    description: str,
    endpoint: str,
):
    target_configuration = {
        "mcp": {
            "mcpServer": {
                "endpoint": endpoint,
            }
        }
    }
    credential_provider_configurations = [
        {
            "credentialProviderType": "GATEWAY_IAM_ROLE",
            "credentialProvider": {
                "iamCredentialProvider": {
                    "service": "bedrock-agentcore",
                    "region": region,
                }
            },
        }
    ]

    for attempt in range(MAX_ATTEMPTS):
        existing = _find_target_by_name(client, gateway_id, target_name)
        if existing:
            target_id = existing["targetId"]
            existing_endpoint = (
                existing.get("targetConfiguration", {})
                .get("mcp", {})
                .get("mcpServer", {})
                .get("endpoint")
            )
            if existing_endpoint != endpoint or existing.get("description") != description:
                try:
                    client.update_gateway_target(
                        gatewayIdentifier=gateway_id,
                        targetId=target_id,
                        name=target_name,
                        description=description,
                        targetConfiguration=target_configuration,
                        credentialProviderConfigurations=credential_provider_configurations,
                    )
                except ClientError as exc:
                    if _is_transient_state_error(exc) and attempt < MAX_ATTEMPTS - 1:
                        time.sleep(WAIT_SECONDS)
                        continue
                    raise
            return target_id

        try:
            created = client.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=target_name,
                description=description,
                clientToken=str(uuid.uuid4()),
                targetConfiguration=target_configuration,
                credentialProviderConfigurations=credential_provider_configurations,
            )
            return created["targetId"]
        except ClientError as exc:
            if _is_transient_state_error(exc) and attempt < MAX_ATTEMPTS - 1:
                time.sleep(WAIT_SECONDS)
                continue
            raise

    raise RuntimeError("Timed out while waiting to upsert gateway target")


def _delete_target(client, gateway_id: str, target_name: str):
    existing = _find_target_by_name(client, gateway_id, target_name)
    if not existing:
        return ""
    target_id = existing["targetId"]

    for attempt in range(MAX_ATTEMPTS):
        try:
            client.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
        except ClientError as exc:
            if not _is_transient_state_error(exc) and "not found" not in str(exc).lower():
                raise
            if attempt == MAX_ATTEMPTS - 1:
                raise

        time.sleep(WAIT_SECONDS)
        if not _find_target_by_name(client, gateway_id, target_name):
            return target_id

    raise RuntimeError("Timed out while waiting to delete gateway target")


def main():
    parser = argparse.ArgumentParser(description="Manage Bedrock AgentCore Gateway Target")
    parser.add_argument("--mode", choices=["upsert", "delete"], required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--gateway-id", required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--endpoint", default="")

    args = parser.parse_args()

    client = boto3.client("bedrock-agentcore-control", region_name=args.region)

    if args.mode == "upsert":
        if not args.endpoint:
            raise ValueError("--endpoint is required in upsert mode")
        target_id = _upsert_target(
            client,
            args.region,
            args.gateway_id,
            args.target_name,
            args.description,
            args.endpoint,
        )
        print(target_id)
        return

    deleted_target_id = _delete_target(client, args.gateway_id, args.target_name)
    print(deleted_target_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Keep stderr readable for Pulumi command logs.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
