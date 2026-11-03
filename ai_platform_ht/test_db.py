import asyncio
import sys
sys.path.append('d:/project/python/ai_platform/ai_platform_ht')
from utils.mysqldb import db_client
async def run():
    res = await db_client.fetch_all('SHOW COLUMNS FROM AI_AGENT')
    print([dict(r) for r in res])
asyncio.run(run())
