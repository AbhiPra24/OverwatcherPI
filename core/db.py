"""Shared asyncpg connection pool for the bot process.

Replaces DatabaseManager's aiosqlite-per-process-singleton pattern with a
pooled set of Postgres connections, initialized once at startup and reused
everywhere via get_pool().
"""

import logging

import asyncpg

from config import config

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool():
    global _pool
    if _pool is not None:
        return _pool
    dsn = config.database_url.get_secret_value()
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set in .env")
    logger.info("Initializing Supabase connection pool...")
    _pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)
    logger.info("Supabase connection pool ready.")
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Connection pool not initialized — call init_pool() first")
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
