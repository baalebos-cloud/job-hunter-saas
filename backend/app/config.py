import os
from pydantic_settings import BaseSettings

# Calculate the absolute path to ensure DB consistency
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "job_hunter.db")

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = f"sqlite:///{os.path.abspath(DB_PATH)}"
    
    # Auth (Added these to fix your validation errors)
    secret_key: str = "placeholder_key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Redis config
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = "" 

    # Email config
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = Field(default="", env="SMTP_USER")
    SMTP_PASSWORD: str = Field(default="", env="SMTP_PASSWORD")

    @property
    def redis_url(self):
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    class Config:
        env_file = ".env"
        # This allows Pydantic to ignore extra fields in your .env 
        # instead of crashing, but adding them above is cleaner!
        extra = "ignore" 

settings = Settings()
