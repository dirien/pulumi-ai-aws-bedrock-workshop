import hashlib
import json
import os

import pulumi
import pulumi_aws as aws

# ============================================================================
# Configuration
# ============================================================================

config = pulumi.Config()
orchestrator_name = config.get("orchestratorName") or "OrchestratorAgent"
specialist_name = config.get("specialistName") or "SpecialistAgent"
network_mode = config.get("networkMode") or "PUBLIC"
image_tag = config.get("imageTag") or "latest"
stack_name = config.get("stackName") or "agentcore-multi-agent"
ecr_repository_name = config.get("ecrRepositoryName") or "multi-agent"

aws_config = pulumi.Config("aws")
aws_region = aws_config.require("region")

# ============================================================================
# Data Sources
# ============================================================================

current_identity = aws.get_caller_identity_output()
current_region = aws.get_region_output()

# ============================================================================
# S3 Buckets for Agent Source Code
# ============================================================================

orchestrator_source_bucket = aws.s3.Bucket(
    "orchestrator_source",
    bucket_prefix=f"{stack_name}-orch-src-",
    force_destroy=True,
    tags={
        "Name": f"{stack_name}-orchestrator-source",
        "Purpose": "Store Orchestrator agent source code for CodeBuild",
    },
)

specialist_source_bucket = aws.s3.Bucket(
    "specialist_source",
    bucket_prefix=f"{stack_name}-spec-src-",
    force_destroy=True,
    tags={
        "Name": f"{stack_name}-specialist-source",
        "Purpose": "Store Specialist agent source code for CodeBuild",
    },
)

aws.s3.BucketPublicAccessBlock(
    "orchestrator_source",
    bucket=orchestrator_source_bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

aws.s3.BucketPublicAccessBlock(
    "specialist_source",
    bucket=specialist_source_bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

aws.s3.BucketVersioning(
    "orchestrator_source",
    bucket=orchestrator_source_bucket.id,
    versioning_configuration={"status": "Enabled"},
)

aws.s3.BucketVersioning(
    "specialist_source",
    bucket=specialist_source_bucket.id,
    versioning_configuration={"status": "Enabled"},
)

# ============================================================================
# Upload Agent Source Code to S3
# ============================================================================

orchestrator_source_object = aws.s3.BucketObjectv2(
    "orchestrator_source",
    bucket=orchestrator_source_bucket.id,
    key="agent-orchestrator-code.zip",
    source=pulumi.FileArchive(
        os.path.join(os.path.dirname(__file__), "agent-orchestrator-code")
    ),
    tags={"Name": "agent-orchestrator-source-code"},
)

specialist_source_object = aws.s3.BucketObjectv2(
    "specialist_source",
    bucket=specialist_source_bucket.id,
    key="agent-specialist-code.zip",
    source=pulumi.FileArchive(
        os.path.join(os.path.dirname(__file__), "agent-specialist-code")
    ),
    tags={"Name": "agent-specialist-source-code"},
)

# ============================================================================
# ECR Repositories - Container Registries for Agent Images
# ============================================================================

orchestrator_ecr = aws.ecr.Repository(
    "orchestrator",
    name=f"{stack_name}-{ecr_repository_name}-orchestrator",
    image_tag_mutability="MUTABLE",
    image_scanning_configuration={"scan_on_push": True},
    force_delete=True,
    tags={
        "Name": f"{stack_name}-orchestrator-ecr-repository",
        "Module": "ECR",
    },
)

specialist_ecr = aws.ecr.Repository(
    "specialist",
    name=f"{stack_name}-{ecr_repository_name}-specialist",
    image_tag_mutability="MUTABLE",
    image_scanning_configuration={"scan_on_push": True},
    force_delete=True,
    tags={
        "Name": f"{stack_name}-specialist-ecr-repository",
        "Module": "ECR",
    },
)

aws.ecr.RepositoryPolicy(
    "orchestrator",
    repository=orchestrator_ecr.name,
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

aws.ecr.RepositoryPolicy(
    "specialist",
    repository=specialist_ecr.name,
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
    "orchestrator",
    repository=orchestrator_ecr.name,
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

aws.ecr.LifecyclePolicy(
    "specialist",
    repository=specialist_ecr.name,
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
# Orchestrator Agent Execution Role - For AgentCore Runtime
# ============================================================================

orchestrator_execution = aws.iam.Role(
    "orchestrator_execution",
    name=f"{stack_name}-orchestrator-execution-role",
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
        "Name": f"{stack_name}-orchestrator-execution-role",
        "Module": "IAM",
    },
)

orchestrator_execution_role_policy = aws.iam.RolePolicy(
    "orchestrator_execution",
    name="OrchestratorCoreExecutionPolicy",
    role=orchestrator_execution.id,
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
                    "Resource": orchestrator_ecr.arn,
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
# Orchestrator A2A Policy - Allows Orchestrator to Invoke Specialist
# ============================================================================

orchestrator_invoke_specialist = aws.iam.RolePolicy(
    "orchestrator_invoke_specialist",
    name="OrchestratorInvokeSpecialistPolicy",
    role=orchestrator_execution.id,
    policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "InvokeSpecialistRuntime",
                    "Effect": "Allow",
                    # InvokeAgentRuntime carries the A2A messages; GetAgentCard
                    # lets the A2A client discover the specialist's card first.
                    "Action": [
                        "bedrock-agentcore:InvokeAgentRuntime",
                        "bedrock-agentcore:GetAgentCard",
                    ],
                    "Resource": pulumi.Output.all(
                        current_region, current_identity
                    ).apply(
                        lambda args: f"arn:aws:bedrock-agentcore:{args[0].region}:{args[1].account_id}:runtime/*"
                    ),
                }
            ],
        }
    ),
)

# ============================================================================
# Specialist Agent Execution Role - For AgentCore Runtime
# ============================================================================

specialist_execution = aws.iam.Role(
    "specialist_execution",
    name=f"{stack_name}-specialist-execution-role",
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
        "Name": f"{stack_name}-specialist-execution-role",
        "Module": "IAM",
    },
)

