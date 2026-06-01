#!/usr/bin/env bash
# Build the AgentCore direct-code deployment package.
#
# AgentCore Runtime runs on ARM64 (Graviton), so we download ARM64/Linux wheels
# for every dependency, then drop the agent code in alongside them. Pulumi zips
# the resulting build/ directory and uploads it to S3.
set -euo pipefail

cd "$(dirname "$0")"

RUNTIME_PY_VERSION="${RUNTIME_PY_VERSION:-3.13}"

echo "Cleaning build/ ..."
rm -rf build
mkdir -p build

echo "Installing ARM64 dependencies for Python ${RUNTIME_PY_VERSION} ..."
# AgentCore Runtime runs on Amazon Linux 2023 (glibc 2.34), so target the
# manylinux_2_28 aarch64 wheel tag. --only-binary keeps the build host-agnostic.
uv pip install \
  --python-platform aarch64-manylinux_2_28 \
  --python-version "${RUNTIME_PY_VERSION}" \
  --target build \
  --only-binary=:all: \
  -r agent-code/requirements.txt

echo "Adding agent code ..."
cp agent-code/basic_agent.py build/

# Bytecode compiled on this machine may not match the runtime; drop it.
find build -name '__pycache__' -type d -prune -exec rm -rf {} +

echo "Done. build/ is ready for 'pulumi up'."
