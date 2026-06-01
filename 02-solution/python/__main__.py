"""Module 2 - Deploy your first agent (direct code / ZIP deployment).

Ships the same agent you ran locally in Module 1 to Amazon Bedrock AgentCore
using AgentCore's direct code deployment - a .zip of the agent and its
dependencies instead of a Docker image.

Deploy with a single command:

    pulumi up

The packaging build (build.sh, which installs ARM64 deps into build/) runs
automatically as part of `pulumi up` via a command.local.Command resource.
"""

import hashlib
import os

import pulumi
import pulumi_aws as aws
import pulumi_command as command

config = pulumi.Config()
agent_name = config.get("agentName") or "BasicAgent"
stack_name = config.get("stackName") or "agentcore-basic"
runtime_version = config.get("runtime") or "PYTHON_3_13"

aws_config = pulumi.Config("aws")
aws_region = aws_config.require("region")

current_identity = aws.get_caller_identity_output()
current_region = aws.get_region_output()

here = os.path.dirname(__file__)
agent_code_dir = os.path.join(here, "agent-code")
build_dir = os.path.join(here, "build")


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# Hash of the inputs that should trigger a repackage: the agent and its deps.
source_hash = hashlib.sha256(
    (
        _sha256(os.path.join(agent_code_dir, "basic_agent.py"))
        + _sha256(os.path.join(agent_code_dir, "requirements.txt"))
    ).encode()
).hexdigest()

# --- Build the ARM64 deployment package during `pulumi up` ---
# build.sh installs Linux ARM64 wheels into build/ and copies the agent in.
# triggers means it only re-runs when the agent or its deps change.
build = command.local.Command(
    "build_package",
    create=f"bash {os.path.join(here, 'build.sh')}",
    dir=here,
    triggers=[source_hash],
)

# --- S3 bucket holding the zipped agent package ---
code_bucket = aws.s3.Bucket(
    "agent_code",
    bucket_prefix=f"{stack_name}-code-",
    force_destroy=True,
)

aws.s3.BucketPublicAccessBlock(
    "agent_code",
    bucket=code_bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

aws.s3.BucketVersioning(
    "agent_code",
    bucket=code_bucket.id,
    versioning_configuration={"status": "Enabled"},
)

# Pulumi zips build/ (produced by the build command above) and uploads it.
code_object = aws.s3.BucketObjectv2(
    "agent_code",
    bucket=code_bucket.id,
    key="agent-code.zip",
    source=pulumi.FileArchive(build_dir),
    opts=pulumi.ResourceOptions(depends_on=[build]),
)

# --- IAM execution role ---
agent_execution = aws.iam.Role(
    "agent_execution",
    name=f"{stack_name}-agent-execution-role",
    assume_role_policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
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
                                lambda a: f"arn:aws:bedrock-agentcore:{a[0].region}:{a[1].account_id}:*"
                            ),
                        },
                    },
                }
            ],
        }
    ),
)

aws.iam.RolePolicyAttachment(
    "agent_execution_managed",
    role=agent_execution.name,
    policy_arn="arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess",
)

agent_execution_policy = aws.iam.RolePolicy(
    "agent_execution",
    name="AgentCoreExecutionPolicy",
    role=agent_execution.id,
    policy=pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "S3CodeAccess",
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                    "Resource": pulumi.Output.concat(code_bucket.arn, "/*"),
                },
                {
                    "Sid": "CloudWatchLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogStreams",
                        "logs:DescribeLogGroups",
                    ],
                    "Resource": pulumi.Output.all(
                        current_region, current_identity
                    ).apply(
                        lambda a: f"arn:aws:logs:{a[0].region}:{a[1].account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
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
                            lambda a: f"arn:aws:bedrock-agentcore:{a[0].region}:{a[1].account_id}:workload-identity-directory/default"
                        ),
                        pulumi.Output.all(current_region, current_identity).apply(
                            lambda a: f"arn:aws:bedrock-agentcore:{a[0].region}:{a[1].account_id}:workload-identity-directory/default/workload-identity/*"
                        ),
                    ],
                },
            ],
        }
    ),
)

# --- AgentCore Runtime (direct code) ---
runtime_name = f"{stack_name}_{agent_name}".replace("-", "_")

basic_agent = aws.bedrock.AgentcoreAgentRuntime(
    "basic_agent",
    agent_runtime_name=runtime_name,
    role_arn=agent_execution.arn,
    agent_runtime_artifact={
        "code_configuration": {
            "entry_points": ["basic_agent.py"],
            "runtime": runtime_version,
            "code": {
                "s3": {
                    "bucket": code_bucket.id,
                    "prefix": code_object.key,
                    "version_id": code_object.version_id,  # redeploy on change
                },
            },
        },
    },
    network_configuration={"network_mode": "PUBLIC"},
    environment_variables={
        "AWS_REGION": aws_region,
        "AWS_DEFAULT_REGION": aws_region,
    },
    opts=pulumi.ResourceOptions(depends_on=[agent_execution_policy]),
)

pulumi.export("agentRuntimeArn", basic_agent.agent_runtime_arn)
pulumi.export("agentRuntimeId", basic_agent.agent_runtime_id)
