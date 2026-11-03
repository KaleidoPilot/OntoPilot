import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from utils.response import success, server_error, bad_request
from utils.mysqldb import db_client
from utils.context import fill_audit_fields
from utils.crypto import get_password_hash, verify_password
from pydantic import BaseModel
from api.endpoints.user.modular.user import (
    CompanyAdministratorCreate, CompanyAdministratorQuery, CompanyAdministratorUpdate,
    ExternalUserGroupCreate,
    ExternalUserGroupDelete,
    ExternalUserGroupQuery,
    ExternalUserGroupUpdate,
    ExternalUserBatchDelete,
    ExternalUserChangePassword,
    ExternalUserCreate,
    ExternalUserDelete,
    ExternalUserQuery,
    ExternalUserResetPassword,
    ExternalUserUpdate,
    UserResponse, UserQueryRequest, UserCreate, UserUpdate,
)
from api.endpoints.user.dependencies import get_platform_identity, validate_internal_identity, require_super_administrator, get_super_administrator
from api.endpoints.organization.sql import get_organization_sql
from api.endpoints.organization.dependencies import get_organization_scope
from api.endpoints.user.sql import get_user_sql

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/me', summary='读取当前登录账号的实时身份与权限')
async def current_user(identity: dict = Depends(get_platform_identity)):
    return success(data=identity)


def _is_internal(identity: dict) -> bool:
    return _scope_identity(identity).get("userType") == "internal"


def _scope_identity(scope: dict) -> dict:
    if not isinstance(scope, dict):
        return {"id": 1, "name": "admin", "userType": "internal"}
    return scope.get("identity", scope)


def _scope_org_id(scope: dict) -> int:
    return int(scope.get("orgId", 1)) if isinstance(scope, dict) else 1

class DeleteRequest(BaseModel):
    id: int

class LoginRequest(BaseModel):
    username: str
    password: str


async def _external_account_exists(account: str, *, exclude_id: int = 0) -> bool:
    internal = await db_client.fetch_one(
        get_user_sql("external_user.find_internal_account"), {"account": account}
    )
    if internal:
        return True
    external = await db_client.fetch_one(
        get_user_sql("external_user.find_external_account"),
        {"account": account, "excludeId": exclude_id},
    )
    return external is not None


async def _group_agents_valid(agent_ids: str, org_id: int) -> bool:
    rows = await db_client.fetch_all(
        get_user_sql("user_group.find_agents"),
        {"agentIds": agent_ids, "orgId": org_id},
    )
    return {int(row["id"]) for row in rows} == {int(value) for value in agent_ids.split(",")}


@router.get("/external/agents", summary="查询当前外部用户实时可用的智能体")
async def query_external_user_agents(identity: dict = Depends(get_platform_identity)):
    if identity.get("userType") != "external":
        return bad_request(message="仅外部用户可查询组内智能体")
    try:
        rows = await db_client.fetch_all(
            get_user_sql("user_group.external_agents"), {"id": identity["id"]},
        )
        return success(data={"list": rows})
    except Exception:
        logger.exception("查询组内智能体失败")
        return server_error("组内智能体加载失败")


async def _delete_external_users_transaction(
    user_ids: list[int], org_id: int = 1
) -> dict[str, int]:
    if not db_client.engine:
        raise RuntimeError("MySQL engine is not initialized")
    deleted_users = 0
    deleted_skills = 0
    deleted_shares = 0
    deleted_libraries = 0
    async with db_client.engine.begin() as connection:
        from api.endpoints.mcp.service import cleanup_user
        await cleanup_user(connection, org_id, user_ids)
        for user_id in user_ids:
            delete_params = {"id": user_id, "orgId": org_id}
            share_result = await connection.execute(
                text(get_user_sql("external_user.delete_shares")), delete_params
            )
            library_result = await connection.execute(
                text(get_user_sql("external_user.delete_libraries")), delete_params
            )
            skill_result = await connection.execute(
                text(get_user_sql("external_user.delete_private_skills")), delete_params
            )
            user_result = await connection.execute(
                text(get_user_sql("external_user.physical_delete")),
                {"id": user_id, "orgId": org_id},
            )
            if user_result.rowcount != 1:
                raise RuntimeError("批量删除用户时数据已发生变化")
            deleted_shares += max(share_result.rowcount, 0)
            deleted_libraries += max(library_result.rowcount, 0)
            deleted_skills += max(skill_result.rowcount, 0)
            deleted_users += user_result.rowcount
    return {
        "deletedUsers": deleted_users,
        "deletedSkills": deleted_skills,
        "deletedShares": deleted_shares,
        "deletedLibraries": deleted_libraries,
    }


