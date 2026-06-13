"""S3-compatible storage backend for AWS S3, Cloudflare R2, and similar services."""

from __future__ import annotations

import hashlib
from functools import partial
from typing import Any

import boto3
import structlog
from anyio import to_thread
from botocore.exceptions import ClientError

from .interface import StoredObject
from .paths import validate_key

logger = structlog.get_logger()


class S3Storage:
    """S3-compatible object storage with presigned download URLs."""

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "auto",
        *,
        client: Any | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = client or boto3.client(
            "s3",
            endpoint_url=endpoint or None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    @staticmethod
    def _validate(org_id: str, key: str) -> None:
        if not validate_key(org_id, key):
            raise ValueError(f"Unsafe storage key rejected: {key!r}")

    async def put(
        self, org_id: str, key: str, data: bytes, content_type: str
    ) -> StoredObject:
        self._validate(org_id, key)
        await to_thread.run_sync(
            partial(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        )
        digest = hashlib.sha256(data).hexdigest()
        logger.debug("storage_put", backend="s3", key=key, size=len(data))
        return StoredObject(
            key=key,
            size=len(data),
            content_type=content_type,
            hash=digest,
            backend="s3",
        )

    async def get(self, org_id: str, key: str) -> bytes:
        self._validate(org_id, key)

        def read_object() -> bytes:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()

        return await to_thread.run_sync(read_object)

    def signed_url(self, org_id: str, key: str, ttl: int = 600) -> str:
        self._validate(org_id, key)
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl,
        )

    async def delete(self, org_id: str, key: str) -> None:
        self._validate(org_id, key)
        await to_thread.run_sync(
            partial(self._client.delete_object, Bucket=self._bucket, Key=key)
        )
        logger.debug("storage_delete", backend="s3", key=key)

    async def exists(self, org_id: str, key: str) -> bool:
        if not validate_key(org_id, key):
            return False
        try:
            await to_thread.run_sync(
                partial(self._client.head_object, Bucket=self._bucket, Key=key)
            )
            return True
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def local_path(self, org_id: str, key: str) -> str | None:
        return None
