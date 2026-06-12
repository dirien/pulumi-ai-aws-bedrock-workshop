import hashlib
import json
import os

import pulumi
import pulumi_aws as aws

# ============================================================================
# Configuration
# ============================================================================

config = pulumi.Config()
agent_name = config.get("agentName") or "WeatherAgent"
memory_name = config.get("memoryName") or "WeatherAgentMemory"
network_mode = config.get("networkMode") or "PUBLIC"
image_tag = config.get("imageTag") or "latest"
stack_name = config.get("stackName") or "agentcore-weather"
description = (
    config.get("description")
    or "End-to-end Weather Agent with AgentCore tools (Browser, Code Interpreter, Memory)"
)
ecr_repository_name = config.get("ecrRepositoryName") or "weather-agent"

aws_config = pulumi.Config("aws")
aws_region = aws_config.require("region")

# ============================================================================
# Data Sources
# ============================================================================

current_identity = aws.get_caller_identity_output()
current_region = aws.get_region_output()

# ============================================================================
# Browser Tool - For Web Browsing Capabilities
# ============================================================================

browser = aws.bedrock.AgentcoreBrowser(
    "browser",
    name=f"{stack_name.replace('-', '_')}_browser",
    description=f"Browser tool for {stack_name} weather agent to access weather websites",
    network_configuration={"network_mode": network_mode},
    tags={
        "Name": f"{stack_name}-browser-tool",
        "Module": "AgentCore-Tools",
    },
)

# ============================================================================
# Code Interpreter Tool - For Python Code Execution and Data Analysis
# ============================================================================

code_interpreter = aws.bedrock.AgentcoreCodeInterpreter(
    "code_interpreter",
    name=f"{stack_name.replace('-', '_')}_code_interpreter",
    description=f"Code interpreter tool for {stack_name} weather agent to analyze weather data",
    network_configuration={"network_mode": network_mode},
    tags={
        "Name": f"{stack_name}-code-interpreter-tool",
        "Module": "AgentCore-Tools",
    },
)

# ============================================================================
# Memory - For Persistent Conversation Context
# ============================================================================

memory = aws.bedrock.AgentcoreMemory(
    "memory",
    name=f"{stack_name.replace('-', '_')}_{memory_name}",
    description=f"Memory for {stack_name} weather agent to maintain conversation context",
    event_expiry_duration=30,
    tags={
        "Name": f"{stack_name}-memory",
        "Module": "AgentCore-Tools",
    },
)

# Long-term extraction: the USER_PREFERENCE strategy reads conversation
# events and distills preference records into the preferences/{actorId}
# namespace, where the agent's memory tool looks them up.
memory_strategy = aws.bedrock.AgentcoreMemoryStrategy(
    "user_preferences",
    name="user_preferences",
    memory_id=memory.id,
    type="USER_PREFERENCE",
    description="Extract long-term activity preferences from conversation",
    namespaces=["preferences/{actorId}"],
)

# ============================================================================
# S3 Buckets
# ============================================================================

# Agent Source Code Bucket
agent_source_bucket = aws.s3.Bucket(
    "agent_source",
    bucket_prefix=f"{stack_name}-source-",
    force_destroy=True,
    tags={
        "Name": f"{stack_name}-agent-source",
        "Purpose": "Store agent source code for CodeBuild",
    },
)

# Results Bucket (for agent-generated artifacts)
results = aws.s3.Bucket(
    "results",
    bucket_prefix=f"{stack_name}-results-",
    force_destroy=True,
    tags={
        "Name": f"{stack_name}-results",
        "Purpose": "Store weather agent generated artifacts",
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

aws.s3.BucketPublicAccessBlock(
    "results",
    bucket=results.id,
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

aws.s3.BucketVersioning(
    "results",
    bucket=results.id,
    versioning_configuration={"status": "Enabled"},
)

# ============================================================================
# Upload Agent Source Code to S3
# ============================================================================

agent_source_object = aws.s3.BucketObjectv2(
    "agent_source",
    bucket=agent_source_bucket.id,
    key="agent-code.zip",
    source=pulumi.FileArchive(os.path.join(os.path.dirname(__file__), "agent-code")),
    tags={"Name": "agent-source-code"},
)

# ============================================================================
# ECR Repository - Container Registry for Agent Image
# ============================================================================

weather_ecr = aws.ecr.Repository(
    "weather_ecr",
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
    "weather_ecr",
    repository=weather_ecr.name,
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
    "weather_ecr",
    repository=weather_ecr.name,
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
                    "Resource": weather_ecr.arn,
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
                {
                    "Sid": "S3ResultsAccess",
                    "Effect": "Allow",
                    "Action": [
                        "s3:PutObject",
                        "s3:GetObject",
                        "s3:DeleteObject",
                        "s3:ListBucket",
                    ],
                    "Resource": [
                        results.arn,
                        pulumi.Output.concat(results.arn, "/*"),
                    ],
                },
            ],
        }
    ),
)

