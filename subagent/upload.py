from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
import logfire
from botocore.client import BaseClient
from pydantic import BaseModel, Field
from pydantic_ai import Agent, FunctionToolset, ModelSettings, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from config.settings import setting,model


@dataclass(slots=True)
class R2Storage:
    access_key: str
    secret_key: str
    endpoint_url: str
    bucket: str
    public_url: str

    client: BaseClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.client = boto3.client(
            service_name="s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="auto",
        )

    def upload(
        self,
        file_path: str,
        *,
        key: str | None = None,
    ) -> str:

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(path)

        content_type, _ = mimetypes.guess_type(path)

        extra_args = {}

        if content_type:
            extra_args["ContentType"] = content_type

        if key is None:
            key = f"uploads/{uuid4()}{path.suffix}"

        logfire.info(
            "Uploading file to Cloudflare R2",
            bucket=self.bucket,
            key=key,
            file=str(path),
        )

        self.client.upload_file(
            Filename=str(path),
            Bucket=self.bucket,
            Key=key,
            ExtraArgs=extra_args,
        )

        url = f"{self.public_url}/{key}"

        logfire.info(
            "Upload successful",
            url=url,
        )

        return url



class UploadFileRequest(BaseModel):
    file_path: str = Field(
        description="Absolute path of the local file to upload."
    )

class SubagentResponse(BaseModel):
    success:bool = Field(...,description="whether document uploaded successfully or not")
    message:str = Field(...,description="success or failure message")
    url:str =Field(...,description="document url if uploaded successfully else empty string")


utilities_toolset = FunctionToolset[R2Storage]()


@utilities_toolset.tool
async def upload_file_to_r2(
    ctx: RunContext[Any],
    request: UploadFileRequest,
) -> str:
    """
    Upload a local file to Cloudflare R2.

    Returns the public URL.
    """

    storage = ctx.deps.r2_storage

    return storage.upload(request.file_path)


document_upload_agent = Agent[R2Storage,SubagentResponse](
    model,
    name="document_upload_agent",
    description="subagent for uploading all types of document and media to R2 cloud storage",
    deps_type=R2Storage,
    output_type=SubagentResponse,
    toolsets=[utilities_toolset],
    instructions="""
        You are an upload agent that uploads local files to Cloudflare R2 cloud storage.

        1. Call 'upload_file_to_r2' providing the absolute file_path of the local file.
        2. Take the exact public URL returned by the 'upload_file_to_r2' tool call and return it in your SubagentResponse `url` field.
        3. Set `success=True` and provide a descriptive `message`.
        """
)