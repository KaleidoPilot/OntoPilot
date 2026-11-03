import asyncio
import json

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from api.endpoints.mcp.modular.mcp import (CompanyMcpQuery, CompanyMcpSave, McpUserQuery, SkillMcpOptions,
    McpApproval, McpBindingsSave, McpConfigSave, McpId, McpToolsSave, McpTest, McpCategorySave)
from api.endpoints.mcp.runtime import approval_state, discover, http_definition, send_http
from api.endpoints.mcp.service import (config_view, get_personal_identity, json_value, owned_config,
    owned_skill, save_bindings, save_config, scope, transaction, personal_config,
    company_config, get_company_scope, save_company_config, get_runtime_identity)
from api.endpoints.mcp.sql import get_mcp_sql
from utils.mysqldb import db_client
from utils.response import bad_request, server_error, success
from utils.context import fill_audit_fields

class PersonalMcpRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                # FastAPI 默认校验错误会附带请求原文；个人凭据接口只返回字段名和错误。
                errors = [{"field": ".".join(map(str, item["loc"])), "message": item["msg"]} for item in exc.errors()]
                return bad_request(message="请检查 MCP 配置字段", data={"errors": errors})
            except HTTPException:
                raise
            except Exception:
                return server_error("MCP 请求失败，请稍后重试")
        return handler


router = APIRouter(route_class=PersonalMcpRoute)


def test_arguments(tool, arguments):
    values = tool['httpRequest'].get('testValues', {})
    return {**{key: value for key, value in values.items() if key in tool['inputSchema']['properties']}, **arguments}


@router.get('/company/categories', summary='查询当前公司 MCP 分类')
async def company_categories(company=Depends(get_company_scope)):
    return success(data=await db_client.fetch_all(get_mcp_sql('category.list'), {'orgId': company['orgId']}))


@router.get('/categories', summary='查询本人公司 MCP 分类名称')
async def available_categories(identity=Depends(get_personal_identity)):
    return success(data=await db_client.fetch_all(get_mcp_sql('category.names'), scope(identity)))


@router.post('/company/categories/save', summary='新增或编辑公司 MCP 分类')
async def save_category(data: McpCategorySave, company=Depends(get_company_scope)):
    params = {'orgId': company['orgId'], 'id': data.id, 'name': data.name}
    try:
        async with db_client.engine.begin() as conn:
            if data.id and not (await conn.execute(text(get_mcp_sql('category.lock')), params)).mappings().first():
                raise ValueError('分类不存在或不属于当前公司')
            fill_audit_fields(params, company['identity'], is_update=bool(data.id))
            result = await conn.execute(text(get_mcp_sql('category.update' if data.id else 'category.insert')), params)
        return success(data={'id': data.id or int(result.lastrowid)}, message='分类已保存')
    except IntegrityError:
        return bad_request(message='当前公司已有同名分类')
    except ValueError as exc:
        return bad_request(message=str(exc))


@router.post('/company/categories/delete', summary='删除未使用的公司 MCP 分类')
async def delete_category(data: McpId, company=Depends(get_company_scope)):
    params = {'orgId': company['orgId'], 'id': data.id}
    try:
        async with db_client.engine.begin() as conn:
            if not (await conn.execute(text(get_mcp_sql('category.lock')), params)).mappings().first():
                raise ValueError('分类不存在或不属于当前公司')
            count = (await conn.execute(text(get_mcp_sql('category.references')), params)).mappings().first()
            if count['total']:
                raise ValueError('分类下仍有 MCP，请先移动或删除 MCP')
            await conn.execute(text(get_mcp_sql('category.delete')), params)
        return success(message='分类已删除')
    except ValueError as exc:
        return bad_request(message=str(exc))


@router.get("/personal", summary="查询本人的 MCP 配置")
async def list_configs(identity=Depends(get_personal_identity)):
    records = await db_client.fetch_all(get_mcp_sql("config.list"), scope(identity))
    return success(data=[config_view(dict(row)) for row in records])


@router.get("/available", summary="查询本人有权使用的个人及公司 MCP")
async def available_configs(identity=Depends(get_personal_identity)):
    records = await db_client.fetch_all(get_mcp_sql("available.list"), scope(identity))
    return success(data=[config_view(dict(row)) for row in records])


@router.post("/personal/save", summary="保存个人 MCP 配置")
async def save(data: McpConfigSave, identity=Depends(get_personal_identity)):
    try:
        return success(data={"id": await save_config(identity, data)}, message="MCP 配置已保存")
    except IntegrityError:
        return bad_request(message="已有同名 MCP 配置")
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        return server_error("MCP 配置保存失败")


