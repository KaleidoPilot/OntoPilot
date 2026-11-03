import sys
import asyncio
import logging
logging.basicConfig(level=logging.INFO)
sys.path.append('d:/project/ai/ttxz/ttxz-ht')

from api.endpoints.user.api.userApi import login, LoginRequest
from utils.mysqldb import db_client

async def main():
    await db_client.init_pool()
    req = LoginRequest(username='admin', password='admin123')
    res = await login(req)
    print("SUCCESS")
    print(res.body.decode('utf-8'))
    await db_client.close_pool()

if __name__ == '__main__':
    asyncio.run(main())