specialist_execution_role_policy = aws.iam.RolePolicy(
    "specialist_execution",
    name="SpecialistCoreExecutionPolicy",
    role=specialist_execution.id,
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
                    "Resource": specialist_ecr.arn,
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
# CodeBuild Service Role - For Docker Image Building (Both Agents)
# ============================================================================

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
                    "Resource": [orchestrator_ecr.arn, specialist_ecr.arn, "*"],
                },
                {
                    "Sid": "S3SourceAccess",
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                    "Resource": [
                        pulumi.Output.concat(
                            orchestrator_source_bucket.arn, "/*"
                        ),
                        pulumi.Output.concat(
                            specialist_source_bucket.arn, "/*"
                        ),
                    ],
                },
                {
                    "Sid": "S3BucketAccess",
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
                    "Resource": [
                        orchestrator_source_bucket.arn,
                        specialist_source_bucket.arn,
                    ],
                },
            ],
        }
    ),
)

# ============================================================================
# Build Trigger Lambda - Start and Wait for CodeBuild
# ============================================================================

orchestrator_project_name = f"{stack_name}-orchestrator-build"
specialist_project_name = f"{stack_name}-specialist-build"

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
                                "Resource": [
                                    f"arn:aws:codebuild:{args[0].region}:{args[1].account_id}:project/{orchestrator_project_name}",
                                    f"arn:aws:codebuild:{args[0].region}:{args[1].account_id}:project/{specialist_project_name}",
                                ],
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
# CodeBuild Projects - Build and Push Docker Images
# ============================================================================

orchestrator_buildspec_path = os.path.join(
    os.path.dirname(__file__), "buildspec-orchestrator.yml"
)
with open(orchestrator_buildspec_path) as f:
    orchestrator_buildspec_content = f.read()
