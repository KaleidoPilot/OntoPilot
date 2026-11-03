import logging

from fastapi import APIRouter, Depends, HTTPException

from api.endpoints.organization.modular.organization import (
    OrganizationCreate,
    OrganizationDelete,
    OrganizationQuery,
    OrganizationUpdate,
)
from api.endpoints.organization.sql import get_organization_sql
from api.endpoints.user.dependencies import get_platform_identity, require_super_administrator
from utils.context import fill_audit_fields
from utils.mysqldb import db_client
from utils.response import bad_request, server_error, success


router = APIRouter()
logger = logging.getLogger(__name__)


def _require_internal(identity: dict) -> bool:
    return identity.get("userType") == "internal"


def _check_company_access(identity: dict, org_id: int):
    if identity.get('deptLevel') == 1 and identity.get('orgId') != org_id:
        raise HTTPException(403, '只能管理所属公司')


@router.post("/querylist", summary="分页查询公司")
async def query_organizations(
    query: OrganizationQuery,
    identity: dict = Depends(get_platform_identity),
):
    if not _require_internal(identity):
        return bad_request(message="仅内部管理员可管理公司")
    try:
        filters = {"keyword": query.keyword, "enabled": query.enabled,
                   "orgId": identity.get('orgId') if identity.get('deptLevel') == 1 else None}
        count = await db_client.fetch_one(
            get_organization_sql("organization.count"), filters
        )
        rows = await db_client.fetch_all(
            get_organization_sql("organization.list"),
            {
                **filters,
                "limit": query.pageSize,
                "offset": (query.pageNo - 1) * query.pageSize,
            },
        )
        return success(data={
            "list": rows,
            "total": int(count.get("total", 0)) if count else 0,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize,
        })
    except Exception:
        logger.exception("查询公司失败")
        return server_error("查询公司失败")


@router.get("/options", summary="查询启用公司选项")
async def query_organization_options(
    identity: dict = Depends(get_platform_identity),
):
    if not _require_internal(identity):
        return bad_request(message="仅内部管理员可查询公司")
    try:
        if identity.get('deptLevel') == 1:
            row = await db_client.fetch_one(get_organization_sql('organization.find_active_by_id'), {'id': identity['orgId']})
            rows = [row] if row else []
        else:
            rows = await db_client.fetch_all(get_organization_sql("organization.options"))
        return success(data={"list": rows})
    except Exception:
        logger.exception("查询公司选项失败")
        return server_error("查询公司选项失败")


@router.post("/insert", summary="新增公司")
async def create_organization(
    data: OrganizationCreate,
    identity: dict = Depends(get_platform_identity),
):
    if not _require_internal(identity):
        return bad_request(message="仅内部管理员可新增公司")
    await require_super_administrator(identity)
    try:
        duplicate = await db_client.fetch_one(
            get_organization_sql("organization.find_by_code"),
            {"orgCode": data.orgCode, "excludeId": 0},
        )
        if duplicate:
            return bad_request(message="公司编码已存在")
        params = fill_audit_fields(data.model_dump(), identity, is_update=False)
        org_id = await db_client.execute_insert(
            get_organization_sql("organization.insert"), params
        )
        row = await db_client.fetch_one(
            get_organization_sql("organization.find_by_id"), {"id": org_id}
        )
        return success(data=row, message="公司新增成功")
    except Exception:
        logger.exception("新增公司失败")
        return server_error("新增公司失败")


@router.post("/update", summary="修改公司")
async def update_organization(
    data: OrganizationUpdate,
    identity: dict = Depends(get_platform_identity),
):
    if not _require_internal(identity):
        return bad_request(message="仅内部管理员可修改公司")
    _check_company_access(identity, data.id)
    try:
        existing = await db_client.fetch_one(
            get_organization_sql("organization.find_by_id"), {"id": data.id}
        )
        if not existing:
            return bad_request(message="公司不存在")
        duplicate = await db_client.fetch_one(
            get_organization_sql("organization.find_by_code"),
            {"orgCode": data.orgCode or existing["orgCode"], "excludeId": data.id},
        )
        if duplicate:
            return bad_request(message="公司编码已存在")
        params = fill_audit_fields(data.model_dump(), identity, is_update=True)
        affected = await db_client.execute(
            get_organization_sql("organization.update"), params
        )
        if affected != 1:
            return bad_request(message="公司数据已发生变化，请刷新后重试")
        row = await db_client.fetch_one(
            get_organization_sql("organization.find_by_id"), {"id": data.id}
        )
        return success(data=row, message="公司修改成功")
    except Exception:
        logger.exception("修改公司失败")
        return server_error("修改公司失败")


@router.post("/delete", summary="物理删除空公司")
async def delete_organization(
    data: OrganizationDelete,
    identity: dict = Depends(get_platform_identity),
):
    if not _require_internal(identity):
        return bad_request(message="仅内部管理员可删除公司")
    _check_company_access(identity, data.id)
    try:
        existing = await db_client.fetch_one(
            get_organization_sql("organization.find_by_id"), {"id": data.id}
        )
        if not existing:
            return bad_request(message="公司不存在")
        counts = await db_client.fetch_one(
            get_organization_sql("organization.reference_counts"), {"id": data.id}
        ) or {}
        if any(int(value or 0) > 0 for value in counts.values()):
            return bad_request(message="公司仍有关联数据，不能删除")
        affected = await db_client.execute(
            get_organization_sql("organization.delete"), {"id": data.id}
        )
        if affected != 1:
            return bad_request(message="公司数据已发生变化，请刷新后重试")
        return success(message="公司删除成功")
    except Exception:
        logger.exception("删除公司失败")
        return server_error("删除公司失败")
