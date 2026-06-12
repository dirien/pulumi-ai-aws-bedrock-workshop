"""Orchestrator agent: HTTP entrypoint in front, A2A client toward the specialist.

The orchestrator itself still speaks the Module 2 HTTP contract (port 8080,
/invocations), so you invoke it exactly like before. What changed is how it
reaches the specialist: instead of a hand-rolled boto3 call, it uses an A2A
client that discovers the specialist through its agent card and talks
JSON-RPC - signed with the same IAM credentials as any AWS API call.
"""

import os

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.runtime.a2a import build_runtime_url
from sigv4 import SigV4HTTPXAuth
from strands import Agent
from strands_tools.a2a_client import A2AClientToolProvider

app = BedrockAgentCoreApp()

# The specialist's A2A endpoint rides the AgentCore data plane: its URL is the
# InvokeAgentRuntime endpoint with the runtime ARN encoded into the path.
# SPECIALIST_A2A_URL overrides it for local runs (e.g. http://localhost:9000).
SPECIALIST_URL = os.getenv("SPECIALIST_A2A_URL")
if not SPECIALIST_URL:
    specialist_arn = os.getenv("SPECIALIST_ARN")
    if not specialist_arn:
        raise EnvironmentError("SPECIALIST_ARN environment variable is required")
    SPECIALIST_URL = build_runtime_url(specialist_arn)

# Pin the model so every learner gets the same behavior and cost. Without an
# explicit model, Strands falls back to a default that changes between releases.
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def create_orchestrator_agent() -> Agent:
    """Create the orchestrator agent with A2A client tools for the specialist."""
    system_prompt = """You are an orchestrator agent.
    You can handle simple queries directly, but for complex analytical tasks,
    you should delegate to the specialist agent: use the a2a_send_message tool
    to send it the question (it is already discovered for you).

    Use the specialist agent when:
    - The query requires detailed analysis
    - The query is about complex topics
    - The user explicitly asks for expert analysis

    Handle simple queries (greetings, basic questions) yourself."""

    # Sign every request to the specialist with SigV4 - same IAM identity,
    # same InvokeAgentRuntime permission as a boto3 call, new protocol.
    session = boto3.Session()
    auth = SigV4HTTPXAuth(
        credentials=session.get_credentials(),
        service="bedrock-agentcore",
        region=os.getenv("AWS_REGION") or session.region_name,
    )

    # The provider fetches the specialist's agent card and exposes A2A tools
    # (a2a_send_message, a2a_discover_agent, ...) to the orchestrator.
    specialist = A2AClientToolProvider(
        known_agent_urls=[SPECIALIST_URL],
        httpx_client_args={"auth": auth},
    )

    return Agent(
        model=MODEL_ID,
        tools=specialist.tools,
        system_prompt=system_prompt,
        name="OrchestratorAgent",
    )


@app.entrypoint
async def invoke(payload=None):
    """Main entrypoint for orchestrator agent"""
    try:
        # Get the query from payload
        query = (
            payload.get("prompt", "Hello, how are you?")
            if payload
            else "Hello, how are you?"
        )

        # Create and use the orchestrator agent
        agent = create_orchestrator_agent()
        response = agent(query)

        return {
            "status": "success",
            "agent": "orchestrator",
            "response": response.message["content"][0]["text"],
        }

    except Exception as e:
        return {"status": "error", "agent": "orchestrator", "error": str(e)}


if __name__ == "__main__":
    app.run()
