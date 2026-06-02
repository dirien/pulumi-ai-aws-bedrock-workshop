# Instructor credential sharing site

A static website deployed via CloudFront that displays workshop credentials and config values with click-to-copy. No more mistyped tokens from PowerPoint slides.

## What it does

1. Creates an IAM user for workshop participants with the permissions needed to deploy the workshop infrastructure, plus a long-term access key.
2. Generates a Pulumi-branded credential page with a two-step onboarding flow — **Step 1: fork the repo** (with a screenshot from `assets/fork.png`) and **Step 2: add your AWS credentials** (a ready-to-paste Pulumi ESC YAML block with click-to-copy).
3. Uploads the page to a private S3 bucket and serves it over HTTPS via CloudFront (Origin Access Control), then shortens the URL for easy sharing.
4. Participants open the URL, fork the repo, and copy the credential block — no more mistyped tokens from slides.

As the instructor you just need an ESC environment (or local SSO creds) that lets the stack create the IAM user and CloudFront resources declared in this project.

## Configuration

Set with `pulumi config set <key> <value>` from the `instructor/` directory:

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `workshopName` | yes | — | Event name. Shown as the page eyebrow and applied as the `workshop` AWS default tag. |
| `workshopTitle` | no | `Workshop Credentials` | Heading for the credentials step. |
| `pageTitle` | no | `Deploying AI Agents on AWS with Pulumi and Amazon Bedrock AgentCore` | Hero page title; the words `Pulumi` and `AgentCore` are auto-highlighted. |
| `keyVersion` | no | `1` | Bump (e.g. `2`) to rotate the participant access key on the next `pulumi up`. |
| `values` | no | — | Extra key/value pairs merged onto the page; IAM credentials are always added automatically. |

## Setup

### 1. Set up AWS credentials for the stack

The credentials need to be able to create IAM user and policies and the various cloudfront related infrastructure the stack deploys.

### 2. Deploy

```bash
cd instructor
npm install
pulumi up
```

The output includes the CloudFront URL. Share this URL with participants.

### 3. Update values

To change values mid-workshop add or update the `keyVersion` stack config item to `2` or greater:

```bash
# Update the ESC environment
pulumi config set keyVersion 2

# Redeploy (takes ~30 seconds)
pulumi up --yes
```

The HTML regenerates with the new values. CloudFront cache TTL is 5 minutes, so changes propagate quickly. To force immediate propagation:

```bash
aws cloudfront create-invalidation --distribution-id $(pulumi stack output distributionId) --paths "/*"
```

### 4. Tear down

```bash
pulumi destroy --yes
```

## Architecture

```
Pulumi ESC (workshop-values)
    |  config values
Pulumi program (index.ts)
    |  generates HTML
S3 bucket (private)
    |  OAC
CloudFront distribution (HTTPS)
    |
Participants browser
```

## Adding custom values

Edit the ESC environment to add any key-value pair. The site renders all pairs from `instructor:values` automatically. Sensitive values (tokens, passwords) are displayed in monospace with a copy button, so participants never need to type them manually.
