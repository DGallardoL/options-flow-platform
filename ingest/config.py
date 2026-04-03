import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    POLYGON_API_KEY: str = Field(...)
    MONGO_URI: str = Field(
        default_factory=lambda: (
            f"mongodb://ingest_writer:{os.environ.get('MONGO_INGEST_PWD', 'ingest_secure_2024')}"
            f"@localhost:27025/"
            f"?authSource=admin"
        )
    )
    MONGO_DB: str = "options_raw"
    FLUSH_INTERVAL: float = 1.0
    FLUSH_SIZE: int = 100

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
