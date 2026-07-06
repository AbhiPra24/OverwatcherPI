from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    telegram_bot_token: SecretStr
    telegram_owner_id: int
    scan_subnet: str = "192.168.1.0/24"
    db_path: Path = Field(default=Path("data/netmon.db"))
    log_level: str = "INFO"
    log_file: Path = Field(default=Path("logs/overwatcher.log"))
    hourly_report_enabled: bool = True
    ble_scan_timeout: float = 10.0
    ble_adapter: str = "hci0"
    sweep_interval_minutes: int = 5
    speedtest_interval_hours: int = 3


# Singleton instance for the application
config = Settings()
