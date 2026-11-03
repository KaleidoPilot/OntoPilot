import logging
from typing import Any, Dict, List, Optional, Union
from core.config import yaml_config
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy import text
from sqlalchemy.sql import Executable

logger = logging.getLogger(__name__)

class MySQLClient:
    """
    MySQL 异步数据库操作工具类 (基于 SQLAlchemy AsyncEngine)
    """
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None

    async def init_pool(self, host: str = None, port: int = None, user: str = None, password: str = None, db: str = None, minsize: int = 1, maxsize: int = 10, **kwargs):
        """
        初始化数据库连接池
        如果未传入连接参数，将自动从 config.yaml 中的 database_settings 读取配置
        建议在 FastAPI 的 lifespan 或 startup 事件中调用
        """
        try:
            # 自动从 config.yaml 读取配置
            db_settings = yaml_config.get("database_settings", {})
            db_type = db_settings.get("db_type", "mysql")
            
            if db_type == "mysql":
                mysql_config = db_settings.get("mysql", {})
                host = host or mysql_config.get("host", "127.0.0.1")
                port = port or mysql_config.get("port", 3306)
                user = user or mysql_config.get("user", "root")
                password = password or mysql_config.get("password", "")
                db = db or mysql_config.get("db", "")
                minsize = mysql_config.get("minsize", minsize)
                maxsize = mysql_config.get("maxsize", maxsize)
            
            # 构建 SQLAlchemy 异步连接 URL (使用 aiomysql 驱动)
            url = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{db}"
            
            self.engine = create_async_engine(
                url,
                pool_size=minsize,
                max_overflow=maxsize - minsize,
                echo=False,  # 如果需要 SQLAlchemy 自动打印 SQL，可设置为 True
                **kwargs
            )
            logger.info("MySQL connection pool initialized successfully via SQLAlchemy.")
        except Exception as e:
            logger.error(f"Failed to initialize MySQL pool: {e}")
            raise e

    async def close_pool(self):
        """
        关闭数据库连接池
        建议在 FastAPI 的 lifespan 或 shutdown 事件中调用
        """
        if self.engine:
            await self.engine.dispose()
            logger.info("MySQL connection pool closed.")

    def _get_executable_sql(self, query: Union[str, Executable]) -> str:
        """
        尝试将 SQLAlchemy 的查询对象转换为带有字面量参数的可执行 SQL 字符串，方便日志查看
        """
        if isinstance(query, str):
            return query
        try:
            # 使用 mysql 方言进行编译，并将参数直接绑定到 SQL 字符串中
            from sqlalchemy.dialects import mysql
            compiled_sql = query.compile(
                dialect=mysql.dialect(),
                compile_kwargs={"literal_binds": True}
            )
            return str(compiled_sql)
        except Exception:
            return str(query)

    async def fetch_one(self, query: Union[str, Executable], args: dict = None) -> Optional[Dict[str, Any]]:
        """
        执行查询并返回单条记录
        """
        if not self.engine:
            raise RuntimeError("MySQL engine is not initialized")
            
        sql_str = self._get_executable_sql(query)
        if isinstance(query, str):
            query = text(query)
            
        logger.info(f"Executing SQL:\n{sql_str}")
        if args:
            logger.info(f"Args: {args}")
            
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(query, args or {})
                row = result.mappings().fetchone()
                if row:
                    # 动态检查 query 中的 label 并进行映射
                    keys_map = {}
                    if hasattr(query, 'selected_columns'):
                        for col in query.selected_columns:
                            keys_map[col.name] = col.key
                    
                    return {keys_map.get(k, k): v for k, v in row.items()}
                return None
        except Exception as e:
            logger.error(f"SQL Execution Error: {e}\nFailed SQL:\n{sql_str}")
            raise e

    async def fetch_all(self, query: Union[str, Executable], args: dict = None) -> List[Dict[str, Any]]:
        """
        执行查询并返回多条记录
        """
        if not self.engine:
            raise RuntimeError("MySQL engine is not initialized")
            
        sql_str = self._get_executable_sql(query)
        if isinstance(query, str):
            query = text(query)
            
        logger.info(f"Executing SQL:\n{sql_str}")
        if args:
            logger.info(f"Args: {args}")
            
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(query, args or {})
                
                # 动态检查 query 中的 label 并进行映射
                keys_map = {}
                if hasattr(query, 'selected_columns'):
                    for col in query.selected_columns:
                        keys_map[col.name] = col.key

                return [{keys_map.get(k, k): v for k, v in row.items()} for row in result.mappings().fetchall()]
        except Exception as e:
            logger.error(f"SQL Execution Error: {e}\nFailed SQL:\n{sql_str}")
            raise e

    async def execute(self, query: Union[str, Executable], args: dict = None) -> int:
        """
        执行 INSERT/UPDATE/DELETE 等语句，返回受影响的行数
        """
        if not self.engine:
            raise RuntimeError("MySQL engine is not initialized")
            
        sql_str = self._get_executable_sql(query)
        if isinstance(query, str):
            query = text(query)
            
        logger.info(f"Executing SQL:\n{sql_str}")
        if args:
            logger.info(f"Args: {args}")
            
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(query, args or {})
                return result.rowcount
        except Exception as e:
            logger.error(f"SQL Execution Error: {e}\nFailed SQL:\n{sql_str}")
            raise e

    async def execute_insert(self, query: Union[str, Executable], args: dict = None) -> int:
        """
        执行 INSERT 语句，返回插入的最后一条记录的主键 ID
        """
        if not self.engine:
            raise RuntimeError("MySQL engine is not initialized")
            
        sql_str = self._get_executable_sql(query)
        if isinstance(query, str):
            query = text(query)
            
        logger.info(f"Executing SQL:\n{sql_str}")
        if args:
            logger.info(f"Args: {args}")
            
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(query, args or {})
                return result.lastrowid
        except Exception as e:
            logger.error(f"SQL Execution Error: {e}\nFailed SQL:\n{sql_str}")
            raise e

# 全局数据库客户端实例
db_client = MySQLClient()
