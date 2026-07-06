import time
import psutil
from dataclasses import dataclass
from pathlib import Path
import subprocess


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
    throttling_status: str


def get_soc_temp() -> float:
    """Read SoC temperature from the Raspberry Pi thermal zone."""
    base_dir = Path("/sys/class/thermal")
    if base_dir.exists():
        for zone in base_dir.glob("thermal_zone*"):
            type_file = zone / "type"
            if type_file.exists():
                try:
                    zone_type = type_file.read_text().strip().lower()
                    if "cpu" in zone_type or "soc" in zone_type or "bcm" in zone_type or "x86_pkg_temp" in zone_type:
                        temp_file = zone / "temp"
                        if temp_file.exists():
                            return float(temp_file.read_text().strip()) / 1000.0
                except Exception:
                    continue
        
        # Fallback to thermal_zone0
        temp_file = base_dir / "thermal_zone0" / "temp"
        if temp_file.exists():
            try:
                return float(temp_file.read_text().strip()) / 1000.0
            except Exception:
                pass
    return 0.0

def get_throttling_status() -> str:
    """Read Raspberry Pi throttling status via vcgencmd."""
    try:
        output = subprocess.check_output(["vcgencmd", "get_throttled"], stderr=subprocess.STDOUT, text=True)
        if "throttled=" in output:
            hex_val = output.strip().split("=")[1]
            val = int(hex_val, 16)
            if val == 0:
                return "✅ Normal"
            
            issues = []
            if val & 0x1:
                issues.append("Under-voltage detected")
            if val & 0x2:
                issues.append("ARM frequency capped")
            if val & 0x4:
                issues.append("Currently throttled")
            if val & 0x8:
                issues.append("Soft temperature limit active")
            if val & 0x10000:
                issues.append("Under-voltage occurred")
            if val & 0x20000:
                issues.append("ARM freq capped occurred")
            if val & 0x40000:
                issues.append("Throttling occurred")
            if val & 0x80000:
                issues.append("Soft temp limit occurred")
                
            if issues:
                return "⚠️ " + ", ".join(issues)
    except FileNotFoundError:
        return "Not available (vcgencmd missing)"
    except Exception as e:
        return f"Error: {e}"
        
    return "Unknown"


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
        uptime_seconds=uptime_seconds,
        throttling_status=get_throttling_status()
    )
