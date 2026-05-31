---
title: Glossary
---

Every acronym used in this workshop, with what it stands for and how it shows up here. Each one is also expanded on first use in the chapter where it appears.

| Acronym | Stands for | In this workshop |
|---------|------------|------------------|
| A2A | Agent-to-Agent | One agent invoking another agent runtime directly on AgentCore (Module 3) |
| API | Application Programming Interface | The interface your code calls AWS and AgentCore through |
| ARM64 | 64-bit Arm architecture | AgentCore runs Arm64 containers; CodeBuild builds the images on native Arm64 hardware |
| ARN | Amazon Resource Name | The unique identifier for an AWS resource (e.g. an agent runtime's ARN) |
| AWS | Amazon Web Services | The cloud provider hosting every resource in the workshop |
| CLI | Command-Line Interface | The terminal tools you use, such as the Pulumi CLI |
| EC2 | Elastic Compute Cloud | AWS virtual machines — what you'd otherwise run agents on |
| ECR | Elastic Container Registry | Stores the Docker images CodeBuild produces for your agents |
| ECS | Elastic Container Service | AWS container orchestration — another thing AgentCore saves you from managing |
| ESC | Environments, Secrets, and Configuration | Pulumi's encrypted secrets and config store for your AWS credentials |
| HTTP | HyperText Transfer Protocol | The protocol agents and MCP servers speak over |
| IAM | Identity and Access Management | AWS roles and policies that control what each agent can do |
| JSON | JavaScript Object Notation | The data format for agent payloads and IAM policies |
| JWT | JSON Web Token | The bearer token Cognito issues and the AgentCore Gateway validates (Module 2) |
| LLM | Large Language Model | The model your agent calls through Amazon Bedrock |
| MCP | Model Context Protocol | Open standard for how agents discover and call tools (Module 2) |
| OIDC | OpenID Connect | Identity layer the Gateway uses via Cognito's discovery URL (Module 2) |
| S3 | Simple Storage Service | Object storage for source archives and the agent's result files |
| SDK | Software Development Kit | A framework you build with, such as the Strands Agents SDK |
| SigV4 | Signature Version 4 | AWS's request-signing scheme the Gateway uses to call your runtime (Module 2) |
| TTL | Time To Live | How long a Memory event lives before it expires (Module 4) |
| UI | User Interface | The Pulumi Cloud web console |
| YAML | YAML Ain't Markup Language | Config file format used for buildspecs and Pulumi config |
