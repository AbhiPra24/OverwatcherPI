from pydantic import Field, SecretStr, field_validator
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    telegram_bot_token: SecretStr
    telegram_owner_ids: List[int]

    @field_validator("telegram_owner_ids", mode="before")
    def parse_owner_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v
    scan_subnet: str = "192.168.1.0/24"
    max_concurrent_scans: int = 2
    gateway_ip: str = "192.168.1.1"
    sniffer_interface: str = ""
    trusted_dhcp_server: str = ""
    db_path: Path = Field(default=Path("data/netmon.db"))
    dashboard_password: str = ""
    db_retention_days: int = 90
    db_backup_retention_days: int = 30
    log_level: str = "INFO"
    log_format: str = "text"
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
    cpu_warn_percent: float = 85.0
    ram_warn_percent: float = 85.0
    disk_warn_percent: float = 90.0
    resource_alert_cooldown_hours: float = 1.0
    watched_services: List[str] = ["overwatcher-dashboard", "overwatcher-caddy", "overwatcher-sniffer"]
    quiet_hours_start: int = 1
    quiet_hours_end: int = 5
    network_jitter_threshold_ms: float = 50.0
    api_token: str
    api_port: int = 8000

    @field_validator("watched_services", mode="before")
    def parse_watched_services(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

# Singleton instance for the application
config = Settings()
