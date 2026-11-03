import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from api.endpoints.system.sql import get_system_sql
from utils.mysqldb import db_client


@dataclass(frozen=True)
class CompanyRuntimeConfig:
    database: dict[str, Any]
    models: dict[str, Any]
    vector: dict[str, Any]
    sandbox: dict[str, Any]


def _decode_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    decoded = json.loads(value or "{}")
    if not isinstance(decoded, dict):
        raise ValueError("公司系统配置必须是JSON对象")
    return decoded


async def get_company_runtime_config(org_id: int) -> CompanyRuntimeConfig:
    rows = await db_client.fetch_all(
        get_system_sql("system_config.list_active"), {"orgId": org_id}
    )
    by_type: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_type.setdefault(int(row["configType"]), []).append(row)

    def select(config_type: int, preferred_name: str) -> dict[str, Any]:
        candidates = by_type.get(config_type, [])
        preferred = next(
            (row for row in candidates if row.get("configName") == preferred_name),
            None,
        )
        return _decode_json((preferred or (candidates[0] if candidates else {})).get("configJson"))

    return CompanyRuntimeConfig(
        database=select(1, "平台业务数据库"),
        models=select(2, "运行时AI模型"),
        vector=select(3, "知识库向量库"),
        sandbox=select(4, "默认沙箱"),
    )


def validate_sandbox_config(value: dict[str, Any], *, require_database: bool = False) -> dict[str, Any]:
    """数据库凭据只用于沙箱内建连，不交给模型或平台直连。"""
    if set(value) - {"url", "token", "database", "name"}:
        raise ValueError("沙箱配置只支持名称、URL、Token 和数据库连接")
    url = value.get("url")
    token = value.get("token", "")
    if token is None:
        token = ""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("请填写沙箱 URL")
    if not isinstance(token, str):
        raise ValueError("沙箱 Token 必须是字符串")
    url = url.strip().rstrip("/")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ValueError("沙箱 URL 格式不正确") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in url)
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("沙箱 URL 必须是 HTTP(S) 服务地址，不能包含账号、Token、查询参数或锚点")
    if any(char in token for char in "\r\n") or token.strip() == "******":
        raise ValueError("请填写有效的沙箱 Token")
    result = {"url": url, "token": token.strip()}
    if "name" in value:
        name = value["name"]
        if not isinstance(name, str) or len(name.strip()) > 100:
            raise ValueError("沙箱名称最多 100 个字符")
        result["name"] = name.strip()
    database = value.get("database")
    if database is None and not require_database:
        return result
    if not isinstance(database, dict):
        raise ValueError("请配置沙箱对应的数据库连接")
    if set(database) - {"host", "port", "username", "password", "database"}:
        raise ValueError("数据库连接包含不支持的配置项")
    normalized = {}
    # 兼容旧配置中的 database 库名，但不再用它限制连接；库名由项目首次导入确定。
    for key, label in (("host", "数据库地址"), ("username", "数据库账号")):
        field = database.get(key)
        if not isinstance(field, str) or not field.strip() or any(c in field for c in '\r\n\x00'):
            raise ValueError(f"请填写有效的{label}")
        normalized[key] = field.strip()
    port = database.get("port", 3306)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("数据库端口必须为 1—65535 的整数")
    password = database.get("password")
    if not isinstance(password, str) or not password or password == "******":
        raise ValueError("请填写数据库密码")
    normalized.update(port=port, password=password)
    result["database"] = normalized
    return result


async def get_company_sandbox_config(org_id: int, config_id: int | None) -> dict[str, str]:
    if not config_id:
        raise ValueError("项目组尚未绑定沙箱，请先编辑一级项目组并选择沙箱")
    record = await db_client.fetch_one(
        get_system_sql("system_config.find_by_id"), {"id": config_id, "orgId": org_id}
    )
    if not record or int(record["configType"]) != 4:
        raise ValueError("所选沙箱不存在或不属于当前公司")
    if int(record["enabled"]) != 1:
        raise ValueError("所选沙箱已停用，请先启用或选择其他沙箱")
    return validate_sandbox_config(_decode_json(record["configJson"]))
