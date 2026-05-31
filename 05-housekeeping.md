---
---
# Module 5: Cleanup

**Duration:** ~10 minutes

## Cleaning up

Each module created AWS resources that cost money while they're running. Let's tear everything down.

Destroy the stacks in reverse order. Module 4 first, then 3, 2, 1. The order matters because later modules don't depend on earlier ones (they're separate stacks), but going in reverse is a good habit.

> If you skipped the stretch goals (Modules 2 and 4), skip those sections below too. There's nothing to tear down for stacks you never created.

### Module 4: Weather agent _(stretch goal, skip if not deployed)_

```bash
cd 04-weather-agent
pulumi destroy --yes
cd ..
```

This removes the Browser, Code Interpreter, Memory, results S3 bucket, CloudWatch log groups, ECR repository, CodeBuild project, Lambda functions, IAM roles, and the AgentCore Runtime.

### Module 3: Multi-agent orchestration

```bash
cd 03-multi-agent
pulumi destroy --yes
cd ..
```

### Module 2: MCP server _(stretch goal, skip if not deployed)_

```bash
cd 02-mcp-server
pulumi destroy --yes
cd ..
```

This also removes the Cognito User Pool and test user.

If you created a Policy Engine in the Policy Enforcement section, remove it separately:

```bash
aws bedrock-agentcore-control delete-policy-engine \
  --policy-engine-id <YOUR_POLICY_ENGINE_ID>
```

### Module 1: Basic agent

```bash
cd 01-my-first-agent
pulumi destroy --yes
cd ..
```

## Verification

Check that everything is gone:

1. Open [Pulumi Cloud](https://app.pulumi.com) and verify all stacks show 0 resources
2. In the AWS Console, check:
   - **ECR**: No repositories with `agentcore-` prefix
   - **S3**: No buckets with `agentcore-` prefix
   - **CodeBuild**: No build projects with `agentcore-` prefix
   - **Bedrock AgentCore**: No runtimes listed

## Optional cleanup

Remove local project directories:

```bash
rm -rf 01-my-first-agent 02-mcp-server 03-multi-agent 04-weather-agent
```

If you created the test project in Module 0:

```bash
rm -rf /tmp/verify-setup
```

## Wrap-up

Over the last three hours you went from zero to a multi-tool agent that browses the web, runs Python, and remembers user preferences. All of it deployed with Pulumi and running on AgentCore.

The code from this workshop is yours to keep. Fork the repo and use the solution folders as starting points for your own agents.

If you want to go further, here are some things we didn't cover today:

- AgentCore can run MCP tools server-side, without routing through your agent container
- MCP servers can be stateful, maintaining session state and prompting users for input via elicitation
- Memory events can stream to Kinesis for real-time processing pipelines
- The managed Browser supports custom profiles and extensions for more complex scraping
- The Policy Engine can generate Cedar policies from plain English descriptions

Thanks for participating. If you have questions or want to share what you build, find us in the [Pulumi Community Slack](https://slack.pulumi.com).
