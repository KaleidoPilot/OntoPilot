import json
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends
from sqlalchemy import text

from api.endpoints.organization.dependencies import (
    get_internal_organization_scope as get_organization_scope,
)
from api.endpoints.system.modular.system import (
    ModelConfigCreate,
    ModelConfigBatchDelete,
    ModelConfigDelete,
    ModelConfigQuery,
    ModelConfigUpdate,
    SystemConfigCreate,
    SystemConfigDelete,
    SystemConfigQuery,
    SystemConfigSecretReveal,
    SystemConfigUpdate,
)
from api.endpoints.system.sql import SQL_CONFIG_PATH, get_system_sql
from api.endpoints.system.service import validate_sandbox_config
from utils.context import fill_audit_fields
from utils.mysqldb import db_client
from utils.response import bad_request, server_error, success


router = APIRouter()
logger = logging.getLogger(__name__)
MASKED_SECRET = "******"
SECRET_KEYS = {"api_key", "apikey", "password", "token", "secret"}


class _SecretParameter(str):
    """数据库接收真实字符串，但公共 SQL 参数日志不展示密钥。"""

    def __repr__(self) -> str:
        return "'***'"


def get_sql(key: str) -> str:
    return get_system_sql(key)


def _is_secret_key(key: str) -> bool:
    normalized = key.replace("-", "").replace("_", "").lower()
    return normalized in SECRET_KEYS or normalized.endswith(
        ("apikey", "password", "token", "secret")
    )


def _mask_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: MASKED_SECRET if _is_secret_key(key) and item else _mask_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask_secrets(item) for item in value]
    return value


def _preserve_masked_secrets(new_value: Any, old_value: Any) -> Any:
    if isinstance(new_value, dict):
        old_dict = old_value if isinstance(old_value, dict) else {}
        result: dict[str, Any] = {}
        for key, item in new_value.items():
            if _is_secret_key(key) and item in (None, "", MASKED_SECRET):
                result[key] = old_dict.get(key)
            else:
                result[key] = _preserve_masked_secrets(item, old_dict.get(key))
        return result
    if isinstance(new_value, list):
        old_list = old_value if isinstance(old_value, list) else []
        return [
            _preserve_masked_secrets(item, old_list[index] if index < len(old_list) else None)
            for index, item in enumerate(new_value)
        ]
    return new_value


def _decode_config(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        decoded = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("配置内容不是合法JSON") from error
    if not isinstance(decoded, dict):
        raise ValueError("配置内容必须是JSON对象")
    return decoded


def _serialize_config_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "configJson": _mask_secrets(_decode_config(row.get("configJson"))),
    }


def _scope_org_id(scope: dict[str, Any]) -> int:
    """路由依赖始终提供 orgId；默认值仅保留旧单元测试的直接函数调用。"""
    return int(scope.get("orgId", 1)) if isinstance(scope, dict) else 1


