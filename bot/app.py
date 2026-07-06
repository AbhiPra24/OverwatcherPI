import logging
from telegram.ext import ApplicationBuilder, CommandHandler

from bot import handlers
from config import config

logger = logging.getLogger(__name__)


def setup_application(post_init_hook=None):
    """Create and configure the Telegram bot application."""
    builder = ApplicationBuilder().token(config.telegram_bot_token.get_secret_value())
    
    if post_init_hook:
        builder.post_init(post_init_hook)
        
    app = builder.build()
    
    app.add_handler(CommandHandler("start", handlers.start_handler))
    app.add_handler(CommandHandler("status", handlers.status_handler))
    app.add_handler(CommandHandler("network", handlers.network_handler))
    app.add_handler(CommandHandler("bluetooth", handlers.bluetooth_handler))
    
    return app
