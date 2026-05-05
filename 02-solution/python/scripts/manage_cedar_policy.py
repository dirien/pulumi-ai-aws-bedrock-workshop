#!/usr/bin/env python3
"""Manage Cedar policy enforcement for an AgentCore Gateway.

Upsert mode:
  1. Create (or find existing) Policy Engine, wait for ACTIVE
  2. Create (or update) Cedar policy
  3. Attach Policy Engine to Gateway in ENFORCE mode via update_gateway

Delete mode:
  1. Detach Policy Engine from Gateway (update_gateway without policyEngineConfiguration)
  2. Delete policy
  3. Delete Policy Engine

Stdout: the policyEngineId (used by Pulumi to capture the resource id).
"""

import argparse
import re
import sys
import time
import uuid

import boto3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_policy_engine_by_name(client, name: str):
    next_token = None
    while True:
        kwargs = {"maxResults": 100}
        if next_token:
            kwargs["nextToken"] = next_token
        response = client.list_policy_engines(**kwargs)
        for item in response.get("items", []):
            if item.get("name") == name:
                return item
        next_token = response.get("nextToken")
        if not next_token:
            return None


def _sanitize_identifier(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not sanitized:
        return "PolicyResource"
    if not sanitized[0].isalpha():
        sanitized = f"P_{sanitized}"
    return sanitized


def _find_policy_by_name(client, policy_engine_id: str, name: str):
    next_token = None
    while True:
        kwargs = {"policyEngineId": policy_engine_id, "maxResults": 100}
        if next_token:
            kwargs["nextToken"] = next_token
        response = client.list_policies(**kwargs)
        for item in response.get("items", []):
            if item.get("name") == name:
                return item
        next_token = response.get("nextToken")
        if not next_token:
            return None


def _wait_for_engine_active(client, policy_engine_id: str, timeout: int = 90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get_policy_engine(policyEngineId=policy_engine_id)
        status = response.get("status")
        if status == "ACTIVE":
            return
        if status in ("FAILED", "DELETING", "DELETED"):
            raise RuntimeError(f"Policy engine entered unexpected status: {status}")
        time.sleep(5)
    raise TimeoutError(f"Policy engine did not become ACTIVE within {timeout}s")


def _build_cedar_statement(gateway_arn: str, target_name: str) -> str:
    """Build Cedar permit statement allowing add_numbers and greet_user."""
    prefix = target_name
    return (
        f'permit('
        f'principal is AgentCore::OAuthUser, '
        f'action in ['
        f'AgentCore::Action::"{prefix}___add_numbers", '
        f'AgentCore::Action::"{prefix}___greet_user"'
        f'], '
        f'resource == AgentCore::Gateway::"{gateway_arn}"'
        f');'
    )


def _base_gateway_kwargs(gateway_id, gateway_name, gateway_role_arn,
                         discovery_url, allowed_clients):
    return dict(
        gatewayIdentifier=gateway_id,
        name=gateway_name,
        roleArn=gateway_role_arn,
        protocolType="MCP",
        authorizerType="CUSTOM_JWT",
        authorizerConfiguration={
            "customJWTAuthorizer": {
                "discoveryUrl": discovery_url,
                "allowedClients": [c.strip() for c in allowed_clients.split(",")],
                "allowedScopes": ["aws.cognito.signin.user.admin"],
            }
        },
    )


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def _upsert(
    client,
    gateway_id,
    gateway_name,
    gateway_role_arn,
    discovery_url,
    allowed_clients,
    target_name,
    gateway_arn,
    engine_name,
    policy_name,
    engine_description,
    policy_description,
):
    cedar_statement = _build_cedar_statement(gateway_arn, target_name)

    # 1. Ensure policy engine exists
    existing_engine = _find_policy_engine_by_name(client, engine_name)
    if existing_engine:
        engine_id = existing_engine["policyEngineId"]
        engine_arn = existing_engine["policyEngineArn"]
    else:
        resp = client.create_policy_engine(
            name=engine_name,
            description=engine_description,
            clientToken=str(uuid.uuid4()),
        )
        engine_id = resp["policyEngineId"]
        engine_arn = resp["policyEngineArn"]

    _wait_for_engine_active(client, engine_id)

    # 2. Ensure policy exists / is up to date
    existing_policy = _find_policy_by_name(client, engine_id, policy_name)
    if existing_policy:
        policy_id = existing_policy["policyId"]
        existing_statement = (
            existing_policy.get("definition", {})
            .get("cedar", {})
            .get("statement")
        )
        if existing_statement != cedar_statement or existing_policy.get("description") != policy_description:
            client.update_policy(
                policyEngineId=engine_id,
                policyId=policy_id,
                name=policy_name,
                description=policy_description,
                definition={"cedar": {"statement": cedar_statement}},
            )
    else:
        client.create_policy(
            policyEngineId=engine_id,
            name=policy_name,
            description=policy_description,
            clientToken=str(uuid.uuid4()),
            definition={"cedar": {"statement": cedar_statement}},
        )

    # 3. Attach policy engine to gateway in ENFORCE mode
    kwargs = _base_gateway_kwargs(
        gateway_id, gateway_name, gateway_role_arn, discovery_url, allowed_clients
    )
    kwargs["policyEngineConfiguration"] = {"arn": engine_arn, "mode": "ENFORCE"}
    client.update_gateway(**kwargs)

    print(engine_id)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def _delete(
    client,
    gateway_id,
    gateway_name,
    gateway_role_arn,
    discovery_url,
    allowed_clients,
    engine_name,
    policy_name,
):
    existing_engine = _find_policy_engine_by_name(client, engine_name)
    if not existing_engine:
        print("")
        return

    engine_id = existing_engine["policyEngineId"]

    # 1. Detach: update gateway without policyEngineConfiguration
    try:
        kwargs = _base_gateway_kwargs(
            gateway_id, gateway_name, gateway_role_arn, discovery_url, allowed_clients
        )
        client.update_gateway(**kwargs)
    except Exception as e:
        print(f"Warning: gateway detach failed: {e}", file=sys.stderr)

    # 2. Delete policy
    existing_policy = _find_policy_by_name(client, engine_id, policy_name)
    if existing_policy:
        try:
            client.delete_policy(
                policyEngineId=engine_id,
                policyId=existing_policy["policyId"],
            )
        except Exception as e:
            print(f"Warning: policy delete failed: {e}", file=sys.stderr)

    # 3. Delete policy engine
    try:
        client.delete_policy_engine(policyEngineId=engine_id)
    except Exception as e:
        print(f"Warning: policy engine delete failed: {e}", file=sys.stderr)

    print(engine_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Manage Cedar policy enforcement for AgentCore Gateway"
    )
    parser.add_argument("--mode", choices=["upsert", "delete"], required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--gateway-id", required=True)
    parser.add_argument("--gateway-name", required=True)
    parser.add_argument("--gateway-role-arn", required=True)
    parser.add_argument("--discovery-url", required=True)
    parser.add_argument("--allowed-clients", required=True, help="Comma-separated client IDs")
    parser.add_argument("--target-name", default="", help="Gateway target name (tool prefix)")
    parser.add_argument("--gateway-arn", default="")
    parser.add_argument("--engine-name", required=True)
    parser.add_argument("--policy-name", required=True)
    parser.add_argument("--engine-description", default="")
    parser.add_argument("--policy-description", default="")

    args = parser.parse_args()

    client = boto3.client("bedrock-agentcore-control", region_name=args.region)

    engine_name = _sanitize_identifier(args.engine_name)
    policy_name = _sanitize_identifier(args.policy_name)

    if args.mode == "upsert":
        if not args.gateway_arn:
            raise ValueError("--gateway-arn is required in upsert mode")
        if not args.target_name:
            raise ValueError("--target-name is required in upsert mode")
        _upsert(
            client,
            args.gateway_id,
            args.gateway_name,
            args.gateway_role_arn,
            args.discovery_url,
            args.allowed_clients,
            args.target_name,
            args.gateway_arn,
            engine_name,
            policy_name,
            args.engine_description,
            args.policy_description,
        )
    else:
        _delete(
            client,
            args.gateway_id,
            args.gateway_name,
            args.gateway_role_arn,
            args.discovery_url,
            args.allowed_clients,
            engine_name,
            policy_name,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
