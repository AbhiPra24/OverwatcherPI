import functools
import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import config

logger = logging.getLogger(__name__)


def auth_required(func):
    """Decorator to enforce Telegram user whitelisting."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or user.id != config.telegram_owner_id:
            logger.warning(f"Unauthorized access attempt from user_id={user.id if user else 'None'} username={user.username if user else 'None'}")
            if update.message:
                await update.message.reply_text("⛔ Unauthorized.", parse_mode="HTML")
            return
            
        return await func(update, context)
        
    return wrapper
