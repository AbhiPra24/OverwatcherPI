import asyncio
import time
import os
import uuid
import logging
from typing import Dict
from core.database import DatabaseManager

logger = logging.getLogger(__name__)

JOB_QUEUE = asyncio.Queue()
ACTIVE_PROCESSES: Dict[str, asyncio.subprocess.Process] = {}

class JobQueue:
    @staticmethod
    async def add_job(command: str, requester_chat_id: int) -> str:
        job_id = str(uuid.uuid4())[:8]
        db = await DatabaseManager.get_db()
        await db.execute("""
            INSERT INTO jobs (id, job_type, target, status, created_at, requester_chat_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (job_id, 'shell', command, "queued", time.time(), requester_chat_id))
        await db.commit()
        
        await JOB_QUEUE.put({
            "id": job_id,
            "command": command,
            "requester_chat_id": requester_chat_id
        })
        return job_id

    @staticmethod
    async def cancel_job(job_id: str) -> bool:
        db = await DatabaseManager.get_db()
        cur = await db.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        row = await cur.fetchone()
        if not row:
            return False
            
        status = row["status"]
        if status == "running":
            if job_id in ACTIVE_PROCESSES:
                proc = ACTIVE_PROCESSES[job_id]
                try:
                    proc.kill()
                except Exception:
                    pass
                await db.execute("UPDATE jobs SET status = 'cancelled' WHERE id = ?", (job_id,))
                await db.commit()
                return True
        elif status == "queued":
            await db.execute("UPDATE jobs SET status = 'cancelled' WHERE id = ?", (job_id,))
            await db.commit()
            return True
        return False

async def job_worker(app_or_bot):
    os.makedirs("data/osint_results", exist_ok=True)
    
    while True:
        job = await JOB_QUEUE.get()
        job_id = job["id"]
        command = job["command"]
        chat_id = job["requester_chat_id"]
        
        db = await DatabaseManager.get_db()
        cur = await db.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        row = await cur.fetchone()
        if row and row["status"] == "cancelled":
            JOB_QUEUE.task_done()
            continue
            
        await db.execute("UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?", (time.time(), job_id,))
        await db.commit()
        
        try:
            import shlex
            args = shlex.split(command)
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            ACTIVE_PROCESSES[job_id] = proc
            
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300) # 5 min timeout
            except asyncio.TimeoutError:
                proc.kill()
                stdout, stderr = await proc.communicate()
                stderr += b"\nTimeout reached."
                
            out_text = stdout.decode('utf-8', errors='ignore')
            err_text = stderr.decode('utf-8', errors='ignore')
            
            file_path = f"data/osint_results/{job_id}.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Command: {command}\n\nSTDOUT:\n{out_text}\n\nSTDERR:\n{err_text}")
                
            cur = await db.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
            row = await cur.fetchone()
            if row and row["status"] == "cancelled":
                summary = f"⚠️ Job `{job_id}` was cancelled."
                await app_or_bot.bot.send_message(chat_id=chat_id, text=summary)
            else:
                await db.execute("""
                    UPDATE jobs 
                    SET status = 'completed', result_summary = ?, error = ?, finished_at = ?, result_path = ?
                    WHERE id = ?
                """, (out_text[:100], err_text, time.time(), file_path, job_id))
                await db.commit()
                
                summary = f"✅ Job `{job_id}` completed.\n*Command:* `{command}`"
                
                from telegram.constants import ParseMode
                if len(out_text) > 2000 or len(err_text) > 1000:
                    await app_or_bot.bot.send_message(chat_id=chat_id, text=summary, parse_mode=ParseMode.MARKDOWN)
                    with open(file_path, "rb") as doc:
                        await app_or_bot.bot.send_document(chat_id=chat_id, document=doc, filename=f"job_{job_id}.txt")
                else:
                    out_snippet = out_text[:1000]
                    err_snippet = err_text[:500]
                    msg = summary + f"\n\n*Output:*\n```\n{out_snippet}\n```"
                    if err_snippet:
                        msg += f"\n*Errors:*\n```\n{err_snippet}\n```"
                    await app_or_bot.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)
                
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            await db.execute("""
                UPDATE jobs 
                SET status = 'failed', error = ?, finished_at = ?
                WHERE id = ?
            """, (str(e), time.time(), job_id))
            await db.commit()
            from telegram.constants import ParseMode
            await app_or_bot.bot.send_message(chat_id=chat_id, text=f"❌ Job `{job_id}` failed: {e}", parse_mode=ParseMode.MARKDOWN)
            
        finally:
            ACTIVE_PROCESSES.pop(job_id, None)
            JOB_QUEUE.task_done()
