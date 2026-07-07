import logging
from telegram.ext import Application
from config import config

logger = logging.getLogger(__name__)

async def broadcast_message(app: Application, text: str, disable_notification: bool = False, parse_mode: str = "HTML", **kwargs):
    """Send a message to all configured Telegram owners."""
    for owner_id in config.telegram_owner_ids:
        try:
            await app.bot.send_message(
                chat_id=owner_id,
                text=text,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to send message to {owner_id}: {e}")
