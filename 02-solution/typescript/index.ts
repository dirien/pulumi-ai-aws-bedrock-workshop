/**
 * Module 2 - Deploy your first agent (direct code / ZIP deployment).
 *
 * Ships the same agent you ran locally in Module 1 to Amazon Bedrock AgentCore
 * using AgentCore's direct code deployment - a .zip of the agent and its
 * dependencies instead of a Docker image.
 *
 * Deploy with a single command:
 *
 *     pulumi up
 *
 * The packaging build (build.sh, which installs ARM64 deps into build/) runs
 * automatically as part of `pulumi up` via a command.local.Command resource.
 */
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as command from "@pulumi/command";
import { createHash } from "crypto";
import * as fs from "fs";
import * as path from "path";

const config = new pulumi.Config();
const agentName = config.get("agentName") || "BasicAgent";
const stackName = config.get("stackName") || "agentcore-basic";
const runtimeVersion = config.get("runtime") || "PYTHON_3_13";

const awsConfig = new pulumi.Config("aws");
const awsRegion = awsConfig.require("region");

const currentIdentity = aws.getCallerIdentityOutput({});
const currentRegion = aws.getRegionOutput({});

const agentCodeDir = path.resolve(__dirname, "agent-code");
const buildDir = path.resolve(__dirname, "build");

// Hash of the inputs that should trigger a repackage: the agent and its deps.
const sourceHash = createHash("sha256")
  .update(fs.readFileSync(path.join(agentCodeDir, "basic_agent.py")))
  .update(fs.readFileSync(path.join(agentCodeDir, "requirements.txt")))
  .digest("hex");

// --- Build the ARM64 deployment package during `pulumi up` ---
// build.sh installs Linux ARM64 wheels into build/ and copies the agent in.
// triggers means it only re-runs when the agent or its deps change.
const build = new command.local.Command("build_package", {
  create: `bash ${path.join(__dirname, "build.sh")}`,
  dir: __dirname,
  triggers: [sourceHash],
});

// --- S3 bucket holding the zipped agent package ---
const codeBucket = new aws.s3.Bucket("agent_code", {
  bucketPrefix: `${stackName}-code-`,
  forceDestroy: true,
});

new aws.s3.BucketPublicAccessBlock("agent_code", {
  bucket: codeBucket.id,
  blockPublicAcls: true,
  blockPublicPolicy: true,
  ignorePublicAcls: true,
  restrictPublicBuckets: true,
});

new aws.s3.BucketVersioning("agent_code", {
  bucket: codeBucket.id,
  versioningConfiguration: { status: "Enabled" },
});

// Pulumi zips build/ (produced by the build command above) and uploads it.
const codeObject = new aws.s3.BucketObjectv2(
  "agent_code",
  {
    bucket: codeBucket.id,
    key: "agent-code.zip",
    source: new pulumi.asset.FileArchive(buildDir),
  },
  { dependsOn: [build] },
);

// --- IAM execution role ---
const agentExecution = new aws.iam.Role("agent_execution", {
  name: `${stackName}-agent-execution-role`,
  assumeRolePolicy: pulumi.jsonStringify({
    Version: "2012-10-17",
    Statement: [
      {
        Effect: "Allow",
        Principal: { Service: "bedrock-agentcore.amazonaws.com" },
        Action: "sts:AssumeRole",
        Condition: {
          StringEquals: {
            "aws:SourceAccount": currentIdentity.apply((id) => id.accountId),
          },
          ArnLike: {
            "aws:SourceArn": pulumi
              .all([currentRegion, currentIdentity])
              .apply(
                ([r, id]) =>
                  `arn:aws:bedrock-agentcore:${r.region}:${id.accountId}:*`,
              ),
          },
        },
      },
    ],
  }),
});

new aws.iam.RolePolicyAttachment("agent_execution_managed", {
  role: agentExecution.name,
  policyArn: "arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess",
});

const agentExecutionPolicy = new aws.iam.RolePolicy("agent_execution", {
  name: "AgentCoreExecutionPolicy",
  role: agentExecution.id,
  policy: pulumi.jsonStringify({
    Version: "2012-10-17",
    Statement: [
      {
        Sid: "S3CodeAccess",
        Effect: "Allow",
        Action: ["s3:GetObject", "s3:GetObjectVersion"],
        Resource: pulumi.interpolate`${codeBucket.arn}/*`,
      },
      {
        Sid: "CloudWatchLogs",
        Effect: "Allow",
        Action: [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:DescribeLogGroups",
        ],
        Resource: pulumi
          .all([currentRegion, currentIdentity])
          .apply(
            ([r, id]) =>
              `arn:aws:logs:${r.region}:${id.accountId}:log-group:/aws/bedrock-agentcore/runtimes/*`,
          ),
      },
      {
        Sid: "XRayTracing",
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
        Sid: "BedrockModelInvocation",
        Effect: "Allow",
        Action: ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        Resource: "*",
      },
      {
        Sid: "GetAgentAccessToken",
        Effect: "Allow",
        Action: [
          "bedrock-agentcore:GetWorkloadAccessToken",
          "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
          "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
        ],
        Resource: [
          pulumi
            .all([currentRegion, currentIdentity])
            .apply(
              ([r, id]) =>
                `arn:aws:bedrock-agentcore:${r.region}:${id.accountId}:workload-identity-directory/default`,
            ),
          pulumi
            .all([currentRegion, currentIdentity])
            .apply(
              ([r, id]) =>
                `arn:aws:bedrock-agentcore:${r.region}:${id.accountId}:workload-identity-directory/default/workload-identity/*`,
            ),
        ],
      },
    ],
  }),
});

// --- AgentCore Runtime (direct code) ---
const runtimeName = `${stackName}_${agentName}`.replace(/-/g, "_");

const basicAgent = new aws.bedrock.AgentcoreAgentRuntime(
  "basic_agent",
  {
    agentRuntimeName: runtimeName,
    roleArn: agentExecution.arn,
    agentRuntimeArtifact: {
      codeConfiguration: {
        entryPoints: ["basic_agent.py"],
        runtime: runtimeVersion,
        code: {
          s3: {
            bucket: codeBucket.id,
            prefix: codeObject.key,
            versionId: codeObject.versionId, // redeploy when the zip changes
          },
        },
      },
    },
    networkConfiguration: { networkMode: "PUBLIC" },
    environmentVariables: {
      AWS_REGION: awsRegion,
      AWS_DEFAULT_REGION: awsRegion,
    },
  },
  { dependsOn: [agentExecutionPolicy] },
);

export const agentRuntimeArn = basicAgent.agentRuntimeArn;
export const agentRuntimeId = basicAgent.agentRuntimeId;
