import hashlib
import json
import os
import urllib.parse

import pulumi
import pulumi_aws as aws
import pulumi_aws_native as aws_native
import pulumi_command as command
import pulumiverse_time as time

# ============================================================================
# Configuration
# ============================================================================

config = pulumi.Config()
agent_name = config.get("agentName") or "MCPServerAgent"
network_mode = config.get("networkMode") or "PUBLIC"
image_tag = config.get("imageTag") or "latest"
stack_name = config.get("stackName") or "agentcore-mcp-server"
description = config.get("description") or "MCP server runtime with JWT authentication"
environment_variables = config.get_object("environmentVariables") or {}
ecr_repository_name = config.get("ecrRepositoryName") or "mcp-server"
test_user_name = config.get("testUsername") or "testuser"
test_user_password = config.require_secret("testPassword")

aws_config = pulumi.Config("aws")
aws_region = aws_config.require("region")

# ============================================================================
# Data Sources
# ============================================================================

current_identity = aws.get_caller_identity_output()
current_region = aws.get_region_output()

# ============================================================================
# S3 Bucket for MCP Server Source Code
# ============================================================================

agent_source_bucket = aws.s3.Bucket(
    "agent_source",
    bucket_prefix=f"{stack_name}-source-",
    force_destroy=True,
    tags={
        "Name": f"{stack_name}-mcp-server-source",
        "Purpose": "Store MCP server source code for CodeBuild",
    },
)

aws.s3.BucketPublicAccessBlock(
    "agent_source",
    bucket=agent_source_bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

aws.s3.BucketVersioning(
    "agent_source",
    bucket=agent_source_bucket.id,
    versioning_configuration={"status": "Enabled"},
)

# ============================================================================
# Upload MCP Server Source Code to S3
# ============================================================================

agent_source_object = aws.s3.BucketObjectv2(
    "agent_source",
    bucket=agent_source_bucket.id,
    key="mcp-server-code.zip",
    source=pulumi.FileArchive(
        os.path.join(os.path.dirname(__file__), "mcp-server-code")
    ),
    tags={"Name": "mcp-server-source-code"},
)

# ============================================================================
# Cognito User Pool for JWT Authentication
# ============================================================================

mcp_user_pool = aws.cognito.UserPool(
    "mcp_user_pool",
    name=f"{stack_name}-user-pool",
    password_policy={
        "minimum_length": 8,
        "require_uppercase": False,
        "require_lowercase": False,
        "require_numbers": False,
        "require_symbols": False,
    },
    schemas=[
        {
            "name": "email",
            "attribute_data_type": "String",
            "required": False,
            "mutable": True,
        }
    ],
    tags={
        "Name": f"{stack_name}-user-pool",
        "StackName": stack_name,
        "Module": "Cognito",
    },
)

# ============================================================================
# Cognito User Pool Client
# ============================================================================

mcp_client = aws.cognito.UserPoolClient(
    "mcp_client",
    name=f"{stack_name}-client",
    user_pool_id=mcp_user_pool.id,
    explicit_auth_flows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    generate_secret=False,
    prevent_user_existence_errors="ENABLED",
)

# ============================================================================
# Test User
# ============================================================================

test_user = aws.cognito.User(
    "test_user",
    user_pool_id=mcp_user_pool.id,
    username=test_user_name,
    message_action="SUPPRESS",
)

# ============================================================================
# Cognito Password Setter Lambda - Set Permanent Password for Test User
# ============================================================================

cognito_password_setter_role = aws.iam.Role(
    "cognito_password_setter",
    name=f"{stack_name}-cognito-pw-setter-role",
    assume_role_policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
    inline_policies=[
        aws.iam.RoleInlinePolicyArgs(
            name="CognitoSetPasswordPolicy",
            policy=pulumi.Output.json_dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "SetUserPassword",
                            "Effect": "Allow",
                            "Action": ["cognito-idp:AdminSetUserPassword"],
                            "Resource": mcp_user_pool.arn,
                        }
                    ],
                }
            ),
        )
    ],
    tags={
        "Name": f"{stack_name}-cognito-pw-setter-role",
        "Module": "Lambda",
    },
)

