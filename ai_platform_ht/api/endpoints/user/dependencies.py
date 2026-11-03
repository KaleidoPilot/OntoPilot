from typing import Any

from fastapi import HTTPException, Request

from api.endpoints.user.sql import get_user_sql
from utils.context import get_current_user
from utils.mysqldb import db_client


async def validate_internal_identity(record: dict[str, Any]) -> dict[str, Any]:
    """管理员等级及所属公司只读取数据库，不能由登录请求指定。"""
    if record.get('deptLevel') not in (0, 1):
        raise HTTPException(403, '管理员等级配置不正确，请联系管理员')
    if record['deptLevel'] == 0:
        return record
    org_id = record.get('orgId')
    if not isinstance(org_id, int) or org_id <= 0:
        raise HTTPException(403, '企业管理员尚未绑定公司，请联系管理员')
    from api.endpoints.organization.sql import get_organization_sql
    org = await db_client.fetch_one(get_organization_sql('organization.find_active_by_id'), {'id': org_id})
    if not org:
        raise HTTPException(403, '所属公司不存在或已停用')
    return {**record, 'orgCode': org['orgCode'], 'orgName': org['name']}


async def require_super_administrator(identity: dict[str, Any]) -> dict[str, Any]:
    if identity.get('userType') != 'internal' or identity.get('deptLevel') != 0:
        raise HTTPException(403, '仅最高权限管理员可执行此操作')
    return identity


def read_session_claims(request: Request) -> dict[str, Any]:
    base_user = get_current_user(request)
    # 复用密码登录已有的签名凭证，禁止通过请求头冒充最高权限管理员。
    import json
    from cryptography.fernet import InvalidToken
    from api.endpoints.mcp.service import cipher
    try:
        payload = json.loads(cipher().decrypt(request.headers.get('x-mcp-token', '').encode(), ttl=86400))
        if not isinstance(payload, dict):
            raise ValueError()
        user_id = int(payload['id'])
        user_type = payload.get('userType', 'external')
        if payload.get('purpose') != 'personal-mcp' or user_type not in ('internal', 'external') or user_id <= 0:
            raise ValueError()
    except (InvalidToken, ValueError, TypeError, KeyError):
        raise HTTPException(401, '登录状态已失效，请重新登录') from None
    if request.headers.get('x-user-id') and base_user['id'] != user_id:
        raise HTTPException(403, '用户身份不一致')
    if request.headers.get('x-user-type') and request.headers['x-user-type'].strip().lower() != user_type:
        raise HTTPException(403, '用户身份不一致')
    return {**payload, 'id': user_id, 'userType': user_type}


async def get_platform_identity(request: Request) -> dict[str, Any]:
    claims = read_session_claims(request)
    user_id, user_type = claims['id'], claims['userType']
    if user_type == "external":
        record = await db_client.fetch_one(
            get_user_sql("identity.external_by_id"),
            {"id": user_id},
        )
        if not record:
            raise HTTPException(status_code=401, detail="外部用户不存在或已停用")
        return {**record, "name": record["realName"], "userType": "external"}

    record = await db_client.fetch_one(
        get_user_sql("identity.internal_by_id"),
        {"id": user_id},
    )
    if not record:
        raise HTTPException(status_code=401, detail="内部用户不存在或已停用")
    record = await validate_internal_identity(record)
    return {**record, "name": record["realName"], "userType": "internal"}


async def get_super_administrator(request: Request) -> dict[str, Any]:
    return await require_super_administrator(await get_platform_identity(request))
