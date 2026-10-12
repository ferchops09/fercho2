import os
from pathlib import Path


class Settings:
    # App
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "7421"))
    log_level: str = os.getenv("LOG_LEVEL", "info")

    # Storage - default local si no está en Docker
    _default_download_dir = os.getenv("DOWNLOAD_DIR") or str(Path(__file__).parent.parent / "downloads")
    download_dir: str = _default_download_dir
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))

    # YouTube
    yt_timeout_seconds: int = int(os.getenv("YT_TIMEOUT_SECONDS", "30"))
    yt_max_retries: int = int(os.getenv("YT_MAX_RETRIES", "3"))


settings = Settings()
