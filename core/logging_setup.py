import logging
import json
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    """Emits one JSON object per log line."""

    def __init__(self, service_name: str):
        super().__init__()
        self._service = service_name

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "service": self._service,
            "logger": record.name,
            "message": record.getMessage(),
        })


def configure_logging(service_name: str) -> None:
    """Unified logging configuration for all OverwatcherPI entry points.

    Reads ``config.log_level`` and ``config.log_format`` (text|json).
    Produces a RotatingFileHandler to ``logs/<service_name>.log`` (5 MB × 3
    backups) and a StreamHandler to stdout so systemd journal / docker logs
    both work.  Silences noisy third-party libraries regardless of format.
    """
    # Import here to avoid circular imports at module load time
    from config import config  # noqa: PLC0415

    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    use_json = getattr(config, "log_format", "text").lower() == "json"

    if use_json:
        fmt: logging.Formatter = _JsonFormatter(service_name)
    else:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir / f"{service_name}.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    logging.basicConfig(level=log_level, handlers=[file_handler, stream_handler])

    # Tone down noisy libraries
    for noisy in ("httpx", "apscheduler", "bleak", "telegram"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
