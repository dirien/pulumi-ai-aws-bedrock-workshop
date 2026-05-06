import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as awsNative from "@pulumi/aws-native";
import * as command from "@pulumi/command";
import * as time from "@pulumiverse/time";
import { createHash } from "crypto";
import * as fs from "fs";
import * as path from "path";

// ============================================================================
// Configuration
// ============================================================================

const config = new pulumi.Config();
const agentName = config.get("agentName") || "MCPServerAgent";
const networkMode = config.get("networkMode") || "PUBLIC";
const imageTag = config.get("imageTag") || "latest";
const stackName = config.get("stackName") || "agentcore-mcp-server";
const description =
  config.get("description") || "MCP server runtime with JWT authentication";
const environmentVariables =
  config.getObject<Record<string, string>>("environmentVariables") || {};
const ecrRepositoryName = config.get("ecrRepositoryName") || "mcp-server";
const testUserName = config.get("testUsername") || "testuser";
const testUserPassword = config.requireSecret("testPassword");

// Get the AWS region from the provider configuration
const awsConfig = new pulumi.Config("aws");
const awsRegion = awsConfig.require("region");

// ============================================================================
// Data Sources
// ============================================================================

const currentIdentity = aws.getCallerIdentityOutput({});
const currentRegion = aws.getRegionOutput({});

// ============================================================================
// S3 Bucket for MCP Server Source Code
// ============================================================================

const agentSourceBucket = new aws.s3.Bucket("agent_source", {
  bucketPrefix: `${stackName}-source-`,
  forceDestroy: true,
  tags: {
    Name: `${stackName}-mcp-server-source`,
    Purpose: "Store MCP server source code for CodeBuild",
  },
});

new aws.s3.BucketPublicAccessBlock("agent_source", {
  bucket: agentSourceBucket.id,
  blockPublicAcls: true,
  blockPublicPolicy: true,
  ignorePublicAcls: true,
  restrictPublicBuckets: true,
});

new aws.s3.BucketVersioning("agent_source", {
  bucket: agentSourceBucket.id,
  versioningConfiguration: {
    status: "Enabled",
  },
});

// ============================================================================
// Upload MCP Server Source Code to S3
// ============================================================================

const agentSourceObject = new aws.s3.BucketObjectv2("agent_source", {
  bucket: agentSourceBucket.id,
  key: "mcp-server-code.zip",
  source: new pulumi.asset.FileArchive(
    path.resolve(__dirname, "mcp-server-code"),
  ),
  tags: {
    Name: "mcp-server-source-code",
  },
});

// ============================================================================
// Cognito User Pool for JWT Authentication
// ============================================================================

const mcpUserPool = new aws.cognito.UserPool("mcp_user_pool", {
  name: `${stackName}-user-pool`,
  passwordPolicy: {
    minimumLength: 8,
    requireUppercase: false,
    requireLowercase: false,
    requireNumbers: false,
    requireSymbols: false,
  },
  schemas: [
    {
      name: "email",
      attributeDataType: "String",
      required: false,
      mutable: true,
    },
  ],
  tags: {
    Name: `${stackName}-user-pool`,
    StackName: stackName,
    Module: "Cognito",
  },
});

// ============================================================================
// Cognito User Pool Client
// ============================================================================

const mcpClient = new aws.cognito.UserPoolClient("mcp_client", {
  name: `${stackName}-client`,
  userPoolId: mcpUserPool.id,
  explicitAuthFlows: ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
  generateSecret: false,
  preventUserExistenceErrors: "ENABLED",
});

// ============================================================================
// Test User
// ============================================================================

const testUser = new aws.cognito.User("test_user", {
  userPoolId: mcpUserPool.id,
  username: testUserName,
  messageAction: "SUPPRESS",
});

// ============================================================================
// Cognito Password Setter Lambda - Set Permanent Password for Test User
// ============================================================================

