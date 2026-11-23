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

def get_throttling_status(ignore_undervoltage: bool | None = None) -> str:
    """Read Raspberry Pi throttling status via vcgencmd."""
    if ignore_undervoltage is None:
        try:
            from config import config
            ignore_undervoltage = getattr(config, "ignore_undervoltage", False)
        except Exception:
            ignore_undervoltage = False

    try:
        output = subprocess.check_output(["vcgencmd", "get_throttled"], stderr=subprocess.STDOUT, text=True)
        if "throttled=" in output:
            hex_val = output.strip().split("=")[1]
            val = int(hex_val, 16)
            if val == 0:
                return "✅ Normal"
            
            issues = []
            if val & 0x1 and not ignore_undervoltage:
                issues.append("Under-voltage detected")
            if val & 0x2:
                issues.append("ARM frequency capped")
            if val & 0x4:
                issues.append("Currently throttled")
            if val & 0x8:
                issues.append("Soft temperature limit active")
            if val & 0x10000 and not ignore_undervoltage:
                issues.append("Under-voltage occurred")
            if val & 0x20000:
                issues.append("ARM frequency capping occurred")
            if val & 0x40000:
                issues.append("Throttling occurred")
            if val & 0x80000:
                issues.append("Soft temperature limit occurred")
                
            if issues:
                return "⚠️ " + ", ".join(issues)
            return "✅ Normal"
    except FileNotFoundError:
        return "Not available (vcgencmd missing)"
    except subprocess.CalledProcessError as e:
        if e.returncode == 255:
            return "⚠️ Permission denied (needs 'video' group or root)"
        return f"Error (exit code {e.returncode})"
    except Exception as e:
        return f"Error: {e}"
        
    return "Unknown"


def get_docker_container_status(container_name: str) -> str:
    import socket
    import json
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect("/var/run/docker.sock")
        request = f"GET /containers/{container_name}/json HTTP/1.0\r\n\r\n"
        s.sendall(request.encode())
        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
        s.close()
        
        header, body = response.split(b"\r\n\r\n", 1)
        if b"200 OK" in header:
            data = json.loads(body.decode())
            state = data.get("State", {})
            if state.get("Running"):
                health = state.get("Health", {})
                if health:
                    status = health.get("Status")
                    if status == "healthy":
                        return "active"
                    return status or "failed"
                return "active"
            return state.get("Status", "inactive")
    except Exception:
        pass
    return "unknown"


def get_docker_container_logs(container_name: str, tail: int = 25) -> str:
    """Fetch the last `tail` lines of docker container logs via the Docker UNIX socket."""
    import socket
    import struct
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect("/var/run/docker.sock")
        request = f"GET /containers/{container_name}/logs?stderr=1&stdout=1&tail={tail} HTTP/1.0\r\n\r\n"
        s.sendall(request.encode())
        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
        s.close()

        parts = response.split(b"\r\n\r\n", 1)
        if len(parts) < 2:
            return ""
        header, raw = parts
        if b"200 OK" not in header:
            return ""

        lines = []
        offset = 0
        while offset < len(raw):
            if offset + 8 <= len(raw):
                _, size = struct.unpack(">BxxxI", raw[offset:offset+8])
                payload = raw[offset+8:offset+8+size]
                lines.append(payload.decode("utf-8", errors="replace"))
                offset += 8 + size
            else:
                lines.append(raw[offset:].decode("utf-8", errors="replace"))
                break
        return "".join(lines).strip()
    except Exception:
        return ""


