"""
Publisher factory.

Phase 6 logic:
  - dry_run=True  → DryRunPublisher  (same as Phase 5, no network calls)
  - dry_run=False, write_enabled=True, provider="real"
                  → RealPublisher backed by RealMetaWriteClient
  - dry_run=False, write_enabled=True, provider="mock"
                  → RealPublisher backed by a mock httpx transport (integration tests)

The two-flag requirement (dry_run=False AND write_enabled=True) is enforced
by the guard layer BEFORE calling this factory.  The factory itself does not
re-validate guards; it only constructs the publisher.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .dry_run_publisher import DryRunPublisher

if TYPE_CHECKING:
    from .real_publisher import RealPublisher


def get_meta_publisher(
    *,
    dry_run: bool = True,
    write_enabled: bool = False,
    access_token: str = "",
    app_secret: str = "",
    api_version: str = "v21.0",
    max_retries: int = 3,
    timeout_s: float = 60.0,
    idempotency_tag: str = "",
) -> DryRunPublisher | RealPublisher:
    """
    Return the appropriate publisher.

    In dry_run mode, all arguments except dry_run are ignored.
    In real mode, access_token and app_secret must be non-empty.
    """
    if dry_run:
        return DryRunPublisher()

    if not write_enabled:
        raise ValueError(
            "get_meta_publisher called with dry_run=False but write_enabled=False. "
            "Both DRY_RUN=false and META_WRITE_ENABLED=true are required for real publishing."
        )

    if not access_token or not app_secret:
        raise ValueError(
            "Real Meta publish requires valid access_token and app_secret. "
            "Both must be non-empty strings."
        )

    from .real_publisher import RealPublisher
    from .write_client_real import RealMetaWriteClient

    client = RealMetaWriteClient(
        access_token=access_token,
        app_secret=app_secret,
        api_version=api_version,
        max_retries=max_retries,
        timeout_s=timeout_s,
    )
    return RealPublisher(client=client, idempotency_tag=idempotency_tag)
