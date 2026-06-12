"""SigV4 signing for httpx, so A2A clients can call AgentCore-hosted agents.

AgentCore's data plane authenticates with AWS Signature Version 4, but
off-the-shelf A2A clients speak plain HTTP. This httpx.Auth implementation
signs each outgoing request with the caller's IAM credentials - the same
identity and permissions boto3 would use.

No SDK ships this glue yet; it follows the official AWS pattern from
github.com/strands-agents/samples (01-a2a-orchestration/utils/sigv4_auth.py).
Copy it as is.
"""

from typing import Generator

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials


class SigV4HTTPXAuth(httpx.Auth):
    """Sign httpx requests with AWS SigV4 for Amazon Bedrock AgentCore."""

    def __init__(self, credentials: Credentials, service: str, region: str):
        self.credentials = credentials
        self.service = service
        self.region = region

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        headers = dict(request.headers)

        # AgentCore excludes the connection header from its server-side
        # signature; signing it client-side causes SignatureDoesNotMatch.
        headers.pop("connection", None)

        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers=headers,
        )

        # Freeze credentials per request so IAM role auto-refresh keeps working.
        frozen_credentials = self.credentials.get_frozen_credentials()
        SigV4Auth(frozen_credentials, self.service, self.region).add_auth(aws_request)

        request.headers.update(dict(aws_request.headers))
        yield request
