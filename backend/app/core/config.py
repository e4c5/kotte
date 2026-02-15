"""Application configuration."""

import secrets
from typing import List

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

    # CORS
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Query Limits
    query_timeout: int = 300  # 5 minutes
    query_max_result_rows: int = 100000
    query_safe_mode: bool = False  # Reject mutating queries when True

    # Import Limits
    import_max_file_size: int = 104857600  # 100MB
    import_max_rows: int = 1000000

    # Logging
    log_level: str = "INFO"

    # Credential Storage
    credential_storage_type: str = "json_file"  # json_file, sqlite, postgresql, redis
    credential_storage_path: str = "/var/lib/kotte/connections.json"
    master_encryption_key: str = ""  # Must be set from environment

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Generate secret key if not provided (for development only)
        if not self.session_secret_key:
            if self.environment == "production":
                raise ValueError(
                    "SESSION_SECRET_KEY must be set in production environment"
                )
            self.session_secret_key = secrets.token_urlsafe(32)
            import warnings

            warnings.warn(
                "SESSION_SECRET_KEY not set, using generated key. "
                "Set SESSION_SECRET_KEY in production!",
                UserWarning,
            )


settings = Settings()

