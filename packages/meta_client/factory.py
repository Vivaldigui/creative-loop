from __future__ import annotations

from .interface import MetaClientProtocol
from .mock import MockMetaClient


def get_meta_client(provider: str = "mock") -> MetaClientProtocol:
    if provider == "real":
        from app.config import get_settings

        from .real import RealMetaClient

        s = get_settings()
        return RealMetaClient(
            access_token=s.meta_access_token,
            app_secret=s.meta_app_secret,
            api_version=s.meta_graph_api_version,
            page_limit=s.meta_page_limit,
            max_retries=s.meta_max_retries,
            rate_limit_threshold=s.meta_rate_limit_threshold,
        )
    return MockMetaClient()
