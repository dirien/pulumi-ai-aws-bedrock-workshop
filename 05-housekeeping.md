---
---
# Module 5: Cleanup

**Duration:** ~10 minutes

## Cleaning up

Each module created AWS resources that cost money while they're running. Let's tear everything down.

Destroy the stacks in reverse order. Module 4 first, then 3, then 2. Each module is a separate stack with no dependency on the others, so order matters less than completeness, but going in reverse is a good habit. (Module 1 ran entirely on your laptop and created no cloud resources, so there's nothing to tear down there.)

> If you skipped the stretch goal (Module 4), skip that section below too. There's nothing to tear down for a stack you never created.

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

### Module 2: Your first agent

```bash
cd 02-my-first-agent
pulumi destroy --yes
cd ..
```

This removes the S3 bucket, the IAM execution role, and the AgentCore Runtime.

## Optional cleanup

Remove local project directories:

```bash
rm -rf 01-hello-agent 02-my-first-agent 03-multi-agent 04-weather-agent
```

If you created the test project in Module 0:

```bash
rm -rf /tmp/verify-setup
```

## Wrap-up

Over the last couple of hours you went from running an agent on your laptop to deploying it on AgentCore and having agents call each other - all with Pulumi. And if you took the weather-agent stretch goal, you also wired in Browser, Code Interpreter, and Memory.

The code from this workshop is yours to keep. Fork the repo and use the solution folders as starting points for your own agents.

Thanks for participating. If you have questions or want to share what you build, find us in the [Pulumi Community Slack](https://slack.pulumi.com).
