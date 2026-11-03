from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=64)
def get_mcp_sql(key: str) -> str:
    value = yaml.safe_load(Path(__file__).with_name("sql.yaml").read_text(encoding="utf-8"))
    for part in key.split("."):
        value = value[part]
    if not isinstance(value, str):
        raise ValueError("无效的 MCP SQL 键")
    return value
