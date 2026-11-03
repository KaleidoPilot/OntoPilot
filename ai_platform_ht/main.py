import uvicorn
import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api.router import router as api_router
from utils.mysqldb import db_client
from api.endpoints.skill.template_service import TemplateSkillService, active_company_owner

# 日志：控制台在导入期配置；文件日志在 lifespan 中挂载。
# 模板检索、沙箱重试这类排查信息只打控制台很容易丢，落一份文件便于回溯。
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
log_dir = Path(__file__).resolve().parent / "logs"
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def _enable_file_logging() -> None:
    """由实际服务进程挂载 logs/app.log 文件日志。

    uvicorn 在 reload 模式下会启动父进程（文件监听）与子进程（实际服务），
    两者都会 import 本模块。如果两边各自打开同一个日志文件，Windows 下
    轮转时的 os.rename 会因文件被另一进程占用而失败（WinError 32），
    且之后每条日志都会重试轮转、持续刷同样的错误。
    放到 lifespan 中执行，可确保只有实际服务进程持有该文件。
    """
    root = logging.getLogger()
    if any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(file_handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 文件日志只在真正服务的进程里挂载，避免 reload 父子进程争抢同一个日志文件
    _enable_file_logging()
    # Startup: Initialize database connection pool
    await db_client.init_pool()
    service = TemplateSkillService()
    app.state.template_skills = service
    company_service = TemplateSkillService(scope='company',identity_checker=active_company_owner)
    app.state.company_template_skills = company_service
    try:
        await service.start()
        await company_service.start()
        yield
    finally:
        from api.endpoints.knowledge.api.knowledgeApi import tenant_graphs
        await tenant_graphs.stop()
        await service.stop()
        await company_service.stop()
        await db_client.close_pool()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="AI Report Generation API",
        version="1.0.0",
        debug=settings.debug,
        lifespan=lifespan
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有域名跨域
        allow_credentials=True,
        allow_methods=["*"],  # 允许所有方法
        allow_headers=["*"],  # 允许所有 Header
        expose_headers=["Content-Disposition"],
    )

    # Include the router
    app.include_router(api_router, prefix="/fijoAi", tags=["core"])

    @app.get("/")
    async def root():
        return {
            "message": f"Welcome to {settings.app_name}",
            "env": settings.app_env,
            "docs": "/docs"
        }

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug
    )
