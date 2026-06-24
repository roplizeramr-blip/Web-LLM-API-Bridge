from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROVIDERS_DIR = DATA_DIR / "providers"
SESSIONS_DIR = DATA_DIR / "sessions"
BROWSER_DIR = DATA_DIR / "browser"


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 9920
    default_model: str = "chatgpt"
    headless: bool = False
    response_idle_seconds: float = 1.5
    response_timeout_seconds: float = 180.0

    model_config = SettingsConfigDict(env_prefix="API_BRIDGE_", env_file=".env")


settings = Settings()


def ensure_data_dirs() -> None:
    for directory in (DATA_DIR, PROVIDERS_DIR, SESSIONS_DIR, BROWSER_DIR):
        directory.mkdir(parents=True, exist_ok=True)
