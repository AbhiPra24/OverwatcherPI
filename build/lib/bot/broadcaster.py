import logging
from telegram.ext import Application
from config import config

logger = logging.getLogger(__name__)

async def broadcast_message(app: Application, text: str, disable_notification: bool = False, parse_mode: str = "HTML", **kwargs):
    """Send a message to all configured Telegram owners."""
    from core.database import DatabaseManager
    import datetime
    from pathlib import Path

    success = False
    for owner_id in config.telegram_owner_ids:
        try:
            await app.bot.send_message(
                chat_id=owner_id,
                text=text,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
                **kwargs
            )
            success = True
        except Exception as e:
            logger.error(f"Failed to send message to {owner_id}: {e}")
            try:
                log_path = Path("logs/undelivered_alerts.log")
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("a", encoding="utf-8") as f:
                    timestamp = datetime.datetime.now().isoformat()
                    f.write(f"[{timestamp}] To {owner_id}: {text}\n")
            except Exception as e2:
                logger.error(f"Failed to write to undelivered_alerts.log: {e2}")
                
    if success:
        await DatabaseManager.record_scan_heartbeat("telegram_delivery")
