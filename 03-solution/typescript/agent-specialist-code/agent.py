"""Specialist agent, served over the open A2A protocol.

Instead of the HTTP contract from Module 2 (BedrockAgentCoreApp on port 8080),
this agent is an A2A server: JSON-RPC 2.0 on port 9000, an agent card at
/.well-known/agent-card.json, and a /ping health check. Any A2A client can
discover and call it - the orchestrator is just one of them.
"""

from bedrock_agentcore.runtime.a2a import serve_a2a
from strands import Agent
from strands.multiagent.a2a import StrandsA2AExecutor

# Pin the model so every learner gets the same behavior and cost. Without an
# explicit model, Strands falls back to a default that changes between releases.
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def create_specialist_agent() -> Agent:
    """Create a specialist agent that handles specific analytical tasks"""
    system_prompt = """You are a specialist analytical agent.
    You are an expert at analyzing data and providing detailed insights.
    When asked questions, provide thorough, well-reasoned responses with specific details.
    Focus on accuracy and completeness in your answers."""

    return Agent(
        model=MODEL_ID,
        system_prompt=system_prompt,
        name="SpecialistAgent",
        description="An analytical specialist that gives thorough, detailed answers.",
    )


if __name__ == "__main__":
    # serve_a2a handles the protocol plumbing: JSON-RPC routing, the agent
    # card, and the /ping health check AgentCore polls. Bind to 0.0.0.0 so
    # the runtime can reach the server inside the container.
    serve_a2a(StrandsA2AExecutor(create_specialist_agent()), host="0.0.0.0")
