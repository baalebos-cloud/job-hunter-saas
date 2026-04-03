import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # --- Database Settings ---
    # Pydantic will automatically grab DATABASE_URL from your .env
    DATABASE_URL: str = Field(..., env="DATABASE_URL")

    # --- Redis / ElastiCache Settings ---
    # This fixes the 'settings object has no attribute redis_url' error
    REDIS_URL: str = Field(..., env="REDIS_URL")

    # --- Security & Auth ---
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    # --- AI & Mail ---
    OPENAI_API_KEY: str = Field(None, env="OPENAI_API_KEY")
    MAIL_USERNAME: str = Field(None, env="MAIL_USERNAME")
    MAIL_PASSWORD: str = Field(None, env="MAIL_PASSWORD")
    MAIL_FROM: str = Field(None, env="MAIL_FROM")
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"

    # --- App State ---
    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    class Config:
        # This points Pydantic to your .env file
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"
# Initialize the settings object
settings = Settings()
