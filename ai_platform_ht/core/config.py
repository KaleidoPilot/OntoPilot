# app/core/config.py
import os
import yaml
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 核心配置：根据APP_ENV自动加载对应的.env文件
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,  # 忽略环境变量大小写
    )

    # ========== 基础配置 ==========
    app_name: str = "AI Report API"
    app_env: str = Field(default="test", pattern="^(test|prod)$")  # 仅允许2种环境
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True


    # ========== 日志配置 ==========
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_file: str = "app.log"
    template_lightrag_python: str | None = None

    # 自定义属性：判断是否为生产环境
    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"

# 核心逻辑：根据APP_ENV环境变量，加载对应的.env文件
def load_settings() -> Settings:
    # 获取APP_ENV（默认test）
    app_env = os.getenv("APP_ENV", "test")
    # 拼接对应环境的.env文件路径
    env_file = f".env.{app_env}"
    
    # 校验文件是否存在，如果不存在则使用默认值
    if os.path.exists(env_file):
        settings = Settings(_env_file=env_file)
    else:
        # 如果环境配置文件不存在，则直接加载默认值
        settings = Settings()
    return settings

# 全局配置实例（项目中直接导入使用）
settings = load_settings()

def load_yaml_config() -> dict:
    """加载 config.yaml 配置文件"""
    yaml_path = Path(__file__).parent.parent / "config.yaml"
    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def save_yaml_config(config: dict):
    """保存配置到 config.yaml"""
    global yaml_config
    yaml_path = Path(__file__).parent.parent / "config.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)
    # 更新内存中的配置
    yaml_config.clear()
    yaml_config.update(config)

yaml_config = load_yaml_config()
