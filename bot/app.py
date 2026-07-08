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
            BotCommand("dns", "View recent DNS queries for host"),
            BotCommand("name", "Assign friendly name to device"),
            BotCommand("maintenance", "Mute alerts for device"),
            BotCommand("snooze", "Mute alerts for a device (hours)"),
            BotCommand("export", "Export database as CSV"),
            BotCommand("jobs", "List recent and running jobs"),
            BotCommand("job", "Show job details"),
            BotCommand("canceljob", "Cancel a running or queued job"),
            BotCommand("health", "Show container health and system info"),
            BotCommand("help", "Detailed list of all commands and usage"),
            BotCommand("nmap_full", "Run full nmap scan on target"),
            BotCommand("sherlock", "Run OSINT on username"),
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
                
        ssh_watcher_task = asyncio.create_task(supervisor())
        app.bot_data["ssh_watcher_task"] = ssh_watcher_task
        
        from core.job_queue import job_worker
        job_worker_task = asyncio.create_task(job_worker(app))
        app.bot_data["job_worker_task"] = job_worker_task
        
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
    app.add_handler(CommandHandler("dns", handlers.dns_handler))
    app.add_handler(CommandHandler("traceroute", handlers.traceroute_handler))
    app.add_handler(CommandHandler("name", handlers.name_handler))
    app.add_handler(CommandHandler("maintenance", handlers.maintenance_handler))
    app.add_handler(CommandHandler("export", handlers.export_handler))
    app.add_handler(CommandHandler("logs", handlers.logs_handler))
    app.add_handler(CommandHandler("attacker", handlers.attacker_handler))
    
    app.add_handler(CommandHandler("jobs", handlers.jobs_handler))
    app.add_handler(CommandHandler("job", handlers.job_detail_handler))
    app.add_handler(CommandHandler("canceljob", handlers.canceljob_handler))
    app.add_handler(CommandHandler("health", handlers.health_handler))
    app.add_handler(CommandHandler("help", handlers.help_handler))
    app.add_handler(CommandHandler("snooze", handlers.snooze_handler))
    app.add_handler(CommandHandler("nmap_full", handlers.nmap_full_handler))
    app.add_handler(CommandHandler("sherlock", handlers.sherlock_handler))
    
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(handlers.callback_query_handler))
    
    app.add_error_handler(global_error_handler)
    
    return app