cognito_password_setter_basic_execution = aws.iam.RolePolicyAttachment(
    "cognito_password_setter_basic_execution",
    role=cognito_password_setter_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
)

cognito_password_setter_function = aws.lambda_.Function(
    "cognito_password_setter",
    name=f"{stack_name}-cognito-pw-setter",
    role=cognito_password_setter_role.arn,
    runtime=aws.lambda_.Runtime.PYTHON3D12,
    handler="index.handler",
    timeout=60,
    code=pulumi.FileArchive(
        os.path.join(os.path.dirname(__file__), "lambda/cognito-password-setter")
    ),
    tags={
        "Name": f"{stack_name}-cognito-pw-setter",
        "Module": "Lambda",
    },
)

set_cognito_password = aws.lambda_.Invocation(
    "set_cognito_password",
    function_name=cognito_password_setter_function.name,
    input=pulumi.Output.all(mcp_user_pool.id, current_region, test_user_password).apply(
        lambda args: json.dumps(
            {
                "userPoolId": args[0],
                "username": test_user_name,
                "password": args[2],
                "region": args[1].region,
            }
        )
    ),
    opts=pulumi.ResourceOptions(
        depends_on=[
            test_user,
            cognito_password_setter_basic_execution,
            cognito_password_setter_function,
        ]
    ),
)

# ============================================================================
# ECR Repository - Container Registry for MCP Server Image
# ============================================================================

server_ecr = aws.ecr.Repository(
    "server_ecr",
    name=f"{stack_name}-{ecr_repository_name}",
    image_tag_mutability="MUTABLE",
    image_scanning_configuration={"scan_on_push": True},
    force_delete=True,
    tags={
        "Name": f"{stack_name}-ecr-repository",
        "Module": "ECR",
    },
)

aws.ecr.RepositoryPolicy(
    "server_ecr",
    repository=server_ecr.name,
    policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowPullFromAccount",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": current_identity.apply(
                            lambda id: f"arn:aws:iam::{id.account_id}:root"
                        ),
                    },
                    "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                }
            ],
        }
    ),
)

aws.ecr.LifecyclePolicy(
    "server_ecr",
    repository=server_ecr.name,
    policy=json.dumps(
        {
            "rules": [
                {
                    "rulePriority": 1,
                    "description": "Keep last 5 images",
                    "selection": {
                        "tagStatus": "any",
                        "countType": "imageCountMoreThan",
                        "countNumber": 5,
                    },
                    "action": {"type": "expire"},
                }
            ]
        }
    ),
)

# ============================================================================
# Agent Execution Role - For AgentCore Runtime
# ============================================================================

agent_execution = aws.iam.Role(
    "agent_execution",
    name=f"{stack_name}-agent-execution-role",
    assume_role_policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AssumeRolePolicy",
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {
                            "aws:SourceAccount": current_identity.apply(
                                lambda id: id.account_id
                            ),
                        },
                        "ArnLike": {
                            "aws:SourceArn": pulumi.Output.all(
                                current_region, current_identity
                            ).apply(
                                lambda args: f"arn:aws:bedrock-agentcore:{args[0].region}:{args[1].account_id}:*"
                            ),
                        },
                    },
                }
            ],
        }
    ),
    tags={
        "Name": f"{stack_name}-agent-execution-role",
        "Module": "IAM",
    },
)

agent_execution_managed = aws.iam.RolePolicyAttachment(
    "agent_execution_managed",
    role=agent_execution.name,
    policy_arn="arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess",
)

