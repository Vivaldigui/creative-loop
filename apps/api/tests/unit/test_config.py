from app.config import Settings


def test_neon_database_url_is_normalized_for_asyncpg() -> None:
    settings = Settings(
        database_url=(
            "postgresql://user:password@example.neon.tech/neondb"
            "?sslmode=require&channel_binding=require"
        )
    )

    assert settings.database_url == (
        "postgresql+asyncpg://user:password@example.neon.tech/neondb?ssl=require"
    )


def test_asyncpg_database_url_is_kept_unchanged() -> None:
    url = "postgresql+asyncpg://user:password@example.neon.tech/neondb?ssl=require"

    assert Settings(database_url=url).database_url == url