async def _insert_external_user_with_password(params: dict) -> int:
    if not db_client.engine:
        raise RuntimeError("MySQL engine is not initialized")
    async with db_client.engine.begin() as connection:
        result = await connection.execute(
            text(get_user_sql("external_user.insert")), params
        )
        if result.lastrowid is None:
            raise RuntimeError("外部用户新增后未返回主键")
        return int(result.lastrowid)


async def _update_external_user_password(params: dict) -> int:
    if not db_client.engine:
        raise RuntimeError("MySQL engine is not initialized")
    async with db_client.engine.begin() as connection:
        result = await connection.execute(
            text(get_user_sql("external_user.reset_password")), params
        )
        return result.rowcount


@router.post("/group/querylist", summary="分页查询外部用户组")
async def query_external_user_groups(
    query: ExternalUserGroupQuery,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可管理用户组")
    try:
        params = {
            "orgId": _scope_org_id(identity),
            "keyword": query.keyword,
            "enabled": query.enabled,
        }
        count_row = await db_client.fetch_one(get_user_sql("user_group.count"), params)
        rows = await db_client.fetch_all(
            get_user_sql("user_group.list"),
            {
                **params,
                "limit": query.pageSize,
                "offset": (query.pageNo - 1) * query.pageSize,
            },
        )
        return success(data={
            "list": rows,
            "total": int(count_row.get("total", 0)) if count_row else 0,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize,
        })
    except Exception:
        logger.exception("查询外部用户组失败")
        return server_error("外部用户组查询失败")


@router.get("/group/options", summary="查询启用的外部用户组选项")
async def query_external_user_group_options(
    includeDisabled: bool = False,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可查询用户组选项")
    try:
        rows = await db_client.fetch_all(
            get_user_sql("user_group.options"), {"orgId": _scope_org_id(identity), 'includeDisabled': int(includeDisabled)}
        )
        return success(data={"list": rows})
    except Exception:
        logger.exception("查询用户组选项失败")
        return server_error("用户组选项查询失败")


@router.get("/group/agent-options", summary="查询可绑定的智能体")
async def query_user_group_agent_options(
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可查询智能体")
    try:
        rows = await db_client.fetch_all(
            get_user_sql("user_group.agent_options"),
            {"orgId": _scope_org_id(identity)},
        )
        return success(data={"list": rows})
    except Exception:
        logger.exception("查询智能体选项失败")
        return server_error("智能体选项查询失败")


@router.post("/group/insert", summary="新增外部用户组")
async def create_external_user_group(
    data: ExternalUserGroupCreate,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可新增用户组")
    try:
        if not await _group_agents_valid(data.agentId, _scope_org_id(identity)):
            return bad_request(message="部分所选智能体不存在、已停用或不属于当前公司")
        duplicate = await db_client.fetch_one(
            get_user_sql("user_group.find_duplicate_name"),
            {
                "orgId": _scope_org_id(identity),
                "groupName": data.groupName,
                "excludeId": 0,
            },
        )
        if duplicate:
            return bad_request(message="已存在同名用户组")
        params = {"orgId": _scope_org_id(identity), **data.model_dump()}
        params = fill_audit_fields(
            params, _scope_identity(identity), is_update=False
        )
        inserted_id = await db_client.execute_insert(
            get_user_sql("user_group.insert"), params
        )
        return success(data={"id": int(inserted_id)}, message="用户组新增成功")
    except Exception:
        logger.exception("新增外部用户组失败")
        return server_error("用户组新增失败")


@router.post("/group/update", summary="修改外部用户组")
async def update_external_user_group(
    data: ExternalUserGroupUpdate,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可修改用户组")
    try:
        existing = await db_client.fetch_one(
            get_user_sql("user_group.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        if not existing:
            return bad_request(message="用户组不存在")
        if not await _group_agents_valid(data.agentId, _scope_org_id(identity)):
            return bad_request(message="部分所选智能体不存在、已停用或不属于当前公司")
        duplicate = await db_client.fetch_one(
            get_user_sql("user_group.find_duplicate_name"),
            {
                "orgId": _scope_org_id(identity),
                "groupName": data.groupName,
                "excludeId": data.id,
            },
        )
        if duplicate:
            return bad_request(message="已存在同名用户组")
        params = {"orgId": _scope_org_id(identity), **data.model_dump()}
        params = fill_audit_fields(params, _scope_identity(identity), is_update=True)
        affected = await db_client.execute(get_user_sql("user_group.update"), params)
        if affected != 1:
            return server_error("用户组修改失败")
        return success(data={"id": data.id}, message="用户组修改成功")
    except Exception:
        logger.exception("修改外部用户组失败")
        return server_error("用户组修改失败")


@router.post("/group/delete", summary="物理删除空用户组")
async def delete_external_user_group(
    data: ExternalUserGroupDelete,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可删除用户组")
    try:
        existing = await db_client.fetch_one(
            get_user_sql("user_group.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        if not existing:
            return bad_request(message="用户组不存在")
        count_row = await db_client.fetch_one(
            get_user_sql("user_group.count_users"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        user_count = int(count_row.get("total", 0)) if count_row else 0
        if user_count:
            return bad_request(message=f"用户组下仍有 {user_count} 名用户，不能删除")
        skill_groups = await db_client.fetch_one(
            get_user_sql('user_group.skill_group_references'), {'id': data.id, 'orgId': _scope_org_id(identity)})
        if int((skill_groups or {}).get('total', 0)):
            return bad_request(message='用户组仍被技能组授权引用，请先在技能管理中解除关联')
        affected = await db_client.execute(
            get_user_sql("user_group.physical_delete"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        if affected != 1:
            return server_error("用户组删除失败")
        return success(data={"id": data.id}, message="用户组删除成功")
    except Exception:
        logger.exception("删除外部用户组失败")
        return server_error("用户组删除失败")


@router.post("/external/querylist", summary="分页查询外部用户")
async def query_external_users(
    query: ExternalUserQuery,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可查询全部外部用户")
    try:
        params = {
            "orgId": _scope_org_id(identity),
            "keyword": query.keyword,
            "groupId": query.groupId,
            "enabled": query.enabled,
        }
        count_row = await db_client.fetch_one(get_user_sql("external_user.count"), params)
        rows = await db_client.fetch_all(
            get_user_sql("external_user.list"),
            {
                **params,
                "limit": query.pageSize,
                "offset": (query.pageNo - 1) * query.pageSize,
            },
        )
        return success(data={
            "list": rows,
            "total": int(count_row.get("total", 0)) if count_row else 0,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize,
        })
    except Exception:
        logger.exception("查询外部用户失败")
        return server_error("外部用户查询失败")


@router.post("/external/insert", summary="新增外部用户")
async def create_external_user(
    data: ExternalUserCreate,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可新增外部用户")
    try:
        group = await db_client.fetch_one(
            get_user_sql("external_user.find_active_group"),
            {"groupId": data.groupId, "orgId": _scope_org_id(identity)},
        )
        if not group:
            return bad_request(message="用户组不存在或已停用")
        if await _external_account_exists(data.account):
            return bad_request(message="登录账号已存在")
        params = data.model_dump()
        params["password"] = get_password_hash(data.password)
        fill_audit_fields(params, _scope_identity(identity), is_update=False)
        inserted_id = await _insert_external_user_with_password(params)
        return success(data={"id": int(inserted_id)}, message="外部用户新增成功")
    except Exception:
        logger.exception("新增外部用户失败")
        return server_error("外部用户新增失败")


@router.post("/external/update", summary="修改外部用户")
async def update_external_user(
    data: ExternalUserUpdate,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可修改外部用户")
    try:
        existing = await db_client.fetch_one(
            get_user_sql("external_user.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        if not existing:
            return bad_request(message="外部用户不存在")
        group = await db_client.fetch_one(
            get_user_sql("external_user.find_active_group"),
            {"groupId": data.groupId, "orgId": _scope_org_id(identity)},
        )
        if not group:
            return bad_request(message="用户组不存在或已停用")
        if await _external_account_exists(data.account, exclude_id=data.id):
            return bad_request(message="登录账号已存在")
        params = {"orgId": _scope_org_id(identity), **data.model_dump()}
        params = fill_audit_fields(params, _scope_identity(identity), is_update=True)
        affected = await db_client.execute(get_user_sql("external_user.update"), params)
        if affected != 1:
            return server_error("外部用户修改失败")
        return success(data={"id": data.id}, message="外部用户修改成功")
    except Exception:
        logger.exception("修改外部用户失败")
        return server_error("外部用户修改失败")


@router.post("/external/reset-password", summary="管理员重置外部用户密码")
async def reset_external_user_password(
    data: ExternalUserResetPassword,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可重置密码")
    try:
        existing = await db_client.fetch_one(
            get_user_sql("external_user.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(identity)},
        )
        if not existing:
            return bad_request(message="外部用户不存在")
        params = fill_audit_fields(
            {
                "id": data.id,
                "orgId": _scope_org_id(identity),
                "password": get_password_hash(data.newPassword),
            },
            _scope_identity(identity),
            is_update=True,
        )
        affected = await _update_external_user_password(params)
        if affected != 1:
            return server_error("密码重置失败")
        return success(message="密码重置成功")
    except Exception:
        logger.exception("重置外部用户密码失败")
        return server_error("密码重置失败")


@router.post("/external/change-password", summary="外部用户修改自己的密码")
async def change_external_user_password(
    data: ExternalUserChangePassword,
    identity: dict = Depends(get_platform_identity),
):
    if identity.get("userType") != "external":
        return bad_request(message="仅外部用户可在此修改自己的密码")
    try:
        existing = await db_client.fetch_one(
            get_user_sql("external_user.find_by_id"),
            {"id": identity["id"], "orgId": identity["orgId"]},
        )
        if not existing or not verify_password(data.oldPassword, existing["password"]):
            return bad_request(message="原密码错误")
        params = fill_audit_fields(
            {
                "id": identity["id"],
                "orgId": identity["orgId"],
                "password": get_password_hash(data.newPassword),
            },
            identity,
            is_update=True,
        )
        affected = await _update_external_user_password(params)
        if affected != 1:
            return server_error("密码修改失败")
        return success(message="密码修改成功")
    except Exception:
        logger.exception("修改外部用户密码失败")
        return server_error("密码修改失败")


async def _validate_external_user_ids(ids: list[int], org_id: int = 1) -> bool:
    rows = await db_client.fetch_all(
        get_user_sql("external_user.find_ids"),
        {"ids": ",".join(str(user_id) for user_id in ids), "orgId": org_id},
    )
    return {int(row["id"]) for row in rows} == set(ids)


@router.post("/external/delete", summary="物理删除外部用户及关联数据")
async def delete_external_user(
    data: ExternalUserDelete,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可删除外部用户")
    if not await _validate_external_user_ids([data.id], _scope_org_id(identity)):
        return bad_request(message="外部用户不存在")
    try:
        summary = await _delete_external_users_transaction(
            [data.id], _scope_org_id(identity)
        )
        return success(data=summary, message="外部用户删除成功")
    except Exception:
        logger.exception("删除外部用户失败")
        return server_error("外部用户删除失败，已回滚")


@router.post("/external/batch-delete", summary="批量物理删除外部用户及关联数据")
async def batch_delete_external_users(
    data: ExternalUserBatchDelete,
    identity: dict = Depends(get_organization_scope),
):
    if not _is_internal(identity):
        return bad_request(message="仅内部管理员可批量删除外部用户")
    if not await _validate_external_user_ids(data.ids, _scope_org_id(identity)):
        return bad_request(message="部分外部用户不存在，请刷新后重试")
    try:
        summary = await _delete_external_users_transaction(
            data.ids, _scope_org_id(identity)
        )
        return success(data=summary, message=f"已删除 {summary['deletedUsers']} 名外部用户")
    except Exception:
        logger.exception("批量删除外部用户失败")
        return server_error("批量删除失败，已全部回滚")

@router.post("/login", summary="用户登录")
async def login(req: LoginRequest):
    try:
        account = req.username.strip()
        internal = await db_client.fetch_one(
            get_user_sql("login.internal_by_account"), {"account": account}
        )
        external = await db_client.fetch_one(
            get_user_sql("login.external_by_account"), {"account": account}
        )
        if internal and external:
            return bad_request(message="登录账号存在身份冲突，请联系管理员")
        user_record = internal or external
        if not user_record:
            return bad_request(message="用户名或密码错误")
        stored_password = user_record.get("password")
        if not stored_password or not verify_password(req.password, stored_password):
            return bad_request(message="用户名或密码错误")
        user_info = dict(user_record)
        user_info.pop("password", None)
        user_type = "internal" if internal else "external"
        if internal:
            user_info = await validate_internal_identity(user_info)
        user_info["userType"] = user_type
        from api.endpoints.mcp.service import issue_access_token
        user_info["mcpToken"] = issue_access_token(user_info)
        return success(data={
            "token": f"token-{user_info.get('id')}-{user_info.get('account')}-{user_type}",
            "userInfo": user_info
        }, message="登录成功")
    except HTTPException:
        raise
    except Exception:
        logger.exception("用户登录失败")
        return server_error("登录失败")

async def _company_administrator_account_exists(account: str, exclude_id: int = 0) -> bool:
    internal = await db_client.fetch_one(get_user_sql('internal_user.find_by_account'), {'account': account})
    if internal and internal['id'] != exclude_id:
        return True
    return await db_client.fetch_one(get_user_sql('external_user.find_external_account'),
                                   {'account': account, 'excludeId': 0}) is not None


@router.post('/company-admin/querylist', summary='最高权限管理员分页管理公司管理员')
async def query_company_administrators(data: CompanyAdministratorQuery, actor: dict = Depends(get_super_administrator)):
    try:
        company = await db_client.fetch_one(get_organization_sql('organization.find_by_id'), {'id': data.orgId})
        if not company:
            return bad_request(message='公司不存在或已删除')
        params = {'orgId': data.orgId, 'keyword': data.keyword.strip(), 'enabled': data.enabled}
        total = await db_client.fetch_one(get_user_sql('internal_user.company_count'), params)
        rows = await db_client.fetch_all(get_user_sql('internal_user.company_list'),
            {**params, 'limit': data.pageSize, 'offset': (data.pageNo - 1) * data.pageSize})
        return success(data={'list': rows, 'total': int(total['total']), 'pageNo': data.pageNo, 'pageSize': data.pageSize})
    except Exception:
        logger.exception('查询公司管理员失败')
        return server_error('公司管理员加载失败')


@router.post('/company-admin/insert', summary='最高权限管理员创建公司1级管理员')
async def create_company_administrator(data: CompanyAdministratorCreate, actor: dict = Depends(get_super_administrator)):
    from sqlalchemy.exc import IntegrityError
    try:
        company = await db_client.fetch_one(get_organization_sql('organization.find_active_by_id'), {'id': data.orgId})
        if not company:
            return bad_request(message='请先启用公司后再创建管理员')
        if await _company_administrator_account_exists(data.account):
            return bad_request(message='登录账号已存在')
        params = data.model_dump(exclude={'password'})
        params['password'] = get_password_hash(data.password.get_secret_value())
        fill_audit_fields(params, actor)
        async with db_client.engine.begin() as connection:
            result = await connection.execute(text(get_user_sql('internal_user.insert_company_administrator')), params)
            if result.rowcount != 1:
                return bad_request(message='公司状态已发生变化，请刷新后重试')
            user_id = int(result.lastrowid)
        return success(data={'id': user_id}, message='公司管理员创建成功')
    except IntegrityError:
        return bad_request(message='登录账号已存在，请使用其他账号')
    except Exception as error:
        logger.error('创建公司管理员失败：%s', type(error).__name__)
        return server_error('公司管理员创建失败')


@router.post('/company-admin/update', summary='最高权限管理员编辑公司1级管理员')
async def update_company_administrator(data: CompanyAdministratorUpdate, actor: dict = Depends(get_super_administrator)):
    from sqlalchemy.exc import IntegrityError
    try:
        company = await db_client.fetch_one(get_organization_sql('organization.find_by_id'), {'id': data.orgId})
        if not company:
            return bad_request(message='公司不存在或已删除')
        if data.enabled == 1 and company['enabled'] != 1:
            return bad_request(message='请先启用所属公司，再启用管理员')
        existing = await db_client.fetch_one(get_user_sql('internal_user.find_company_administrator'), {'id': data.id, 'orgId': data.orgId})
        if not existing:
            return bad_request(message='该公司管理员不存在或不属于当前公司')
        if await _company_administrator_account_exists(data.account, data.id):
            return bad_request(message='登录账号已存在')
        params = data.model_dump(exclude={'password'})
        params['password'] = get_password_hash(data.password.get_secret_value()) if data.password else None
        fill_audit_fields(params, actor, is_update=True)
        async with db_client.engine.begin() as connection:
            result = await connection.execute(text(get_user_sql('internal_user.company_update')), params)
            if result.rowcount != 1:
                return bad_request(message='管理员状态已发生变化，请刷新后重试')
        return success(data={'id': data.id}, message='公司管理员保存成功')
    except IntegrityError:
        return bad_request(message='登录账号已存在，请使用其他账号')
    except Exception as error:
        logger.error('编辑公司管理员失败：%s', type(error).__name__)
        return server_error('公司管理员保存失败')


@router.post("/querylist", response_model=dict, summary="查询列表")
async def query_user_list(query: UserQueryRequest, identity: dict = Depends(get_platform_identity)):
    await require_super_administrator(identity)
    try:
        params = query.model_dump(exclude={'password', 'pageNo', 'pageSize'})
        params = {key: None if value == '' else value for key, value in params.items()}
        total_record = await db_client.fetch_one(get_user_sql('internal_user.count'), params)
        records = await db_client.fetch_all(get_user_sql('internal_user.list'),
            {**params, 'limit': query.pageSize, 'offset': (query.pageNo - 1) * query.pageSize})
        validated_records = [UserResponse(**record).model_dump() for record in records]
        return success(data={
            "total": int(total_record['total']),
            "list": validated_records,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize
        })
    except Exception:
        logger.exception('查询管理员失败')
        return server_error('查询管理员失败')


@router.post("/update", summary="修改记录")
async def update_user(data: UserUpdate, identity: dict = Depends(get_platform_identity)):
    await require_super_administrator(identity)
    try:
        existing = await db_client.fetch_one(get_user_sql('internal_user.find_by_id'), {'id': data.id})
        if not existing:
            return bad_request(message='管理员不存在')
        changed = data.model_dump(include={'realName', 'account', 'password', 'phone', 'deptName', 'deptLevel', 'orgId', 'remarks', 'enabled', 'removed'}, exclude_unset=True)
        if not changed:
            return bad_request(message='没有需要更新的字段')
        await validate_internal_identity({**existing, **changed})
        params = {key: changed.get(key) for key in ('realName', 'account', 'password', 'phone', 'deptName', 'deptLevel', 'orgId', 'remarks', 'enabled', 'removed')}
        if params['password'] is not None:
            if not 8 <= len(params['password'].encode('utf-8')) <= 72:
                return bad_request(message='密码长度必须为8至72字节')
            params['password'] = get_password_hash(params['password'])
        params.update(id=data.id, setOrgId=int('orgId' in changed))
        fill_audit_fields(params, identity, is_update=True)
        affected = await db_client.execute(get_user_sql('internal_user.update'), params)
        if affected > 0:
            return success(message="修改成功")
        return server_error("修改失败，记录不存在")
    except HTTPException:
        raise
    except Exception:
        logger.exception('修改管理员失败')
        return server_error('修改管理员失败')

@router.post("/delete", summary="物理删除")
async def delete_user(req: DeleteRequest, identity: dict = Depends(get_platform_identity)):
    await require_super_administrator(identity)
    try:
        affected = await db_client.execute(get_user_sql('internal_user.physical_delete'), {'id': req.id})
        if affected > 0:
            return success(message="删除成功")
        return server_error("删除失败，记录不存在")
    except Exception:
        logger.exception('删除管理员失败')
        return server_error('删除管理员失败')

@router.post("/deleteLj", summary="逻辑删除")
async def delete_lj_user(req: DeleteRequest, identity: dict = Depends(get_platform_identity)):
    await require_super_administrator(identity)
    try:
        params = fill_audit_fields({'id': req.id}, identity, is_update=True)
        affected = await db_client.execute(get_user_sql('internal_user.logical_delete'), params)
        if affected > 0:
            return success(message="逻辑删除成功")
        return server_error("逻辑删除失败，记录不存在")
    except Exception:
        logger.exception('删除管理员失败')
        return server_error('删除管理员失败')