agent_execution_role_policy = aws.iam.RolePolicy(
    "agent_execution",
    name="AgentCoreExecutionPolicy",
    role=agent_execution.id,
    policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "ECRImageAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecr:BatchGetImage",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchCheckLayerAvailability",
                    ],
                    "Resource": server_ecr.arn,
                },
                {
                    "Sid": "ECRTokenAccess",
                    "Effect": "Allow",
                    "Action": ["ecr:GetAuthorizationToken"],
                    "Resource": "*",
                },
                {
                    "Sid": "CloudWatchLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:DescribeLogStreams",
                        "logs:CreateLogGroup",
                        "logs:DescribeLogGroups",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": pulumi.Output.all(
                        current_region, current_identity
                    ).apply(
                        lambda args: f"arn:aws:logs:{args[0].region}:{args[1].account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
                    ),
                },
                {
                    "Sid": "XRayTracing",
                    "Effect": "Allow",
                    "Action": [
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "CloudWatchMetrics",
                    "Effect": "Allow",
                    "Action": ["cloudwatch:PutMetricData"],
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
                    },
                },
                {
                    "Sid": "BedrockModelInvocation",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "GetAgentAccessToken",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                        "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                    ],
                    "Resource": [
                        pulumi.Output.all(current_region, current_identity).apply(
                            lambda args: f"arn:aws:bedrock-agentcore:{args[0].region}:{args[1].account_id}:workload-identity-directory/default"
                        ),
                        pulumi.Output.all(current_region, current_identity).apply(
                            lambda args: f"arn:aws:bedrock-agentcore:{args[0].region}:{args[1].account_id}:workload-identity-directory/default/workload-identity/*"
                        ),
                    ],
                },
            ],
        }
    ),
)

# ============================================================================
# CodeBuild Service Role - For Docker Image Building
# ============================================================================

agent_image_project_name = f"{stack_name}-mcp-server-build"

codebuild_role = aws.iam.Role(
    "codebuild",
    name=f"{stack_name}-codebuild-role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "codebuild.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
    tags={
        "Name": f"{stack_name}-codebuild-role",
        "Module": "IAM",
    },
)

codebuild_role_policy = aws.iam.RolePolicy(
    "codebuild",
    name="CodeBuildPolicy",
    role=codebuild_role.id,
    policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "CloudWatchLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": pulumi.Output.all(
                        current_region, current_identity
                    ).apply(
                        lambda args: f"arn:aws:logs:{args[0].region}:{args[1].account_id}:log-group:/aws/codebuild/*"
                    ),
                },
                {
                    "Sid": "ECRAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                        "ecr:GetAuthorizationToken",
                        "ecr:PutImage",
                        "ecr:InitiateLayerUpload",
                        "ecr:UploadLayerPart",
                        "ecr:CompleteLayerUpload",
                    ],
                    "Resource": [server_ecr.arn, "*"],
                },
                {
                    "Sid": "S3SourceAccess",
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                    "Resource": pulumi.Output.concat(agent_source_bucket.arn, "/*"),
                },
                {
                    "Sid": "S3BucketAccess",
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
                    "Resource": agent_source_bucket.arn,
                },
            ],
        }
    ),
)

# ============================================================================
# Build Trigger Lambda - Start and Wait for CodeBuild
# ============================================================================

build_trigger_role = aws.iam.Role(
    "build_trigger",
    name=f"{stack_name}-build-trigger-role",
    assume_role_policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
    inline_policies=[
        aws.iam.RoleInlinePolicyArgs(
            name="BuildTriggerPolicy",
            policy=pulumi.Output.all(current_region, current_identity).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "ManageBuild",
                                "Effect": "Allow",
                                "Action": [
                                    "codebuild:StartBuild",
                                    "codebuild:BatchGetBuilds",
                                ],
                                "Resource": f"arn:aws:codebuild:{args[0].region}:{args[1].account_id}:project/{agent_image_project_name}",
                            }
                        ],
                    }
                )
            ),
        )
    ],
    tags={
        "Name": f"{stack_name}-build-trigger-role",
        "Module": "Lambda",
    },
)

build_trigger_basic_execution = aws.iam.RolePolicyAttachment(
    "build_trigger_basic_execution",
    role=build_trigger_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
)

build_trigger_function = aws.lambda_.Function(
    "build_trigger",
    name=f"{stack_name}-build-trigger",
    role=build_trigger_role.arn,
    runtime=aws.lambda_.Runtime.PYTHON3D12,
    handler="index.handler",
    timeout=900,
    code=pulumi.FileArchive(
        os.path.join(os.path.dirname(__file__), "lambda/build-trigger")
    ),
    tags={
        "Name": f"{stack_name}-build-trigger",
        "Module": "Lambda",
    },
)

