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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

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
