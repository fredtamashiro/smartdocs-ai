from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Centraliza as configuracoes da aplicacao lidas do ambiente."""
    app_env: str = "local"
    app_name: str = "SmartDocs AI"
    langfuse_tracing_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    evaluation_judge_model: str = "gpt-4.1-mini"
    evaluation_judge_timeout_seconds: float = Field(default=60.0, gt=0)
    openai_api_key: str
    app_api_key: str | None = None

    openai_chat_model: str = "gpt-5-mini"
    openai_chat_temperature: float = 1
    openai_embedding_model: str = "text-embedding-3-small"
    chat_alternative_queries_limit: int = 3
    enable_multi_query: bool = True
    max_search_queries: int = 2
    max_chunks_to_grade: int = 3
    enable_batch_relevance_grader: bool = True
    skip_grader_for_high_confidence_retrieval: bool = True
    high_confidence_vector_distance_threshold: float = 0.25
    min_high_confidence_chunks: int = 2
    max_answer_context_chunks: int = 2
    max_answer_context_chars_per_chunk: int = 900
    question_guard_enabled: bool = True
    question_guard_blocked_terms: str = ""
    chat_answer_cache_enabled: bool = True
    chat_answer_cache_semantic_enabled: bool = True
    chat_answer_cache_similarity_threshold: float = 0.06
    chat_answer_cache_ttl_days: int = 30
    
    max_relevance_score: float = 1.2
    max_display_source_score: float = 1.0
    display_source_score_margin: float = 0.15
    max_upload_file_size_mb: int = 10
    min_enriched_chunk_quality_score: float = 0.5
    database_url: str = "postgresql://smartdocs:smartdocs@postgres:5432/smartdocs"
    redis_url: str = "redis://redis:6379/0"
    chat_rate_limit_per_ip_daily: int = 30
    chat_rate_limit_global_daily: int = 300
    jwt_secret_key: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 720
    admin_cookie_name: str = "smartdocs_admin_token"
    frontend_origins: str = "http://localhost:2000"
    cookie_domain: str | None = None
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    admin_seed_email: str = ""
    admin_seed_password: str = ""
    admin_seed_name: str = ""

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