# ============================================================================
# CodeBuild Project - Build and Push MCP Server Docker Image
# ============================================================================

buildspec_path = os.path.join(os.path.dirname(__file__), "buildspec.yml")
with open(buildspec_path) as f:
    buildspec_content = f.read()
buildspec_fingerprint = hashlib.sha256(buildspec_content.encode()).hexdigest()

agent_image = aws.codebuild.Project(
    "agent_image",
    name=agent_image_project_name,
    description=f"Build MCP server Docker image for {stack_name}",
    service_role=codebuild_role.arn,
    build_timeout=60,
    artifacts={"type": "NO_ARTIFACTS"},
    environment={
        "compute_type": "BUILD_GENERAL1_LARGE",
        "image": "aws/codebuild/amazonlinux2-aarch64-standard:3.0",
        "type": "ARM_CONTAINER",
        "privileged_mode": True,
        "image_pull_credentials_type": "CODEBUILD",
        "environment_variables": [
            {
                "name": "AWS_DEFAULT_REGION",
                "value": current_region.apply(lambda r: r.region),
            },
            {
                "name": "AWS_ACCOUNT_ID",
                "value": current_identity.apply(lambda id: id.account_id),
            },
            {"name": "IMAGE_REPO_NAME", "value": server_ecr.name},
            {"name": "IMAGE_TAG", "value": image_tag},
            {"name": "STACK_NAME", "value": stack_name},
        ],
    },
    source={
        "type": "S3",
        "location": pulumi.Output.concat(
            agent_source_bucket.id, "/", agent_source_object.key
        ),
        "buildspec": buildspec_content,
    },
    logs_config={
        "cloudwatch_logs": {
            "group_name": f"/aws/codebuild/{agent_image_project_name}",
        }
    },
    tags={
        "Name": agent_image_project_name,
        "Module": "CodeBuild",
    },
)

# ============================================================================
# Trigger CodeBuild - Build Image Before Creating Runtime
# ============================================================================

build_trigger_invocation_input = pulumi.Output.all(
    agent_image.name, current_region
).apply(
    lambda args: json.dumps(
        {
            "projectName": args[0],
            "region": args[1].region,
            "pollIntervalSeconds": 15,
        }
    )
)

trigger_build = aws.lambda_.Invocation(
    "trigger_build",
    function_name=build_trigger_function.name,
    input=build_trigger_invocation_input,
    triggers={
        "sourceVersion": agent_source_object.version_id,
        "imageTag": image_tag,
        "buildspecSha256": buildspec_fingerprint,
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            agent_image,
            server_ecr,
            codebuild_role_policy,
            agent_source_object,
            build_trigger_basic_execution,
            build_trigger_function,
        ]
    ),
)

# ============================================================================
# AgentCore Runtime - MCP Server Runtime Resource
# ============================================================================

runtime_name = f"{stack_name}_{agent_name}".replace("-", "_")

source_hash = agent_source_object.version_id.apply(lambda v: v if v else "initial")

merged_env_vars = {
    "AWS_REGION": aws_region,
    "AWS_DEFAULT_REGION": aws_region,
    **environment_variables,
}

mcp_server = aws.bedrock.AgentcoreAgentRuntime(
    "mcp_server",
    agent_runtime_name=runtime_name,
    description=description,
    role_arn=agent_execution.arn,
    agent_runtime_artifact={
        "container_configuration": {
            "container_uri": pulumi.Output.concat(
                server_ecr.repository_url, ":", image_tag
            ),
        }
    },
    network_configuration={"network_mode": network_mode},
    protocol_configuration={"server_protocol": "MCP"},
    environment_variables={
        **merged_env_vars,
        "SOURCE_VERSION": source_hash,
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            trigger_build,
            agent_execution_role_policy,
            agent_execution_managed,
        ]
    ),
)

# ============================================================================
# AgentCore Policy Engine (aws-native) - Cedar policy host
# ============================================================================
# The classic aws.bedrock provider does not yet expose PolicyEngine / Policy
# resources, so we use the aws-native provider for these. Both providers can
# coexist in one program and share AWS credentials from the ESC environment.

