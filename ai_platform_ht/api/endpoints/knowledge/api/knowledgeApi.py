import logging
import asyncio
import json
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, Dict, Literal
from urllib.parse import quote

import yaml
from fastapi import APIRouter, Depends, File, Path as ApiPath, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import text

from api.endpoints.knowledge.files import delete_original, read_original, save_original, text_download_name
from api.endpoints.knowledge.files import extract_complete_text, split_knowledge_text, document_warnings
from api.endpoints.knowledge.access import (
    COMPANY_PRIVATE,
    COMPANY_PUBLIC,
    PERSONAL,
    actor_from_scope,
    can_manage_tenant,
    can_read_tenant,
    join_ids,
    parse_id_list,
)
from api.endpoints.knowledge.modular.knowledge import (
    KnowledgeDocumentContent,
    KnowledgeRecordCreate,
    KnowledgeRecordDelete,
    KnowledgeRecordUpdate,
    KnowledgeRetrievalRequest,
    KnowledgeGraphQuestion,
    TenantCreate,
    TenantDelete,
    TenantUpdate,
    KnowledgeFolderWrite,
    KnowledgeFolderDelete,
    KnowledgeDocumentMove,
)
from api.endpoints.organization.dependencies import get_organization_scope
from utils.context import fill_audit_fields
from utils.mysqldb import db_client
from utils.response import bad_request, server_error, success
from api.endpoints.knowledge.graph_service import GraphError
from api.endpoints.knowledge.service import derive_sync_status, get_knowledge_store
from api.endpoints.knowledge.tenant_graph import TenantGraphService
from api.endpoints.knowledge.service import normalize_tenant_ids, KnowledgeFolders, knowledge_folder_scope
from api.endpoints.system.service import get_company_runtime_config


router = APIRouter()
logger = logging.getLogger(__name__)
tenant_graphs = TenantGraphService()
knowledge_folders = KnowledgeFolders()
SQL_CONFIG_PATH = Path(__file__).resolve().parents[1] / "sql" / "sql.yaml"
ALLOWED_UPLOAD_EXTENSIONS = {".docx", ".xlsx", ".xls"}
MAX_UPLOAD_FILES = 10
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_CONTENT_BYTES = 60_000
MAX_UPLOAD_CHUNKS = 100
ACCESS_DENIED = "知识库不存在或无权使用"


def _scope_org_id(scope: Dict[str, Any]) -> int:
    return int(scope.get("orgId", 1)) if isinstance(scope, dict) else 1


def _scope_user(scope: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(scope, dict):
        return {"id": 1, "name": "admin"}
    identity = scope.get("identity", scope)
    return identity if isinstance(identity, dict) else scope


def _actor(scope: Dict[str, Any]) -> Dict[str, Any]:
    return actor_from_scope(scope)


def _present_tenant(row: dict[str, Any], *, include_grants: bool) -> dict[str, Any]:
    presented = _serialize_record(row)
    presented["id"] = int(presented["id"])
    presented["scopeType"] = int(presented.get("scopeType") or 0)
    if include_grants:
        presented["accessUserIds"] = parse_id_list(presented.get("accessUserIds"))
        presented["accessGroupIds"] = parse_id_list(presented.get("accessGroupIds"))
    else:
        presented.pop("accessUserIds", None)
        presented.pop("accessGroupIds", None)
        presented.pop("ownerUserId", None)
    return presented


async def _company_grants(org_id: int, user_ids: list[int], group_ids: list[int]) -> tuple[str | None, str | None]:
    users = parse_id_list(user_ids)
    groups = parse_id_list(group_ids)
    if not users and not groups:
        raise ValueError("公司私有知识库至少指定一位用户或一个用户组")
    if users:
        rows = await db_client.fetch_all(
            get_sql("grant.users_in_company"),
            {"orgId": org_id, "userIds": ",".join(str(item) for item in users)},
        )
        if {int(row["id"]) for row in rows} != set(users):
            raise ValueError("授权用户必须是本公司已启用的外部用户")
    if groups:
        rows = await db_client.fetch_all(
            get_sql("grant.groups_in_company"),
            {"orgId": org_id, "groupIds": ",".join(str(item) for item in groups)},
        )
        if {int(row["id"]) for row in rows} != set(groups):
            raise ValueError("授权用户组必须是本公司已启用的用户组")
    return join_ids(users), join_ids(groups)


async def _load_tenant(tenant_id: int, org_id: int) -> dict[str, Any] | None:
    return await db_client.fetch_one(
        get_sql("tenant.find_by_id"),
        {"tenantId": tenant_id, "orgId": org_id},
    )


async def filter_usable_tenant_ids(tenant_id: str, identity: dict[str, Any]) -> str:
    """只保留当前调用者有权用于 AI 检索的知识库 ID。"""
    actor = actor_from_scope({"orgId": identity.get("orgId"), "identity": identity})
    tenant_ids = normalize_tenant_ids(tenant_id)
    rows = await db_client.fetch_all(
        get_sql("tenant.ids_usable"),
        {
            "tenantIds": ",".join(str(item) for item in tenant_ids),
            "orgId": actor["orgId"],
            "userId": actor["id"],
            "groupId": actor["groupId"],
            "userType": actor["userType"],
        },
    )
    allowed = {int(row["id"]) for row in rows}
    return ",".join(str(item) for item in tenant_ids if item in allowed)


def get_sql(key: str) -> str:
    with SQL_CONFIG_PATH.open("r", encoding="utf-8") as file:
        value: Any = yaml.safe_load(file) or {}
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(f"SQL key not found: {key}")
        value = value[part]
    if not isinstance(value, str):
        raise KeyError(f"SQL key does not point to a statement: {key}")
    return value


def _normalized_keyword(keyword: str | None) -> str | None:
    normalized = keyword.strip() if keyword else ""
    return normalized or None


def _serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, datetime):
            serialized[key] = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, date):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


async def _knowledge_store_for_scope(scope: Dict[str, Any]):
    if db_client.engine is None or not isinstance(scope, dict) or "orgId" not in scope or "identity" not in scope:
        return get_knowledge_store()
    config = await get_company_runtime_config(_scope_org_id(scope))
    return get_knowledge_store(
        json.dumps(config.models, ensure_ascii=False, sort_keys=True),
        json.dumps(config.vector, ensure_ascii=False, sort_keys=True),
    )


async def _knowledge_store_for_tenant_ids(tenant_id: str):
    if db_client.engine is None:
        return get_knowledge_store()
    tenant_ids = normalize_tenant_ids(tenant_id)
    rows = await db_client.fetch_all(
        get_sql("tenant.find_orgs_by_ids"),
        {"tenantIds": ",".join(str(value) for value in tenant_ids)},
    )
    matched = sum(int(row.get("tenantCount") or 0) for row in rows)
    if matched != len(tenant_ids):
        raise ValueError("部分知识库不存在或已停用")
    if len(rows) != 1:
        raise ValueError("一次查询的知识库必须属于同一公司")
    config = await get_company_runtime_config(int(rows[0]["orgId"]))
    return get_knowledge_store(
        json.dumps(config.models, ensure_ascii=False, sort_keys=True),
        json.dumps(config.vector, ensure_ascii=False, sort_keys=True),
    )


async def _with_sync_status(
    rows: list[dict[str, Any]], store=None
) -> list[dict[str, Any]]:
    record_ids = [int(row["id"]) for row in rows]
    vector_store = store or get_knowledge_store()
    versions = await asyncio.to_thread(vector_store.get_versions, record_ids)
    return [
        {
            **row,
            "milvusVersion": versions.get(int(row["id"])),
            "syncStatus": derive_sync_status(
                enabled=int(row.get("enabled") or 0),
                source_version=int(row.get("version") or 0),
                vector_version=versions.get(int(row["id"])),
            ),
        }
        for row in rows
    ]


