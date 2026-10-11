from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./geospatial.db"

    # File storage — uploaded files are saved here temporarily
    UPLOAD_DIR: str = "uploads"

    # Max upload size in bytes (50 MB)
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024

    # Allowed MIME types / extensions
    ALLOWED_EXTENSIONS: list[str] = [".zip", ".kml"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure upload directory exists
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