mcp_policy_engine = aws_native.bedrockagentcore.PolicyEngine(
    "mcp_policy_engine",
    name=f"{stack_name}_policy_engine".replace("-", "_"),
    description=f"Policy engine for {stack_name}",
    tags=[
        {"key": "Name", "value": f"{stack_name}-policy-engine"},
        {"key": "Module", "value": "PolicyEngine"},
    ],
)

# IAM is eventually consistent. AgentCore validates the gateway role's trust
# policy when attaching a policy engine to a gateway, and that check can
# fail on the first try if the role and its policy attachments were just
# created. A short delay gives propagation enough time on a fresh deploy.
# This is the same pattern Terraform users reach for via hashicorp/time's
# `time_sleep` resource - the underlying limitation is in AWS Cloud Control.
iam_propagation_wait = time.Sleep(
    "iam_propagation_wait",
    create_duration="30s",
    triggers={
        "role_arn": agent_execution.arn,
        "managed_attachment": agent_execution_managed.id,
        "inline_policy": agent_execution_role_policy.id,
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            agent_execution,
            agent_execution_managed,
            agent_execution_role_policy,
        ]
    ),
)

# ============================================================================
# AgentCore Gateway (aws-native) - JWT Auth + Cedar policy enforcement
# ============================================================================
# Migrated from aws.bedrock.AgentcoreGateway because the classic provider
# does not expose policy_engine_configuration. The native resource attaches
# the policy engine in ENFORCE mode in a single declarative step.

cognito_discovery_url = pulumi.Output.all(current_region, mcp_user_pool.id).apply(
    lambda args: f"https://cognito-idp.{args[0].region}.amazonaws.com/{args[1]}/.well-known/openid-configuration"
)

mcp_gateway = aws_native.bedrockagentcore.Gateway(
    "mcp_gateway",
    name=f"{stack_name}-mcp-gateway",
    description=f"MCP Gateway with JWT auth for {stack_name}",
    protocol_type=aws_native.bedrockagentcore.GatewayProtocolType.MCP,
    role_arn=agent_execution.arn,
    authorizer_type=aws_native.bedrockagentcore.GatewayAuthorizerType.CUSTOM_JWT,
    authorizer_configuration={
        "custom_jwt_authorizer": {
            "allowed_clients": [mcp_client.id],
            "allowed_scopes": ["aws.cognito.signin.user.admin"],
            "discovery_url": cognito_discovery_url,
        },
    },
    policy_engine_configuration={
        "arn": mcp_policy_engine.policy_engine_arn,
        "mode": aws_native.bedrockagentcore.GatewayPolicyEngineMode.ENFORCE,
    },
    tags={
        "Name": f"{stack_name}-mcp-gateway",
        "Module": "Gateway",
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            iam_propagation_wait,
            mcp_policy_engine,
        ]
    ),
)

# ============================================================================
# AgentCore Gateway Target - wire gateway to MCP runtime
# ============================================================================
# Verified directly against CloudControl: AgentCore-hosted MCP runtimes need
# CredentialProvider.IamCredentialProvider, but that variant is missing from
# the published AWS::BedrockAgentCore::GatewayTarget schema. CloudControl's
# handler accepts the field, but pulumi-aws-native's typed bridge filters it
# out before sending. Until the CFN schema gains the variant, fall back to a
# command.local.Command running boto3.

mcp_target_name = "mcp-server-target"

runtime_invocation_endpoint = pulumi.Output.all(
    current_region, mcp_server.agent_runtime_arn
).apply(
    lambda args: (
        f"https://bedrock-agentcore.{args[0].region}.amazonaws.com/runtimes/"
        f"{urllib.parse.quote(args[1], safe='')}/invocations?qualifier=DEFAULT"
    )
)

