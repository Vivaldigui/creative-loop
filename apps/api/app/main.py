from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import (
    analyses,
    approvals,
    assets,
    auth,
    brand,
    creatives,
    integrations,
    learnings,
    metrics,
    products,
    prompt_versions,
    prompts,
    publish,
    reports,
    source_ads,
    sync,
)
from app.routers.experiments import router as experiments_router
from app.routers.experiments import suggestions_router
from app.routers.publish import drafts_router

logger = structlog.get_logger()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Creative Loop API",
        description="AI-powered creative generation and ad management platform.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ─────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # ── Health endpoints ─────────────────────────────────────────
    @app.get("/healthz", tags=["Health"])
    async def healthz() -> dict:
        return {"status": "ok", "service": "creative-loop-api"}

    @app.get("/readyz", tags=["Health"])
    async def readyz() -> dict:
        from sqlalchemy import text

        from app.db import get_engine
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception as e:
            logger.error("readyz_db_fail", error=str(e))
            db_ok = False

        status = "ok" if db_ok else "degraded"
        return {"status": status, "db": db_ok}

    # ── Routers ──────────────────────────────────────────────────
    app.include_router(auth.router, prefix="/auth", tags=["Auth"])
    app.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])
    app.include_router(products.router, prefix="/products", tags=["Products"])
    app.include_router(brand.router, prefix="/brand", tags=["Brand"])
    app.include_router(source_ads.router, prefix="/source-ads", tags=["Source Ads"])
    app.include_router(analyses.router, prefix="/analyses", tags=["Analyses"])
    app.include_router(prompts.router, prefix="/prompts", tags=["Prompts"])
    app.include_router(prompt_versions.router, prefix="/prompt-versions", tags=["Prompt Versions"])
    app.include_router(creatives.router, prefix="/creatives", tags=["Creatives"])
    app.include_router(approvals.router, prefix="/approvals", tags=["Approvals"])
    app.include_router(assets.router, prefix="/assets", tags=["Assets"])
    app.include_router(publish.router, prefix="/publish", tags=["Publish"])
    # Phase 5: /publication-drafts/{id} and /publication-attempts/{id} at root
    app.include_router(drafts_router, prefix="", tags=["Publish"])
    app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
    app.include_router(sync.router, prefix="/sync", tags=["Sync"])
    # Phase 7: Experiments, Learnings, Reports
    app.include_router(experiments_router, prefix="/experiments", tags=["Experiments"])
    app.include_router(suggestions_router, prefix="", tags=["Suggestions"])
    app.include_router(learnings.router, prefix="/learnings", tags=["Learnings"])
    app.include_router(reports.router, prefix="/reports", tags=["Reports"])

    return app


app = create_app()
