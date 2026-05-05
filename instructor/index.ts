import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as command from "@pulumi/command";

// ============================================================================
// Configuration
// ============================================================================

const config = new pulumi.Config();
const workshopTitle = config.get("workshopTitle") || "Workshop Credentials";
const workshopName = config.require("workshopName");
// Extra display values merged onto the credential page (optional – IAM creds are always added automatically)
const extraValues = config.getObject<Record<string, string>>("values") ?? {};
// Bump this value (e.g. "2", "3") to rotate the workshop participant's access key on the next `pulumi up`
const keyVersion = config.get("keyVersion") ?? "1";

// ============================================================================
// Generate HTML
// ============================================================================

function buildEscYaml(kvPairs: Record<string, string>, workshopName: string): string {
  const lines: string[] = ["values:", "  secrets:"];
  for (const [k, v] of Object.entries(kvPairs)) {
    lines.push(`    ${k}:`);
    lines.push(`      fn::secret: ${v}`);
  }
  lines.push("  environmentVariables:");
  for (const k of Object.keys(kvPairs)) {
    lines.push(`    ${k}: \${secrets.${k}}`);
  }
  lines.push("  pulumiConfig:");
  lines.push("    aws:region: us-east-1");
  lines.push("    aws:defaultTags:");
  lines.push("      tags:");
  lines.push(`        workshop: ${workshopName}`);
  return lines.join("\n");
}

function generateHtml(
  title: string,
  kvPairs: Record<string, string>,
  workshopName: string,
): string {
  const escYaml = buildEscYaml(kvPairs, workshopName);
  const yamlHtml = escYaml
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  const count = Object.keys(kvPairs).length;
  const now = new Date().toISOString().split("T")[0];
  const h1 = title
    .replace("Pulumi", '<span class="hl">Pulumi</span>')
    .replace("AgentCore", '<span class="hl">AgentCore</span>');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #08080c; --surface: rgba(255,255,255,0.03);
      --border: rgba(255,255,255,0.07);
      --amber: #f0a830; --amber-dim: #c78520; --amber-glow: rgba(240,168,48,0.08);
      --green: #34d399; --text: #d4d4d8; --text-dim: #63636e;
      --font-display: 'Outfit', system-ui, sans-serif;
      --font-mono: 'IBM Plex Mono', 'SF Mono', monospace;
    }
    html { font-size: 16px; }
    body {
      font-family: var(--font-display); background: var(--bg); color: var(--text);
      min-height: 100vh; overflow-x: hidden; -webkit-font-smoothing: antialiased;
    }
    body::after {
      content: ''; position: fixed; inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.08) 2px, rgba(0,0,0,0.08) 4px);
      pointer-events: none; z-index: 1000;
    }
    .glow {
      position: fixed; width: 600px; height: 600px; border-radius: 50%;
      background: radial-gradient(circle, var(--amber-glow) 0%, transparent 70%);
      top: -200px; left: 50%; transform: translateX(-50%);
      pointer-events: none; z-index: 0;
    }
    .container { position: relative; z-index: 1; max-width: 760px; margin: 0 auto; padding: 72px 24px 80px; }
    @media (max-width: 640px) { .container { padding: 40px 16px 48px; } }
    .header { margin-bottom: 40px; }
    .header-meta {
      display: flex; align-items: center; gap: 12px; margin-bottom: 20px;
      font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.06em;
      text-transform: uppercase; color: var(--text-dim);
    }
    .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); animation: pulse 2s ease-in-out infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    h1 { font-size: clamp(1.6rem, 4.5vw, 2.2rem); font-weight: 700; letter-spacing: -0.03em; line-height: 1.15; color: #fff; margin-bottom: 12px; }
    .hl { color: var(--amber); }
    .subtitle { font-family: var(--font-mono); font-size: 13px; color: var(--text-dim); line-height: 1.6; }
    .subtitle a { color: var(--amber-dim); text-decoration: none; }
    .subtitle a:hover { text-decoration: underline; }
    .divider { height: 1px; background: linear-gradient(90deg, transparent, var(--border), transparent); margin: 32px 0; }
    .yaml-wrapper { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
    .yaml-toolbar {
      display: flex; align-items: center; justify-content: space-between;
      padding: 10px 16px; border-bottom: 1px solid var(--border);
      background: rgba(255,255,255,0.02);
    }
    .yaml-lang { font-family: var(--font-mono); font-size: 10px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-dim); }
    .copy-btn {
      font-family: var(--font-mono); font-size: 10px; font-weight: 600;
      letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-dim);
      background: none; border: 1px solid var(--border); border-radius: 4px;
      padding: 4px 12px; cursor: pointer; transition: color 0.15s, border-color 0.15s;
    }
    .copy-btn:hover { color: var(--amber); border-color: rgba(240,168,48,0.4); }
    .copy-btn .done { display: none; color: var(--green); }
    .copy-btn.copied .label { display: none; }
    .copy-btn.copied .done { display: inline; }
    pre.yaml-pre {
      padding: 20px 24px; overflow-x: auto;
      font-family: var(--font-mono); font-size: 13px; line-height: 1.75;
      color: var(--text); white-space: pre; tab-size: 2; background: none;
    }
    .toast {
      position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%) translateY(16px);
      font-family: var(--font-mono); font-size: 12px; font-weight: 500; letter-spacing: 0.04em;
      color: var(--green); background: rgba(8,8,12,0.95);
      border: 1px solid rgba(52,211,153,0.2); border-radius: 6px; padding: 10px 20px;
      opacity: 0; transition: opacity 0.25s, transform 0.25s;
      pointer-events: none; z-index: 999; backdrop-filter: blur(12px);
    }
    .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
    .footer { margin-top: 48px; font-family: var(--font-mono); font-size: 11px; color: var(--text-dim); text-align: center; letter-spacing: 0.02em; }
    .footer a { color: var(--amber-dim); text-decoration: none; }
    .footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="glow"></div>
  <div class="container">
    <header class="header">
      <div class="header-meta">
        <span class="dot"></span>
        <span>live &middot; ${count} credential${count === 1 ? "" : "s"} &middot; ${now}</span>
      </div>
      <h1>${h1}</h1>
      <p class="subtitle">Paste this YAML into your <a href="https://www.pulumi.com/product/esc/" target="_blank">Pulumi ESC</a> environment, then run <code style="font-family:var(--font-mono)">pulumi env open</code> to verify.</p>
    </header>
    <div class="divider"></div>
    <div class="yaml-wrapper">
      <div class="yaml-toolbar">
        <span class="yaml-lang">ESC YAML</span>
        <button class="copy-btn" id="copyBtn" onclick="copyYaml()">
          <span class="label">COPY</span>
          <span class="done">COPIED</span>
        </button>
      </div>
      <pre class="yaml-pre" id="yamlPre">${yamlHtml}</pre>
    </div>
    <div class="divider"></div>
    <footer class="footer">
      Served from <a href="https://www.pulumi.com/product/esc/" target="_blank">Pulumi ESC</a> &middot; Deployed with <a href="https://www.pulumi.com" target="_blank">Pulumi</a>
    </footer>
  </div>
  <div class="toast" id="toast">YAML copied to clipboard</div>
  <script>
    function copyYaml() {
      navigator.clipboard.writeText(document.getElementById('yamlPre').innerText).then(() => {
        const btn = document.getElementById('copyBtn');
        btn.classList.add('copied');
        document.getElementById('toast').classList.add('show');
        setTimeout(() => {
          btn.classList.remove('copied');
          document.getElementById('toast').classList.remove('show');
        }, 2000);
      });
    }
  </script>
