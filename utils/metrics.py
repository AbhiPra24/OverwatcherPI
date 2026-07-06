import time
import psutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SystemStatus:
    cpu_per_core: list[float]
    ram_used_mb: float
    ram_total_mb: float
    temp_celsius: float
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    uptime_seconds: float


def get_soc_temp() -> float:
    """Read SoC temperature from the Raspberry Pi thermal zone."""
    temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp_file.exists():
        try:
            return float(temp_file.read_text().strip()) / 1000.0
        except Exception:
            pass
    return 0.0


def get_system_status() -> SystemStatus:
    """Collect full system diagnostics."""
    # Memory
    mem = psutil.virtual_memory()
    ram_used_mb = mem.used / (1024 * 1024)
    ram_total_mb = mem.total / (1024 * 1024)
    
    # Disk
    disk = psutil.disk_usage('/')
    disk_used_gb = disk.used / (1024**3)
    disk_total_gb = disk.total / (1024**3)
    
    # Uptime
    uptime_seconds = time.time() - psutil.boot_time()
    
    return SystemStatus(
        cpu_per_core=psutil.cpu_percent(percpu=True, interval=0.1),
        ram_used_mb=ram_used_mb,
        ram_total_mb=ram_total_mb,
        temp_celsius=get_soc_temp(),
        disk_used_gb=disk_used_gb,
        disk_total_gb=disk_total_gb,
        disk_percent=disk.percent,
        uptime_seconds=uptime_seconds
    )