def _scope_identity(scope: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(scope, dict):
        return {"id": 1, "name": "admin"}
    return scope.get("identity", scope)


@router.get("/config", summary="读取当前公司的兼容配置视图")
async def get_config(scope: dict = Depends(get_organization_scope)):
    try:
        rows = await db_client.fetch_all(
            get_sql("system_config.list_active"), {"orgId": _scope_org_id(scope)}
        )
        result = {
            "model_settings": {},
            "milvus_settings": {},
            "database_settings": {},
            "sandbox_settings": {},
        }
        type_keys = {
            1: "database_settings",
            2: "model_settings",
            3: "milvus_settings",
            4: "sandbox_settings",
        }
        for row in rows:
            key = type_keys.get(int(row["configType"]))
            if key and not result[key]:
                result[key] = _mask_secrets(_decode_config(row["configJson"]))
        return success(data=result)
    except Exception:
        logger.exception("读取公司系统配置失败")
        return server_error("读取系统配置失败")


@router.put("/config", summary="更新当前公司的兼容配置视图")
async def update_config(
    config: Dict[str, Any] = Body(...),
    scope: dict = Depends(get_organization_scope),
):
    mapping = {
        "database_settings": (1, "平台业务数据库"),
        "model_settings": (2, "运行时AI模型"),
        "milvus_settings": (3, "默认向量库"),
        "sandbox_settings": (4, "默认沙箱"),
    }
    try:
        for key, (config_type, config_name) in mapping.items():
            if key not in config:
                continue
            existing = await db_client.fetch_one(
                get_sql("system_config.find_duplicate"),
                {
                    "orgId": _scope_org_id(scope),
                    "configType": config_type,
                    "configName": config_name,
                    "excludeId": 0,
                },
            )
            if not existing:
                return bad_request(message=f"缺少“{config_name}”配置记录")
            record = await db_client.fetch_one(
                get_sql("system_config.find_by_id"),
                {"id": existing["id"], "orgId": _scope_org_id(scope)},
            )
            merged = _preserve_masked_secrets(
                config[key], _decode_config(record["configJson"])
            )
            if config_type == 4:
                merged = validate_sandbox_config(merged)
            params = fill_audit_fields(
                {
                    "id": existing["id"],
                    "orgId": _scope_org_id(scope),
                    "configType": None,
                    "configName": None,
                    "configJson": _SecretParameter(json.dumps(merged, ensure_ascii=False)),
                    "enabled": None,
                },
                _scope_identity(scope),
                is_update=True,
            )
            await db_client.execute(get_sql("system_config.update"), params)
        return success(message="配置更新成功")
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("更新公司系统配置失败")
        return server_error("配置更新失败")


@router.post("/configuration/querylist", summary="分页查询公司系统配置")
async def query_system_configs(
    query: SystemConfigQuery,
    scope: dict = Depends(get_organization_scope),
):
    try:
        filters = {
            "orgId": _scope_org_id(scope),
            "configName": query.configName,
            "configType": query.configType,
            "enabled": query.enabled,
        }
        count = await db_client.fetch_one(get_sql("system_config.count"), filters)
        rows = await db_client.fetch_all(
            get_sql("system_config.list"),
            {
                **filters,
                "limit": query.pageSize,
                "offset": (query.pageNo - 1) * query.pageSize,
            },
        )
        return success(data={
            "list": [_serialize_config_row(row) for row in rows],
            "total": int(count.get("total", 0)) if count else 0,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize,
        })
    except Exception:
        logger.exception("查询公司系统配置失败")
        return server_error("系统配置查询失败")


@router.post("/configuration/secret/reveal", summary="显式查看当前公司单条配置密钥")
async def reveal_system_config_secret(
    data: SystemConfigSecretReveal,
    scope: dict = Depends(get_organization_scope),
):
    try:
        record = await db_client.fetch_one(
            get_sql("system_config.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(scope)},
        )
        if not record:
            return bad_request(message="系统配置不存在")
        value: Any = _decode_config(record["configJson"])
        for part in data.secretPath.split("."):
            if not isinstance(value, dict) or part not in value:
                return bad_request(message="该配置没有可查看的密钥")
            value = value[part]
        response = success(data={"value": str(value or "")})
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response
    except Exception:
        logger.exception("查看系统配置密钥失败")
        return server_error("系统配置密钥读取失败")


@router.get("/configuration/sandbox-options", summary="当前公司可绑定的沙箱（不返回Token）")
async def list_sandbox_options(scope: dict = Depends(get_organization_scope)):
    try:
        rows = await db_client.fetch_all(get_sql("system_config.list_active"), {"orgId": _scope_org_id(scope)})
        options = []
        for row in rows:
            if int(row["configType"]) != 4:
                continue
            try:
                config = validate_sandbox_config(_decode_config(row["configJson"]))
            except ValueError:
                continue
            options.append({"id": row["id"], "url": config["url"], "name": config.get("name", "")})
        return success(data={"list": options})
    except Exception:
        logger.exception("读取可用沙箱失败")
        return server_error("可用沙箱读取失败")


@router.post("/configuration/insert", summary="新增公司系统配置")
async def create_system_config(
    data: SystemConfigCreate,
    scope: dict = Depends(get_organization_scope),
):
    try:
        config_json = validate_sandbox_config(data.configJson, require_database=True) if data.configType == 4 else data.configJson
        duplicate = await db_client.fetch_one(
            get_sql("system_config.find_duplicate"),
            {
                "orgId": _scope_org_id(scope),
                "configType": data.configType,
                "configName": data.configName,
                "excludeId": 0,
            },
        )
        if duplicate:
            return bad_request(message="当前公司已存在同类型同名称配置")
        params = fill_audit_fields(
            {
                "orgId": _scope_org_id(scope),
                "configType": data.configType,
                "configName": data.configName,
                "configJson": _SecretParameter(
                    json.dumps(config_json, ensure_ascii=False)
                ),
                "enabled": data.enabled,
            },
            _scope_identity(scope),
            is_update=False,
        )
        config_id = await db_client.execute_insert(
            get_sql("system_config.insert"), params
        )
        return success(data={"id": config_id}, message="系统配置新增成功")
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("新增公司系统配置失败")
        return server_error("系统配置新增失败")


@router.post("/configuration/update", summary="修改公司系统配置")
async def update_system_config(
    data: SystemConfigUpdate,
    scope: dict = Depends(get_organization_scope),
):
    try:
        existing = await db_client.fetch_one(
            get_sql("system_config.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(scope)},
        )
        if not existing:
            return bad_request(message="系统配置不存在")
        config_type = data.configType or int(existing["configType"])
        if config_type != int(existing["configType"]) and 4 in (config_type, int(existing["configType"])):
            return bad_request(message="沙箱配置不能与其他配置类型互相转换")
        config_name = data.configName or existing["configName"]
        duplicate = await db_client.fetch_one(
            get_sql("system_config.find_duplicate"),
            {
                "orgId": _scope_org_id(scope),
                "configType": config_type,
                "configName": config_name,
                "excludeId": data.id,
            },
        )
        if duplicate:
            return bad_request(message="当前公司已存在同类型同名称配置")
        config_json = None
        if data.configJson is not None:
            merged = _preserve_masked_secrets(
                data.configJson, _decode_config(existing["configJson"])
            )
            if config_type == 4:
                merged = validate_sandbox_config(merged)
            config_json = _SecretParameter(json.dumps(merged, ensure_ascii=False))
        elif config_type == 4 and data.enabled == 1:
            validate_sandbox_config(_decode_config(existing["configJson"]))
        params = fill_audit_fields(
            {
                "id": data.id,
                "orgId": _scope_org_id(scope),
                "configType": data.configType,
                "configName": data.configName,
                "configJson": config_json,
                "enabled": data.enabled,
            },
            _scope_identity(scope),
            is_update=True,
        )
        affected = await db_client.execute(get_sql("system_config.update"), params)
        if affected != 1:
            return bad_request(message="系统配置已发生变化，请刷新后重试")
        return success(message="系统配置修改成功")
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("修改公司系统配置失败")
        return server_error("系统配置修改失败")


@router.post("/configuration/delete", summary="物理删除公司系统配置")
async def delete_system_config(
    data: SystemConfigDelete,
    scope: dict = Depends(get_organization_scope),
):
    try:
        reference_params = {"id": data.id, "orgId": _scope_org_id(scope)}
        references = await db_client.fetch_all(get_sql("system_config.sandbox_references"), reference_params)
        if references:
            names = "、".join(f"{row['groupName']}（ID：{row['id']}）" for row in references)
            return bad_request(message=f"沙箱被以下项目组绑定，不能删除：{names}。请先解除绑定或删除相应项目组。", data={"projectGroups": references})
        affected = await db_client.execute(
            get_sql("system_config.delete"),
            {"id": data.id, "orgId": _scope_org_id(scope)},
        )
        if affected != 1:
            references = await db_client.fetch_all(get_sql("system_config.sandbox_references"), reference_params)
            if references:
                names = "、".join(f"{row['groupName']}（ID：{row['id']}）" for row in references)
                return bad_request(message=f"沙箱被以下项目组绑定，不能删除：{names}。请先解除绑定或删除相应项目组。", data={"projectGroups": references})
            return bad_request(message="系统配置不存在")
        return success(message="系统配置删除成功")
    except Exception:
        logger.exception("删除公司系统配置失败")
        return server_error("系统配置删除失败")


# 以下接口保留给尚未迁移的智能体页面，但同样受公司范围限制。
@router.post("/model-config/querylist", response_model=dict, summary="查询兼容模型配置")
async def query_model_configs(
    query: ModelConfigQuery,
    scope: dict = Depends(get_organization_scope),
):
    try:
        filters = {
            "orgId": _scope_org_id(scope),
            "model": query.model,
            "type": query.type,
            "enabled": query.enabled,
        }
        count_row = await db_client.fetch_one(get_sql("model_config.count"), filters)
        rows = await db_client.fetch_all(
            get_sql("model_config.list"),
            {
                **filters,
                "limit": query.pageSize,
                "offset": (query.pageNo - 1) * query.pageSize,
            },
        )
        return success(data={
            "total": int(count_row.get("total", 0)) if count_row else 0,
            "list": [{**row, "hasApiKey": bool(row.get("hasApiKey"))} for row in rows],
            "pageNo": query.pageNo,
            "pageSize": query.pageSize,
        })
    except Exception:
        logger.exception("查询模型配置失败")
        return server_error("查询模型配置失败")


@router.post("/model-config/insert", response_model=dict, summary="新增兼容模型配置")
async def insert_model_config(
    data: ModelConfigCreate,
    scope: dict = Depends(get_organization_scope),
):
    try:
        insert_data = fill_audit_fields(
            {
                "orgId": _scope_org_id(scope),
                "model": data.model,
                "apiKey": _SecretParameter(data.apiKey),
                "baseUrl": data.baseUrl,
                "type": data.type,
                "enabled": data.enabled,
            },
            _scope_identity(scope),
            is_update=False,
        )
        inserted_id = await db_client.execute_insert(
            get_sql("model_config.insert"), insert_data
        )
        return success(data={"id": inserted_id}, message="模型配置新增成功")
    except Exception:
        logger.exception("新增模型配置失败")
        return server_error("新增模型配置失败")


@router.post("/model-config/update", response_model=dict, summary="修改兼容模型配置")
async def update_model_config(
    data: ModelConfigUpdate,
    scope: dict = Depends(get_organization_scope),
):
    try:
        update_data = data.model_dump(exclude={"id"}, exclude_unset=True, exclude_none=True)
        if not update_data:
            return bad_request(message="没有需要更新的模型配置字段")
        existing = await db_client.fetch_one(
            get_sql("model_config.find_by_id"),
            {"id": data.id, "orgId": _scope_org_id(scope)},
        )
        if not existing:
            return bad_request(message="模型配置不存在")
        params = {
            "id": data.id,
            "orgId": _scope_org_id(scope),
            "model": None,
            "baseUrl": None,
            "type": None,
            "enabled": None,
            **update_data,
        }
        sql_key = "model_config.update"
        if "apiKey" in params:
            params["apiKey"] = _SecretParameter(params["apiKey"])
            sql_key = "model_config.update_with_api_key"
        params = fill_audit_fields(params, _scope_identity(scope), is_update=True)
        await db_client.execute(get_sql(sql_key), params)
        return success(message="模型配置修改成功")
    except Exception:
        logger.exception("修改模型配置失败")
        return server_error("修改模型配置失败")


async def _delete_model_configs(ids: list[int], scope: dict):
    params = {"ids": ",".join(str(model_id) for model_id in sorted(ids)), "orgId": _scope_org_id(scope)}
    try:
        async with db_client.engine.begin() as conn:
            models = (await conn.execute(text(get_sql("model_config.lock_for_delete")), params)).mappings().all()
            if len(models) != len(ids):
                raise ValueError("部分模型不存在或已删除，请刷新后重试")
            references = (await conn.execute(text(get_sql("model_config.agent_references")), params)).mappings().all()
            if references:
                names = "、".join(row["agentName"] or str(row["id"]) for row in references)
                raise ValueError(f"模型被智能体引用：{names}。请先在智能体中更换或清空模型，再删除。")
            skill_references = (await conn.execute(text(get_sql('model_config.skill_references')), params)).mappings().all()
            if skill_references:
                names = '、'.join(row['skillName'] or str(row['id']) for row in skill_references)
                raise ValueError(f'模型被技能引用：{names}。请先在技能管理中更换或清空模型。')
            result = await conn.execute(text(get_sql("model_config.delete")), params)
            if result.rowcount != len(ids):
                raise ValueError("模型引用或状态已发生变化，本次未删除任何模型，请刷新后重试")
        return success(data={"deletedCount": len(ids)}, message=f"已删除 {len(ids)} 条模型配置")
    except ValueError as error:
        return bad_request(message=str(error))
    except Exception:
        logger.exception("删除模型配置失败")
        return server_error("模型配置删除失败")


@router.post("/model-config/delete", response_model=dict, summary="物理删除未被智能体引用的模型")
async def delete_model_config(
    data: ModelConfigDelete,
    scope: dict = Depends(get_organization_scope),
):
    return await _delete_model_configs([data.id], scope)


@router.post("/model-config/batch-delete", response_model=dict, summary="原子批量物理删除模型配置")
async def batch_delete_model_configs(
    data: ModelConfigBatchDelete,
    scope: dict = Depends(get_organization_scope),
):
    return await _delete_model_configs(data.ids, scope)
