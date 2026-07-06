import logging
import asyncio
from logging.handlers import RotatingFileHandler
from telegram.ext import Application

from config import config
from core.database import DatabaseManager
from core import oui
from core.scheduler import setup_scheduler
from bot.app import setup_application


def setup_logging():
    """Configure structured logging."""
    # Ensure log directory exists
    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # File handler with rotation (5 MB per file, max 3 backups)
    file_handler = RotatingFileHandler(
        config.log_file, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(formatter)
    
    # Stream handler for systemd journal
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=[file_handler, stream_handler]
    )
    
    # Tone down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("bleak").setLevel(logging.WARNING)


async def _post_init(app: Application) -> None:
    """PTB post_init hook. Runs within the event loop before polling starts."""
    # 1. Initialize SQLite connection and schemas
    await DatabaseManager.get_db()
    
    # 2. Ensure OUI database is cached
    await oui.load_or_refresh()
    
    # 3. Start APScheduler within this event loop
    scheduler = setup_scheduler(app)
    scheduler.start()
    logging.getLogger(__name__).info("APScheduler background jobs started.")


def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Initializing OverwatcherPI Daemon...")
    
    try:
        app = setup_application(post_init_hook=_post_init)
        logger.info("Starting Telegram Bot polling...")
        # drop_pending_updates prevents replaying old commands after restart
        app.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
    except Exception as e:
        logger.exception("Critical error in main loop")
    finally:
        # DB cleanup is handled effectively by OS on exit, but we can explicitly clean up
        asyncio.run(DatabaseManager.close())
        logger.info("OverwatcherPI shutdown complete.")


if __name__ == "__main__":
    main()