const cognitoPasswordSetterRole = new aws.iam.Role("cognito_password_setter", {
  name: `${stackName}-cognito-pw-setter-role`,
  assumeRolePolicy: pulumi.jsonStringify({
    Version: "2012-10-17",
    Statement: [
      {
        Effect: "Allow",
        Principal: {
          Service: "lambda.amazonaws.com",
        },
        Action: "sts:AssumeRole",
      },
    ],
  }),
  inlinePolicies: [
    {
      name: "CognitoSetPasswordPolicy",
      policy: pulumi.jsonStringify({
        Version: "2012-10-17",
        Statement: [
          {
            Sid: "SetUserPassword",
            Effect: "Allow",
            Action: ["cognito-idp:AdminSetUserPassword"],
            Resource: mcpUserPool.arn,
          },
        ],
      }),
    },
  ],
  tags: {
    Name: `${stackName}-cognito-pw-setter-role`,
    Module: "Lambda",
  },
});

const cognitoPasswordSetterBasicExecution = new aws.iam.RolePolicyAttachment(
  "cognito_password_setter_basic_execution",
  {
    role: cognitoPasswordSetterRole.name,
    policyArn:
      "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
  },
);

const cognitoPasswordSetterFunction = new aws.lambda.Function(
  "cognito_password_setter",
  {
    name: `${stackName}-cognito-pw-setter`,
    role: cognitoPasswordSetterRole.arn,
    runtime: aws.lambda.Runtime.Python3d12,
    handler: "index.handler",
    timeout: 60,
    code: new pulumi.asset.FileArchive(
      path.resolve(__dirname, "lambda/cognito-password-setter"),
    ),
    tags: {
      Name: `${stackName}-cognito-pw-setter`,
      Module: "Lambda",
    },
  },
);

const setCognitoPassword = new aws.lambda.Invocation(
  "set_cognito_password",
  {
    functionName: cognitoPasswordSetterFunction.name,
    input: pulumi
      .all([mcpUserPool.id, currentRegion, testUserPassword])
      .apply(([userPoolId, region, password]) =>
        JSON.stringify({
          userPoolId,
          username: testUserName,
          password,
          region: region.region,
        }),
      ),
  },
  {
    dependsOn: [
      testUser,
      cognitoPasswordSetterBasicExecution,
      cognitoPasswordSetterFunction,
    ],
  },
);

// ============================================================================
// ECR Repository - Container Registry for MCP Server Image
// ============================================================================

const serverEcr = new aws.ecr.Repository("server_ecr", {
  name: `${stackName}-${ecrRepositoryName}`,
  imageTagMutability: "MUTABLE",
  imageScanningConfiguration: {
    scanOnPush: true,
  },
  forceDelete: true,
  tags: {
    Name: `${stackName}-ecr-repository`,
    Module: "ECR",
  },
});

new aws.ecr.RepositoryPolicy("server_ecr", {
  repository: serverEcr.name,
  policy: pulumi.jsonStringify({
    Version: "2012-10-17",
    Statement: [
      {
        Sid: "AllowPullFromAccount",
        Effect: "Allow",
        Principal: {
          AWS: currentIdentity.apply(
            (id) => `arn:aws:iam::${id.accountId}:root`,
          ),
        },
        Action: ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
      },
    ],
  }),
});

new aws.ecr.LifecyclePolicy("server_ecr", {
  repository: serverEcr.name,
  policy: JSON.stringify({
    rules: [
      {
        rulePriority: 1,
        description: "Keep last 5 images",
        selection: {
          tagStatus: "any",
          countType: "imageCountMoreThan",
          countNumber: 5,
        },
        action: {
          type: "expire",
        },
      },
    ],
  }),
});

// ============================================================================
// Agent Execution Role - For AgentCore Runtime
// ============================================================================

const agentExecution = new aws.iam.Role("agent_execution", {
  name: `${stackName}-agent-execution-role`,
  assumeRolePolicy: pulumi.jsonStringify({
    Version: "2012-10-17",
    Statement: [
      {
        Sid: "AssumeRolePolicy",
        Effect: "Allow",
        Principal: {
          Service: "bedrock-agentcore.amazonaws.com",
        },
        Action: "sts:AssumeRole",
        Condition: {
          StringEquals: {
            "aws:SourceAccount": currentIdentity.apply((id) => id.accountId),
          },
          ArnLike: {
            "aws:SourceArn": pulumi
              .all([currentRegion, currentIdentity])
              .apply(
                ([region, identity]) =>
                  `arn:aws:bedrock-agentcore:${region.region}:${identity.accountId}:*`,
              ),
          },
        },
      },
    ],
  }),
  tags: {
    Name: `${stackName}-agent-execution-role`,
    Module: "IAM",
  },
});

