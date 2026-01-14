"""Application configuration using Pydantic settings."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "VariantIQ"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Genomic Variant Commercial Intelligence Platform"
    DEBUG: bool = False
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")

    # API
    API_V1_PREFIX: str = "/api/v1"
    API_TITLE: str = "VariantIQ API"

    # Security
    SECRET_KEY: str = Field(..., min_length=32, description="Secret key for JWT tokens")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: list[str] = ["*"]
    CORS_HEADERS: list[str] = ["*"]

    # Database
    DATABASE_URL: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection URL"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_PRE_PING: bool = True
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: RedisDsn = Field(..., description="Redis connection URL")
    REDIS_CACHE_TTL: int = 60 * 60  # 1 hour
    REDIS_MAX_CONNECTIONS: int = 10

    # External APIs
    NCBI_API_KEY: Optional[str] = None
    NCBI_EMAIL: Optional[str] = None
    NCBI_TOOL: str = "VariantIQ"
    NCBI_RATE_LIMIT: int = 3  # requests per second (10 with API key)

    DRUGBANK_API_KEY: Optional[str] = None
    DRUGBANK_RATE_LIMIT: int = 1  # requests per second

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"

    # ML Models
    MODEL_DIR: str = "data/models"
    DRUGGABILITY_MODEL_PATH: str = "data/models/druggability_v1.pkl"
    ML_BATCH_SIZE: int = 32
    ML_NUM_WORKERS: int = 4

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    # Logging
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    LOG_FILE: Optional[str] = None
    LOG_ROTATION: str = "100 MB"
    LOG_RETENTION: str = "10 days"

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090

    # Data Pipeline
    DATA_DIR: str = "data"
    RAW_DATA_DIR: str = "data/raw"
    PROCESSED_DATA_DIR: str = "data/processed"
    DATA_UPDATE_CRON: str = "0 2 * * *"  # Daily at 2 AM

    # ClinVar
    CLINVAR_RELEASE_DATE: Optional[str] = None
    CLINVAR_FTP_URL: str = "ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/"

    # Clinical Trials
    AACT_DATABASE_URL: Optional[PostgresDsn] = None

    # Performance
    MAX_WORKERS: int = 4
    REQUEST_TIMEOUT: int = 30
    DB_QUERY_TIMEOUT: int = 10

    # Feature Flags
    ENABLE_DRUGGABILITY_SCORING: bool = True
    ENABLE_MARKET_ANALYSIS: bool = True
    ENABLE_PATENT_SEARCH: bool = False  # Coming soon
    ENABLE_REAL_TIME_TRIALS: bool = False  # Coming soon

    @field_validator("NCBI_RATE_LIMIT")
    @classmethod
    def adjust_ncbi_rate_limit(cls, v: int, info) -> int:
        """Adjust NCBI rate limit based on API key presence."""
        if info.data.get("NCBI_API_KEY"):
            return 10  # Higher limit with API key
        return 3

    @property
    def database_url_str(self) -> str:
        """Get database URL as string."""
        return str(self.DATABASE_URL)

    @property
    def redis_url_str(self) -> str:
        """Get Redis URL as string."""
        return str(self.REDIS_URL)

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    This function is cached to avoid re-reading environment variables
    on every request.

    Returns:
        Settings: Application configuration
    """
    return Settings()


# Convenience alias
settings = get_settings()
