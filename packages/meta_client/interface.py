from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Protocol


class MetaReadClient(Protocol):
    """
    Read-only interface for the Meta Marketing API.
    No write methods. Enforced at transport layer (GET-only).
    """

    async def validate_credentials(self) -> bool: ...
    async def health_check(self) -> bool: ...
    async def list_ad_accounts(self) -> list[dict[str, Any]]: ...

    def iter_campaigns(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]: ...

    def iter_adsets(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]: ...

    def iter_ads(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]: ...

    def iter_ad_images(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]: ...

    def iter_insights(
        self,
        account_id: str,
        level: str,
        date_start: str,
        date_stop: str,
        fields: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]: ...

    # Kept for publish router backwards-compatibility (Phase 1)
    async def publish_dry_run(self, payload: dict[str, Any]) -> dict[str, Any]: ...


# Backwards-compatible alias — existing code that imports MetaClientProtocol continues to work.
MetaClientProtocol = MetaReadClient


class MetaWriteClient(Protocol):
    """
    Write interface for the Meta Marketing API.
    NOT IMPLEMENTED until Phase 6.
    All methods in RealMetaWriteClient raise MetaPublishDisabledError.
    """

    async def create_campaign(self, account_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def create_adset(self, account_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def upload_image(self, account_id: str, image_bytes: bytes, filename: str) -> dict[str, Any]: ...
    async def create_ad_creative(self, account_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def create_ad(self, account_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def update_ad_status(self, ad_id: str, status: str) -> dict[str, Any]: ...
    async def update_budget(self, adset_id: str, daily_budget: int) -> dict[str, Any]: ...


class MetaPublisher(Protocol):
    """
    High-level publish orchestrator.
    In Phase 5, only DryRunPublisher implements this protocol.
    """

    async def publish(
        self,
        payload: MetaPublishPayload,  # type: ignore[name-defined]  # noqa: F821
        correlation_id: str | None = None,
    ) -> SimulatedPublishResponse: ...  # type: ignore[name-defined]  # noqa: F821