orchestrator_buildspec_fingerprint = hashlib.sha256(
    orchestrator_buildspec_content.encode()
).hexdigest()

specialist_buildspec_path = os.path.join(
    os.path.dirname(__file__), "buildspec-specialist.yml"
)
with open(specialist_buildspec_path) as f:
    specialist_buildspec_content = f.read()
specialist_buildspec_fingerprint = hashlib.sha256(
    specialist_buildspec_content.encode()
).hexdigest()

orchestrator_image = aws.codebuild.Project(
    "orchestrator_image",
    name=orchestrator_project_name,
    description=f"Build Orchestrator agent Docker image for {stack_name}",
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
            {"name": "IMAGE_REPO_NAME", "value": orchestrator_ecr.name},
            {"name": "IMAGE_TAG", "value": image_tag},
            {"name": "STACK_NAME", "value": stack_name},
        ],
    },
    source={
        "type": "S3",
        "location": pulumi.Output.concat(
            orchestrator_source_bucket.id, "/", orchestrator_source_object.key
        ),
        "buildspec": orchestrator_buildspec_content,
    },
    logs_config={
        "cloudwatch_logs": {
            "group_name": f"/aws/codebuild/{orchestrator_project_name}",
        }
    },
    tags={
        "Name": f"{stack_name}-orchestrator-build",
        "Module": "CodeBuild",
    },
)

specialist_image = aws.codebuild.Project(
    "specialist_image",
    name=specialist_project_name,
    description=f"Build Specialist agent Docker image for {stack_name}",
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
            {"name": "IMAGE_REPO_NAME", "value": specialist_ecr.name},
            {"name": "IMAGE_TAG", "value": image_tag},
            {"name": "STACK_NAME", "value": stack_name},
        ],
    },
    source={
        "type": "S3",
        "location": pulumi.Output.concat(
            specialist_source_bucket.id, "/", specialist_source_object.key
        ),
        "buildspec": specialist_buildspec_content,
    },
    logs_config={
        "cloudwatch_logs": {
            "group_name": f"/aws/codebuild/{specialist_project_name}",
        }
    },
    tags={
        "Name": f"{stack_name}-specialist-build",
        "Module": "CodeBuild",
    },
)

# ============================================================================
# Trigger CodeBuild - Sequential Build Process
# Specialist builds first (independent), then Orchestrator
# ============================================================================

trigger_build_specialist = aws.lambda_.Invocation(
    "trigger_build_specialist",
    function_name=build_trigger_function.name,
    input=pulumi.Output.all(specialist_image.name, current_region).apply(
        lambda args: json.dumps(
            {
                "projectName": args[0],
                "region": args[1].region,
                "pollIntervalSeconds": 15,
            }
        )
    ),
    triggers={
        "sourceVersion": specialist_source_object.version_id,
        "imageTag": image_tag,
        "buildspecSha256": specialist_buildspec_fingerprint,
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            specialist_image,
            specialist_ecr,
            codebuild_role_policy,
            specialist_source_object,
            build_trigger_basic_execution,
            build_trigger_function,
        ]
    ),
)

trigger_build_orchestrator = aws.lambda_.Invocation(
    "trigger_build_orchestrator",
    function_name=build_trigger_function.name,
    input=pulumi.Output.all(orchestrator_image.name, current_region).apply(
        lambda args: json.dumps(
            {
                "projectName": args[0],
                "region": args[1].region,
                "pollIntervalSeconds": 15,
            }
        )
    ),
    triggers={
        "sourceVersion": orchestrator_source_object.version_id,
        "imageTag": image_tag,
        "buildspecSha256": orchestrator_buildspec_fingerprint,
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            orchestrator_image,
            orchestrator_ecr,
            codebuild_role_policy,
            orchestrator_source_object,
            build_trigger_basic_execution,
            build_trigger_function,
            trigger_build_specialist,
        ]
    ),
)