# The upsert script: create the target if missing, update it if the endpoint changed,
# then wait for READY. Used for both create and update so the delete script is never
# called during normal trigger-driven re-runs (which would kill the just-created target).
_GATEWAY_TARGET_UPSERT_SCRIPT = r"""python3 <<'PYEOF'
import boto3, hashlib, os, sys, time
client = boto3.client('bedrock-agentcore-control', region_name=os.environ['REGION'])
target_id = None
existing_endpoint = None
existing_description = None
source_stamp = hashlib.sha1(os.environ['SOURCE_VERSION'].encode()).hexdigest()[:10]
description = f'Target for AgentCore-hosted MCP server [{source_stamp}]'
for t in client.list_gateway_targets(gatewayIdentifier=os.environ['GATEWAY_ID']).get('items', []):
    if t['name'] == os.environ['TARGET_NAME']:
        target_id = t['targetId']
        existing_endpoint = (
            t.get('targetConfiguration', {}).get('mcp', {}).get('mcpServer', {}).get('endpoint')
        )
        existing_description = t.get('description')
        break
if target_id is None:
    r = client.create_gateway_target(
        gatewayIdentifier=os.environ['GATEWAY_ID'],
        name=os.environ['TARGET_NAME'],
        description=description,
        targetConfiguration={'mcp': {'mcpServer': {'endpoint': os.environ['ENDPOINT']}}},
        credentialProviderConfigurations=[{
            'credentialProviderType': 'GATEWAY_IAM_ROLE',
            'credentialProvider': {'iamCredentialProvider': {'service': 'bedrock-agentcore'}},
        }],
    )
    target_id = r['targetId']
elif existing_endpoint != os.environ['ENDPOINT'] or existing_description != description:
    client.update_gateway_target(
        gatewayIdentifier=os.environ['GATEWAY_ID'],
        targetId=target_id,
        name=os.environ['TARGET_NAME'],
        description=description,
        targetConfiguration={'mcp': {'mcpServer': {'endpoint': os.environ['ENDPOINT']}}},
        credentialProviderConfigurations=[{
            'credentialProviderType': 'GATEWAY_IAM_ROLE',
            'credentialProvider': {'iamCredentialProvider': {'service': 'bedrock-agentcore'}},
        }],
    )
for _ in range(60):
    g = client.get_gateway_target(gatewayIdentifier=os.environ['GATEWAY_ID'], targetId=target_id)
    status = g.get('status')
    if status == 'READY':
        break
    if status in ('FAILED', 'DELETING'):
        sys.stderr.write(f'target failed: status={status} reasons={g.get("statusReasons")}\n')
        sys.exit(1)
    time.sleep(5)
print(target_id)
PYEOF
"""

_GATEWAY_TARGET_DELETE_SCRIPT = r"""python3 <<'PYEOF'
import boto3, hashlib, os
client = boto3.client('bedrock-agentcore-control', region_name=os.environ['REGION'])
source_stamp = hashlib.sha1(os.environ['SOURCE_VERSION'].encode()).hexdigest()[:10]
expected_description = f'Target for AgentCore-hosted MCP server [{source_stamp}]'
try:
    targets = client.list_gateway_targets(gatewayIdentifier=os.environ['GATEWAY_ID']).get('items', [])
except client.exceptions.ResourceNotFoundException:
    targets = []
for t in targets:
    if t['name'] == os.environ['TARGET_NAME'] and t.get('description') == expected_description:
        client.delete_gateway_target(gatewayIdentifier=os.environ['GATEWAY_ID'], targetId=t['targetId'])
        break
PYEOF
"""

mcp_gateway_target = command.local.Command(
    "mcp_gateway_target",
    create=_GATEWAY_TARGET_UPSERT_SCRIPT,
    update=_GATEWAY_TARGET_UPSERT_SCRIPT,
    delete=_GATEWAY_TARGET_DELETE_SCRIPT,
    environment={
        "REGION": current_region.apply(lambda r: r.region),
        "GATEWAY_ID": mcp_gateway.gateway_identifier,
        "TARGET_NAME": mcp_target_name,
        "ENDPOINT": runtime_invocation_endpoint,
        # Include the source version so that when MCP code changes, Pulumi runs
        # the update script (not a replace) so the delete path is never triggered.
        "SOURCE_VERSION": agent_source_object.version_id.apply(
            lambda v: v if v else "initial"
        ),
    },
)

