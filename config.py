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
    max_concurrent_scans: int = 2
    gateway_ip: str = "192.168.1.1"
    sniffer_interface: str = ""
    trusted_dhcp_server: str = ""
    db_path: Path = Field(default=Path("data/netmon.db"))
    dashboard_password: str = ""
    db_retention_days: int = 90
    log_level: str = "INFO"
    log_file: Path = Field(default=Path("logs/overwatcher.log"))
    hourly_report_enabled: bool = True
    macvendors_api_enabled: bool = True
    macvendors_api_timeout: float = 5.0
    ble_scan_timeout: float = 10.0
    ble_alert_cooldown_hours: float = 2.0
    ble_adapter: str = "hci0"
    dashboard_temp_warn_c: float = 70.0
    dashboard_temp_crit_c: float = 80.0
    ble_proximity_immediate_dbm: int = -50
    ble_proximity_near_dbm: int = -70
    sweep_interval_minutes: int = 5
    speedtest_interval_hours: int = 3


# Singleton instance for the application
config = Settings()
