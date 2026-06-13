"""Unit tests for packages.storage (local backend)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from packages.storage.local import LocalStorage
from packages.storage.paths import make_key, validate_key
from packages.storage.s3 import S3Storage

# ── path helpers ──────────────────────────────────────────────────


def test_make_key_includes_org_prefix():
    key = make_key("org-123", ".png")
    assert key.startswith("org-123/")
    assert key.endswith(".png")


def test_make_key_unknown_ext_becomes_bin():
    key = make_key("org-123", ".bmp")
    assert key.endswith(".bin")


def test_validate_key_accepts_valid():
    key = make_key("org-abc", ".png")
    assert validate_key("org-abc", key) is True


def test_validate_key_rejects_traversal():
    assert validate_key("org-abc", "org-abc/../secret.png") is False


def test_validate_key_rejects_wrong_org():
    key = make_key("org-abc", ".png")
    assert validate_key("org-xyz", key) is False


def test_validate_key_rejects_null_byte():
    assert validate_key("org-abc", "org-abc/\x00evil.png") is False


# ── LocalStorage ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_put_and_get(tmp_path):
    ls = LocalStorage(base_dir=str(tmp_path), secret_key="test-secret-32byteslong_padding!")
    data = b"hello world"
    key = make_key("org-1", ".png")
    obj = await ls.put("org-1", key, data, "image/png")
    assert obj.size == len(data)
    assert obj.backend == "local"

    got = await ls.get("org-1", key)
    assert got == data


@pytest.mark.asyncio
async def test_exists(tmp_path):
    ls = LocalStorage(base_dir=str(tmp_path), secret_key="test-secret-32byteslong_padding!")
    key = make_key("org-1", ".png")
    assert await ls.exists("org-1", key) is False
    await ls.put("org-1", key, b"data", "image/png")
    assert await ls.exists("org-1", key) is True


@pytest.mark.asyncio
async def test_delete(tmp_path):
    ls = LocalStorage(base_dir=str(tmp_path), secret_key="test-secret-32byteslong_padding!")
    key = make_key("org-1", ".png")
    await ls.put("org-1", key, b"data", "image/png")
    await ls.delete("org-1", key)
    assert await ls.exists("org-1", key) is False


def test_signed_url_format(tmp_path):
    ls = LocalStorage(base_dir=str(tmp_path), secret_key="test-secret-32byteslong_padding!")
    key = make_key("org-1", ".png")
    url = ls.signed_url("org-1", key, ttl=600)
    assert url.startswith("/assets/")


def test_signed_url_verify_roundtrip(tmp_path):
    ls = LocalStorage(base_dir=str(tmp_path), secret_key="test-secret-32byteslong_padding!")
    key = make_key("org-1", ".png")
    url = ls.signed_url("org-1", key, ttl=600)
    token = url.removeprefix("/assets/")
    claims = ls.verify_token(token)
    assert claims["org_id"] == "org-1"
    assert claims["key"] == key


def test_expired_token_rejected(tmp_path):
    ls = LocalStorage(base_dir=str(tmp_path), secret_key="test-secret-32byteslong_padding!")
    key = make_key("org-1", ".png")
    # ttl=-1 → already expired
    url = ls.signed_url("org-1", key, ttl=-1)
    token = url.removeprefix("/assets/")
    with pytest.raises(ValueError, match="expired"):
        ls.verify_token(token)


def test_tampered_token_rejected(tmp_path):
    ls = LocalStorage(base_dir=str(tmp_path), secret_key="test-secret-32byteslong_padding!")
    key = make_key("org-1", ".png")
    url = ls.signed_url("org-1", key, ttl=600)
    token = url.removeprefix("/assets/")
    # Corrupt last char
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(ValueError):
        ls.verify_token(tampered)


@pytest.mark.asyncio
async def test_put_rejects_unsafe_key(tmp_path):
    ls = LocalStorage(base_dir=str(tmp_path), secret_key="test-secret-32byteslong_padding!")
    with pytest.raises(ValueError):
        await ls.put("org-1", "org-2/../../etc/passwd", b"bad", "text/plain")


class FakeS3Client:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def get_object(self, *, Bucket, Key):
        class BodyReader:
            def __init__(self, data):
                self.data = data

            def read(self):
                return self.data

        return {"Body": BodyReader(self.objects[Key])}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        return f"https://storage.example/{Params['Key']}?ttl={ExpiresIn}"

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)

    def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            from botocore.exceptions import ClientError

            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}},
                "HeadObject",
            )
        return {"ContentLength": len(self.objects[Key])}


@pytest.mark.asyncio
async def test_s3_roundtrip_and_presigned_url():
    client = FakeS3Client()
    storage = S3Storage("", "bucket", "key", "secret", client=client)
    key = make_key("org-1", ".png")

    stored = await storage.put("org-1", key, b"image", "image/png")
    assert stored.backend == "s3"
    assert await storage.exists("org-1", key) is True
    assert await storage.get("org-1", key) == b"image"
    assert storage.signed_url("org-1", key, ttl=60).endswith("?ttl=60")

    await storage.delete("org-1", key)
    assert await storage.exists("org-1", key) is False


@pytest.mark.asyncio
async def test_s3_rejects_unsafe_key():
    storage = S3Storage("", "bucket", "key", "secret", client=FakeS3Client())
    with pytest.raises(ValueError):
        await storage.put("org-1", "org-2/../../secret", b"bad", "text/plain")
