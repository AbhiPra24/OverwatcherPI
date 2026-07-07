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

    # 4. Start API Server
    from api.server import start_api_server
    asyncio.create_task(start_api_server())
    logging.getLogger(__name__).info("FastAPI server starting...")

    # 4. Boot notification
    try:
        from bot.broadcaster import broadcast_message
        import psutil
        from datetime import datetime
        import socket
        
        boot_time_dt = datetime.fromtimestamp(psutil.boot_time())
        formatted_boot = boot_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        hostname = socket.gethostname()
        
        # Broadcast to all owners via the configured broadcaster
        await broadcast_message(
            app,
            text=f"🟢 <b>OverwatcherPI started</b> — {hostname}\nBoot time: {formatted_boot}\nUptime since boot: 0m",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to send boot notification: {e}")


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
