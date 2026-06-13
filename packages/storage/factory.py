from __future__ import annotations

from .interface import StorageBackend


def get_storage(
    backend: str = "local",
    *,
    base_dir: str = "./storage",
    secret_key: str = "",
    s3_endpoint: str = "",
    s3_bucket: str = "",
    s3_access_key: str = "",
    s3_secret_key: str = "",
    s3_region: str = "auto",
) -> StorageBackend:
    if backend == "local":
        from .local import LocalStorage

        return LocalStorage(base_dir=base_dir, secret_key=secret_key)
    if backend == "s3":
        from .s3 import S3Storage

        return S3Storage(
            endpoint=s3_endpoint,
            bucket=s3_bucket,
            access_key=s3_access_key,
            secret_key=s3_secret_key,
            region=s3_region,
        )
    raise ValueError(f"Unknown storage backend: {backend!r}. Choose 'local' or 's3'.")