</body>
</html>`;
}

// ============================================================================
// S3 Bucket (private, CloudFront origin)
// ============================================================================

const siteBucket = new aws.s3.Bucket("site", {
  bucketPrefix: "workshop-instructor-",
  forceDestroy: true,
  tags: { Name: "workshop-instructor-site", Purpose: "Instructor credential sharing" },
});

new aws.s3.BucketPublicAccessBlock("site", {
  bucket: siteBucket.id,
  blockPublicAcls: true,
  blockPublicPolicy: true,
  ignorePublicAcls: true,
  restrictPublicBuckets: true,
});

// ============================================================================
// Workshop Participant IAM User
// ============================================================================

const workshopParticipant = new aws.iam.User("workshop_participant", {
  forceDestroy: true,
  tags: {
    Purpose: "AWS Bedrock AgentCore Workshop",
  },
});

// ============================================================================
// Workshop Participant IAM Policy
// ============================================================================

const workshopPolicy = new aws.iam.Policy("workshop_policy", {
  name: "WorkshopParticipantPolicy",
  description:
    "Permissions for workshop participants to deploy solutions 01-04",
  policy: JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      {
        Sid: "STSAccess",
        Effect: "Allow",
        Action: ["sts:GetCallerIdentity"],
        Resource: "*",
      },
      {
        Sid: "S3Access",
        Effect: "Allow",
        Action: ["s3:*"],
        Resource: "*",
      },
      {
        Sid: "ECRAccess",
        Effect: "Allow",
        Action: [
          "ecr:CreateRepository",
          "ecr:DeleteRepository",
          "ecr:DescribeRepositories",
          "ecr:ListRepositories",
          "ecr:GetRepositoryPolicy",
          "ecr:SetRepositoryPolicy",
          "ecr:DeleteRepositoryPolicy",
          "ecr:GetLifecyclePolicy",
          "ecr:PutLifecyclePolicy",
          "ecr:DeleteLifecyclePolicy",
          "ecr:GetAuthorizationToken",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:ListImages",
          "ecr:DescribeImages",
          "ecr:TagResource",
          "ecr:UntagResource",
          "ecr:ListTagsForResource",
          "ecr:PutImageTagMutability",
          "ecr:PutImageScanningConfiguration",
        ],
        Resource: "*",
      },
      {
        Sid: "CodeBuildAccess",
        Effect: "Allow",
        Action: [
          "codebuild:CreateProject",
          "codebuild:DeleteProject",
          "codebuild:UpdateProject",
          "codebuild:BatchGetProjects",
          "codebuild:ListProjects",
          "codebuild:StartBuild",
          "codebuild:StopBuild",
          "codebuild:BatchGetBuilds",
          "codebuild:ListBuildsForProject",
          "codebuild:ListBuilds",
        ],
        Resource: "*",
      },
      {
        Sid: "LambdaAccess",
        Effect: "Allow",
        Action: ["lambda:*"],
        Resource: "*",
      },
      {
        // Needed to create and manage service roles used by Lambda, CodeBuild, and AgentCore
        Sid: "IAMManagement",
        Effect: "Allow",
        Action: [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:ListRoles",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:ListAttachedRolePolicies",
          "iam:PassRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:ListPolicies",
          "iam:ListPolicyVersions",
          "iam:CreateServiceLinkedRole",
          "iam:ListInstanceProfilesForRole",
        ],
        Resource: "*",
      },
      {
        Sid: "CloudWatchLogsAccess",
        Effect: "Allow",
        Action: [
          "logs:CreateLogGroup",
          "logs:DeleteLogGroup",
          "logs:CreateLogStream",
          "logs:DeleteLogStream",
          "logs:PutLogEvents",
          "logs:GetLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:PutRetentionPolicy",
          "logs:DeleteRetentionPolicy",
          "logs:TagLogGroup",
          "logs:UntagLogGroup",
          "logs:TagResource",
          "logs:UntagResource",
          "logs:ListTagsLogGroup",
          "logs:ListTagsForResource",
          // Used by solution 04 for AgentCore trace/log delivery
          "logs:DescribeDeliveries",
          "logs:CreateDelivery",
          "logs:DeleteDelivery",
          "logs:GetDelivery",
          "logs:UpdateDelivery",
          "logs:DescribeDeliveryDestinations",
          "logs:CreateDeliveryDestination",
          "logs:DeleteDeliveryDestination",
          "logs:GetDeliveryDestination",
          "logs:PutDeliveryDestinationPolicy",
          "logs:GetDeliveryDestinationPolicy",
          "logs:DeleteDeliveryDestinationPolicy",
          "logs:DescribeDeliverySources",
          "logs:CreateDeliverySource",
          "logs:DeleteDeliverySource",
          "logs:GetDeliverySource",
        ],
        Resource: "*",
      },
      {
        Sid: "CloudWatchMetricsAccess",
        Effect: "Allow",
        Action: [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricData",
          "cloudwatch:DescribeAlarms",
        ],
        Resource: "*",
      },
      {
        Sid: "XRayAccess",
        Effect: "Allow",
        Action: [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets",
        ],
        Resource: "*",
      },
      {
        // Covers Runtime, Gateway, Browser, Code Interpreter, Memory (all solutions)
        Sid: "BedrockAgentCoreAccess",
        Effect: "Allow",
        Action: ["bedrock-agentcore:*"],
        Resource: "*",
      },
      {
        Sid: "BedrockModelAccess",
        Effect: "Allow",
        Action: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel",
        ],
        Resource: "*",
      },
      {
        // Used by solution 02 for JWT authentication on the MCP Gateway
        Sid: "CognitoAccess",
        Effect: "Allow",
        Action: [
          "cognito-idp:CreateUserPool",
          "cognito-idp:DeleteUserPool",
          "cognito-idp:DescribeUserPool",
          "cognito-idp:UpdateUserPool",
          "cognito-idp:ListUserPools",
          "cognito-idp:CreateUserPoolClient",
          "cognito-idp:DeleteUserPoolClient",
          "cognito-idp:DescribeUserPoolClient",
          "cognito-idp:UpdateUserPoolClient",
          "cognito-idp:ListUserPoolClients",
          "cognito-idp:AdminCreateUser",
          "cognito-idp:AdminDeleteUser",
          "cognito-idp:AdminSetUserPassword",
          "cognito-idp:AdminGetUser",
          "cognito-idp:GetUserPoolMfaConfig",
          "cognito-idp:TagResource",
          "cognito-idp:UntagResource",
        ],
        Resource: "*",
      },
    ],
  }),
});

new aws.iam.UserPolicyAttachment("workshop_policy", {
  user: workshopParticipant.name,
  policyArn: workshopPolicy.arn,
});

// ============================================================================
// Workshop Participant IAM Access Key
// ============================================================================

const workshopAccessKey = new aws.iam.AccessKey(`workshop_participant_v${keyVersion}`, {
  user: workshopParticipant.name,
});

// ============================================================================
// Generate and upload HTML
// ============================================================================

// IAM credentials are always first; extraValues from config are merged in after
const allValues = pulumi
  .all([workshopAccessKey.id, workshopAccessKey.secret])
  .apply(([accessKeyId, secretAccessKey]: [string, string]) => ({
    AWS_ACCESS_KEY_ID: accessKeyId,
    AWS_SECRET_ACCESS_KEY: secretAccessKey,
    ...extraValues,
  }));

const htmlContent = allValues.apply((vals: Record<string, string>) =>
  generateHtml(workshopTitle, vals, workshopName),
);

const indexHtml = new aws.s3.BucketObjectv2("index", {
  bucket: siteBucket.id,
  key: "index.html",
  content: htmlContent,
  contentType: "text/html",
  tags: { Name: "instructor-index-html" },
});

// ============================================================================
// CloudFront Origin Access Control
// ============================================================================

const oac = new aws.cloudfront.OriginAccessControl("site", {
  name: "workshop-instructor-oac",
  description: "OAC for instructor credential site",
  originAccessControlOriginType: "s3",
  signingBehavior: "always",
  signingProtocol: "sigv4",
});

// ============================================================================
// CloudFront Distribution
// ============================================================================

// Use AWS managed CachingOptimized policy instead of deprecated forwardedValues
const cachingOptimized = aws.cloudfront.getCachePolicyOutput({
  name: "Managed-CachingOptimized",
});

const distribution = new aws.cloudfront.Distribution("site", {
  enabled: true,
  defaultRootObject: "index.html",
  comment: "Workshop instructor credential sharing site",
  origins: [
    {
      domainName: siteBucket.bucketRegionalDomainName,
      originId: "s3-origin",
      originAccessControlId: oac.id,
    },
  ],
  defaultCacheBehavior: {
    targetOriginId: "s3-origin",
    viewerProtocolPolicy: "redirect-to-https",
    allowedMethods: ["GET", "HEAD"],
    cachedMethods: ["GET", "HEAD"],
    cachePolicyId: cachingOptimized.apply((p) => p.id!),
    compress: true,
  },
  restrictions: {
    geoRestriction: { restrictionType: "none" },
  },
  viewerCertificate: {
    cloudfrontDefaultCertificate: true,
  },
  tags: { Name: "workshop-instructor-distribution" },
});

// ============================================================================
// S3 Bucket Policy (allow CloudFront via OAC)
// ============================================================================

new aws.s3.BucketPolicy("site", {
  bucket: siteBucket.id,
  policy: pulumi
    .all([siteBucket.arn, distribution.arn])
    .apply(([bucketArn, distArn]) =>
      JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Sid: "AllowCloudFrontOAC",
            Effect: "Allow",
            Principal: { Service: "cloudfront.amazonaws.com" },
            Action: "s3:GetObject",
            Resource: `${bucketArn}/*`,
            Condition: {
              StringEquals: { "AWS:SourceArn": distArn },
            },
          },
        ],
      }),
    ),
});

// ============================================================================
// Outputs
// ============================================================================

export const siteUrl = pulumi.interpolate`https://${distribution.domainName}`;

const shortUrl = new command.local.Command("shortUrl", {
    create: siteUrl.apply(url => `curl -sf "https://tinyurl.com/api-create.php?url=${encodeURIComponent(url)}"`),
}, { dependsOn: [indexHtml] });

export const workshopUrl = shortUrl.stdout;
export const distributionId = distribution.id;
export const bucketName = siteBucket.id;
export const workshopIamUser = workshopParticipant.name;
