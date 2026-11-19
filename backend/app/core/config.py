import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # --- Database ---
    # Railway injects DATABASE_URL automatically when PostgreSQL plugin is added
    DATABASE_URL: str = Field(default="", env="DATABASE_URL")

    # --- Redis ---
    # Railway injects REDIS_URL automatically when Redis plugin is added
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # --- Security ---
    SECRET_KEY: str = Field(
        default="",
        env="SECRET_KEY"
    )
    ALGORITHM: str = "HS256"
    # Short-lived access JWTs; sessions continue via rotating refresh cookies.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=14, ge=1, le=90)
    REFRESH_COOKIE_NAME: str = "bb_refresh"
    # "strict" requires the API on the same site as the dashboard
    # (e.g. api.baalebo.xyz). Use "none" only while the API is cross-site.
    REFRESH_COOKIE_SAMESITE: str = Field(default="strict", pattern="^(strict|lax|none)$")
    REFRESH_COOKIE_SECURE: bool = True
    REFRESH_COOKIE_DOMAIN: str = ""
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"
    # Proxies whose X-Forwarded-For is trusted (ALB / Railway edge). Comma list.
    TRUSTED_PROXY_CIDRS: str = ""
    CRON_SECRET: str = ""
    # One-time bootstrap: this verified account is granted super_admin by the
    # RBAC migration. Afterwards roles are managed in the database.
    ADMIN_EMAIL: str = ""

    # --- AI ---
    GROQ_API_KEY: str = Field(default="", env="GROQ_API_KEY")
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_MAX_COMPLETION_TOKENS: int = Field(default=8192, ge=1024, le=32768)
    OPENROUTER_API_KEY: str = Field(default="", env="OPENROUTER_API_KEY")
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")

    # SMTP_SSL sender used by backend.app.utils.email (implicit TLS).
    RESEND_API_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = Field(default=465, ge=1, le=65535)
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@baalebo.xyz"
    EMAILS_FROM_NAME: str = "Baalebos Cloud"
    FRONTEND_URL: str = "https://www.baalebo.xyz"
    N8N_APPLICATION_WEBHOOK_URL: str = ""
    N8N_EVENTS_WEBHOOK_URL: str = ""
    N8N_WEBHOOK_SECRET: str = ""
    SCRAPER_STALE_HOURS: int = Field(default=8, ge=1, le=168)
    # "async": uploads return 202 and a Celery worker runs OCR + refiner + PDF.
    # "sync" keeps the work in the API process (no worker required).
    RESUME_PROCESSING_MODE: str = Field(default="sync", pattern="^(sync|async)$")
    RESUME_JOB_TIMEOUT_MINUTES: int = Field(default=15, ge=2, le=120)
    # Optional read replica (e.g. RDS replica behind PgBouncer) for read-only GETs.
    DATABASE_READ_URL: str = ""

    # --- Mail ---
    MAIL_USERNAME: str = Field(default="", env="MAIL_USERNAME")
    MAIL_PASSWORD: str = Field(default="", env="MAIL_PASSWORD")
    MAIL_FROM: str = Field(default="", env="MAIL_FROM")
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"

    # --- App ---
    ENVIRONMENT: str = Field(default="production", env="ENVIRONMENT")
    DEBUG: bool = False

    class Config:
        # Read from env vars directly — works on Railway, local, and Docker
        # env_file is optional fallback for local dev
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
