from fastapi import APIRouter
from utils.response import success

router = APIRouter()

@router.get("/hello", summary="测试接口")
async def test_hello():
    """
    一个简单的测试接口，返回成功响应。
    """
    return success(data={"message": "AI Report API 运行正常！"})

@router.get("/status", summary="查看状态")
async def test_status():
    """
    返回 API 状态。
    """
    return success(data={"status": "online", "version": "1.0.0"})

@router.get("/test_custom_sql", summary="测试自定义原生SQL执行")
async def test_custom_sql(book_name: str = "test"):
    """
    这是一个示例接口，演示如何使用 db_client 执行自定义原生 SQL，
    并自动处理字典键名为小写。
    """
    try:
        from sqlalchemy import text
        
        custom_sql = text("""
            SELECT ID AS id, BOOK_NAME AS bookName, AUTHOR AS author, PUBLISHER AS publisher
            FROM BOOK_COLLECTION 
            WHERE BOOK_NAME LIKE :bookName AND REMOVED = 0
            ORDER BY CREATE_TIME DESC
            LIMIT 5
        """)
        
        params = {"bookName": f"%{book_name}%"}
        records = await db_client.fetch_all(custom_sql, params)
        return success(data=records)
    except Exception as e:
        return server_error(f"自定义SQL执行失败: {str(e)}")