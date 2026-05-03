"""Application configuration."""

import secrets
from typing import List, Union

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: str = "development"
    debug: bool = False

    # Session Security
    session_secret_key: str = ""
    session_cookie_name: str = "kotte_session"
    session_max_age: int = 3600  # 1 hour
    session_idle_timeout: int = 1800  # 30 minutes

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_connect_timeout: int = 10  # seconds
    db_pool_min_size: int = Field(default=1, ge=0)
    db_pool_max_size: int = Field(default=10, ge=1)
    db_pool_max_idle: int = Field(default=300, ge=0)  # seconds

    # CORS — accepts either a JSON array or a comma-separated string so both
    # the documented form ("http://a,http://b") and the pydantic-settings native
    # form ('["http://a","http://b"]') work without operator confusion.
    # Union[List[str], str] sets allow_parse_failure=True in EnvSettingsSource so
    # a non-JSON string is passed through to the field_validator rather than
    # raising a SettingsError.
    cors_origins: Union[List[str], str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> List[str]:
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return list(v)  # type: ignore[call-overload]

    # Query Limits
    query_timeout: int = 300  # 5 minutes
    query_max_result_rows: int = 100000
    query_max_variable_hops: int = 20
    query_safe_mode: bool = False  # Reject mutating queries when True

    # Visualization Limits
    max_nodes_for_graph: int = 5000  # Maximum nodes for graph visualization
    max_edges_for_graph: int = 10000  # Maximum edges for graph visualization

    # Import Limits
    import_max_file_size: int = 104857600  # 100MB
    import_max_rows: int = 1000000
    max_import_jobs: int = 1000  # Max jobs in memory; oldest evicted when exceeded
    import_job_ttl_seconds: int = 86400  # Remove jobs older than 24h

    # Logging
    log_level: str = "INFO"
    structured_logging: bool = True

    # Credential Storage
    credential_storage_type: str = "json_file"  # json_file, sqlite, postgresql, redis
    credential_storage_path: str = "./data/connections.json"  # Default to local data directory
    master_encryption_key: str = ""  # Must be set from environment

    # Redis (optional, for Milestone D multi-user)
    redis_enabled: bool = False  # Set to True to use Redis for sessions and query tracking
    redis_url: str = "redis://localhost:6379"  # Redis connection URL

    # OpenTelemetry (optional, for Milestone D4 observability)
    otel_enabled: bool = False  # Set to True to enable OpenTelemetry tracing
    otel_service_name: str = "kotte-backend"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"  # gRPC endpoint

    # Security
    csrf_enabled: bool = True
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60  # Requests per minute per IP
    rate_limit_per_user: int = 100  # Requests per minute per user

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Generate secret key if not provided (for development only)
        if not self.session_secret_key:
            if self.environment == "production":
                raise ValueError("SESSION_SECRET_KEY must be set in production environment")
            self.session_secret_key = secrets.token_urlsafe(32)
            if self.environment != "test":
                import warnings

                warnings.warn(
                    "SESSION_SECRET_KEY not set, using generated key. "
                    "Set SESSION_SECRET_KEY in production!",
                    UserWarning,
                )

    @model_validator(mode="after")
    def validate_pool_sizes(self) -> "Settings":
        if self.db_pool_min_size > self.db_pool_max_size:
            raise ValueError("db_pool_min_size must be less than or equal to db_pool_max_size")
        return self


settings = Settings()
