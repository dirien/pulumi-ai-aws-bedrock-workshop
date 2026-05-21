# Deploying AI Agents on AWS with Pulumi and Amazon Bedrock AgentCore

A hands-on workshop where you build, deploy, and connect AI agents on AWS using Pulumi infrastructure-as-code and Amazon Bedrock AgentCore.

**Duration:** 3 hours | **Format:** Instructor-led, hands-on

**Instructors:** Engin Diri (Senior Solutions Architect, Pulumi) & Adam Gordon Bell (Community Engineer, Pulumi)

## What you'll build

By the end of this workshop, you will have deployed:

- A basic AI agent running on AgentCore Runtime
- An MCP server with JWT authentication and Cedar-based policy enforcement
- A multi-agent system where an orchestrator delegates to a specialist
- A full-stack weather agent that scrapes websites, runs code, remembers preferences, and writes reports to S3

All infrastructure is defined as code with Pulumi (TypeScript or Python) and deployed through Pulumi ESC for centralized credential management.

## Prerequisites

- A laptop with internet access
- An AWS account with Bedrock model access enabled (provided for the workshop)
- A [Pulumi account](https://app.pulumi.com/signup) (free tier works)
- A GitHub account
- Node.js 18+ or Python 3.11+ installed
- Python packages for testing: `pip install boto3 mcp`
- Basic terminal familiarity

We recommend using GitHub Codespaces with the included devcontainer for a zero-install experience.

## Workshop modules

| Module | Topic | Duration |
|--------|-------|----------|
| [Module 0](00-setup-and-orientation.md) | Setup and orientation | 15 min |
| [Module 1](01-your-first-agent.md) | Your first agent on AgentCore | 30 min |
| [Module 2](02-mcp-server-jwt-auth.md) | Hosting an MCP server behind an AgentCore Gateway | 45 min |
| [Module 3](03-multi-agent-orchestration.md) | Multi-agent orchestration | 40 min |
| [Module 4](04-full-stack-weather-agent.md) | The full stack: weather agent with tools and memory | 40 min |
| [Module 5](05-housekeeping.md) | Cleanup | 10 min |

## Getting started

### Option A: GitHub Codespaces (recommended)

1. Fork this repository
2. Click **Code** > **Codespaces** > **Create codespace on main**
3. Wait for the devcontainer to build (takes a couple minutes)
4. You're ready. Jump to [Module 0](00-setup-and-orientation.md).

### Option B: Local machine

1. Clone this repository
2. Install the [Pulumi CLI](https://www.pulumi.com/docs/install/)
3. Install Node.js 18+ and Python 3.11+
4. Install the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
5. Run `pulumi login` to authenticate with Pulumi Cloud
6. Jump to [Module 0](00-setup-and-orientation.md)

## Troubleshooting

**`pulumi up` hangs during CodeBuild**: The first build takes 5-10 minutes while Docker images are built and pushed to ECR. This is normal.

**AWS credentials expired**: If you see auth errors, run `pulumi env open aws-bedrock-workshop/dev` to verify your credentials are configured correctly, then retry.

**Agent invocation returns 500**: Check CloudWatch Logs at `/aws/bedrock-agentcore/runtimes/` for your runtime. Common causes are missing IAM permissions or environment variables.

**CodeBuild fails**: Check the build logs in the AWS Console under CodeBuild > Build projects. The most common issue is ECR permission errors during docker push.

## Repository structure

```
├── 00-setup-and-orientation.md    # Module 0: Setup
├── 01-your-first-agent.md         # Module 1: Basic agent
├── 02-mcp-server-jwt-auth.md      # Module 2: MCP + JWT + Policy
├── 03-multi-agent-orchestration.md # Module 3: A2A communication
├── 04-full-stack-weather-agent.md  # Module 4: Full stack agent
├── 05-housekeeping.md              # Module 5: Cleanup
├── 01-solution/typescript/         # Module 1 solution code
├── 02-solution/typescript/         # Module 2 solution code
├── 03-solution/typescript/         # Module 3 solution code
├── 04-solution/typescript/         # Module 4 solution code
├── esc/                            # Pulumi ESC environment templates
└── .devcontainer/                  # GitHub Codespaces config
```

## Community

Questions or feedback? Find us on the [Pulumi Community Slack](https://slack.pulumi.com) or open an issue on this repository.

## License

Apache 2.0 - see [LICENSE](LICENSE)
