import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from bot import handlers
from config import config

logger = logging.getLogger(__name__)

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(f"⚠️ An error occurred: {context.error}")
        except Exception:
            pass


def setup_application(post_init_hook=None):
    """Create and configure the Telegram bot application."""
    builder = ApplicationBuilder().token(config.telegram_bot_token.get_secret_value())
    
    async def internal_post_init(app):
        if post_init_hook:
            await post_init_hook(app)
            
        from telegram import BotCommand
        await app.bot.set_my_commands([
            BotCommand("status", "Hardware diagnostics"),
            BotCommand("network", "Scan local subnet"),
            BotCommand("bluetooth", "Scan nearby BLE devices"),
            BotCommand("speedtest", "Check internet speed"),
            BotCommand("traceroute", "Run traceroute to host"),
            BotCommand("whitelist", "Mark a device as safe"),
            BotCommand("attacker", "WHOIS OSINT lookup"),
            BotCommand("monitor", "Pin host for ping monitor"),
            BotCommand("unmonitor", "Remove host from ping monitor"),
            BotCommand("export", "Export database to CSV"),
            BotCommand("logs", "Fetch systemd logs")
        ])
        
        import asyncio
        from core.ssh_watcher import ssh_log_watcher
        
        async def supervisor():
            while True:
                try:
                    await ssh_log_watcher(app)
                except Exception as e:
                    logger.error(f"SSH watcher crashed: {e}")
                logger.warning("SSH watcher exited. Restarting in 10s...")
                await asyncio.sleep(10)
                
        task = asyncio.create_task(supervisor())
        app.bot_data["ssh_watcher_task"] = task
        
    builder.post_init(internal_post_init)
        
    app = builder.build()
    
    app.add_handler(CommandHandler("start", handlers.start_handler))
    app.add_handler(CommandHandler("status", handlers.status_handler))
    app.add_handler(CommandHandler("network", handlers.network_handler))
    app.add_handler(CommandHandler("bluetooth", handlers.bluetooth_handler))
    app.add_handler(CommandHandler("speedtest", handlers.speedtest_handler))
    app.add_handler(CommandHandler("whitelist", handlers.whitelist_handler))
    app.add_handler(CommandHandler("monitor", handlers.monitor_handler))
    app.add_handler(CommandHandler("unmonitor", handlers.unmonitor_handler))
    app.add_handler(CommandHandler("traceroute", handlers.traceroute_handler))
    app.add_handler(CommandHandler("export", handlers.export_handler))
    app.add_handler(CommandHandler("logs", handlers.logs_handler))
    
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(handlers.callback_query_handler))
    
    app.add_error_handler(global_error_handler)
    
    return app