# ============================================================================
# CodeBuild Service Role - For Docker Image Building
# ============================================================================

agent_image_project_name = f"{stack_name}-agent-build"

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
                    "Resource": [weather_ecr.arn, "*"],
                },
                {
                    "Sid": "S3SourceAccess",
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                    "Resource": pulumi.Output.concat(
                        agent_source_bucket.arn, "/*"
                    ),
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
# CodeBuild Project - Build and Push Docker Image
# ============================================================================

buildspec_path = os.path.join(os.path.dirname(__file__), "buildspec.yml")
with open(buildspec_path) as f:
    buildspec_content = f.read()
buildspec_fingerprint = hashlib.sha256(buildspec_content.encode()).hexdigest()

agent_image = aws.codebuild.Project(
    "agent_image",
    name=agent_image_project_name,
    description=f"Build Weather Agent Docker image for {stack_name}",
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
            {"name": "IMAGE_REPO_NAME", "value": weather_ecr.name},
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
        "Name": f"{stack_name}-agent-build",
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
            weather_ecr,
            codebuild_role_policy,
            agent_source_object,
            build_trigger_basic_execution,
            build_trigger_function,
        ]
    ),
)

# ============================================================================
# Memory Initialization Lambda - Populate Activity Preferences
# ============================================================================

memory_init_role = aws.iam.Role(
    "memory_init",
    name=f"{stack_name}-memory-init-role",
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
            name="MemoryInitPolicy",
            policy=memory.arn.apply(
                lambda memory_arn: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "CreateMemoryEvent",
                                "Effect": "Allow",
                                "Action": ["bedrock-agentcore:CreateEvent"],
                                "Resource": memory_arn,
                            }
                        ],
                    }
                )
            ),
        )
    ],
    tags={
        "Name": f"{stack_name}-memory-init-role",
        "Module": "Lambda",
    },
)

memory_init_basic_execution = aws.iam.RolePolicyAttachment(
    "memory_init_basic_execution",
    role=memory_init_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
)

memory_init_function = aws.lambda_.Function(
    "memory_init",
    name=f"{stack_name}-memory-init",
    role=memory_init_role.arn,
    runtime=aws.lambda_.Runtime.PYTHON3D12,
    handler="index.handler",
    timeout=60,
    code=pulumi.FileArchive(
        os.path.join(os.path.dirname(__file__), "lambda/init-memory")
    ),
    tags={
        "Name": f"{stack_name}-memory-init",
        "Module": "Lambda",
    },
)

memory_init_lambda_path = os.path.join(
    os.path.dirname(__file__), "lambda/init-memory/index.py"
)
with open(memory_init_lambda_path) as f:
    memory_init_code_content = f.read()
memory_init_code_hash = hashlib.sha256(memory_init_code_content.encode()).hexdigest()

aws.lambda_.Invocation(
    "initialize_memory",
    function_name=memory_init_function.name,
    input=pulumi.Output.all(memory.id, current_region).apply(
        lambda args: json.dumps(
            {
                "memoryId": args[0],
                "region": args[1].region,
            }
        )
    ),
    triggers={
        "memoryId": memory.id,
        "lambdaCodeHash": memory_init_code_hash,
    },
    # The strategy must exist before the seed event is written - extraction
    # only processes events that arrive while the strategy is active.
    opts=pulumi.ResourceOptions(
        depends_on=[
            memory,
            memory_strategy,
            memory_init_function,
            memory_init_basic_execution,
        ]
    ),
)

# ============================================================================
# Weather Agent Runtime
# ============================================================================

runtime_name = f"{stack_name}_{agent_name}".replace("-", "_")

source_hash = agent_source_object.version_id.apply(lambda v: v if v else "initial")

weather_agent = aws.bedrock.AgentcoreAgentRuntime(
    "weather_agent",
    agent_runtime_name=runtime_name,
    description=description,
    role_arn=agent_execution.arn,
    agent_runtime_artifact={
        "container_configuration": {
            "container_uri": pulumi.Output.concat(
                weather_ecr.repository_url, ":", image_tag
            ),
        }
    },
    network_configuration={"network_mode": network_mode},
    environment_variables={
        "AWS_REGION": aws_region,
        "AWS_DEFAULT_REGION": aws_region,
        "RESULTS_BUCKET": results.id,
        "BROWSER_ID": browser.browser_id,
        "CODE_INTERPRETER_ID": code_interpreter.code_interpreter_id,
        "MEMORY_ID": memory.id,
        "SOURCE_VERSION": source_hash,
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            trigger_build,
            agent_execution_role_policy,
            agent_execution_managed,
            browser,
            code_interpreter,
            memory,
        ]
    ),
)

