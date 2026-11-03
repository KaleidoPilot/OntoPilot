from typing import Any

from fastapi import Depends, HTTPException, Request

from api.endpoints.organization.sql import get_organization_sql
from api.endpoints.user.dependencies import get_platform_identity
from utils.mysqldb import db_client


async def get_organization_scope(
    request: Request,
    identity: dict[str, Any] = Depends(get_platform_identity),
) -> dict[str, Any]:
    if identity.get("userType") == "external" or identity.get('deptLevel') == 1:
        raw_org_id = identity.get("orgId")
    else:
        raw_org_id = request.headers.get("x-org-id")

    try:
        org_id = int(raw_org_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="请先选择公司") from None
    if org_id <= 0:
        raise HTTPException(status_code=400, detail="公司ID不正确")

    organization = await db_client.fetch_one(
        get_organization_sql("organization.find_active_by_id"),
        {"id": org_id},
    )
    if not organization:
        raise HTTPException(status_code=403, detail="公司不存在或已停用")
    return {**organization, "orgId": org_id, "identity": identity}


async def get_internal_organization_scope(
    scope: dict[str, Any] = Depends(get_organization_scope),
) -> dict[str, Any]:
    if scope["identity"].get("userType") != "internal":
        raise HTTPException(status_code=403, detail="仅内部管理员可执行此操作")
    return scope