mcp_gateway_target_id = mcp_gateway_target.stdout.apply(lambda s: s.strip())

# ============================================================================
# Cedar Policy (aws-native) - allow add_numbers + greet_user, deny the rest
# ============================================================================
# Default-deny: tools not explicitly permitted are blocked. The Gateway
# prefixes tool names with the target name and three underscores.

cedar_statement = pulumi.Output.all(
    mcp_gateway.gateway_arn, pulumi.Output.from_input(mcp_target_name)
).apply(
    lambda args: (
        "permit("
        "principal is AgentCore::OAuthUser, "
        f'action in [AgentCore::Action::"{args[1]}___add_numbers", '
        f'AgentCore::Action::"{args[1]}___greet_user"], '
        f'resource == AgentCore::Gateway::"{args[0]}"'
        ");"
    )
)

allow_add_and_greet = aws_native.bedrockagentcore.Policy(
    "allow_add_and_greet",
    policy_engine_id=mcp_policy_engine.policy_engine_id,
    name="allow_add_and_greet",
    description="Allow add_numbers and greet_user only - deny multiply_numbers",
    definition={
        "cedar": {
            "statement": cedar_statement,
        },
    },
    # MCP tool actions (e.g. "mcp-server-target___add_numbers") are not in
    # the policy engine's action catalog until tools are listed via the
    # gateway target. Cedar's default validator rejects them at create time.
    # IGNORE_ALL_FINDINGS skips that validation - actions are still enforced
    # at runtime when the gateway evaluates the policy.
    validation_mode=aws_native.bedrockagentcore.PolicyValidationMode.IGNORE_ALL_FINDINGS,
    opts=pulumi.ResourceOptions(depends_on=[mcp_gateway_target]),
)

# ============================================================================
# Outputs
# ============================================================================

pulumi.export("agentRuntimeId", mcp_server.agent_runtime_id)
pulumi.export("agentRuntimeArn", mcp_server.agent_runtime_arn)
pulumi.export("agentRuntimeVersion", mcp_server.agent_runtime_version)
pulumi.export("ecrRepositoryUrl", server_ecr.repository_url)
pulumi.export("ecrRepositoryArn", server_ecr.arn)
pulumi.export("agentExecutionRoleArn", agent_execution.arn)
pulumi.export("codebuildProjectName", agent_image.name)
pulumi.export("codebuildProjectArn", agent_image.arn)
pulumi.export("sourceBucketName", agent_source_bucket.id)
pulumi.export("sourceBucketArn", agent_source_bucket.arn)
pulumi.export("sourceObjectKey", agent_source_object.key)
pulumi.export("cognitoUserPoolId", mcp_user_pool.id)
pulumi.export("cognitoUserPoolArn", mcp_user_pool.arn)
pulumi.export("cognitoUserPoolClientId", mcp_client.id)
pulumi.export(
    "cognitoDiscoveryUrl",
    pulumi.Output.all(current_region, mcp_user_pool.id).apply(
        lambda args: f"https://cognito-idp.{args[0].region}.amazonaws.com/{args[1]}/.well-known/openid-configuration"
    ),
)
pulumi.export("testUsername", test_user_name)
pulumi.export("testPassword", test_user_password)
pulumi.export(
    "getTokenCommand",
    pulumi.Output.all(mcp_client.id, current_region, test_user_password).apply(
        lambda args: f"python get_token.py {args[0]} {test_user_name} '{args[2]}' {args[1].region}"
    ),
)
pulumi.export("gatewayId", mcp_gateway.gateway_identifier)
pulumi.export("gatewayArn", mcp_gateway.gateway_arn)
pulumi.export("gatewayUrl", mcp_gateway.gateway_url)
pulumi.export("policyEngineId", mcp_policy_engine.policy_engine_id)
pulumi.export("policyEngineArn", mcp_policy_engine.policy_engine_arn)
pulumi.export("policyId", allow_add_and_greet.policy_id)
pulumi.export("policyArn", allow_add_and_greet.policy_arn)
pulumi.export("gatewayTargetId", mcp_gateway_target_id)
