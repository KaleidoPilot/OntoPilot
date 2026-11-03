from pathlib import Path
from typing import Any

import yaml


SQL_CONFIG_PATH = Path(__file__).with_name("sql.yaml")


def get_organization_sql(key: str) -> str:
    with SQL_CONFIG_PATH.open("r", encoding="utf-8") as file:
        value: Any = yaml.safe_load(file) or {}
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(f"SQL key not found: {key}")
        value = value[part]
    if not isinstance(value, str) or not value.strip():
        raise KeyError(f"SQL key does not point to a statement: {key}")
    return value.strip()
