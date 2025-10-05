import asyncpg

pool = None

async def create_db_pool():
    global pool
    pool = await asyncpg.create_pool(
        user='postgres',
        password='root',
        database='footycards2',
        host='localhost',
        port=5432
    )
    return pool


async def get_db_pool():
    return pool

async def close_db_pool():
    if pool:
        await pool.close()