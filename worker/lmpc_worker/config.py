import socket
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    LMPC_API_URL: str = "http://localhost:8080"
    LMPC_WORKER_NAME: str = socket.gethostname()
    LMPC_TOKEN_PATH: Path = Path.home() / ".lmpc" / "token"
    LMPC_PLATFORMS: list[str] = ["stub"]
    LMPC_LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = WorkerSettings()