@router.post("/personal/test", summary="连接本人的 MCP 并读取工具列表")
async def test_connection(data: McpTest, identity=Depends(get_personal_identity)):
    try:
        config = await personal_config(identity, data.id)
        if http_definition(config):
            result = await send_http(config, test_arguments(http_definition(config), data.arguments))
            return success(data={"tools": [http_definition(config)], "result": result}, message="HTTP 请求已完成")
        async with asyncio.timeout(60):
            tools = await discover(config)
        params = scope(identity, id=data.id, url=config["url"], authType=config["authType"], secretCipher=config["secretCipher"],
                       toolsJson=json.dumps(tools, ensure_ascii=False))
        changed = await db_client.execute(get_mcp_sql("config.snapshot"), params)
        if not changed:
            current = await personal_config(identity, data.id)
            if any(current[k] != config[k] for k in ("url", "authType", "secretCipher")):
                return bad_request(message="配置已变更，请重新测试连接")
        return success(data={"tools": tools}, message="连接成功，请选择需要的工具")
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        return bad_request(message="请求失败或超时，请检查服务地址和后端网络；POST 可能已执行，请核对后再重试")


@router.post("/personal/tools", summary="保存本人允许使用的 MCP 工具")
async def save_tools(data: McpToolsSave, identity=Depends(get_personal_identity)):
    try:
        config = await personal_config(identity, data.id)
        available = {tool["name"] for tool in json_value(config["toolsJson"], [])}
        if not set(data.toolNames) <= available:
            return bad_request(message="请先测试连接，并从返回列表中选择工具")
        await db_client.execute(get_mcp_sql("config.tools"), scope(identity, id=data.id,
            selectedToolsJson=json.dumps(data.toolNames, ensure_ascii=False)))
        return success(message="工具选择已保存")
    except ValueError as exc:
        return bad_request(message=str(exc))


@router.post("/personal/delete", summary="删除本人的 MCP 配置及技能绑定")
async def delete(data: McpId, identity=Depends(get_personal_identity)):
    try:
        await personal_config(identity, data.id)
        params = scope(identity, id=data.id)
        await transaction([("binding.delete_config", params), ("config.delete", params)])
        return success(message="MCP 配置已删除")
    except ValueError as exc:
        return bad_request(message=str(exc))


@router.get("/personal/skills/{skill_id}", summary="查询本人私有技能的 MCP 工具绑定")
async def bindings(skill_id: int, identity=Depends(get_personal_identity)):
    try:
        await owned_skill(identity, skill_id)
        rows = await db_client.fetch_all(get_mcp_sql("binding.list"), scope(identity, skillId=skill_id))
        result = []
        for row in rows:
            available = True
            try:
                current = await owned_config(identity, row["configId"], active=True)
                available = set(json_value(row["toolNamesJson"], [])) <= set(json_value(current["selectedToolsJson"], []))
            except ValueError:
                available = False
            result.append({"configId": row["configId"], "toolNames": json_value(row["toolNamesJson"], []), "available": available})
        return success(data=result)
    except ValueError as exc:
        return bad_request(message=str(exc))


@router.post("/personal/skills/save", summary="保存本人私有技能的 MCP 工具绑定")
async def bind(data: McpBindingsSave, identity=Depends(get_personal_identity)):
    try:
        await save_bindings(identity, data)
        return success(message="技能工具绑定已保存")
    except ValueError as exc:
        return bad_request(message=str(exc))


@router.post("/personal/approvals/reject", summary="拒绝本人的 MCP 待确认操作")
async def reject(data: McpApproval, identity=Depends(get_personal_identity)):
    try:
        await approval_state(identity, data.configId, reject={"id": data.id})
        return success(message="操作已取消")
    except ValueError as exc:
        return bad_request(message=str(exc))


@router.post("/company/querylist", summary="分页查询当前公司的 MCP")
async def company_list(query: CompanyMcpQuery, company=Depends(get_company_scope)):
    params = {"orgId": company["orgId"], "keyword": query.keyword or None,
        "visibility": query.visibility, "enabled": query.enabled, "categoryId": query.categoryId}
    count = await db_client.fetch_one(get_mcp_sql("company.count"), params)
    rows = await db_client.fetch_all(get_mcp_sql("company.list"), {**params,
        "limit": query.pageSize, "offset": (query.pageNo - 1) * query.pageSize})
    return success(data={"list": [{**config_view(dict(row)), "canManage": True,
        "accessUserIds": json_value(row["accessUserIdsJson"], [])} for row in rows],
        "total": int(count["total"]), "pageNo": query.pageNo, "pageSize": query.pageSize})


@router.post("/runtime/approvals/reject", summary="拒绝当前调用人的 MCP 操作确认")
async def reject_runtime(data: McpApproval, identity=Depends(get_runtime_identity)):
    try:
        await approval_state(identity, data.configId, reject={"id": data.id})
        return success(message="操作已取消")
    except ValueError as exc:
        return bad_request(message=str(exc))


@router.post("/company/users", summary="查询当前公司可授权的用户")
async def company_users(query: McpUserQuery, company=Depends(get_company_scope)):
    users = await db_client.fetch_all(get_mcp_sql("company.users"), {"orgId": company["orgId"],
        "keyword": query.keyword or None, "ids": ",".join(map(str, query.ids))})
    return success(data={"list": users})


