from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Centraliza as configuracoes da aplicacao lidas do ambiente."""
    openai_api_key: str
    app_api_key: str | None = None

    openai_chat_model: str = "gpt-4o-mini"
    openai_chat_temperature: float = 1
    openai_embedding_model: str = "text-embedding-3-small"
    
    max_relevance_score: float = 1.2
    max_display_source_score: float = 1.0
    display_source_score_margin: float = 0.15
    max_upload_file_size_mb: int = 10
    min_enriched_chunk_quality_score: float = 0.5
    database_url: str = "postgresql://smartdocs:smartdocs@postgres:5432/smartdocs"
    redis_url: str = "redis://redis:6379/0"
    chat_rate_limit_per_ip_daily: int = 30
    chat_rate_limit_global_daily: int = 300
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_cookie_name: str = "smartdocs_admin_access_token"
    frontend_origins: str = "http://localhost:2000"
    cookie_domain: str | None = None
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def normalize_cookie_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    class Config:
        """Configura como o Pydantic carrega variaveis do arquivo .env."""
        env_file = Path(__file__).resolve().parents[1] / ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