async def _execute_transaction(
    statements: list[tuple[str, dict[str, Any]]],
) -> list[int]:
    if db_client.engine is None:
        raise RuntimeError("MySQL engine is not initialized")
    affected_rows: list[int] = []
    async with db_client.engine.begin() as connection:
        for sql, params in statements:
            result = await connection.execute(text(sql), params)
            affected_rows.append(result.rowcount)
    return affected_rows


async def _insert_uploaded_records(
    records: list[dict[str, Any]],
    user: Dict[str, Any],
) -> list[dict[str, Any]]:
    if db_client.engine is None:
        raise RuntimeError("MySQL engine is not initialized")
    inserted: list[dict[str, Any]] = []
    async with db_client.engine.begin() as connection:
        for tenant_id in sorted({record['tenantId'] for record in records if record.get('folderId')}):
            params={'orgId':user['orgId'],'tenantId':tenant_id}
            await connection.execute(text(get_sql('folder.tenant_lock')),params)
            folders=(await connection.execute(text(get_sql('folder.list')),params)).mappings().all()
            for record in records:
                if record['tenantId']==tenant_id:knowledge_folder_scope(folders,int(record.get('folderId') or 0))
        for record in records:
            params = fill_audit_fields({'folderId':0,**record}, user, is_update=False)
            result = await connection.execute(text(get_sql("record.insert")), params)
            if result.lastrowid is None:
                raise RuntimeError("知识数据新增后未返回主键")
            inserted.append({**record, "id": int(result.lastrowid), "version": 1})
    return inserted


async def verify_knowledge_evidence(items: list[dict], actor: dict, tenant_ids: list[int]) -> list[dict]:
    """向量片段只有在来源仍有效且版本一致时才能作为回答证据。"""
    if items:
        rows = await db_client.fetch_all(get_sql('record.retrieval_current'),
            {'orgId': actor['orgId'], 'tenantIds': ','.join(map(str, tenant_ids)),
             'recordIds': ','.join(str(int(item['id'])) for item in items)})
        sources = {int(row['id']): row for row in rows}
        verified = []
        for item in items:
            source = sources.get(int(item['id']))
            if not source or any(str(source.get(field) or '') != str(item.get(field) or '') for field in ('version','tenantId','fileId')):
                raise ValueError('知识索引与当前资料不一致，可能已更新、停用或删除，请先修复同步后重试')
            verified.append({**item, 'title': source['title'], 'fileUrl': source.get('fileUrl') or '',
                             'tenantName': source.get('tenantName') or ''})
        items = verified
    grants = await db_client.fetch_all(get_sql('tenant.ids_usable'),
        {'tenantIds': ','.join(map(str, tenant_ids)), 'orgId': actor['orgId'], 'userId': actor['id'],
         'groupId': actor['groupId'], 'userType': actor['userType']})
    if {int(row['id']) for row in grants} != set(tenant_ids):
        raise ValueError(ACCESS_DENIED)
    return items