const agentExecutionManaged = new aws.iam.RolePolicyAttachment(
  "agent_execution_managed",
  {
    role: agentExecution.name,
    policyArn: "arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess",
  },
);

const agentExecutionRolePolicy = new aws.iam.RolePolicy("agent_execution", {
  name: "AgentCoreExecutionPolicy",
  role: agentExecution.id,
  policy: pulumi.jsonStringify({
    Version: "2012-10-17",
    Statement: [
      {
        Sid: "ECRImageAccess",
        Effect: "Allow",
        Action: [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability",
        ],
        Resource: serverEcr.arn,
      },
      {
        Sid: "ECRTokenAccess",
        Effect: "Allow",
        Action: ["ecr:GetAuthorizationToken"],
        Resource: "*",
      },
      {
        Sid: "CloudWatchLogs",
        Effect: "Allow",
        Action: [
          "logs:DescribeLogStreams",
          "logs:CreateLogGroup",
          "logs:DescribeLogGroups",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ],
        Resource: pulumi
          .all([currentRegion, currentIdentity])
          .apply(
            ([region, identity]) =>
              `arn:aws:logs:${region.region}:${identity.accountId}:log-group:/aws/bedrock-agentcore/runtimes/*`,
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
        Sid: "CloudWatchMetrics",
        Effect: "Allow",
        Action: ["cloudwatch:PutMetricData"],
        Resource: "*",
        Condition: {
          StringEquals: {
            "cloudwatch:namespace": "bedrock-agentcore",
          },
        },
      },
      {
        Sid: "BedrockModelInvocation",
        Effect: "Allow",
        Action: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ],
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
              ([region, identity]) =>
                `arn:aws:bedrock-agentcore:${region.region}:${identity.accountId}:workload-identity-directory/default`,
            ),
          pulumi
            .all([currentRegion, currentIdentity])
            .apply(
              ([region, identity]) =>
                `arn:aws:bedrock-agentcore:${region.region}:${identity.accountId}:workload-identity-directory/default/workload-identity/*`,
            ),
        ],
      },
    ],
  }),
});

// ============================================================================
// CodeBuild Service Role - For Docker Image Building
// ============================================================================

const codebuildRole = new aws.iam.Role("codebuild", {
  name: `${stackName}-codebuild-role`,
  assumeRolePolicy: JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      {
        Effect: "Allow",
        Principal: {
          Service: "codebuild.amazonaws.com",
        },
        Action: "sts:AssumeRole",
      },
    ],
  }),
  tags: {
    Name: `${stackName}-codebuild-role`,
    Module: "IAM",
  },
});

