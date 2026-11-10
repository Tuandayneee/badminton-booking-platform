import logging
import os

import asyncpg
import redis.asyncio as redis

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


class Database:
    pg_pool = None
    redis_client = None

    @classmethod
    async def connect(cls):
        cls.pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
        logger.info("FastAPI connected to PostgreSQL")
        cls.redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        logger.info("FastAPI connected to Redis")

    @classmethod
    async def disconnect(cls):
        if cls.pg_pool is not None:
            await cls.pg_pool.close()
        if cls.redis_client is not None:
            await cls.redis_client.close()
        logger.info("FastAPI disconnected from DBs")


db = Database()
