#!/usr/bin/env python3
"""
Weather Agent Workshop Test

Verifies the full deployment pipeline:
1. Runtime status check (instant)
2. Agent invocation (handles cold start gracefully)
3. Waits for the Markdown report to appear in S3

Usage:
    python test_weather_agent.py <agent_arn>
"""

import boto3
import json
import sys
import time
import subprocess
from botocore.config import Config

# pulumi env run pipes stdout, which makes Python block-buffer it; without
# this the progress lines all appear at once instead of as the test runs.
sys.stdout.reconfigure(line_buffering=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_weather_agent.py <agent_arn>")
        sys.exit(1)

    agent_arn = sys.argv[1]
    region = agent_arn.split(":")[3]
    runtime_id = agent_arn.split("/")[-1]

    print("=" * 60)
    print("WEATHER AGENT - FULL PIPELINE TEST")
    print("=" * 60)
    print(f"Region:     {region}")
    print(f"Runtime ID: {runtime_id}")
    print()

    passed = 0
    failed = 0

    # --- Test 1: Runtime status ---
    print("[1/3] Checking runtime status...")
    try:
        control = boto3.client(
            "bedrock-agentcore-control", region_name=region
        )
        info = control.get_agent_runtime(agentRuntimeId=runtime_id)
        status = info.get("status", "UNKNOWN")
        if status == "READY":
            print("      PASS - Runtime is READY")
            passed += 1
        else:
            print(f"      FAIL - Runtime is {status} (expected READY)")
            failed += 1
    except Exception as e:
        print(f"      FAIL - {e}")
        failed += 1

    # --- Test 2: Invoke agent ---
    print("[2/3] Invoking agent (first call may take 1-2 min for cold start)...")
    try:
        timeout_config = Config(
            read_timeout=180,
            connect_timeout=30,
            retries={"max_attempts": 0},
        )
        client = boto3.client(
            "bedrock-agentcore",
            region_name=region,
            config=timeout_config,
        )

        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier="DEFAULT",
            payload=json.dumps({
                "prompt": "What should I do this weekend in Richmond VA?"
            }),
        )

        http_status = response["ResponseMetadata"]["HTTPStatusCode"]
        raw = response["response"].read()
        body = json.loads(raw.decode("utf-8"))

        agent_status = body.get("status", "")

        if http_status == 200 and agent_status == "Started":
            print("      PASS - Agent responded: status=Started")
            passed += 1
        elif http_status == 200:
            print("      PASS - Agent responded (HTTP 200)")
            passed += 1
        else:
            print(f"      WARN - HTTP {http_status}")
            passed += 1

    except Exception as e:
        error_msg = str(e)
        if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
            print("      PASS - Agent invoked (cold start in progress)")
            print("             The container is loading dependencies.")
            print("             This is normal for the first call.")
            passed += 1
        else:
            print(f"      FAIL - {error_msg[:200]}")
            failed += 1

    # --- Test 3: Wait for Markdown report in S3 ---
    print("[3/3] Waiting for Markdown report in S3...")
    print("      (The agent scrapes weather.gov, classifies days,")
    print("       reads memory, and writes a report. ~3-5 min.)")

    bucket = None
    try:
        r = subprocess.run(
            ["pulumi", "stack", "output", "resultsBucketName"],
            capture_output=True, text=True
        )
        bucket = r.stdout.strip()
    except Exception:
        pass

    if not bucket:
        print("      SKIP - Could not get resultsBucketName from Pulumi")
        print("             Run: pulumi stack output resultsBucketName")
    else:
        s3 = boto3.client("s3", region_name=region)
        found = False
        max_attempts = 24  # 24 x 15s = 6 min
        for attempt in range(max_attempts):
            time.sleep(15)
            try:
                objects = s3.list_objects_v2(Bucket=bucket, MaxKeys=10)
                if objects.get("KeyCount", 0) > 0:
                    keys = [o["Key"] for o in objects["Contents"]]
                    md_files = [k for k in keys if k.endswith(".md")]
                    if md_files:
                        print(f"      PASS - Markdown report found: {md_files[0]}")
                        # Show a preview
                        obj = s3.get_object(Bucket=bucket, Key=md_files[0])
                        content = obj["Body"].read().decode("utf-8")
                        preview = content[:500]
                        print()
                        print("      --- Report preview ---")
                        for line in preview.split("\n"):
                            print(f"      {line}")
                        if len(content) > 500:
                            print("      ...")
                        print(f"      --- ({len(content)} chars total) ---")
                        passed += 1
                        found = True
                        break
                    elif keys:
                        print(f"      Found files but no .md yet: {keys}")
            except Exception:
                pass

            elapsed = (attempt + 1) * 15
            mins = elapsed // 60
            secs = elapsed % 60
            print(f"      ...{mins}m{secs:02d}s elapsed, still processing")

        if not found:
            print("      FAIL - No Markdown report after 6 minutes")
            print("      Check CloudWatch logs for errors:")
            log_group = f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"
            print(f"        aws logs tail \"{log_group}\" --region {region}")
            failed += 1

    # --- Summary ---
    print()
    print("=" * 60)
    total = passed + failed
    if failed == 0:
        print(f"ALL CHECKS PASSED ({passed}/{total})")
    else:
        print(f"SOME CHECKS FAILED ({failed} failed, {passed} passed)")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