@router.post(
    "/retrieval/search",
    summary="通过 Embedding 和 Rerank 返回知识片段",
)
async def retrieve_knowledge(
    data: KnowledgeRetrievalRequest,
    scope: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(scope)
        tenant_ids = normalize_tenant_ids(data.tenant_id)
        rows = await db_client.fetch_all(
            get_sql("tenant.ids_usable"),
            {
                "tenantIds": ",".join(str(item) for item in tenant_ids),
                "orgId": actor["orgId"],
                "userId": actor["id"],
                "groupId": actor["groupId"],
                "userType": actor["userType"],
            },
        )
        if {int(row["id"]) for row in rows} != set(tenant_ids):
            return bad_request(message=ACCESS_DENIED)
        store = await _knowledge_store_for_scope(scope)
        folder_options={}
        if data.folderId is not None:
            if len(tenant_ids)!=1:return bad_request(message='指定文档时只能查询一个知识库')
            folder=await knowledge_folders.scope(actor['orgId'],tenant_ids[0],data.folderId)
            scoped_records=await db_client.fetch_all(get_sql('folder.retrieval_records'),{
                'tenantId':tenant_ids[0],'folderIds':','.join(map(str,folder['descendantIds'])),
                'documentKeys':','.join(folder.get('documentKeys',[]))})
            folder_options['record_ids']=[int(row['id']) for row in scoped_records]
        items = await asyncio.to_thread(
            store.retrieve,
            question=data.question,
            confidence=data.confidence,
            top_k=data.topK,
            tenant_id=",".join(str(item) for item in tenant_ids),
            **folder_options,
        )
        items = await verify_knowledge_evidence(items, actor, tenant_ids)
        if data.folderId is not None:
            latest_folder=await knowledge_folders.scope(actor['orgId'],tenant_ids[0],data.folderId)
            latest_records=await db_client.fetch_all(get_sql('folder.retrieval_records'),{
                'tenantId':tenant_ids[0],'folderIds':','.join(map(str,latest_folder['descendantIds'])),
                'documentKeys':','.join(latest_folder.get('documentKeys',[]))})
            allowed={int(row['id']) for row in latest_records}
            items=[item for item in items if int(item['id']) in allowed]
        return success(
            data={
                "question": data.question,
                "confidence": data.confidence,
                "topK": data.topK,
                "tenant_id": ",".join(str(item) for item in tenant_ids),
                "list": items,
                "total": len(items),
            }
        )
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("知识召回失败")
        return server_error("知识召回失败")


@router.get("/tenant/querylist", summary="分页查询知识库")
async def query_tenants(
    keyword: str | None = Query(default=None, max_length=255),
    enabled: int | None = Query(default=None, ge=0, le=1),
    pageNo: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    _user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(_user)
        if actor["userType"] != "internal":
            return bad_request(message="仅内部管理员可管理公司知识库")
        params = {
            "orgId": actor["orgId"],
            "keyword": _normalized_keyword(keyword),
            "enabled": enabled,
        }
        count_row = await db_client.fetch_one(get_sql("tenant.count_page"), params)
        rows = await db_client.fetch_all(
            get_sql("tenant.list_page"),
            {**params, "limit": pageSize, "offset": (pageNo - 1) * pageSize},
        )
        return success(
            data={
                "list": [_present_tenant(row, include_grants=True) for row in rows],
                "total": int(count_row.get("total", 0)) if count_row else 0,
                "pageNo": pageNo,
                "pageSize": pageSize,
            }
        )
    except Exception:
        logger.exception("查询知识库失败")
        return server_error("查询知识库失败")


@router.get("/tenant/usable", summary="查询当前用户可使用的公司知识库和自己的知识库")
async def query_usable_tenants(
    keyword: str | None = Query(default=None, max_length=255),
    section: Literal["company", "personal", "all"] | None = Query(default=None),
    scopeType: int | None = Query(default=None, ge=1, le=3),
    pageNo: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    scope: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(scope)
        if actor["userType"] != "external":
            return bad_request(message="请使用个人账号查看可使用的知识库")
        params = {
            "orgId": actor["orgId"],
            "userId": actor["id"],
            "groupId": actor["groupId"],
            "keyword": _normalized_keyword(keyword),
        }
        page = {**params, "limit": pageSize, "offset": (pageNo - 1) * pageSize}
        if section == "all":
            visible_params = {**params, "scopeType": scopeType}
            count = await db_client.fetch_one(get_sql("tenant.count_visible"), visible_params)
            rows = await db_client.fetch_all(
                get_sql("tenant.visible_page"), {**page, "scopeType": scopeType}
            )
            return success(data={
                "list": [_present_tenant(row, include_grants=False) for row in rows],
                "total": int(count.get("total", 0)) if count else 0,
                "pageNo": pageNo,
                "pageSize": pageSize,
            })
        company_count = await db_client.fetch_one(get_sql("tenant.count_usable_company"), params)
        personal_count = await db_client.fetch_one(get_sql("tenant.count_usable_personal"), params)
        company_rows = [] if section == "personal" else await db_client.fetch_all(get_sql("tenant.usable_company"), page)
        personal_rows = [] if section == "company" else await db_client.fetch_all(get_sql("tenant.usable_personal"), page)
        return success(data={
            "company": [_present_tenant(row, include_grants=False) for row in company_rows],
            "personal": [_present_tenant(row, include_grants=False) for row in personal_rows],
            "companyTotal": int(company_count.get("total", 0)) if company_count else 0,
            "personalTotal": int(personal_count.get("total", 0)) if personal_count else 0,
            "pageNo": pageNo,
            "pageSize": pageSize,
        })
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("查询可使用知识库失败")
        return server_error("查询可使用知识库失败")


@router.get("/tenant/grant-options", summary="查询公司私有知识库可授权的用户和用户组")
async def query_grant_options(scope: Dict[str, Any] = Depends(get_organization_scope)):
    try:
        actor = _actor(scope)
        if actor["userType"] != "internal":
            return bad_request(message="仅内部管理员可配置公司知识库授权")
        users = await db_client.fetch_all(get_sql("grant.user_options"), {"orgId": actor["orgId"]})
        groups = await db_client.fetch_all(get_sql("grant.group_options"), {"orgId": actor["orgId"]})
        return success(data={"users": [_serialize_record(row) for row in users], "groups": [_serialize_record(row) for row in groups]})
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("查询知识库授权选项失败")
        return server_error("查询知识库授权选项失败")


@router.get("/tenant/{tenant_id}", summary="查询知识库详情")
async def get_tenant(
    tenant_id: int = ApiPath(gt=0),
    _user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(_user)
        tenant = await _load_tenant(tenant_id, actor["orgId"])
        if not tenant or not can_read_tenant(tenant, actor):
            return bad_request(message=ACCESS_DENIED)
        return success(data=_present_tenant(tenant, include_grants=actor["userType"] == "internal" and int(tenant["scopeType"]) != PERSONAL))
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("查询知识库详情失败")
        return server_error("查询知识库详情失败")


@router.post("/tenant/insert", summary="新增知识库")
async def create_tenant(
    data: TenantCreate,
    user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(user)
        if actor["userType"] == "external":
            scope_type = PERSONAL
            owner_user_id = actor["id"]
            access_user_ids = None
            access_group_ids = None
        else:
            scope_type = data.scopeType
            if scope_type not in (COMPANY_PUBLIC, COMPANY_PRIVATE):
                return bad_request(message="公司知识库类型只能是公有或私有")
            owner_user_id = None
            if scope_type == COMPANY_PRIVATE:
                access_user_ids, access_group_ids = await _company_grants(
                    actor["orgId"], data.accessUserIds, data.accessGroupIds
                )
            else:
                access_user_ids = None
                access_group_ids = None
        params = fill_audit_fields(
            {
                "orgId": actor["orgId"],
                "scopeType": scope_type,
                "ownerUserId": owner_user_id,
                "accessUserIds": access_user_ids,
                "accessGroupIds": access_group_ids,
                "tenantName": data.tenantName,
                "remarks": data.remarks.strip() if data.remarks else None,
            },
            actor,
            is_update=False,
        )
        tenant_id = await db_client.execute_insert(get_sql("tenant.insert"), params)
        return success(data={"id": int(tenant_id), "scopeType": scope_type}, message="知识库新增成功")
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("新增知识库失败")
        return server_error("新增知识库失败")


@router.post("/tenant/update", summary="修改知识库并同步向量")
async def update_tenant(
    data: TenantUpdate,
    user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(user)
        existing = await _load_tenant(data.id, actor["orgId"])
        if not existing or not can_manage_tenant(existing, actor):
            return bad_request(message=ACCESS_DENIED)
        scope_type = int(existing["scopeType"])
        if scope_type == PERSONAL:
            statement = (
                get_sql("tenant.update_personal"),
                {
                    "tenantId": data.id,
                    "orgId": actor["orgId"],
                    "ownerUserId": actor["id"],
                    "tenantName": data.tenantName,
                    "remarks": data.remarks.strip() if data.remarks else None,
                    "enabled": data.enabled,
                },
            )
        else:
            next_scope = scope_type if data.scopeType is None else data.scopeType
            grants_sent = "accessUserIds" in data.model_fields_set or "accessGroupIds" in data.model_fields_set
            if next_scope == COMPANY_PRIVATE and data.scopeType is None and not grants_sent:
                access_user_ids = existing.get("accessUserIds") or None
                access_group_ids = existing.get("accessGroupIds") or None
            elif next_scope == COMPANY_PRIVATE:
                access_user_ids, access_group_ids = await _company_grants(
                    actor["orgId"], data.accessUserIds, data.accessGroupIds
                )
            else:
                access_user_ids = None
                access_group_ids = None
            statement = (
                get_sql("tenant.update_company"),
                {
                    "tenantId": data.id,
                    "orgId": actor["orgId"],
                    "tenantName": data.tenantName,
                    "remarks": data.remarks.strip() if data.remarks else None,
                    "enabled": data.enabled,
                    "scopeType": next_scope,
                    "accessUserIds": access_user_ids,
                    "accessGroupIds": access_group_ids,
                },
            )

        refresh_vectors = (
            data.tenantName != existing.get("tenantName")
            or data.enabled != int(existing.get("enabled") or 0)
        )
        statements: list[tuple[str, dict[str, Any]]] = [statement]
        if refresh_vectors:
            audit = fill_audit_fields({}, _scope_user(user), is_update=True)
            statements.append(
                (
                    get_sql("record.bump_tenant_versions"),
                    {
                        "tenantId": data.id,
                        "tenantName": data.tenantName,
                        "updateUserId": audit["updateUserId"],
                        "updateUserName": audit["updateUserName"],
                        "updateTime": audit["updateTime"],
                    },
                )
            )
        await _execute_transaction(statements)

        vector_summary = {"synced": 0, "deleted": 0}
        if refresh_vectors:
            id_rows = await db_client.fetch_all(
                get_sql("record.ids_by_tenant"), {"tenantId": data.id}
            )
            record_ids = [int(row["id"]) for row in id_rows]
            store = await _knowledge_store_for_scope({"orgId": actor["orgId"], "identity": actor})
            if data.enabled == 0:
                vector_summary["deleted"] = await asyncio.to_thread(
                    store.delete_ids, record_ids
                )
            else:
                sync_rows = await db_client.fetch_all(
                    get_sql("record.active_sync_by_tenant"),
                    {"tenantId": data.id, "orgId": actor["orgId"]},
                )
                sync_result = await asyncio.to_thread(store.sync_records, sync_rows)
                vector_summary["synced"] = sync_result["synced"]
                active_ids = {int(row["id"]) for row in sync_rows}
                inactive_ids = [record_id for record_id in record_ids if record_id not in active_ids]
                if inactive_ids:
                    vector_summary["deleted"] = await asyncio.to_thread(
                        store.delete_ids, inactive_ids
                    )
        return success(
            data={
                "id": data.id,
                "affectedRecords": len(record_ids) if refresh_vectors else 0,
                "milvus": vector_summary,
            },
            message="知识库修改成功",
        )
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("修改知识库失败")
        return server_error("知识库已保存但向量同步可能未完成，请执行同步修复")


@router.post("/tenant/delete", summary="删除未被知识数据引用的知识库")
async def delete_tenant(
    data: TenantDelete,
    user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(user)
        existing = await _load_tenant(data.id, actor["orgId"])
        if not existing or not can_manage_tenant(existing, actor):
            return bad_request(message=ACCESS_DENIED)
        count_row = await db_client.fetch_one(
            get_sql("tenant.count_knowledge"), {"tenantId": data.id}
        )
        knowledge_count = int(count_row.get("total", 0)) if count_row else 0
        if knowledge_count:
            return bad_request(
                message=f"知识库仍有 {knowledge_count} 条知识数据，不能删除"
            )
        delete_params = {"tenantId": data.id, "orgId": actor["orgId"]}
        folder_count=await db_client.fetch_one(get_sql('folder.count_tenant'),delete_params)
        if int((folder_count or {}).get('total',0)):
            return bad_request(message='知识库仍有文档，请先删除空文档后再删除知识库')
        skill_references = await db_client.fetch_one(get_sql('tenant.skill_references'), delete_params)
        if int((skill_references or {}).get('total', 0)):
            return bad_request(message='知识库仍被技能引用，请先在技能管理中解除关联')
        if int(existing["scopeType"]) == PERSONAL:
            delete_key = "tenant.physical_delete_personal"
            delete_params["ownerUserId"] = actor["id"]
        else:
            delete_key = "tenant.physical_delete_company"
        deleted_rows = await db_client.execute(get_sql(delete_key), delete_params)
        if deleted_rows != 1:
            return server_error("知识库物理删除失败")
        return success(data={"id": data.id}, message="知识库删除成功")
    except Exception:
        logger.exception("删除知识库失败")
        return server_error("删除知识库失败")


_SEGMENT_SUFFIX = re.compile(r"（第\d+/\d+段）$")
_SYNC_SEVERITY = {"missing": 3, "outdated": 2, "orphaned": 1, "synced": 0}


def _document_title(row: dict[str, Any]) -> str:
    file_name = str(row.get("fileUrl") or "").strip()
    if file_name:
        return file_name
    title = _SEGMENT_SUFFIX.sub("", str(row.get("title") or "")).strip()
    return title or "未命名文档"


def _group_documents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """一份上传文件的多个文本段在列表里只算一个文档。"""
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        file_id = str(row.get("fileId") or "").strip()
        key = file_id or f"id:{row['id']}"
        if key not in grouped:
            grouped[key] = {
                "id": int(row["id"]),
                "title": _document_title(row),
                "fileUrl": row.get("fileUrl") or "",
                "fileId": row.get("fileId") or "",
                "version": int(row.get("version") or 0),
                "tenantId": row.get("tenantId"),
                "enabled": int(row.get("enabled") or 0),
                "createTime": row.get("createTime"),
                "updateTime": row.get("updateTime"),
                "milvusVersion": row.get("milvusVersion"),
                "syncStatus": row.get("syncStatus") or "synced",
            }
            order.append(key)
            continue
        current = grouped[key]
        current["id"] = min(int(current["id"]), int(row["id"]))
        current["version"] = max(int(current["version"]), int(row.get("version") or 0))
        current["enabled"] = min(int(current["enabled"]), int(row.get("enabled") or 0))
        if _SYNC_SEVERITY.get(row.get("syncStatus"), 0) > _SYNC_SEVERITY.get(current["syncStatus"], 0):
            current["syncStatus"] = row["syncStatus"]
            current["milvusVersion"] = row.get("milvusVersion")
    return [grouped[key] for key in order]


async def _folder_access(actor,tenant_id,folder_id=0,*,manage=False):
    tenant=await _load_tenant(tenant_id,actor['orgId'])
    allowed=can_manage_tenant(tenant,actor) if tenant and manage else tenant and can_read_tenant(tenant,actor)
    if not allowed or manage and int(tenant.get('enabled') or 0)!=1:
        raise ValueError(ACCESS_DENIED)
    return await knowledge_folders.scope(actor['orgId'],tenant_id,folder_id)


@router.get('/tenant/{tenant_id}/folders',summary='查看当前文档、直接子文档及面包屑')
async def list_knowledge_folders(tenant_id:int=ApiPath(gt=0),folderId:Annotated[int,Query(ge=0)]=0,
        user:dict=Depends(get_organization_scope)):
    try:
        return success(await _folder_access(_actor(user),tenant_id,folderId))
    except ValueError as exc:return bad_request(message=str(exc))
    except Exception:
        logger.exception('读取知识库文档失败')
        return server_error('文档读取失败，请刷新重试；新环境请先执行文档数据库升级')


@router.post('/tenant/{tenant_id}/folders',summary='在当前层级创建知识库文档')
async def create_knowledge_folder(data:KnowledgeFolderWrite,tenant_id:int=ApiPath(gt=0),user:dict=Depends(get_organization_scope)):
    try:
        actor=_actor(user);await _folder_access(actor,tenant_id,data.parentId,manage=True)
        return success(await knowledge_folders.save(actor,tenant_id,data),'文档已创建')
    except ValueError as exc:return bad_request(message=str(exc))
    except Exception:
        logger.exception('创建知识库文档失败');return server_error('文档创建失败，请刷新重试')


@router.put('/tenant/{tenant_id}/folders/{folder_id}',summary='修改文档名称或上级，禁止循环')
async def update_knowledge_folder(data:KnowledgeFolderWrite,tenant_id:int=ApiPath(gt=0),folder_id:int=ApiPath(gt=0),user:dict=Depends(get_organization_scope)):
    try:
        actor=_actor(user);await _folder_access(actor,tenant_id,folder_id,manage=True)
        return success(await knowledge_folders.save(actor,tenant_id,data,folder_id),'文档已修改')
    except ValueError as exc:return bad_request(message=str(exc))
    except Exception:
        logger.exception('修改知识库文档失败');return server_error('文档修改失败，请刷新重试')


@router.post('/tenant/{tenant_id}/records/{record_id}/open',summary='打开文件文档，返回稳定的文档层级入口')
async def open_knowledge_document(tenant_id:int=ApiPath(gt=0),record_id:int=ApiPath(gt=0),user:dict=Depends(get_organization_scope)):
    try:
        actor=_actor(user)
        tenant=await _load_tenant(tenant_id,actor['orgId'])
        if not tenant or not can_read_tenant(tenant,actor):return bad_request(message=ACCESS_DENIED)
        return success(await knowledge_folders.open_document(actor,tenant_id,record_id))
    except ValueError as exc:return bad_request(message=str(exc))
    except Exception:
        logger.exception('打开文档失败');return server_error('文档打开失败，请刷新重试')


@router.post('/tenant/{tenant_id}/folders/{folder_id}/delete',summary='二次确认后物理删除空文档')
async def delete_knowledge_folder(data:KnowledgeFolderDelete,tenant_id:int=ApiPath(gt=0),folder_id:int=ApiPath(gt=0),user:dict=Depends(get_organization_scope)):
    try:
        if not data.confirmed:return bad_request(message='请先确认删除文档')
        actor=_actor(user);await _folder_access(actor,tenant_id,folder_id,manage=True)
        return success(await knowledge_folders.delete(actor,tenant_id,folder_id),'空文档已删除')
    except ValueError as exc:return bad_request(message=str(exc))
    except Exception:
        logger.exception('删除知识库文档失败');return server_error('文档删除失败，请刷新重试')


@router.post('/tenant/{tenant_id}/records/move',summary='批量移动整份文档的全部分段，保留资料和向量ID')
async def move_knowledge_documents(data:KnowledgeDocumentMove,tenant_id:int=ApiPath(gt=0),user:dict=Depends(get_organization_scope)):
    try:
        actor=_actor(user);await _folder_access(actor,tenant_id,data.folderId,manage=True)
        return success(await knowledge_folders.move(actor,tenant_id,data),'文档已移动；相关文档图谱按当前资料更新')
    except ValueError as exc:return bad_request(message=str(exc))
    except Exception:
        logger.exception('移动知识库文档失败');return server_error('文档移动失败，已回滚，请刷新重试')


@router.get("/tenant/{tenant_id}/records", summary="分页查询知识库数据")
async def query_tenant_records(
    tenant_id: int = ApiPath(gt=0),
    keyword: str | None = Query(default=None, max_length=255),
    syncStatus: Literal["synced", "pending"] | None = Query(default=None),
    pageNo: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    _user: Dict[str, Any] = Depends(get_organization_scope),
    folderId: Annotated[int | None,Query(ge=0)] = None,
):
    try:
        actor = _actor(_user)
        tenant = await _load_tenant(tenant_id, actor["orgId"])
        if not tenant or not can_read_tenant(tenant, actor):
            return bad_request(message=ACCESS_DENIED)
        if folderId is not None:await knowledge_folders.scope(actor['orgId'],tenant_id,folderId)
        params = {
            "folderId":folderId,
            "tenantId": tenant_id,
            "orgId": actor["orgId"],
            "keyword": _normalized_keyword(keyword),
        }
        if syncStatus:
            store = await _knowledge_store_for_scope({"orgId": actor["orgId"], "identity": actor})
            candidates = await db_client.fetch_all(
                get_sql("record.list_status_index_by_tenant"), params
            )
            candidates = await _with_sync_status(candidates, store)
            documents = _group_documents(candidates)
            if syncStatus == "synced":
                filtered = [row for row in documents if row["syncStatus"] == "synced"]
            else:
                filtered = [row for row in documents if row["syncStatus"] != "synced"]
            total = len(filtered)
            offset = (pageNo - 1) * pageSize
            rows = filtered[offset : offset + pageSize]
        else:
            store = await _knowledge_store_for_scope({"orgId": actor["orgId"], "identity": actor})
            count_row = await db_client.fetch_one(
                get_sql("record.count_documents_by_tenant"), params
            )
            page_rows = await db_client.fetch_all(
                get_sql("record.list_documents_by_tenant"),
                {**params, "limit": pageSize, "offset": (pageNo - 1) * pageSize},
            )
            file_ids = [str(row.get("fileId") or "") for row in page_rows if str(row.get("fileId") or "")]
            chunks = []
            if file_ids:
                chunks = await db_client.fetch_all(
                    get_sql("record.list_by_file_ids"),
                    {**params, "fileIds": ",".join(file_ids)},
                )
            chunks = await _with_sync_status(chunks, store)
            by_file = {
                str(item["fileId"]): item
                for item in _group_documents(chunks)
                if str(item.get("fileId") or "")
            }
            missing = [row for row in page_rows if str(row.get("fileId") or "") not in by_file]
            missing_status = {
                int(row["id"]): row for row in await _with_sync_status(missing, store)
            } if missing else {}
            rows = []
            for row in page_rows:
                document = by_file.get(str(row.get("fileId") or ""))
                if document:
                    rows.append(document)
                    continue
                alone = missing_status[int(row["id"])]
                alone["title"] = _document_title(alone)
                rows.append(alone)
            total = int(count_row.get("total", 0)) if count_row else 0
        return success(
            data={
                "tenant": _present_tenant(tenant, include_grants=actor["userType"] == "internal" and int(tenant["scopeType"]) != PERSONAL),
                "list": [_serialize_record(row) for row in rows],
                "total": total,
                "pageNo": pageNo,
                "pageSize": pageSize,
            }
        )
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("查询知识库数据失败")
        return server_error("查询知识库数据失败")


async def _tenant_graph_scope(actor,tenant_id,folder_id):
    if not folder_id:return tenant_graphs
    try:await knowledge_folders.scope(actor['orgId'],tenant_id,folder_id)
    except ValueError as exc:raise GraphError(str(exc),'FOLDER_NOT_FOUND',404) from None
    return tenant_graphs.for_folder(folder_id)


@router.get('/tenant/{tenant_id}/graph', summary='查看知识库的实体关系图谱')
async def tenant_graph_view(tenant_id: int = ApiPath(gt=0), _user: Dict[str, Any] = Depends(get_organization_scope),folderId:Annotated[int,Query(ge=0)]=0):
    try:
        actor = _actor(_user)
        tenant = await _load_tenant(tenant_id, actor['orgId'])
        if not tenant or not can_read_tenant(tenant, actor):
            return bad_request(message=ACCESS_DENIED)
        service=await _tenant_graph_scope(actor,tenant_id,folderId)
        return success(await service.view(actor['orgId'], tenant_id))
    except GraphError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception('查看知识库图谱失败')
        return server_error('查看知识库图谱失败')


@router.post('/tenant/{tenant_id}/graph', summary='按知识库当前全部文档建立实体关系图谱')
async def tenant_graph_build(tenant_id: int = ApiPath(gt=0), _user: Dict[str, Any] = Depends(get_organization_scope),folderId:Annotated[int,Query(ge=0)]=0):
    try:
        actor = _actor(_user)
        tenant = await _load_tenant(tenant_id, actor['orgId'])
        if not tenant or not can_manage_tenant(tenant, actor):
            return bad_request(message=ACCESS_DENIED)
        service=await _tenant_graph_scope(actor,tenant_id,folderId)
        return success(await service.start(actor['orgId'], tenant_id), message='知识图谱任务已提交')
    except GraphError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception('建立知识库图谱失败')
        return server_error('建立知识库图谱失败')


@router.get('/tenant/{tenant_id}/graph/evidence/{evidence_id}', summary='查看知识库图谱节点对应的原文')
async def tenant_graph_evidence(tenant_id: int = ApiPath(gt=0), evidence_id: str = ApiPath(min_length=1, max_length=200),
        folderId:Annotated[int,Query(ge=0)]=0,
        _user: Dict[str, Any] = Depends(get_organization_scope)):
    try:
        actor = _actor(_user)
        tenant = await _load_tenant(tenant_id, actor['orgId'])
        if not tenant or not can_read_tenant(tenant, actor):
            return bad_request(message=ACCESS_DENIED)
        service=await _tenant_graph_scope(actor,tenant_id,folderId)
        return success(await service.evidence(actor['orgId'], tenant_id, evidence_id))
    except GraphError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception('查看知识库图谱原文失败')
        return server_error('查看知识库图谱原文失败')


@router.post('/tenant/{tenant_id}/graph/query', summary='根据当前知识图谱及原文依据回答问题')
async def tenant_graph_query(body: KnowledgeGraphQuestion, tenant_id: int = ApiPath(gt=0),
        folderId:Annotated[int,Query(ge=0)]=0,
                             _user: Dict[str, Any] = Depends(get_organization_scope)):
    try:
        actor = _actor(_user)
        tenant = await _load_tenant(tenant_id, actor['orgId'])
        if not tenant or not can_read_tenant(tenant, actor):
            return bad_request(message=ACCESS_DENIED)
        service=await _tenant_graph_scope(actor,tenant_id,folderId)
        result = await service.answer(actor['orgId'], tenant_id, body.question)
        tenant = await _load_tenant(tenant_id, actor['orgId'])
        if not tenant or not can_read_tenant(tenant, actor):
            return bad_request(message=ACCESS_DENIED)
        return success(result)
    except GraphError as error:
        return bad_request(message=str(error), data={'errorCode': error.code})
    except Exception:
        logger.error('知识库图谱问答失败', exc_info=False)
        return server_error('图谱问答失败，请稍后重试')


def _attachment(filename: str, media_type: str, content: bytes) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "no-store",
        },
    )


async def _authorized_record(record_id: int, actor: dict[str, Any], *, manage: bool) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    record = await db_client.fetch_one(
        get_sql("record.find_by_id"),
        {"recordId": record_id, "orgId": actor["orgId"]},
    )
    if not record:
        return None, None
    tenant = await _load_tenant(int(record["tenantId"]), actor["orgId"])
    allowed = can_manage_tenant(tenant, actor) if manage and tenant else bool(tenant and can_read_tenant(tenant, actor))
    if not tenant or not allowed:
        return None, None
    return record, tenant


@router.get("/record/{record_id}", summary="查询知识数据详情")
async def get_record(
    record_id: int = ApiPath(gt=0),
    _user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(_user)
        record, _tenant = await _authorized_record(record_id, actor, manage=False)
        if not record:
            return bad_request(message=ACCESS_DENIED)
        return success(data=_serialize_record(record))
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("查询知识数据详情失败")
        return server_error("查询知识数据详情失败")


@router.get("/record/{record_id}/download", summary="下载知识资料文件")
async def download_record(
    record_id: int = ApiPath(gt=0),
    _user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(_user)
        record, _tenant = await _authorized_record(record_id, actor, manage=False)
        if not record:
            return bad_request(message=ACCESS_DENIED)
        original = read_original(str(record.get("fileId") or ""), str(record.get("fileUrl") or ""))
        if original:
            payload, filename, media_type = original
            return _attachment(filename, media_type, payload)
        content = await _document_text(record, actor)
        if not content.strip():
            return bad_request(message="没有可下载的内容")
        filename = text_download_name(str(record.get("fileUrl") or ""), str(record.get("title") or ""))
        return _attachment(filename, "text/plain; charset=utf-8", content.encode("utf-8-sig"))
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("下载知识资料失败")
        return server_error("下载知识资料失败")


@router.post("/tenant/{tenant_id}/records/insert", summary="手动新增知识资料并同步向量")
async def create_tenant_record(
    data: KnowledgeRecordCreate,
    tenant_id: int = ApiPath(gt=0),
    user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(user)
        tenant = await _load_tenant(tenant_id, actor["orgId"])
        if not tenant or int(tenant.get("enabled") or 0) != 1 or not can_manage_tenant(tenant, actor):
            return bad_request(message="知识库不存在或已停用")

        content = data.content.strip()
        if data.folderId:await knowledge_folders.scope(actor['orgId'],tenant_id,data.folderId)
        if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
            return bad_request(message="正文不能超过 60000 字节")
        prepared = {
            "title": data.title.strip(),
            "content": content,
            "fileUrl": "",
            "fileId": uuid.uuid4().hex[:12],
            "tenantId": tenant_id,
            "tenantName": tenant["tenantName"],
            "folderId":data.folderId,
        }
        inserted = await _insert_uploaded_records([prepared], actor)
        store = await _knowledge_store_for_scope(user)
        sync_result = await asyncio.to_thread(store.sync_records, inserted)
        record = inserted[0]
        response_record = {
            "id": record["id"],
            "title": record["title"],
            "fileUrl": record["fileUrl"],
            "fileId": record["fileId"],
            "version": record["version"],
            "tenantId": record["tenantId"],
            "tenantName": record["tenantName"],
        }
        return success(
            data={"record": response_record, "milvus": sync_result},
            message="知识资料新增并同步成功",
        )
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("手动新增知识资料失败")
        return server_error("MySQL 可能已保存，但向量同步失败，请执行同步修复")


@router.post("/tenant/{tenant_id}/upload", summary="上传 Word/Excel 并同步向量")
async def upload_tenant_records(
    tenant_id: int = ApiPath(gt=0),
    files: list[UploadFile] = File(...),
    user: Dict[str, Any] = Depends(get_organization_scope),
    folderId: Annotated[int,Query(ge=0)] = 0,
):
    if not files:
        return bad_request(message="至少上传一个文件")
    if len(files) > MAX_UPLOAD_FILES:
        for upload in files:
            await upload.close()
        return bad_request(message=f"单次最多上传 {MAX_UPLOAD_FILES} 个文件")
    saved_originals = []
    committed = False
    try:
        actor = _actor(user)
        tenant = await _load_tenant(tenant_id, actor["orgId"])
        if not tenant or int(tenant.get("enabled") or 0) != 1 or not can_manage_tenant(tenant, actor):
            return bad_request(message="知识库不存在或已停用")

        if folderId:await knowledge_folders.scope(actor['orgId'],tenant_id,folderId)
        prepared: list[dict[str, Any]] = []
        originals = []
        warnings = []
        for upload in files:
            safe_name = Path(upload.filename or "").name.strip()
            extension = Path(safe_name).suffix.lower()
            if extension not in ALLOWED_UPLOAD_EXTENSIONS:
                return bad_request(message="仅支持 .docx、.xlsx、.xls 文件")
            contents = await upload.read(MAX_UPLOAD_BYTES + 1)
            if not contents:
                return bad_request(message=f"文件 {safe_name} 不能为空")
            if len(contents) > MAX_UPLOAD_BYTES:
                return bad_request(message=f"文件 {safe_name} 不能超过 10 MB")
            try:
                content = (await asyncio.to_thread(extract_complete_text, safe_name, contents)).strip()
                warnings.extend(await asyncio.to_thread(document_warnings, safe_name, contents))
            except ValueError:
                raise
            except Exception:
                raise ValueError(f'文件 {safe_name} 无法解析，请检查文件格式或是否损坏') from None
            if not content:
                return bad_request(message=f"文件 {safe_name} 没有可提取的内容")
            file_id = uuid.uuid4().hex[:12]
            originals.append((file_id, safe_name, contents))
            parts = split_knowledge_text(content)
            if len(prepared) + len(parts) > MAX_UPLOAD_CHUNKS:
                raise ValueError('本批文件内容过长，请减少文件或拆分后再上传；本批尚未保存')
            for index, part in enumerate(parts, 1):
                prepared.append({
                    "title": Path(safe_name).stem[:220] + (f'（第{index}/{len(parts)}段）' if len(parts) > 1 else ''),
                    "content": part,
                    "fileUrl": safe_name[:300],
                    "fileId": file_id,
                    "tenantId": tenant_id,
                    "tenantName": tenant["tenantName"],
                    "folderId":folderId,
                })

        # 全批文件通过校验后再写文件，避免后面的坏文件导致前面的原件残留。
        for file_id, name, contents in originals:
            save_original(file_id, name, contents)
            saved_originals.append((file_id, name))
        inserted = await _insert_uploaded_records(prepared, actor)
        committed = True
        store = await _knowledge_store_for_scope(user)
        sync_result = await asyncio.to_thread(store.sync_records, inserted)
        response_items = [
            {
                "id": record["id"],
                "title": record["title"],
                "fileUrl": record["fileUrl"],
                "fileId": record["fileId"],
                "version": record["version"],
                "tenantId": record["tenantId"],
                "tenantName": record["tenantName"],
            }
            for record in inserted
        ]
        return success(
            data={"inserted": len(inserted), "files": len(files), "warnings": warnings, "items": response_items, "milvus": sync_result},
            message=f"成功上传 {len(files)} 个文件",
        )
    except ValueError as error:
        if committed:
            return server_error('资料已保存，但向量同步失败，请执行同步修复')
        return bad_request(message=str(error))
    except Exception:
        logger.exception("上传知识数据失败")
        return server_error("资料可能已保存，请刷新列表核对；向量同步失败时执行同步修复")
    finally:
        if saved_originals and not committed:
            for file_id, filename in saved_originals:
                try:
                    count = await db_client.fetch_one(get_sql('record.file_reference_count'), {'fileId': file_id, 'orgId': actor['orgId']})
                    if count and count.get('total') == 0:
                        delete_original(file_id, filename)
                except Exception:
                    logger.warning('原件保存状态待核对，保留文件以便恢复')
        for upload in files:
            await upload.close()


def _joined_document_text(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=lambda row: int(row["id"]))
    return "".join(str(row.get("content") or "") for row in ordered)


async def _document_text(record: dict[str, Any], actor: dict[str, Any]) -> str:
    file_id = str(record.get("fileId") or "").strip()
    if not file_id:
        return str(record.get("content") or "")
    rows = await db_client.fetch_all(
        get_sql("record.contents_by_file"),
        {"fileId": file_id, "tenantId": int(record["tenantId"]), "orgId": actor["orgId"]},
    )
    return _joined_document_text(rows) if rows else str(record.get("content") or "")


async def _remove_replaced_document(existing: dict[str, Any], actor: dict[str, Any], tenant_id: int, store) -> None:
    old_file_id = str(existing.get("fileId") or "").strip()
    record_id = int(existing["id"])
    if old_file_id:
        sibling_rows = await db_client.fetch_all(
            get_sql("record.ids_by_file"),
            {"fileId": old_file_id, "tenantId": tenant_id, "orgId": actor["orgId"]},
        )
        old_ids = [int(row["id"]) for row in sibling_rows] or [record_id]
        await asyncio.to_thread(store.delete_ids, old_ids)
        await db_client.execute(
            get_sql("record.physical_delete_by_file"),
            {"fileId": old_file_id, "tenantId": tenant_id, "orgId": actor["orgId"]},
        )
    else:
        await asyncio.to_thread(store.delete_ids, [record_id])
        await db_client.execute(
            get_sql("record.physical_delete"),
            {"recordId": record_id, "tenantId": tenant_id, "orgId": actor["orgId"]},
        )
    references = await db_client.fetch_one(
        get_sql("record.file_reference_count"),
        {"fileId": old_file_id, "orgId": actor["orgId"]},
    )
    if old_file_id and references and references.get("total") == 0:
        delete_original(old_file_id, str(existing.get("fileUrl") or ""))


@router.get("/tenant/{tenant_id}/records/{record_id}/content", summary="读取一份文档的完整正文")
async def get_document_content(
    tenant_id: int = ApiPath(gt=0),
    record_id: int = ApiPath(gt=0),
    _user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(_user)
        existing = await db_client.fetch_one(
            get_sql("record.find_by_id"),
            {"recordId": record_id, "orgId": actor["orgId"]},
        )
        if not existing or int(existing.get("tenantId") or 0) != tenant_id:
            return bad_request(message="文档不存在或不属于当前知识库")
        tenant = await _load_tenant(tenant_id, actor["orgId"])
        if not tenant or not can_read_tenant(tenant, actor):
            return bad_request(message=ACCESS_DENIED)
        return success(data={
            "id": record_id,
            "title": _document_title(existing),
            "fileUrl": existing.get("fileUrl") or "",
            "content": await _document_text(existing, actor),
        })
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("读取文档正文失败")
        return server_error("读取文档正文失败")


@router.post("/tenant/{tenant_id}/records/{record_id}/content", summary="用编辑后的正文覆盖文档")
async def save_document_content(
    body: KnowledgeDocumentContent,
    tenant_id: int = ApiPath(gt=0),
    record_id: int = ApiPath(gt=0),
    user: Dict[str, Any] = Depends(get_organization_scope),
):
    inserted = None
    try:
        actor = _actor(user)
        existing = await db_client.fetch_one(
            get_sql("record.find_by_id"),
            {"recordId": record_id, "orgId": actor["orgId"]},
        )
        if not existing or int(existing.get("tenantId") or 0) != tenant_id:
            return bad_request(message="文档不存在或不属于当前知识库")
        tenant = await _load_tenant(tenant_id, actor["orgId"])
        if not tenant or int(tenant.get("enabled") or 0) != 1 or not can_manage_tenant(tenant, actor):
            return bad_request(message="知识库不存在或已停用")
        content = body.content.strip()
        parts = split_knowledge_text(content)
        if len(parts) > MAX_UPLOAD_CHUNKS:
            return bad_request(message="文档内容过长，请缩短后再保存；原文档尚未改动")
        file_url = str(existing.get("fileUrl") or "")
        stem = Path(file_url).stem or _document_title(existing)
        file_id = uuid.uuid4().hex[:12]
        prepared = [
            {
                "title": stem[:220] + (f"（第{index}/{len(parts)}段）" if len(parts) > 1 else ""),
                "content": part,
                "fileUrl": file_url[:300],
                "fileId": file_id,
                "tenantId": tenant_id,
                "tenantName": tenant["tenantName"],
                "folderId":int(existing.get('folderId') or 0),
            }
            for index, part in enumerate(parts, 1)
        ]
        inserted = await _insert_uploaded_records(prepared, actor)
        store = await _knowledge_store_for_scope(user)
        sync_result = await asyncio.to_thread(store.sync_records, inserted)
        if existing.get('documentNodeId'):
            await knowledge_folders.rebind_document(actor,tenant_id,existing,inserted[0])
        await _remove_replaced_document(existing, actor, tenant_id, store)
        return success(
            data={"id": inserted[0]["id"], "milvus": sync_result},
            message="已用新内容覆盖，原数据和向量已删除",
        )
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("覆盖文档正文失败")
        if inserted:
            return server_error("新内容已保存，但旧数据清理未完成，请执行同步修复")
        return server_error("保存文档失败，原文档未改动")


@router.post("/tenant/{tenant_id}/records/{record_id}/replace", summary="用新文件覆盖已有文档")
async def replace_tenant_record(
    tenant_id: int = ApiPath(gt=0),
    record_id: int = ApiPath(gt=0),
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_organization_scope),
):
    saved_original = None
    inserted = None
    actor: dict[str, Any] = {}
    try:
        actor = _actor(user)
        existing = await db_client.fetch_one(
            get_sql("record.find_by_id"),
            {"recordId": record_id, "orgId": actor["orgId"]},
        )
        if not existing or int(existing.get("tenantId") or 0) != tenant_id:
            return bad_request(message="文档不存在或不属于当前知识库")
        tenant = await _load_tenant(tenant_id, actor["orgId"])
        if not tenant or int(tenant.get("enabled") or 0) != 1 or not can_manage_tenant(tenant, actor):
            return bad_request(message="知识库不存在或已停用")
        safe_name = Path(file.filename or "").name.strip()
        extension = Path(safe_name).suffix.lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            return bad_request(message="仅支持 .docx、.xlsx、.xls 文件")
        contents = await file.read(MAX_UPLOAD_BYTES + 1)
        if not contents:
            return bad_request(message=f"文件 {safe_name} 不能为空")
        if len(contents) > MAX_UPLOAD_BYTES:
            return bad_request(message=f"文件 {safe_name} 不能超过 10 MB")
        try:
            content = (await asyncio.to_thread(extract_complete_text, safe_name, contents)).strip()
            warnings = await asyncio.to_thread(document_warnings, safe_name, contents)
        except ValueError:
            raise
        except Exception:
            raise ValueError(f"文件 {safe_name} 无法解析，请检查文件格式或是否损坏") from None
        if not content:
            return bad_request(message=f"文件 {safe_name} 没有可提取的内容")
        parts = split_knowledge_text(content)
        if len(parts) > MAX_UPLOAD_CHUNKS:
            raise ValueError("文件内容过长，请拆分后再覆盖；原文档尚未改动")
        file_id = uuid.uuid4().hex[:12]
        prepared = [
            {
                "title": Path(safe_name).stem[:220] + (f"（第{index}/{len(parts)}段）" if len(parts) > 1 else ""),
                "content": part,
                "fileUrl": safe_name[:300],
                "fileId": file_id,
                "tenantId": tenant_id,
                "tenantName": tenant["tenantName"],
                "folderId":int(existing.get('folderId') or 0),
            }
            for index, part in enumerate(parts, 1)
        ]
        save_original(file_id, safe_name, contents)
        saved_original = (file_id, safe_name)
        inserted = await _insert_uploaded_records(prepared, actor)
        store = await _knowledge_store_for_scope(user)
        sync_result = await asyncio.to_thread(store.sync_records, inserted)
        old_file_id = str(existing.get("fileId") or "").strip()
        if existing.get('documentNodeId'):
            await knowledge_folders.rebind_document(actor,tenant_id,existing,inserted[0])
        if old_file_id:
            sibling_rows = await db_client.fetch_all(
                get_sql("record.ids_by_file"),
                {"fileId": old_file_id, "tenantId": tenant_id, "orgId": actor["orgId"]},
            )
            old_ids = [int(row["id"]) for row in sibling_rows]
            await asyncio.to_thread(store.delete_ids, old_ids or [record_id])
            await db_client.execute(
                get_sql("record.physical_delete_by_file"),
                {"fileId": old_file_id, "tenantId": tenant_id, "orgId": actor["orgId"]},
            )
        else:
            await asyncio.to_thread(store.delete_ids, [record_id])
            await db_client.execute(
                get_sql("record.physical_delete"),
                {"recordId": record_id, "tenantId": tenant_id, "orgId": actor["orgId"]},
            )
        references = await db_client.fetch_one(
            get_sql("record.file_reference_count"),
            {"fileId": old_file_id, "orgId": actor["orgId"]},
        )
        if old_file_id and references and references.get("total") == 0:
            delete_original(old_file_id, str(existing.get("fileUrl") or ""))
        return success(
            data={"fileName": safe_name, "warnings": warnings, "milvus": sync_result},
            message="已用新文件覆盖原文档",
        )
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("覆盖知识文档失败")
        if inserted:
            return server_error("新文件已保存，但覆盖未完成，请执行同步修复")
        return server_error("覆盖文档失败，原文档未改动")
    finally:
        if saved_original and inserted is None:
            try:
                count = await db_client.fetch_one(
                    get_sql("record.file_reference_count"),
                    {"fileId": saved_original[0], "orgId": actor["orgId"]},
                )
                if not count or count.get("total") == 0:
                    delete_original(*saved_original)
            except Exception:
                logger.warning("覆盖失败后的新文件待核对，保留以便恢复")
        await file.close()


@router.post("/record/update", summary="修改知识数据并同步向量")
async def update_record(
    data: KnowledgeRecordUpdate,
    user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(user)
        existing = await db_client.fetch_one(
            get_sql("record.find_by_id"),
            {"recordId": data.id, "orgId": actor["orgId"]},
        )
        if not existing:
            return bad_request(message="知识数据不存在")
        tenant = await _load_tenant(data.tenantId, actor["orgId"])
        if not tenant or int(tenant.get("enabled") or 0) != 1 or not can_manage_tenant(tenant, actor):
            return bad_request(message="目标知识库不存在或已停用")
        if int(existing.get("tenantId") or 0) != data.tenantId:
            if existing.get('documentNodeId'):
                return bad_request(message='该文档已关联下级空间，请在当前知识库内移动或管理')
            source = await _load_tenant(int(existing["tenantId"]), actor["orgId"])
            if not source or not can_manage_tenant(source, actor):
                return bad_request(message=ACCESS_DENIED)

        content = data.content.strip()
        if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
            return bad_request(message="正文不能超过 60000 字节")
        audit = fill_audit_fields({}, actor, is_update=True)
        params = {
            "recordId": data.id,
            "orgId": actor["orgId"],
            "expectedVersion": data.expectedVersion,
            "title": data.title.strip(),
            "content": content,
            "fileUrl": data.fileUrl.strip(),
            "tenantId": data.tenantId,
            "tenantName": tenant["tenantName"],
            "enabled": data.enabled,
            "updateUserId": audit["updateUserId"],
            "updateUserName": audit["updateUserName"],
            "updateTime": audit["updateTime"],
        }
        affected_rows = await _execute_transaction([(get_sql("record.update"), params)])
        affected = affected_rows[0] if affected_rows else 0
        if affected != 1:
            return bad_request(message="资料已被其他操作更新，请刷新后重试")
        updated = await db_client.fetch_one(
            get_sql("record.find_sync_by_id"),
            {"recordId": data.id, "orgId": actor["orgId"]},
        )
        if not updated:
            return server_error("修改后的知识数据读取失败")
        store = await _knowledge_store_for_scope(user)
        if data.enabled == 1:
            sync_result = await asyncio.to_thread(store.sync_records, [updated])
        else:
            deleted = await asyncio.to_thread(store.delete_ids, [data.id])
            sync_result = {"total": 1, "synced": 0, "skipped": 0, "deleted": deleted}
        return success(data={"record": updated, "milvus": sync_result}, message="知识数据修改成功")
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("修改知识数据失败")
        return server_error("MySQL 可能已修改，但向量同步失败，请执行同步修复")


@router.post("/record/delete", summary="删除知识数据及对应向量")
async def delete_record(
    data: KnowledgeRecordDelete,
    user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(user)
        existing = await db_client.fetch_one(
            get_sql("record.find_by_id"),
            {"recordId": data.id, "orgId": actor["orgId"]},
        )
        if not existing or int(existing.get("tenantId") or 0) != data.tenantId:
            return bad_request(message="知识数据不存在或不属于当前知识库")
        tenant = await _load_tenant(data.tenantId, actor["orgId"])
        if not tenant or not can_manage_tenant(tenant, actor):
            return bad_request(message=ACCESS_DENIED)
        file_id = str(existing.get("fileId") or "").strip()
        if file_id:
            sibling_rows = await db_client.fetch_all(
                get_sql("record.ids_by_file"),
                {"fileId": file_id, "tenantId": data.tenantId, "orgId": actor["orgId"]},
            )
            record_ids = [int(row["id"]) for row in sibling_rows] or [data.id]
            delete_sql = get_sql("record.physical_delete_by_file")
            delete_params = {"fileId": file_id, "tenantId": data.tenantId, "orgId": actor["orgId"]}
        else:
            record_ids = [data.id]
            delete_sql = get_sql("record.physical_delete")
            delete_params = {"recordId": data.id, "tenantId": data.tenantId, "orgId": actor["orgId"]}
        store = await _knowledge_store_for_scope(user)
        scoped_delete=await knowledge_folders.delete_document(actor,data.tenantId,existing,store) if existing.get('documentNodeId') else None
        if scoped_delete is None:
            deleted_vectors = await asyncio.to_thread(store.delete_ids, record_ids)
            deleted_rows = await db_client.execute(delete_sql, delete_params)
        else:
            deleted_vectors=scoped_delete['deletedVectors'];deleted_rows=scoped_delete['deletedRows']
        if deleted_rows < 1:
            return server_error("MySQL 删除失败，请执行同步修复")
        references = await db_client.fetch_one(get_sql('record.file_reference_count'),
            {'fileId': str(existing.get('fileId') or ''), 'orgId': actor['orgId']})
        if references and references.get('total') == 0:
            delete_original(str(existing.get("fileId") or ""), str(existing.get("fileUrl") or ""))
        return success(
            data={
                "id": data.id,
                "tenantId": data.tenantId,
                "deletedRows": deleted_rows,
                "deletedVectors": deleted_vectors,
            },
            message="文档已删除",
        )
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("删除知识数据失败")
        return server_error("删除知识数据失败")


@router.post("/tenant/{tenant_id}/sync", summary="修复知识库的 MySQL/Milvus 同步")
async def sync_tenant_records(
    tenant_id: int = ApiPath(gt=0),
    user: Dict[str, Any] = Depends(get_organization_scope),
):
    try:
        actor = _actor(user)
        tenant = await _load_tenant(tenant_id, actor["orgId"])
        if not tenant or not can_manage_tenant(tenant, actor):
            return bad_request(message=ACCESS_DENIED)
        records = await db_client.fetch_all(
            get_sql("record.active_sync_by_tenant"),
            {"tenantId": tenant_id, "orgId": actor["orgId"]},
        )
        store = await _knowledge_store_for_scope(user)
        vector_versions = await asyncio.to_thread(store.get_tenant_versions, tenant_id)
        source_ids = {int(record["id"]) for record in records}
        orphan_ids = sorted(record_id for record_id in vector_versions if record_id not in source_ids)
        deleted_orphans = 0
        if orphan_ids:
            deleted_orphans = await asyncio.to_thread(store.delete_ids, orphan_ids)
        sync_result = await asyncio.to_thread(store.sync_records, records)
        return success(
            data={
                **sync_result,
                "deletedOrphans": deleted_orphans,
                "tenantId": tenant_id,
            },
            message="同步修复完成",
        )
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("知识库同步修复失败")
        return server_error("知识库同步修复失败")
