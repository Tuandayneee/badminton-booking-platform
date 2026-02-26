import os
import asyncpg
import redis.asyncio as redis


DATABASE_URL = os.getenv("DATABASE_URL", "")
REDIS_URL = os.getenv("REDIS_URL","redis://redis:6379/0")

class Database:
    pg_pool = None
    redis_client = None

    @classmethod
    async def connect(cls):
        cls.pg_pool = await asyncpg.create_pool(DATABASE_URL,min_size = 5, max_size = 20)
        print("FastAPI: Connected to PostgreSQL")
        cls.redis_client = redis.from_url(REDIS_URL,encoding="utf-8", decode_responses=True)
        print("FastAPI: Connected to Redis")

    @classmethod
    async def disconnect(cls):
        await cls.pg_pool.close()
        await cls.redis_client.close()
        print("FastAPI: Disconnected DBs")

db = Database()
