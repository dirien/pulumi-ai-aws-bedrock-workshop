"""A minimal Strands agent wrapped for Amazon Bedrock AgentCore.

Run it locally:

    python basic_agent.py

It starts an HTTP server on http://localhost:8080 with two routes that
AgentCore also calls in the cloud:

    POST /invocations   -> run the agent on a {"prompt": "..."} payload
    GET  /ping          -> health check

This is the *same* file you deploy in Module 2 - running it locally first
means "deploy" later is just shipping something you've already seen work.
"""

from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

# Pin the model so every learner gets the same behavior and cost. Without an
# explicit model, Strands falls back to a default that changes between releases.
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def create_basic_agent() -> Agent:
    """Create a basic agent with a simple system prompt."""
    system_prompt = "You are a helpful assistant. Answer questions clearly and concisely."
    return Agent(model=MODEL_ID, system_prompt=system_prompt, name="BasicAgent")


@app.entrypoint
async def invoke(payload=None):
    """Entrypoint AgentCore calls for every invocation."""
    try:
        query = (
            payload.get("prompt", "Hello, how are you?")
            if payload
            else "Hello, how are you?"
        )

        agent = create_basic_agent()
        response = agent(query)

        return {"status": "success", "response": response.message["content"][0]["text"]}

    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    app.run()
