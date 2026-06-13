from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/{provider}/test")
async def test_integration(
    provider: Literal["meta", "openai", "anthropic"],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    settings = get_settings()

    if provider == "meta":
        key = settings.meta_access_token
        prov = settings.meta_provider
        if key.startswith("PREENCHER_"):
            return {
                "provider": "meta",
                "status": "not_configured",
                "message": "Set META_ACCESS_TOKEN, META_APP_SECRET, and META_AD_ACCOUNT_ID in .env",
            }
        if prov == "mock":
            return {
                "provider": "meta",
                "status": "mock_ok",
                "message": "Mock provider active — no real API call made.",
                "required_scopes": ["ads_read"],
                "note": "Set META_PROVIDER=real and supply credentials to use the real API.",
            }
        from packages.meta_client.factory import get_meta_client
        client = get_meta_client(prov)
        ok = await client.validate_credentials()
        return {
            "provider": "meta",
            "status": "ok" if ok else "error",
            "required_scopes": ["ads_read"],
        }

    if provider == "anthropic":
        key = settings.anthropic_api_key
        prov = settings.anthropic_provider
        if key.startswith("PREENCHER_"):
            return {"provider": "anthropic", "status": "not_configured",
                    "message": "Set ANTHROPIC_API_KEY in .env"}
        if prov == "mock":
            return {"provider": "anthropic", "status": "mock_ok",
                    "message": "Mock provider active — no real API call made."}
        from packages.anthropic_client.factory import get_anthropic_client
        client = get_anthropic_client(prov)
        ok = await client.health_check()
        return {"provider": "anthropic", "status": "ok" if ok else "error"}

    if provider == "openai":
        key = settings.openai_api_key
        prov = settings.image_provider
        if key.startswith("PREENCHER_"):
            return {"provider": "openai", "status": "not_configured",
                    "message": "Set OPENAI_API_KEY in .env"}
        if prov == "mock":
            return {"provider": "openai", "status": "mock_ok",
                    "message": "Mock provider active — no real API call made."}
        from packages.openai_image_client.factory import get_image_client
        client = get_image_client(prov)
        ok = await client.health_check()
        return {"provider": "openai", "status": "ok" if ok else "error"}

    return {"provider": provider, "status": "unknown"}


@router.get("/meta/accounts")
async def list_meta_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """List ad accounts accessible with the configured Meta token. Read-only."""
    settings = get_settings()
    if settings.meta_access_token.startswith("PREENCHER_"):
        return {
            "accounts": [],
            "status": "not_configured",
            "message": "Set META_ACCESS_TOKEN in .env",
        }
    from packages.meta_client.factory import get_meta_client
    client = get_meta_client(settings.meta_provider)
    accounts = await client.list_ad_accounts()
    return {
        "accounts": accounts,
        "status": "mock" if settings.meta_provider == "mock" else "real",
        "count": len(accounts),
    }