@router.post("/company/skills/options", summary="查询技能可绑定的 MCP 及具体工具")
async def company_skill_options(query: SkillMcpOptions, company=Depends(get_company_scope)):
    if query.skillType == 3:
        if not query.userId or not await db_client.fetch_one(get_mcp_sql("binding.owner"), {"orgId": company["orgId"], "userId": query.userId}):
            return bad_request(message="请先选择当前公司的启用用户")
        rows = await db_client.fetch_all(get_mcp_sql("available.list"), {"orgId": company["orgId"], "userId": query.userId})
    else:
        rows = await db_client.fetch_all(get_mcp_sql("binding.public_options"), {"orgId": company["orgId"]})
    return success(data=[config_view(dict(row)) for row in rows if row["enabled"] == 1])


@router.get("/company/skills/{skill_id}", summary="查询当前公司技能的 MCP 工具绑定")
async def company_skill_bindings(skill_id: int, company=Depends(get_company_scope)):
    skill = await db_client.fetch_one(get_mcp_sql("binding.skill_get"), {"orgId": company["orgId"], "skillId": skill_id})
    if not skill or skill["skillType"] not in (1, 2, 3):
        return bad_request(message="技能不存在或不属于当前公司")
    owner_id = int(skill["userId"]) if skill["skillType"] == 3 else 0
    rows = await db_client.fetch_all(get_mcp_sql("binding.list"), {"orgId": company["orgId"], "userId": owner_id, "skillId": skill_id})
    return success(data=[{"configId": row["configId"], "toolNames": json_value(row["toolNamesJson"], [])} for row in rows])


@router.post("/company/save", summary="保存公司 MCP 及其可用用户范围")
async def company_save(data: CompanyMcpSave, company=Depends(get_company_scope)):
    try:
        config_id = await save_company_config(company, data)
        return success(data={"id": config_id}, message="公司 MCP 已保存")
    except IntegrityError:
        return bad_request(message="当前公司已有同名 MCP")
    except ValueError as exc:
        return bad_request(message=str(exc))


@router.post("/company/test", summary="连接公司 MCP 并读取工具列表")
async def company_test(data: McpTest, company=Depends(get_company_scope)):
    try:
        config = await company_config(company, data.id)
        if http_definition(config):
            result = await send_http(config, test_arguments(http_definition(config), data.arguments))
            return success(data={"tools": [http_definition(config)], "result": result}, message="HTTP 请求已完成")
        async with asyncio.timeout(60):
            tools = await discover(config)
        params = {"orgId": company["orgId"], "id": data.id, "url": config["url"],
            "authType": config["authType"], "secretCipher": config["secretCipher"],
            "toolsJson": json.dumps(tools, ensure_ascii=False)}
        await db_client.execute(get_mcp_sql("company.snapshot"), params)
        current = await company_config(company, data.id)
        if any(current[k] != config[k] for k in ("url", "authType", "secretCipher")):
            return bad_request(message="配置已变更，请重新测试连接")
        return success(data={"tools": tools}, message="连接成功，请选择工具")
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        return bad_request(message="请求失败或超时，请检查服务地址和后端网络；POST 可能已执行，请核对后再重试")


@router.post("/company/tools", summary="保存公司 MCP 可用的工具")
async def company_tools(data: McpToolsSave, company=Depends(get_company_scope)):
    try:
        params = {"orgId": company["orgId"], "id": data.id}
        async with db_client.engine.begin() as conn:
            row = (await conn.execute(text(get_mcp_sql("company.lock")), params)).mappings().first()
            if not row:
                raise ValueError("公司 MCP 不存在或不属于当前公司")
            if not set(data.toolNames) <= {tool["name"] for tool in json_value(row["toolsJson"], [])}:
                raise ValueError("请先测试连接，并从返回列表中选择工具")
            await conn.execute(text(get_mcp_sql("company.tools")), {**params,
                "selectedToolsJson": json.dumps(data.toolNames, ensure_ascii=False)})
        return success(message="工具选择已保存")
    except ValueError as exc:
        return bad_request(message=str(exc))


@router.post("/company/delete", summary="删除公司 MCP 及其全部技能绑定")
async def company_delete(data: McpId, company=Depends(get_company_scope)):
    try:
        params = {"orgId": company["orgId"], "id": data.id}
        async with db_client.engine.begin() as conn:
            row = (await conn.execute(text(get_mcp_sql("company.lock")), params)).mappings().first()
            if not row:
                raise ValueError("公司 MCP 不存在或不属于当前公司")
            await conn.execute(text(get_mcp_sql("binding.delete_company_config")), params)
            await conn.execute(text(get_mcp_sql("company.delete")), params)
        return success(message="公司 MCP 已删除")
    except ValueError as exc:
        return bad_request(message=str(exc))
