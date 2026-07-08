import logging
import asyncio
import signal
from telegram.ext import Application

from config import config
from core.database import DatabaseManager
from core import oui
from core.scheduler import setup_scheduler
from bot.app import setup_application


def setup_logging():
    """Configure structured logging via the shared logging_setup helper."""
    from core.logging_setup import configure_logging
    configure_logging("overwatcher")


async def _post_init(app: Application) -> None:
    """PTB post_init hook. Runs within the event loop before polling starts."""
    # 1. Initialize SQLite connection and schemas
    await DatabaseManager.get_db()
    
    # 2. Ensure OUI database is cached
    await oui.load_or_refresh()
    
    # 2b. Ensure DNS blocklist is cached
    from core import threat_intel
    await threat_intel.load_or_refresh()
    
    # 3. Start APScheduler within this event loop
    scheduler = setup_scheduler(app)
    scheduler.start()
    logging.getLogger(__name__).info("APScheduler background jobs started.")

    # 4. Start API Server (binds 127.0.0.1 only — Caddy proxies /api/* to it)
    from api.server import start_api_server
    app.bot_data["api_task"] = asyncio.create_task(start_api_server())
    logging.getLogger(__name__).info("FastAPI server starting...")

    # 5. Boot notification
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

    # 6. Honeypot service
    if config.honeypot_enabled:
        from core import honeypot
        app.bot_data["honeypot_task"] = asyncio.create_task(honeypot.start_honeypots(app))


async def run_bot():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Initializing OverwatcherPI Daemon...")
    app = setup_application(post_init_hook=_post_init)
    
    stop_event = asyncio.Event()
    
    def shutdown_handler():
        logger.info("Shutdown signal received.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler)
        
    try:
        async with app:
            logger.info("Starting Telegram Bot polling...")
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            
            await stop_event.wait()
            
            logger.info("Stopping polling...")
            await app.updater.stop()
            await app.stop()
            
            logger.info("Cancelling background tasks...")
            for task_name in ["ssh_watcher_task", "api_task", "honeypot_task", "job_worker_task"]:
                task = app.bot_data.get(task_name)
                if task and not task.done():
                    task.cancel()
                    

                    
    except Exception as e:
        logger.exception("Critical error in main loop")
    finally:
        await DatabaseManager.close()
        logger.info("OverwatcherPI shutdown complete.")


def main():
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
