# Module 1 solution - Hello, agent! Run locally

The complete agent from Module 1. No infrastructure, no cloud - it runs on your
laptop and talks to Amazon Bedrock directly.

## Run it

```bash
# from this directory
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Bedrock needs AWS credentials. Inject them from your ESC environment:
pulumi env run aws-bedrock-workshop/dev -- python basic_agent.py
```

The server starts on http://localhost:8080.

## Call it

In a second terminal:

```bash
curl -s -X POST http://localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "What is Amazon Bedrock AgentCore?"}' | jq

# health check
curl -s http://localhost:8080/ping | jq
```

`basic_agent.py` is the same file you deploy to AgentCore in Module 2.
