import asyncio
import sys
sys.path.append('d:/project/python/ai_platform/ai_platform_ht')
from utils.mysqldb import db_client
async def run():
    await db_client.init_pool()
    res = await db_client.fetch_all('SHOW COLUMNS FROM SKILL')
    print([dict(r) for r in res])
asyncio.run(run())
