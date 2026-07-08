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
    fan_rpm: float | str | None = None
    pi_model: str = "Unknown"
    core_voltage_v: float | None = None
    arm_clock_mhz: float | None = None
    ssh_sessions: list[str] = None

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
    except subprocess.CalledProcessError as e:
        if e.returncode == 255:
            return "⚠️ Permission denied (needs 'video' group or root)"
        return f"Error (exit code {e.returncode})"
    except Exception as e:
        return f"Error: {e}"
        
    return "Unknown"


def get_service_status(service_name: str) -> str:
    try:
        output = subprocess.check_output(
            ["systemctl", "is-active", service_name],
            stderr=subprocess.STDOUT, text=True, timeout=2.0
        )
        return output.strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip() if e.output else "failed"
    except Exception:
        return "unknown"

def get_pi_model() -> str:
    try:
        return Path("/sys/firmware/devicetree/base/model").read_text().strip('\x00').strip()
    except Exception:
        return "Unknown"

def get_voltage() -> float | None:
    try:
        output = subprocess.check_output(["vcgencmd", "measure_volts", "core"], stderr=subprocess.STDOUT, text=True)
        if "volt=" in output:
            return float(output.strip().replace("volt=", "").replace("V", ""))
    except Exception:
        pass
    return None

def get_clock_speed_mhz() -> float | None:
    try:
        output = subprocess.check_output(["vcgencmd", "measure_clock", "arm"], stderr=subprocess.STDOUT, text=True)
        if "=" in output:
            hz = float(output.strip().split("=")[1])
            return hz / 1_000_000.0
    except Exception:
        pass
    return None

def get_active_ssh_sessions() -> list[str]:
    try:
        output = subprocess.check_output(["who"], text=True)
        sessions = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 5:
                user = parts[0]
                tty = parts[1]
                since = f"{parts[2]} {parts[3]}"
                ip = parts[4] if parts[4].startswith('(') else f"({parts[4]})"
                sessions.append(f"{user} {tty} {ip} since {since}")
        return sessions
    except Exception:
        return []

def get_fan_rpm():
    if hasattr(psutil, "sensors_fans"):
        try:
            fans = psutil.sensors_fans()
            if fans:
                for name, entries in fans.items():
                    if entries:
                        return float(entries[0].current)
        except Exception:
            pass
            
    try:
        for p in Path("/sys/class/thermal/").glob("cooling_device*"):
            type_file = p / "type"
            if type_file.exists() and "fan" in type_file.read_text().lower():
                cur_state = (p / "cur_state").read_text().strip()
                max_state = (p / "max_state").read_text().strip()
                return f"Fan state: {cur_state}/{max_state}"
    except Exception:
        pass
    return None

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
        throttling_status=get_throttling_status(),
        fan_rpm=get_fan_rpm(),
        pi_model=get_pi_model(),
        core_voltage_v=get_voltage(),
        arm_clock_mhz=get_clock_speed_mhz(),
        ssh_sessions=get_active_ssh_sessions()
    )
