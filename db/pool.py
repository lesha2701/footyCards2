import asyncpg

pool = None

async def create_db_pool():
    global pool
    pool = await asyncpg.create_pool(
        user='gen_user',
        password='eoAxgddEC#44tL',
        database='default_db',
        host='195.58.34.254',
        port=5432
    )
    return pool


async def get_db_pool():
    return pool

async def close_db_pool():
    if pool:
        await pool.close()