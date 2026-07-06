import asyncio
import time
import logging
from collections import defaultdict
from telegram.ext import Application
from telegram.constants import ParseMode

from config import config

logger = logging.getLogger(__name__)

async def ssh_log_watcher(app: Application):
    log_file = "/var/log/auth.log"
    
    # Check if we can read it
    try:
        with open(log_file, "r"): pass
    except Exception as e:
        logger.error(f"SSH watcher cannot read {log_file}: {e}")
        return
        
    logger.info("Starting SSH Auth Log Watcher...")
    
    # `tail -F` to handle log rotation
    process = await asyncio.create_subprocess_exec(
        "tail", "-F", "-n", "0", log_file,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )
    
    failed_attempts = defaultdict(list)
    
    while True:
        line = await process.stdout.readline()
        if not line:
            break
            
        line = line.decode('utf-8', errors='ignore').strip()
        
        if "sshd" in line:
            if "Failed password" in line or "Connection closed by authenticating user" in line:
                parts = line.split()
                if "from" in parts:
                    idx = parts.index("from")
                    if idx + 1 < len(parts):
                        ip = parts[idx + 1]
                        now = time.time()
                        failed_attempts[ip].append(now)
                        
                        # Clean up older than 10 mins (600s)
                        failed_attempts[ip] = [t for t in failed_attempts[ip] if now - t <= 600]
                        
                        # Alert exactly on the 5th attempt in the window to avoid spamming
                        if len(failed_attempts[ip]) == 5:
                            try:
                                await app.bot.send_message(
                                    chat_id=config.telegram_owner_id,
                                    text=f"🚨 <b>SSH Brute Force Detected:</b>\n5 failed logins in 10 mins from IP: <code>{ip}</code>",
                                    parse_mode=ParseMode.HTML
                                )
                            except Exception:
                                pass
                                
            elif "Accepted password" in line or "Accepted publickey" in line:
                parts = line.split()
                if "from" in parts:
                    idx = parts.index("from")
                    if idx + 1 < len(parts):
                        ip = parts[idx + 1]
                        try:
                            await app.bot.send_message(
                                chat_id=config.telegram_owner_id,
                                text=f"✅ <b>SSH Login Successful:</b>\nFrom IP: <code>{ip}</code>",
                                parse_mode=ParseMode.HTML
                            )
                        except Exception:
                            pass
