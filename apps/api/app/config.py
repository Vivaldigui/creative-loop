from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    candidates = [Path.cwd(), *Path(__file__).resolve().parents[:4]]
    for directory in candidates:
        env_file = directory / ".env"
        if env_file.is_file():
            return str(env_file)
    return ".env"


ENV_FILE = _find_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────
    app_base_url: str = "http://localhost:8000"
    app_env: Literal["development", "staging", "production"] = "development"

    # ── Security ─────────────────────────────────────────────────
    secret_key: str = "PREENCHER_SECRET_KEY"
    encryption_key: str = "PREENCHER_ENCRYPTION_KEY"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./creative_loop.db"
    database_driver: Literal["postgres", "sqlite"] = "sqlite"

    # ── Redis ────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Celery ───────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Providers (mock | real) ───────────────────────────────────
    anthropic_provider: Literal["mock", "real"] = "mock"
    image_provider: Literal["mock", "openai"] = "mock"
    meta_provider: Literal["mock", "real"] = "mock"
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: str = "./storage"

    # ── External APIs (filled by user) ───────────────────────────
    anthropic_api_key: str = "PREENCHER_ANTHROPIC_API_KEY"
    anthropic_model: str = "claude-sonnet-4-6"
    # Phase 3 — analysis tuning
    anthropic_timeout_s: float = 60.0
    anthropic_max_retries: int = 3
    anthropic_max_image_mb: float = 5.0
    anthropic_max_tokens: int = 2048
    anthropic_temperature: float = 0.3
    # Override pricing (USD per million tokens); leave empty to use built-in table
    anthropic_price_input_per_mtok: float | None = None
    anthropic_price_output_per_mtok: float | None = None
    openai_api_key: str = "PREENCHER_OPENAI_API_KEY"
    openai_image_model: str = "gpt-image-2"
    # Phase 4 — image generation tuning
    openai_timeout_s: float = 90.0
    openai_max_retries: int = 3
    openai_image_quality: str = "standard"
    image_max_variations: int = 4
    creative_similarity_threshold: int = 6  # pHash Hamming distance for WARNING
    creative_max_file_mb: float = 15.0
    thumbnail_max_px: int = 512
    signed_url_ttl_seconds: int = 600
    quality_cv_enabled: bool = True  # enable Pillow-based CV checks
    quality_ai_enabled: bool = False  # AI vision checks (opt-in, has cost)
    allow_blocked_override: bool = False  # owner can override BLOCKED (disabled by default)
    meta_app_id: str = "PREENCHER_META_APP_ID"
    meta_app_secret: str = "PREENCHER_META_APP_SECRET"
    meta_access_token: str = "PREENCHER_META_ACCESS_TOKEN"
    meta_graph_api_version: str = "v21.0"
    meta_ad_account_id: str = "PREENCHER_META_AD_ACCOUNT_ID"
    meta_business_id: str = "PREENCHER_META_BUSINESS_ID"
    meta_page_id: str = "PREENCHER_META_PAGE_ID"
    meta_instagram_actor_id: str = "PREENCHER_META_INSTAGRAM_ACTOR_ID"
    meta_pixel_id: str = "PREENCHER_META_PIXEL_ID"
    # Phase 2 — import tuning
    meta_page_limit: int = 200
    meta_max_retries: int = 5
    meta_rate_limit_threshold: int = 85
    meta_sync_incremental_days: int = 30
    meta_sync_history_date_start: str = "2024-01-01"

    # ── S3 ────────────────────────────────────────────────────────
    s3_endpoint: str = "PREENCHER_S3_ENDPOINT"
    s3_bucket: str = "PREENCHER_S3_BUCKET"
    s3_access_key: str = "PREENCHER_S3_ACCESS_KEY"
    s3_secret_key: str = "PREENCHER_S3_SECRET_KEY"
    s3_region: str = "auto"

    # ── Safety Guards ─────────────────────────────────────────────
    dry_run: bool = True
    require_human_approval: bool = True
    max_daily_new_ads: int = 3
    max_daily_spend: float | None = None
    max_experiment_budget: float | None = None
    max_automatic_budget_increase_percent: int = 0

    # ── Phase 5 — DRY_RUN publish ─────────────────────────────────
    publication_idempotency_ttl_hours: int = 24

    # ── Phase 6 — Real Meta publish ───────────────────────────────
    # Master write switch — BOTH dry_run=false AND meta_write_enabled=true required.
    meta_write_enabled: bool = False
    # Max retries for safe/idempotent write operations (status check, image upload, pause)
    meta_write_max_retries: int = 3
    meta_write_timeout_s: float = 60.0
    # Require elevated role (owner) specifically for activation
    meta_require_elevated_for_activation: bool = True
    # Require explicit confirmation body field for activation
    meta_activation_require_confirmation: bool = True
    # Enables live-test procedure (opt-in, manual only, never automated)
    meta_live_test_enabled: bool = False
    # Days before token expiry to emit a warning
    credential_rotation_warn_days: int = 30

    # ── Phase 7 — Experiment engine defaults ──────────────────────
    # Default minimum criteria for experiments (overridable per-experiment via min_criteria JSON)
    exp_default_min_spend: float = 50.0
    exp_default_min_impressions: int = 1000
    exp_default_min_clicks: int = 50
    exp_default_min_conversions: int = 0
    exp_default_min_days: int = 3
    exp_default_min_difference: float = 0.10
    exp_default_min_confidence: float = 0.80
    exp_default_max_frequency: float = 4.0
    exp_default_maturation_window_days: int = 3
    # Learning retrieval
    exp_retrieval_max_results: int = 10
    # Diversity penalties
    exp_max_variation_depth: int = 3
    exp_max_learning_reuse: int = 3
    # Embeddings provider: mock | real
    embedding_provider: str = "mock"
    # Reports
    daily_report_hour: int = 8  # BRT (America/Sao_Paulo)
    weekly_report_day: int = 0  # Monday
    # Anomalous spend threshold (multiplier of rolling median)
    anomalous_spend_multiplier: float = 3.0

    # ── Locale ───────────────────────────────────────────────────
    default_currency: str = "BRL"
    default_timezone: str = "America/Sao_Paulo"

    # ── CORS ─────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000"

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_not_be_placeholder(cls, v: str) -> str:
        if v.startswith("PREENCHER_"):
            import warnings

            warnings.warn(
                "SECRET_KEY is a placeholder. Generate a real key with: python scripts/gen_keys.py",
                stacklevel=2,
            )
        return v

    @field_validator("database_url")
    @classmethod
    def resolve_relative_sqlite_path(cls, v: str) -> str:
        prefix = "sqlite+aiosqlite:///./"
        if not v.startswith(prefix):
            return v
        base_dir = Path(ENV_FILE).resolve().parent if Path(ENV_FILE).is_file() else Path.cwd()
        database_path = (base_dir / v.removeprefix(prefix)).resolve().as_posix()
        return f"sqlite+aiosqlite:///{database_path}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_postgres(self) -> bool:
        return self.database_driver == "postgres"


@lru_cache
def get_settings() -> Settings:
    return Settings()
