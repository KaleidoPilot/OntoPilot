"""知识库使用范围。知识库 ID 是 AI_TENANT.ID；1/2/3 只表示类型。"""

from typing import Any

COMPANY_PUBLIC = 1
COMPANY_PRIVATE = 2
PERSONAL = 3
COMPANY_SCOPE_TYPES = (COMPANY_PUBLIC, COMPANY_PRIVATE)
MAX_GRANT_IDS = 100


def parse_id_list(value: Any) -> list[int]:
    if value is None or value == "":
        return []
    parts = value if isinstance(value, list) else str(value).split(",")
    parsed: list[int] = []
    for part in parts:
        text = str(part).strip()
        if not text:
            continue
        if not text.isdigit():
            raise ValueError("授权 ID 必须是正整数")
        number = int(text)
        if number <= 0 or number in parsed:
            continue
        parsed.append(number)
    if len(parsed) > MAX_GRANT_IDS:
        raise ValueError(f"授权数量不能超过 {MAX_GRANT_IDS}")
    return parsed


def join_ids(value: Any) -> str | None:
    parsed = parse_id_list(value)
    return ",".join(str(item) for item in parsed) or None


def actor_from_scope(scope: dict[str, Any]) -> dict[str, Any]:
    identity = scope.get("identity") if isinstance(scope, dict) else None
    if not isinstance(identity, dict):
        raise ValueError("缺少登录身份")
    user_type = identity.get("userType")
    if user_type not in ("internal", "external"):
        raise ValueError("登录身份无效")
    try:
        org_id = int(scope.get("orgId", identity.get("orgId")))
        raw_user_id = identity.get("actorId") if user_type == "internal" and identity.get("actorId") else identity.get("id")
        user_id = int(raw_user_id)
    except (TypeError, ValueError) as error:
        raise ValueError("登录身份无效") from error
    if org_id <= 0 or user_id <= 0:
        raise ValueError("登录身份无效")
    group_id = identity.get("groupId")
    try:
        group_id = int(group_id) if group_id else 0
    except (TypeError, ValueError) as error:
        raise ValueError("登录身份无效") from error
    return {
        "id": user_id,
        "name": identity.get("name") or identity.get("realName") or "",
        "userType": user_type,
        "orgId": org_id,
        "groupId": group_id,
    }


def _same_company(tenant: dict[str, Any], actor: dict[str, Any]) -> bool:
    try:
        org_id = int(tenant.get("orgId") or 0)
        removed = int(tenant.get("removed") or 0)
        scope_type = int(tenant.get("scopeType") or 0)
    except (TypeError, ValueError):
        return False
    return org_id == actor["orgId"] and removed == 0 and scope_type in (COMPANY_PUBLIC, COMPANY_PRIVATE, PERSONAL)


def can_use_tenant(tenant: dict[str, Any], actor: dict[str, Any]) -> bool:
    """当前用户能否在检索和聊天中使用这个已启用的知识库。"""
    if not _same_company(tenant, actor) or int(tenant.get("enabled") or 0) != 1:
        return False
    scope_type = int(tenant["scopeType"])
    if scope_type == COMPANY_PUBLIC:
        return True
    if scope_type == COMPANY_PRIVATE:
        if actor["userType"] == "internal":
            return True
        users = parse_id_list(tenant.get("accessUserIds"))
        groups = parse_id_list(tenant.get("accessGroupIds"))
        return actor["id"] in users or (actor["groupId"] > 0 and actor["groupId"] in groups)
    return actor["userType"] == "external" and int(tenant.get("ownerUserId") or 0) == actor["id"]


def can_manage_tenant(tenant: dict[str, Any], actor: dict[str, Any]) -> bool:
    """内部管理员维护公司库；外部用户只能维护自己创建的个人库。"""
    if not _same_company(tenant, actor):
        return False
    scope_type = int(tenant["scopeType"])
    if actor["userType"] == "internal":
        return scope_type in COMPANY_SCOPE_TYPES
    return scope_type == PERSONAL and int(tenant.get("ownerUserId") or 0) == actor["id"]


def can_read_tenant(tenant: dict[str, Any], actor: dict[str, Any]) -> bool:
    """查看正文和下载文件。管理员可查看停用的公司库，使用者只能查看有权使用的库。"""
    return can_manage_tenant(tenant, actor) or can_use_tenant(tenant, actor)
