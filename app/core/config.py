from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    """

    APP_NAME: str = "CSMBaseAPI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str

    REDIS_URL: str = "redis://localhost:6379/0"

    # Alembic local migration database URL
    ALEMBIC_DATABASE_URL: str | None = None

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES: int = 30

    # Email
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@example.com"
    SMTP_FROM_NAME: str = "CSMBaseAPI"
    SMTP_USE_TLS: bool = True

    PASSWORD_RESET_URL: str = "http://localhost:3000/reset-password"
    EMAIL_VERIFICATION_URL: str = "http://localhost:3000/verify-email"

    # CORS
    CORS_ORIGINS: str = "*"

    # Storage
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_PATH: str = "./uploads"
    MAX_ATTACHMENT_SIZE: int = 10 * 1024 * 1024

    ALLOWED_ATTACHMENT_TYPES: str = (
        "application/pdf,"
        "image/png,"
        "image/jpeg,"
        "image/gif,"
        "text/plain,"
        "text/csv,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    ALLOWED_ATTACHMENT_EXTENSIONS: str = (
        "application/pdf:.pdf,"
        "image/png:.png,"
        "image/jpeg:.jpg|.jpeg,"
        "image/gif:.gif,"
        "text/plain:.txt,"
        "text/csv:.csv,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document:.docx,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet:.xlsx"
    )


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_environment(self):
        """
        Enforce production-safe configuration.
        """

        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError(
                    "DEBUG must be False in production."
                )

            if self.CORS_ORIGINS.strip() == "*":
                raise ValueError(
                    "CORS_ORIGINS must be explicitly configured "
                    "in production."
                )

            if not self.PASSWORD_RESET_URL.startswith("https://"):
                raise ValueError(
                    "PASSWORD_RESET_URL must use HTTPS in production."
                )

            if not self.EMAIL_VERIFICATION_URL.startswith("https://"):
                raise ValueError(
                    "EMAIL_VERIFICATION_URL must use HTTPS in production."
                )

        return self


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