# ============================================================================
# Specialist Agent Runtime - Independent Agent
# ============================================================================

specialist_source_hash = specialist_source_object.version_id.apply(
    lambda v: v if v else "initial"
)
orchestrator_source_hash = orchestrator_source_object.version_id.apply(
    lambda v: v if v else "initial"
)

specialist_runtime_name = f"{stack_name}_{specialist_name}".replace("-", "_")

specialist_agent = aws.bedrock.AgentcoreAgentRuntime(
    "specialist",
    agent_runtime_name=specialist_runtime_name,
    description=f"Specialist agent runtime for {stack_name}",
    role_arn=specialist_execution.arn,
    agent_runtime_artifact={
        "container_configuration": {
            "container_uri": pulumi.Output.concat(
                specialist_ecr.repository_url, ":", image_tag
            ),
        }
    },
    # The specialist speaks the A2A protocol (JSON-RPC on port 9000)
    # instead of the default HTTP contract on port 8080.
    protocol_configuration={"server_protocol": "A2A"},
    network_configuration={"network_mode": network_mode},
    environment_variables={
        "AWS_REGION": aws_region,
        "AWS_DEFAULT_REGION": aws_region,
        "SOURCE_VERSION": specialist_source_hash,
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            trigger_build_specialist,
            specialist_execution_role_policy,
        ]
    ),
)

# ============================================================================
# Orchestrator Agent Runtime - Depends on Specialist Agent
# ============================================================================

orchestrator_runtime_name = f"{stack_name}_{orchestrator_name}".replace("-", "_")

orchestrator_agent = aws.bedrock.AgentcoreAgentRuntime(
    "orchestrator",
    agent_runtime_name=orchestrator_runtime_name,
    description=f"Orchestrator agent runtime for {stack_name}",
    role_arn=orchestrator_execution.arn,
    agent_runtime_artifact={
        "container_configuration": {
            "container_uri": pulumi.Output.concat(
                orchestrator_ecr.repository_url, ":", image_tag
            ),
        }
    },
    network_configuration={"network_mode": network_mode},
    environment_variables={
        "AWS_REGION": aws_region,
        "AWS_DEFAULT_REGION": aws_region,
        "SPECIALIST_ARN": specialist_agent.agent_runtime_arn,
        "SOURCE_VERSION": orchestrator_source_hash,
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            specialist_agent,
            trigger_build_orchestrator,
            orchestrator_execution_role_policy,
            orchestrator_invoke_specialist,
        ]
    ),
)

# ============================================================================
# Outputs
# ============================================================================

pulumi.export("orchestratorRuntimeId", orchestrator_agent.agent_runtime_id)
pulumi.export("orchestratorRuntimeArn", orchestrator_agent.agent_runtime_arn)
pulumi.export("orchestratorRuntimeVersion", orchestrator_agent.agent_runtime_version)
pulumi.export("orchestratorEcrRepositoryUrl", orchestrator_ecr.repository_url)
pulumi.export("orchestratorExecutionRoleArn", orchestrator_execution.arn)

pulumi.export("specialistRuntimeId", specialist_agent.agent_runtime_id)
pulumi.export("specialistRuntimeArn", specialist_agent.agent_runtime_arn)
pulumi.export("specialistRuntimeVersion", specialist_agent.agent_runtime_version)
pulumi.export("specialistEcrRepositoryUrl", specialist_ecr.repository_url)
pulumi.export("specialistExecutionRoleArn", specialist_execution.arn)

pulumi.export("orchestratorCodebuildProjectName", orchestrator_image.name)
pulumi.export("specialistCodebuildProjectName", specialist_image.name)
pulumi.export("orchestratorSourceBucketName", orchestrator_source_bucket.id)
pulumi.export("specialistSourceBucketName", specialist_source_bucket.id)

pulumi.export(
    "testScriptCommand",
    pulumi.Output.concat(
        "python test_multi_agent.py ", orchestrator_agent.agent_runtime_arn
    ),
)