const codebuildRolePolicy = new aws.iam.RolePolicy("codebuild", {
  name: "CodeBuildPolicy",
  role: codebuildRole.id,
  policy: pulumi.jsonStringify({
    Version: "2012-10-17",
    Statement: [
      {
        Sid: "CloudWatchLogs",
        Effect: "Allow",
        Action: [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ],
        Resource: pulumi
          .all([currentRegion, currentIdentity])
          .apply(
            ([region, identity]) =>
              `arn:aws:logs:${region.region}:${identity.accountId}:log-group:/aws/codebuild/*`,
          ),
      },
      {
        Sid: "ECRAccess",
        Effect: "Allow",
        Action: [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:GetAuthorizationToken",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ],
        Resource: [serverEcr.arn, "*"],
      },
      {
        Sid: "S3SourceAccess",
        Effect: "Allow",
        Action: ["s3:GetObject", "s3:GetObjectVersion"],
        Resource: pulumi.interpolate`${agentSourceBucket.arn}/*`,
      },
      {
        Sid: "S3BucketAccess",
        Effect: "Allow",
        Action: ["s3:ListBucket", "s3:GetBucketLocation"],
        Resource: agentSourceBucket.arn,
      },
    ],
  }),
});

// ============================================================================
// Build Trigger Lambda - Start and Wait for CodeBuild
// ============================================================================

const agentImageProjectName = `${stackName}-mcp-server-build`;

const buildTriggerRole = new aws.iam.Role("build_trigger", {
  name: `${stackName}-build-trigger-role`,
  assumeRolePolicy: pulumi.jsonStringify({
    Version: "2012-10-17",
    Statement: [
      {
        Effect: "Allow",
        Principal: {
          Service: "lambda.amazonaws.com",
        },
        Action: "sts:AssumeRole",
      },
    ],
  }),
  inlinePolicies: [
    {
      name: "BuildTriggerPolicy",
      policy: pulumi
        .all([currentRegion, currentIdentity])
        .apply(([region, identity]) =>
          JSON.stringify({
            Version: "2012-10-17",
            Statement: [
              {
                Sid: "ManageBuild",
                Effect: "Allow",
                Action: ["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
                Resource: `arn:aws:codebuild:${region.region}:${identity.accountId}:project/${agentImageProjectName}`,
              },
            ],
          }),
        ),
    },
  ],
  tags: {
    Name: `${stackName}-build-trigger-role`,
    Module: "Lambda",
  },
});

const buildTriggerBasicExecution = new aws.iam.RolePolicyAttachment(
  "build_trigger_basic_execution",
  {
    role: buildTriggerRole.name,
    policyArn:
      "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
  },
);

const buildTriggerFunction = new aws.lambda.Function("build_trigger", {
  name: `${stackName}-build-trigger`,
  role: buildTriggerRole.arn,
  runtime: aws.lambda.Runtime.Python3d12,
  handler: "index.handler",
  timeout: 900,
  code: new pulumi.asset.FileArchive(
    path.resolve(__dirname, "lambda/build-trigger"),
  ),
  tags: {
    Name: `${stackName}-build-trigger`,
    Module: "Lambda",
  },
});

// ============================================================================
// CodeBuild Project - Build and Push MCP Server Docker Image
// ============================================================================

const buildspecContent = fs.readFileSync(
  path.resolve(__dirname, "buildspec.yml"),
  "utf-8",
);
const buildspecFingerprint = createHash("sha256")
  .update(buildspecContent)
  .digest("hex");

const agentImage = new aws.codebuild.Project("agent_image", {
  name: agentImageProjectName,
  description: `Build MCP server Docker image for ${stackName}`,
  serviceRole: codebuildRole.arn,
  buildTimeout: 60,
  artifacts: {
    type: "NO_ARTIFACTS",
  },
  environment: {
    computeType: "BUILD_GENERAL1_LARGE",
    image: "aws/codebuild/amazonlinux2-aarch64-standard:3.0",
    type: "ARM_CONTAINER",
    privilegedMode: true,
    imagePullCredentialsType: "CODEBUILD",
    environmentVariables: [
      {
        name: "AWS_DEFAULT_REGION",
        value: currentRegion.apply((r) => r.region),
      },
      {
        name: "AWS_ACCOUNT_ID",
        value: currentIdentity.apply((id) => id.accountId),
      },
      {
        name: "IMAGE_REPO_NAME",
        value: serverEcr.name,
      },
      {
        name: "IMAGE_TAG",
        value: imageTag,
      },
      {
        name: "STACK_NAME",
        value: stackName,
      },
    ],
  },
  source: {
    type: "S3",
    location: pulumi.interpolate`${agentSourceBucket.id}/${agentSourceObject.key}`,
    buildspec: buildspecContent,
  },
  logsConfig: {
    cloudwatchLogs: {
      groupName: `/aws/codebuild/${agentImageProjectName}`,
    },
  },
  tags: {
    Name: agentImageProjectName,
    Module: "CodeBuild",
  },
});

// ============================================================================
// Trigger CodeBuild - Build Image Before Creating Runtime
// ============================================================================

const buildTriggerInvocationInput = pulumi
  .all([agentImage.name, currentRegion])
  .apply(([projectName, region]) =>
    JSON.stringify({
      projectName,
      region: region.region,
      pollIntervalSeconds: 15,
    }),
  );

const triggerBuild = new aws.lambda.Invocation(
  "trigger_build",
  {
    functionName: buildTriggerFunction.name,
    input: buildTriggerInvocationInput,
    triggers: {
      sourceVersion: agentSourceObject.versionId,
      imageTag,
      buildspecSha256: buildspecFingerprint,
    },
  },
  {
    dependsOn: [
      agentImage,
      serverEcr,
      codebuildRolePolicy,
      agentSourceObject,
      buildTriggerBasicExecution,
      buildTriggerFunction,
    ],
  },
);

// ============================================================================
// AgentCore Runtime - MCP Server Runtime Resource
// ============================================================================

const runtimeName = `${stackName}_${agentName}`.replace(/-/g, "_");

const sourceHash = agentSourceObject.versionId.apply((v) => v ?? "initial");

const mergedEnvVars: Record<string, string> = {
  AWS_REGION: awsRegion,
  AWS_DEFAULT_REGION: awsRegion,
  ...environmentVariables,
};

const mcpServer = new aws.bedrock.AgentcoreAgentRuntime(
  "mcp_server",
  {
    agentRuntimeName: runtimeName,
    description: description,
    roleArn: agentExecution.arn,
    agentRuntimeArtifact: {
      containerConfiguration: {
        containerUri: pulumi.interpolate`${serverEcr.repositoryUrl}:${imageTag}`,
      },
    },
    networkConfiguration: {
      networkMode: networkMode,
    },
    protocolConfiguration: {
      serverProtocol: "MCP",
    },
    environmentVariables: {
      ...mergedEnvVars,
      SOURCE_VERSION: sourceHash,
    },
  },
  {
    dependsOn: [triggerBuild, agentExecutionRolePolicy, agentExecutionManaged],
  },
);

// ============================================================================
// AgentCore Policy Engine (aws-native) - Cedar policy host
// ============================================================================
// The classic aws.bedrock provider does not yet expose PolicyEngine / Policy
// resources, so we use the aws-native provider for these. Both providers can
// coexist in one program and share AWS credentials from the ESC environment.

const mcpPolicyEngine = new awsNative.bedrockagentcore.PolicyEngine(
  "mcp_policy_engine",
  {
    name: `${stackName}_policy_engine`.replace(/-/g, "_"),
    description: `Policy engine for ${stackName}`,
    tags: [
      { key: "Name", value: `${stackName}-policy-engine` },
      { key: "Module", value: "PolicyEngine" },
    ],
  },
);

// IAM is eventually consistent. AgentCore validates the gateway role's trust
// policy when attaching a policy engine to a gateway, and that check can
// fail on the first try if the role and its policy attachments were just
// created. A short delay gives propagation enough time on a fresh deploy.
// This is the same pattern Terraform users reach for via hashicorp/time's
// `time_sleep` resource - the underlying limitation is in AWS Cloud Control.
const iamPropagationWait = new time.Sleep(
  "iam_propagation_wait",
  {
    createDuration: "30s",
    triggers: {
      role_arn: agentExecution.arn,
      managed_attachment: agentExecutionManaged.id,
      inline_policy: agentExecutionRolePolicy.id,
    },
  },
  {
    dependsOn: [
      agentExecution,
      agentExecutionManaged,
      agentExecutionRolePolicy,
    ],
  },
);

// ============================================================================
// AgentCore Gateway (aws-native) - JWT Auth + Cedar policy enforcement
// ============================================================================
// Migrated from aws.bedrock.AgentcoreGateway because the classic provider
// does not expose policyEngineConfiguration. The native resource attaches
// the policy engine in ENFORCE mode in a single declarative step.

const cognitoDiscoveryUrlInput = pulumi
  .all([currentRegion, mcpUserPool.id])
  .apply(
    ([region, userPoolId]) =>
      `https://cognito-idp.${region.region}.amazonaws.com/${userPoolId}/.well-known/openid-configuration`,
  );

const mcpGateway = new awsNative.bedrockagentcore.Gateway(
  "mcp_gateway",
  {
    name: `${stackName}-mcp-gateway`,
    description: `MCP Gateway with JWT auth for ${stackName}`,
    protocolType: awsNative.bedrockagentcore.GatewayProtocolType.Mcp,
    roleArn: agentExecution.arn,
    authorizerType: awsNative.bedrockagentcore.GatewayAuthorizerType.CustomJwt,
    authorizerConfiguration: {
      customJwtAuthorizer: {
        allowedClients: [mcpClient.id],
        discoveryUrl: cognitoDiscoveryUrlInput,
      },
    },
    policyEngineConfiguration: {
      arn: mcpPolicyEngine.policyEngineArn,
      mode: awsNative.bedrockagentcore.GatewayPolicyEngineMode.Enforce,
    },
    tags: {
      Name: `${stackName}-mcp-gateway`,
      Module: "Gateway",
    },
  },
  {
    dependsOn: [iamPropagationWait, mcpPolicyEngine],
  },
);

// ============================================================================
// AgentCore Gateway Target - wire gateway to MCP runtime
// ============================================================================
// Verified directly against CloudControl: AgentCore-hosted MCP runtimes need
// CredentialProvider.IamCredentialProvider, but that variant is missing from
// the published AWS::BedrockAgentCore::GatewayTarget schema. CloudControl's
// handler accepts the field, but pulumi-aws-native's typed bridge filters it
// out before sending. Until the CFN schema gains the variant, fall back to a
// command.local.Command running boto3.

const mcpTargetName = "mcp-server-target";

const runtimeInvocationEndpoint = pulumi
  .all([currentRegion, mcpServer.agentRuntimeArn])
  .apply(
    ([region, arn]) =>
      `https://bedrock-agentcore.${region.region}.amazonaws.com/runtimes/${encodeURIComponent(arn)}/invocations?qualifier=DEFAULT`,
  );

const gatewayTargetCreateScript = `python3 <<'PYEOF'
import boto3, os, sys, time
client = boto3.client('bedrock-agentcore-control', region_name=os.environ['REGION'])
target_id = None
for t in client.list_gateway_targets(gatewayIdentifier=os.environ['GATEWAY_ID']).get('items', []):
    if t['name'] == os.environ['TARGET_NAME']:
        target_id = t['targetId']
        break
if target_id is None:
    r = client.create_gateway_target(
        gatewayIdentifier=os.environ['GATEWAY_ID'],
        name=os.environ['TARGET_NAME'],
        description='Target for AgentCore-hosted MCP server',
        targetConfiguration={'mcp': {'mcpServer': {'endpoint': os.environ['ENDPOINT']}}},
        credentialProviderConfigurations=[{
            'credentialProviderType': 'GATEWAY_IAM_ROLE',
            'credentialProvider': {'iamCredentialProvider': {'service': 'bedrock-agentcore'}},
        }],
    )
    target_id = r['targetId']
# Wait for READY so the policy engine knows the tool actions before any
# Cedar policy referencing them is created.
for _ in range(60):
    g = client.get_gateway_target(gatewayIdentifier=os.environ['GATEWAY_ID'], targetId=target_id)
    status = g.get('status')
    if status == 'READY':
        break
    if status in ('FAILED', 'DELETING'):
        sys.stderr.write(f'target failed: status={status} reasons={g.get("statusReasons")}\\n')
        sys.exit(1)
    time.sleep(5)
print(target_id)
PYEOF
`;

const gatewayTargetDeleteScript = `python3 <<'PYEOF'
import boto3, os
client = boto3.client('bedrock-agentcore-control', region_name=os.environ['REGION'])
try:
    targets = client.list_gateway_targets(gatewayIdentifier=os.environ['GATEWAY_ID']).get('items', [])
except client.exceptions.ResourceNotFoundException:
    targets = []
for t in targets:
    if t['name'] == os.environ['TARGET_NAME']:
        client.delete_gateway_target(gatewayIdentifier=os.environ['GATEWAY_ID'], targetId=t['targetId'])
        break
PYEOF
`;

const mcpGatewayTarget = new command.local.Command("mcp_gateway_target", {
  create: gatewayTargetCreateScript,
  delete: gatewayTargetDeleteScript,
  environment: {
    REGION: currentRegion.apply((r) => r.region),
    GATEWAY_ID: mcpGateway.gatewayIdentifier,
    TARGET_NAME: mcpTargetName,
    ENDPOINT: runtimeInvocationEndpoint,
  },
  triggers: [mcpGateway.gatewayIdentifier, runtimeInvocationEndpoint],
});

const mcpGatewayTargetId = mcpGatewayTarget.stdout.apply((s) => s.trim());

// ============================================================================
// Cedar Policy (aws-native) - allow add_numbers + greet_user, deny the rest
// ============================================================================
// Default-deny: tools not explicitly permitted are blocked. The Gateway
// prefixes tool names with the target name and three underscores.

const cedarStatement = pulumi
  .all([mcpGateway.gatewayArn, mcpTargetName])
  .apply(
    ([gwArn, targetName]) =>
      `permit(principal is AgentCore::OAuthUser, action in [AgentCore::Action::"${targetName}___add_numbers", AgentCore::Action::"${targetName}___greet_user"], resource == AgentCore::Gateway::"${gwArn}");`,
  );

const allowAddAndGreet = new awsNative.bedrockagentcore.Policy(
  "allow_add_and_greet",
  {
    policyEngineId: mcpPolicyEngine.policyEngineId,
    name: "allow_add_and_greet",
    description:
      "Allow add_numbers and greet_user only - deny multiply_numbers",
    definition: {
      cedar: {
        statement: cedarStatement,
      },
    },
    // MCP tool actions (e.g. "mcp-server-target___add_numbers") are not in
    // the policy engine's action catalog until tools are listed via the
    // gateway target. Cedar's default validator rejects them at create time.
    // IGNORE_ALL_FINDINGS skips that validation - actions are still enforced
    // at runtime when the gateway evaluates the policy.
    validationMode:
      awsNative.bedrockagentcore.PolicyValidationMode.IgnoreAllFindings,
  },
  {
    dependsOn: [mcpGatewayTarget],
  },
);

// ============================================================================
// Outputs
// ============================================================================

export const agentRuntimeId = mcpServer.agentRuntimeId;
export const agentRuntimeArn = mcpServer.agentRuntimeArn;
export const agentRuntimeVersion = mcpServer.agentRuntimeVersion;
export const ecrRepositoryUrl = serverEcr.repositoryUrl;
export const ecrRepositoryArn = serverEcr.arn;
export const agentExecutionRoleArn = agentExecution.arn;
export const codebuildProjectName = agentImage.name;
export const codebuildProjectArn = agentImage.arn;
export const sourceBucketName = agentSourceBucket.id;
export const sourceBucketArn = agentSourceBucket.arn;
export const sourceObjectKey = agentSourceObject.key;
export const cognitoUserPoolId = mcpUserPool.id;
export const cognitoUserPoolArn = mcpUserPool.arn;
export const cognitoUserPoolClientId = mcpClient.id;
export const cognitoDiscoveryUrl = pulumi
  .all([currentRegion, mcpUserPool.id])
  .apply(
    ([region, userPoolId]) =>
      `https://cognito-idp.${region.region}.amazonaws.com/${userPoolId}/.well-known/openid-configuration`,
  );
export const testUsername = testUserName;
export const testPassword = testUserPassword;
export const getTokenCommand = pulumi
  .all([mcpClient.id, currentRegion, testUserPassword])
  .apply(
    ([clientId, region, password]) =>
      `python get_token.py ${clientId} ${testUserName} '${password}' ${region.region}`,
  );
export const gatewayId = mcpGateway.gatewayIdentifier;
export const gatewayArn = mcpGateway.gatewayArn;
export const gatewayUrl = mcpGateway.gatewayUrl;
export const policyEngineId = mcpPolicyEngine.policyEngineId;
export const policyEngineArn = mcpPolicyEngine.policyEngineArn;
export const policyId = allowAddAndGreet.policyId;
export const policyArn = allowAddAndGreet.policyArn;
export const gatewayTargetId = mcpGatewayTargetId;
