---
---
# Module 0: Setup and orientation

**Duration:** ~15 minutes

## What you'll learn

- What Amazon Bedrock AgentCore, Strands SDK, and Pulumi ESC are
- How they connect to each other
- How to store AWS credentials securely in a Pulumi ESC environment

## The big picture

Before we write any code, here's how the pieces fit together.

**Amazon Bedrock AgentCore** is a managed runtime for AI agents. You give it a container image with your agent code, and it handles hosting, scaling, and invocation. Think of it as "Lambda for agents": you don't manage servers, you just deploy a container and call it.

**Strands SDK** is a Python framework for writing agents. You define a system prompt, attach tools, and Strands handles the conversation loop with the LLM. It has a built-in `BedrockAgentCoreApp` class that wraps your agent as an HTTP service compatible with AgentCore Runtime.

**Pulumi** is the infrastructure-as-code tool we use to define and deploy everything: S3 buckets, ECR repositories, IAM roles, CodeBuild projects, and the AgentCore runtimes themselves. You can choose either TypeScript or Python for the infrastructure code.

**Pulumi ESC** (Environments, Secrets, and Configuration) is Pulumi's centralized secrets and configuration store. Instead of exporting AWS access keys in your shell or scattering them across `.env` files, ESC stores them encrypted and injects them automatically when you run `pulumi up`. Secrets are encrypted at rest and never appear in plain text in your Pulumi state.

Here's the flow:

```
You write agent code (Python/Strands)
    ↓
Pulumi deploys infrastructure (TypeScript or Python)
    ↓
ESC provides AWS credentials (encrypted secrets)
    ↓
CodeBuild packages your agent into a Docker image
    ↓
AgentCore Runtime runs your agent
```

## Step 1: Log into Pulumi Cloud

If you haven't already, create a free Pulumi account. 

### Codespaces Users and Optionally Local Terminal Users

Go to the Pulumi Cloud UI and click on your user account.

Select `Personal access tokens` and create an access token.

Then log in from the terminal:

```bash
export PULUMI_ACCESS_TOKEN=pul-xxxxxx
pulumi login
```

Verify it worked:

```bash
pulumi whoami
```

You should see your username.

### Local Terminal Users

Log in from the terminal:

```bash
pulumi login
```

This opens a browser window. Sign in (or create an account), then return to the terminal.

Verify it worked:

```bash
pulumi whoami
```

You should see your username.

## Tips for success

1. **Follow the modules sequentially** - each one builds on concepts from the previous module
2. **Complete the verification steps** at the end of each section to catch issues early
3. **Ask your instructors for help** - we're here to keep you moving
4. **Experiment** - once a module works, try modifying the agent prompt or tools to see what happens

## Getting started

### Option 1: GitHub Codespaces (recommended)

Click the badge below to launch a pre-configured development environment:

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/dirien/pulumi-ai-aws-bedrock-workshop?quickstart=1)

Wait for the devcontainer to build (takes a couple of minutes). All tools (Pulumi CLI, Node.js, Python, uv) are pre-installed.

### Option 2: Local development

1. Clone the repository:

   ```bash
   git clone https://github.com/dirien/pulumi-ai-aws-bedrock-workshop.git
   cd pulumi-ai-aws-bedrock-workshop
   ```

2. Install the [Pulumi CLI](https://www.pulumi.com/docs/install/)
3. Install Node.js 18+ and Python 3.11+
4. Install [uv](https://docs.astral.sh/uv/) for Python dependency management
5. Install test dependencies: `pip install boto3 mcp`
6. Run `pulumi login` to authenticate with Pulumi Cloud

## Step 2: Create your ESC environment for AWS credentials

Your instructor has set up a credential sharing page with the AWS credentials for this workshop. You will get the URL from your instructor.

Open the credential page in your browser and copy the **AWS Access Key ID** and **AWS Secret Access Key** values.

Now create a Pulumi ESC environment to store these credentials securely:

1. Navigate to [Pulumi Cloud](https://app.pulumi.com) > **Environments** in the left sidebar
2. Click **Create environment**
3. Set the project name to `aws-bedrock-workshop` and the environment name to `dev`
4. Paste the following YAML configuration, replacing the placeholder values with the credentials you copied:

   ```yaml
   values:
     aws-creds:
       accessKeyId:
         fn::secret: <YOUR_AWS_ACCESS_KEY_ID>
       secretAccessKey:
         fn::secret: <YOUR_AWS_SECRET_ACCESS_KEY>
     environmentVariables:
       AWS_ACCESS_KEY_ID: ${aws-creds.accessKeyId}
       AWS_SECRET_ACCESS_KEY: ${aws-creds.secretAccessKey}
     pulumiConfig:
       aws:region: us-east-1
   ```

5. Click **Save**

The `fn::secret` function encrypts each credential at rest in Pulumi Cloud. When you run `pulumi up`, ESC decrypts them and injects them as environment variables automatically.

Verify the environment works:

```bash
pulumi env open aws-bedrock-workshop/dev
```

You should see the AWS credentials and the `aws:region` config. If you see an error, double-check that the project name is `aws-bedrock-workshop` and the environment name is `dev`.

## Step 3: Verify your setup

Let's make sure everything works end-to-end. Create a throwaway Pulumi project:

<div class="lang-tabs" markdown="1">

<div class="lang-tab" data-lang="typescript" markdown="1">

```bash
mkdir /tmp/verify-setup && cd /tmp/verify-setup
pulumi new aws-typescript --name verify-setup --yes
```

</div>

<div class="lang-tab" data-lang="python" markdown="1">

```bash
mkdir /tmp/verify-setup && cd /tmp/verify-setup
pulumi new aws-python --name verify-setup --yes
```

</div>

</div>

Open `Pulumi.dev.yaml` and add the ESC environment reference:

```yaml
environment:
  - aws-bedrock-workshop/dev
```

Run a preview:

```bash
pulumi preview
```

If this succeeds, your AWS credentials are working through ESC and you're ready for Module 1. Destroy the test project:

```bash
# Destroy the resources
pulumi destroy --yes
# Delete the stack (and state file)
pulumi stack rm
# Clean up the directory
cd -
rm -rf /tmp/verify-setup
```

## Step 4: Pick your unique identifier

Every module creates AWS resources (IAM roles, ECR repos, AgentCore runtimes) that need unique names within the AWS account. If multiple participants share the same account and use the same default names, you'll get conflicts.

Pick a short identifier now - your initials, a nickname, anything 2-5 characters. You'll use it in every module as your `stackName` prefix.

For example, if your identifier is `ed`:

```
Module 1: agentcore-basic-ed
Module 2: agentcore-mcp-ed
Module 3: agentcore-multi-ed
Module 4: agentcore-weather-ed
```

You set this at the start of each module with:

```bash
pulumi config set stackName agentcore-basic-ed
```

Keep this identifier consistent across all modules. Write it down.

## Step 5: Familiarize yourself with the workshop structure

Each module has a markdown file with instructions (what you're reading now) and solution folders (e.g., `01-solution/typescript/` and `01-solution/python/`) with the complete working code in both languages if you get stuck.

The modules build on each other. By Module 4, you'll have deployed a multi-tool agent that browses websites, runs Python code, and remembers user preferences.

## What you learned

- AgentCore is a managed container runtime for AI agents
- Strands SDK is the Python framework for writing agent logic
- Pulumi ESC stores AWS credentials encrypted and injects them into every deployment automatically
- Your local setup can authenticate with AWS and run `pulumi preview`

Next up: [Module 1 - Your first agent on AgentCore](01-your-first-agent.md)