def get_all_docker_containers() -> list[dict]:
    """Retrieve all containers and their health/exit states from Docker socket."""
    import socket
    import json
    containers = []
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect("/var/run/docker.sock")
        s.sendall(b"GET /containers/json?all=1 HTTP/1.0\r\n\r\n")
        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
        s.close()

        parts = response.split(b"\r\n\r\n", 1)
        if len(parts) >= 2 and b"200 OK" in parts[0]:
            raw_containers = json.loads(parts[1].decode())
            for c in raw_containers:
                cid = c.get("Id")
                name = c.get("Names", [""])[0].lstrip("/")
                if not name:
                    continue

                # Inspect container to get exact exit code and health status
                s_ins = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s_ins.settimeout(2.0)
                s_ins.connect("/var/run/docker.sock")
                s_ins.sendall(f"GET /containers/{cid}/json HTTP/1.0\r\n\r\n".encode())
                ins_resp = b""
                while True:
                    chunk = s_ins.recv(4096)
                    if not chunk:
                        break
                    ins_resp += chunk
                s_ins.close()

                ins_parts = ins_resp.split(b"\r\n\r\n", 1)
                if len(ins_parts) >= 2 and b"200 OK" in ins_parts[0]:
                    details = json.loads(ins_parts[1].decode())
                    state = details.get("State", {})
                    health = state.get("Health", {})
                    containers.append({
                        "name": name,
                        "running": state.get("Running", False),
                        "exit_code": state.get("ExitCode", 0),
                        "health_status": health.get("Status") if health else None,
                        "oom_killed": state.get("OOMKilled", False),
                        "status_str": c.get("Status", "")
                    })
    except Exception:
        pass
    return containers


def triage_container_incident(container_name: str, logs: str) -> str | None:
    import json
    import re
    import urllib.request
    from config import config

    if not getattr(config, "ollama_triage_enabled", True):
        return None

    endpoints = [
        (getattr(config, "ollama_base_url", "http://127.0.0.1:11435"), getattr(config, "ollama_model", "pralabs:edge")),
        (getattr(config, "ollama_fallback_url", "http://127.0.0.1:11434"), getattr(config, "ollama_fallback_model", "pralabs:edge")),
    ]

    prompt = (
        "[TASK: DEVOPS_SENTINEL] You are OverwatcherPI Host Sentinel. Parse container telemetry and extract root-cause failures.\n"
        "If the logs show normal, healthy background operations (e.g. HTTP 200 GET requests, routine heartbeats, normal metrics), you MUST output exactly: INCIDENT: NONE.\n"
        "If a failure or crash is detected, output a clean, deterministic 3-line triage block in this exact format:\n"
        "INCIDENT: <container> | SEVERITY: <CRITICAL/WARN>\n"
        "ROOT_CAUSE: <exact failure mechanism e.g., OOMKilled / port conflict>\n"
        "REMEDY: <exact command e.g., sudo systemctl restart ...>\n\n"
        f"Container: {container_name}\n"
        f"Logs:\n{logs}\n"
    )

    last_err = None
    for ollama_url, model in endpoints:
        if not ollama_url:
            continue
        req_body = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_k": 1,
                "top_p": 1.0,
                "num_thread": 4,
                "num_ctx": 2048,
                "num_predict": 128
            }
        }
        url = f"{ollama_url.rstrip('/')}/api/generate"
        req = urllib.request.Request(
            url,
            data=json.dumps(req_body).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_text = data.get("response", "").strip()

                raw_upper = raw_text.upper()
                if "INCIDENT: NONE" in raw_upper or raw_upper.startswith("INCIDENT: NONE"):
                    return None

                incident_match = re.search(r"INCIDENT:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
                root_match = re.search(r"ROOT_CAUSE:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
                remedy_match = re.search(r"REMEDY:\s*([^\n\r]+)", raw_text, re.IGNORECASE)

                if incident_match:
                    inc = f"INCIDENT: {incident_match.group(1).strip()}"
                    root = f"ROOT_CAUSE: {root_match.group(1).strip()}" if root_match else "ROOT_CAUSE: Container failure detected in telemetry."
                    rem = f"REMEDY: {remedy_match.group(1).strip()}" if remedy_match else f"REMEDY: docker restart {container_name}"
                    return f"{inc}\n{root}\n{rem}"

                return raw_text
        except Exception as e:
            last_err = e
            continue

    return f"INCIDENT: {container_name} | SEVERITY: WARN\nROOT_CAUSE: Ollama sentinel unreachable ({last_err})\nREMEDY: docker logs {container_name} --tail 50"


def get_service_status(service_name: str) -> str:
    if Path("/var/run/docker.sock").exists():
        status = get_docker_container_status(service_name)
        if status != "unknown":
            return status

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
    for model_path in ["/etc/pi-model", "/proc/device-tree/model", "/sys/firmware/devicetree/base/model"]:
        try:
            val = Path(model_path).read_text().strip('\x00').strip()
            if val:
                return val
        except Exception:
            pass
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
