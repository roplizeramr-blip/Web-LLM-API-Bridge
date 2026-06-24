from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROVIDERS_DIR = DATA_DIR / "providers"
SESSIONS_DIR = DATA_DIR / "sessions"
BROWSER_DIR = DATA_DIR / "browser"
BROWSER_SETTINGS_PATH = DATA_DIR / "browser_settings.json"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def default_extra_headers() -> dict[str, str]:
    return {
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
    }


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 9920
    default_model: str = "chatgpt"
    headless: bool = False
    response_idle_seconds: float = 1.5
    response_timeout_seconds: float = 180.0
    user_agent: str = DEFAULT_USER_AGENT
    extra_headers: dict[str, str] = Field(default_factory=default_extra_headers)
    disable_webdriver: bool = True
    locale: str = "en-US"
    timezone: str = "America/New_York"
    platform: str = "Win32"

    model_config = SettingsConfigDict(env_prefix="LLM_BRIDGE_", env_file=".env")


settings = Settings()


class BrowserFingerprintSettings(BaseModel):
    user_agent: str = settings.user_agent
    extra_headers: dict[str, str] = Field(default_factory=lambda: dict(settings.extra_headers))
    disable_webdriver: bool = settings.disable_webdriver
    locale: str = settings.locale
    timezone: str = settings.timezone
    platform: str = settings.platform


def ensure_data_dirs() -> None:
    for directory in (DATA_DIR, PROVIDERS_DIR, SESSIONS_DIR, BROWSER_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def load_browser_fingerprint_settings() -> BrowserFingerprintSettings:
    ensure_data_dirs()
    if not BROWSER_SETTINGS_PATH.exists():
        return BrowserFingerprintSettings()
    try:
        return BrowserFingerprintSettings.model_validate_json(
            BROWSER_SETTINGS_PATH.read_text(encoding="utf-8")
        )
    except Exception:
        return BrowserFingerprintSettings()


def save_browser_fingerprint_settings(
    browser_settings: BrowserFingerprintSettings | dict[str, Any],
) -> BrowserFingerprintSettings:
    ensure_data_dirs()
    validated = BrowserFingerprintSettings.model_validate(browser_settings)
    BROWSER_SETTINGS_PATH.write_text(
        validated.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return validated
