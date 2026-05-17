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
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from botocore.config import Config


@contextmanager
def heartbeat(label, interval=10):
    """Print '{label} ... still waiting Ns' every `interval` seconds until exit.

    invoke_agent_runtime is synchronous and can block for minutes while the
    agent runs the full pipeline. Without a heartbeat the user has no signal
    that the call is alive.
    """
    stop = threading.Event()
    start = time.monotonic()

    def tick():
        while not stop.wait(interval):
            elapsed = int(time.monotonic() - start)
            print(f"      {label} ... still waiting ({elapsed}s)", flush=True)

    t = threading.Thread(target=tick, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop.set()
        t.join(timeout=1)
        print(
            f"      {label} returned after {int(time.monotonic() - start)}s",
            flush=True,
        )


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
    # invoke_agent_runtime is synchronous — it blocks until the agent finishes
    # the full pipeline (browser, code-gen, code-exec, memory, S3 write), which
    # can take several minutes. Use a generous read_timeout and a heartbeat.
    print("[2/3] Invoking agent (synchronous; may take several minutes)...")
    invoke_start = datetime.now(timezone.utc)
    try:
        client = boto3.client(
            "bedrock-agentcore",
            region_name=region,
            config=Config(
                read_timeout=900,
                connect_timeout=30,
                retries={"max_attempts": 0},
            ),
        )

        with heartbeat("invoke"):
            response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_arn,
                qualifier="DEFAULT",
                payload=json.dumps({
                    "prompt": "What should I do this weekend in Richmond VA?"
                }),
            )

        http_status = response["ResponseMetadata"]["HTTPStatusCode"]
        if http_status == 200:
            print(f"      PASS - Agent returned HTTP {http_status}")
            passed += 1
        else:
            print(f"      FAIL - Agent returned HTTP {http_status}")
            failed += 1

    except Exception as e:
        print(f"      FAIL - {str(e)[:200]}")
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
        log_group = f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"
        print(f"      Tail live logs: aws logs tail \"{log_group}\" --region {region} --follow")
        print(f"      (only counting reports written after {invoke_start.isoformat()})")
        found = False
        max_attempts = 24  # 24 x 15s = 6 min
        for attempt in range(max_attempts):
            time.sleep(15)
            try:
                objects = s3.list_objects_v2(Bucket=bucket, MaxKeys=20)
                fresh_md = [
                    o for o in objects.get("Contents", [])
                    if o["Key"].endswith(".md") and o["LastModified"] >= invoke_start
                ]
                if fresh_md:
                    fresh_md.sort(key=lambda o: o["LastModified"], reverse=True)
                    key = fresh_md[0]["Key"]
                    print(f"      PASS - Fresh Markdown report: {key}")
                    print(f"             written at {fresh_md[0]['LastModified'].isoformat()}")
                    obj = s3.get_object(Bucket=bucket, Key=key)
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