# ============================================================================
# Observability - CloudWatch Logs and X-Ray Traces Delivery
# ============================================================================

agent_runtime_logs = aws.cloudwatch.LogGroup(
    "agent_runtime_logs",
    name=pulumi.Output.concat(
        "/aws/vendedlogs/bedrock-agentcore/", weather_agent.agent_runtime_id
    ),
    retention_in_days=14,
    tags={
        "Name": f"{stack_name}-agent-logs",
        "Purpose": "Agent runtime application logs",
        "Module": "Observability",
    },
    opts=pulumi.ResourceOptions(depends_on=[weather_agent]),
)

logs = aws.cloudwatch.LogDeliverySource(
    "logs",
    name=pulumi.Output.concat(weather_agent.agent_runtime_id, "-logs-src"),
    log_type="APPLICATION_LOGS",
    resource_arn=weather_agent.agent_runtime_arn,
    opts=pulumi.ResourceOptions(depends_on=[weather_agent]),
)

logs_log_delivery_destination = aws.cloudwatch.LogDeliveryDestination(
    "logs",
    name=pulumi.Output.concat(weather_agent.agent_runtime_id, "-logs-dst"),
    delivery_destination_configuration={
        "destination_resource_arn": agent_runtime_logs.arn,
    },
    tags={
        "Name": f"{stack_name}-logs-dst",
        "Module": "Observability",
    },
    opts=pulumi.ResourceOptions(depends_on=[agent_runtime_logs]),
)

logs_log_delivery = aws.cloudwatch.LogDelivery(
    "logs",
    delivery_source_name=logs.name,
    delivery_destination_arn=logs_log_delivery_destination.arn,
    tags={
        "Name": f"{stack_name}-logs-delivery",
        "Module": "Observability",
    },
    opts=pulumi.ResourceOptions(depends_on=[logs, logs_log_delivery_destination]),
)

traces = aws.cloudwatch.LogDeliverySource(
    "traces",
    name=pulumi.Output.concat(weather_agent.agent_runtime_id, "-traces-src"),
    log_type="TRACES",
    resource_arn=weather_agent.agent_runtime_arn,
    opts=pulumi.ResourceOptions(depends_on=[weather_agent]),
)

traces_log_delivery_destination = aws.cloudwatch.LogDeliveryDestination(
    "traces",
    name=pulumi.Output.concat(weather_agent.agent_runtime_id, "-traces-dst"),
    delivery_destination_type="XRAY",
    tags={
        "Name": f"{stack_name}-traces-dst",
        "Module": "Observability",
    },
)

traces_log_delivery = aws.cloudwatch.LogDelivery(
    "traces",
    delivery_source_name=traces.name,
    delivery_destination_arn=traces_log_delivery_destination.arn,
    tags={
        "Name": f"{stack_name}-traces-delivery",
        "Module": "Observability",
    },
    opts=pulumi.ResourceOptions(
        depends_on=[traces, traces_log_delivery_destination]
    ),
)

# ============================================================================
# Outputs
# ============================================================================

pulumi.export("agentRuntimeId", weather_agent.agent_runtime_id)
pulumi.export("agentRuntimeArn", weather_agent.agent_runtime_arn)
pulumi.export("agentRuntimeVersion", weather_agent.agent_runtime_version)
pulumi.export("agentEcrRepositoryUrl", weather_ecr.repository_url)
pulumi.export("agentExecutionRoleArn", agent_execution.arn)
pulumi.export("codebuildProjectName", agent_image.name)
pulumi.export("sourceBucketName", agent_source_bucket.id)
pulumi.export("resultsBucketName", results.id)
pulumi.export("browserId", browser.browser_id)
pulumi.export("browserArn", browser.browser_arn)
pulumi.export("codeInterpreterId", code_interpreter.code_interpreter_id)
pulumi.export("codeInterpreterArn", code_interpreter.code_interpreter_arn)
pulumi.export("memoryId", memory.id)
pulumi.export("memoryArn", memory.arn)
pulumi.export("logGroupName", agent_runtime_logs.name)
pulumi.export("logGroupArn", agent_runtime_logs.arn)
pulumi.export("logsDeliveryId", logs_log_delivery.id)
pulumi.export("tracesDeliveryId", traces_log_delivery.id)
pulumi.export(
    "testScriptCommand",
    pulumi.Output.concat(
        "python test_weather_agent.py ", weather_agent.agent_runtime_arn
    ),
)
