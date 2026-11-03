"""个人及公司 MCP 的身份、加密存储和工具授权；不修改公共 utils。"""
import json
import os
import threading
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request
from sqlalchemy import text

from api.endpoints.mcp.sql import get_mcp_sql
from api.endpoints.user.sql import get_user_sql
from api.endpoints.organization.sql import get_organization_sql
from utils.context import fill_audit_fields, get_current_user
from utils.mysqldb import db_client

_key_lock = threading.Lock()


def cipher() -> Fernet:
    """部署可用 PERSONAL_MCP_KEY；本机首次使用生成独立、不可入库的密钥。"""
    key = os.getenv("PERSONAL_MCP_KEY")
    if key:
        return Fernet(key.encode())
    path = Path(__file__).resolve().parents[3] / ".personal-mcp.key"
    with _key_lock:
        if not path.exists():
            generated_key = Fernet.generate_key()
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, "wb") as file:
                    file.write(generated_key)
        for _ in range(20):
            key = path.read_bytes().strip()
            if key:
                return Fernet(key)
            # 另一进程可能刚创建文件但尚未完成写入。
            time.sleep(0.01)
    raise ValueError("个人 MCP 密钥文件不可用")


def issue_access_token(user: dict) -> str:
    user_type = user.get("userType", "external")
    payload = {"purpose": "personal-mcp", "id": int(user["id"]), "userType": user_type}
    if user_type == "external":
        payload.update(orgId=int(user["orgId"]), groupId=int(user["groupId"]))
    return cipher().encrypt(json.dumps(payload).encode()).decode()


async def get_personal_identity(request: Request) -> dict:
    token = request.headers.get("x-mcp-token", "")
    if not token:
        raise HTTPException(401, "请重新登录后使用 MCP")
    try:
        payload = json.loads(cipher().decrypt(token.encode(), ttl=86400))
        if payload.get("purpose") != "personal-mcp":
            raise ValueError
        if payload.get("userType", "external") != "external":
            raise HTTPException(403, "此 MCP 接口仅供外部用户使用")
        user_id = int(payload["id"])
    except (InvalidToken, ValueError, KeyError, TypeError):
        raise HTTPException(401, "MCP 登录状态已失效，请重新登录") from None
    if request.headers.get("x-user-id") and get_current_user(request)["id"] != user_id:
        raise HTTPException(403, "用户身份不一致")
    user = await db_client.fetch_one(get_user_sql("identity.external_by_id"), {"id": user_id})
    if not user or user["orgId"] != payload["orgId"] or user["groupId"] != payload["groupId"]:
        raise HTTPException(401, "账号权限已变更，请重新登录")
    return {**user, "name": user["realName"], "userType": "external"}


def scope(identity: dict, **extra) -> dict:
    return {"orgId": int(identity["orgId"]), "userId": int(identity["id"]), **extra}


def json_value(value, default):
    if not value:
        return default
    return json.loads(value) if isinstance(value, str) else value


def config_view(record: dict) -> dict:
    return {"id": record["id"], "categoryId": record.get("categoryId"), "name": record["name"], "url": record["url"], "authType": record["authType"],
            "enabled": record["enabled"], "hasCredential": bool(record.get("hasCredential", record.get("secretCipher"))),
            "tools": json_value(record.get("toolsJson"), []), "selectedTools": json_value(record.get("selectedToolsJson"), []),
            "configScope": record.get("configScope", "personal"), "visibility": record.get("visibility", "private"),
            "canManage": record.get("configScope", "personal") == "personal",
            "httpRequest": next((tool["httpRequest"] for tool in json_value(record.get("toolsJson"), []) if "httpRequest" in tool), None)}


def http_tool(request, name):
    """普通 HTTP 配置复用工具快照字段，不新增表结构。"""
    properties = {item.name: {"type": item.type, "description": item.description or item.name,
        **({"examples": [item.example]} if item.example is not None else {}),
        **({"items": {}} if item.type == "array" else {})} for item in request.variables}
    template = request.model_dump()
    for param in template['params']:
        if not param['description']:
            param.pop('description')
        if param['type'] == 'string':
            param.pop('type')
        if param.get('required', True):
            param.pop('required', None)
    for field in template.get('bodyFields') or []:
        if field.get('required', True):
            field.pop('required', None)
    if not template['bodyFields']:
        template.pop('bodyFields')
    if not template['testValues']:
        template.pop('testValues')
    if not template['bodyNotes']:
        template.pop('bodyNotes')
    if not template['inactiveVariables']:
        template.pop('inactiveVariables')
    # 旧工具快照不含 example；空示例不改变旧快照及其调用指纹。
    for variable in template['variables'] + template.get('inactiveVariables', []):
        if variable['example'] is None:
            variable.pop('example')
        if variable.get('required', True):
            variable.pop('required', None)
    notes = [f"Params {item.key}: {item.description}" for item in request.params if item.enabled and item.description]
    notes.extend(f"JSON {key}: {value}" for key, value in request.bodyNotes.items() if value)
    description = request.description or name
    if notes:
        description += "\n字段备注：\n" + "\n".join(notes)
    required = [item.name for item in request.variables if item.required]
    return {"name": "http_request", "description": description,
        "inputSchema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
        "readOnly": request.method == "GET", "httpRequest": template}


def saved_tools(data, old, unchanged):
    if data.httpRequest is not None:
        snapshot = json.dumps([http_tool(data.httpRequest, data.name)], ensure_ascii=False)
        selected = old["selectedToolsJson"] if old and unchanged and snapshot == old["toolsJson"] else '["http_request"]'
        return snapshot, selected
    if old and any("httpRequest" in tool for tool in json_value(old["toolsJson"], [])):
        raise ValueError("HTTP 工具必须提交请求配置，不能省略 Params 和 Body")
    return (old["toolsJson"], old["selectedToolsJson"]) if unchanged else (None, None)


async def owned_config(identity: dict, config_id: int, *, active=False) -> dict:
    """本人有权使用的个人或公司配置；每次调用前读取当前权限。"""
    record = await db_client.fetch_one(get_mcp_sql("available.get"), scope(identity, id=config_id))
    if not record or (active and record["enabled"] != 1):
        raise ValueError("MCP 配置不存在、无权访问或已停用")
    return dict(record)


async def personal_config(identity: dict, config_id: int) -> dict:
    record = await db_client.fetch_one(get_mcp_sql("config.get"), scope(identity, id=config_id))
    if not record:
        raise ValueError("只能管理本人创建的个人 MCP")
    return dict(record)


async def get_company_scope(request: Request) -> dict:
    """公司 MCP 管理要求密码登录签发的内部身份，不能仅信任用户请求头。"""
    from api.endpoints.user.dependencies import get_platform_identity, read_session_claims
    from api.endpoints.organization.dependencies import get_organization_scope, get_internal_organization_scope
    if read_session_claims(request)['userType'] != 'internal':
        raise HTTPException(403, '仅内部管理员可管理公司 MCP')
    identity = await get_platform_identity(request)
    scope = await get_organization_scope(request, identity)
    return await get_internal_organization_scope(scope)


async def get_runtime_identity(request: Request) -> dict:
    token = request.headers.get("x-mcp-token", "")
    if not token:
        raise HTTPException(401, "请重新登录后执行技能 MCP")
    try:
        payload = json.loads(cipher().decrypt(token.encode(), ttl=86400))
    except (InvalidToken, ValueError, TypeError):
        raise HTTPException(401, "MCP 登录已失效，请重新登录") from None
    if payload.get("userType", "external") == "internal":
        company = await get_company_scope(request)
        return {"id": 0, "actorId": company["identity"]["id"], "name": company["identity"]["name"],
            "orgId": company["orgId"], "userType": "internal"}
    return await get_personal_identity(request)


def approval_actor(identity):
    return f"{identity.get('userType', 'external')}:{identity.get('actorId', identity['id'])}"


async def company_config(company: dict, config_id: int) -> dict:
    row = await db_client.fetch_one(get_mcp_sql("company.get"), {"orgId": company["orgId"], "id": config_id})
    if not row:
        raise ValueError("公司 MCP 不存在或不属于当前公司")
    return dict(row)


def encrypted_secret(data, old) -> str | None:
    if data.authType != "bearer":
        return None
    plaintext = data.token.get_secret_value().strip() if data.token else ""
    if plaintext:
        return cipher().encrypt(plaintext.encode()).decode()
    if old and old["authType"] == "bearer":
        if old["url"] != data.url:
            raise ValueError("更换服务地址时必须重新填写 Token")
        if old["secretCipher"]:
            return old["secretCipher"]
    raise ValueError("Bearer Token 不能为空")


async def save_company_config(company: dict, data) -> int:
    params = {"orgId": company["orgId"], "id": data.id}
    async with db_client.engine.begin() as conn:
        old = None
        if data.id:
            old = (await conn.execute(text(get_mcp_sql("company.lock")), params)).mappings().first()
            if not old:
                raise ValueError("公司 MCP 不存在或不属于当前公司")
            if old["visibility"] != data.visibility and not data.confirmVisibilityChange:
                raise ValueError("切换公用/私有范围前，请确认用户权限将发生变化")
        category_id = data.categoryId if 'categoryId' in data.model_fields_set else (old.get('categoryId') if old else None)
        if category_id and not (await conn.execute(text(get_mcp_sql('category.lock')), {'orgId': company['orgId'], 'id': category_id})).mappings().first():
            raise ValueError('分类不存在或不属于当前公司')
        if data.accessUserIds:
            users = (await conn.execute(text(get_mcp_sql("company.users")), {**params, "keyword": None,
                "ids": ",".join(map(str, data.accessUserIds))})).mappings().all()
            if {row["id"] for row in users} != set(data.accessUserIds):
                raise ValueError("只能选择当前公司启用的用户，部分所选用户已失效")
        if not old:
            count = (await conn.execute(text(get_mcp_sql("company.count")), {**params, "keyword": None,
                "visibility": None, "enabled": None, "categoryId": None})).mappings().first()
            if count["total"] >= 100:
                raise ValueError("公司 MCP 配置最多保存 100 条")
        secret = encrypted_secret(data, old)
        unchanged = old and old["url"] == data.url and old["authType"] == data.authType and old["secretCipher"] == secret
        tools_json, selected_json = saved_tools(data, old, unchanged)
        params.update(categoryId=category_id, name=data.name, url=data.url, authType=data.authType, secretCipher=secret, enabled=data.enabled,
            visibility=data.visibility, accessUserIdsJson=json.dumps(data.accessUserIds),
            toolsJson=tools_json, selectedToolsJson=selected_json)
        fill_audit_fields(params, company["identity"], is_update=bool(old))
        result = await conn.execute(text(get_mcp_sql("company.update" if old else "company.insert")), params)
        return data.id if old else int(result.lastrowid)


async def owned_skill(identity: dict, skill_id: int, *, active=False) -> dict:
    record = await db_client.fetch_one(get_mcp_sql("skill.get"), scope(identity, skillId=skill_id))
    if not record or (active and record["enabled"] != 1):
        raise ValueError("私有技能不存在、无权访问或已停用")
    return dict(record)


async def save_config(identity: dict, data) -> int:
    async with db_client.engine.begin() as conn:
        return await save_personal_config(conn, identity, data)


async def save_personal_config(conn, identity: dict, data) -> int:
    old = await personal_config(identity, data.id) if data.id else None
    secret = encrypted_secret(data, old)
    category_id = data.categoryId if 'categoryId' in data.model_fields_set else (old.get('categoryId') if old else None)
    if category_id and not (await conn.execute(text(get_mcp_sql('category.lock')), scope(identity, id=category_id))).mappings().first():
        raise ValueError('分类不存在或不属于当前公司')
    params = scope(identity, categoryId=category_id, name=data.name, url=data.url, authType=data.authType, secretCipher=secret, enabled=data.enabled)
    unchanged = old and old["url"] == data.url and old["authType"] == data.authType and old["secretCipher"] == secret
    tools_json, selected_json = saved_tools(data, old, unchanged)
    params.update(toolsJson=tools_json, selectedToolsJson=selected_json)
    if not old:
        if len(await db_client.fetch_all(get_mcp_sql("config.list"), scope(identity))) >= 100:
            raise ValueError("个人 MCP 配置最多保存 100 条")
        fill_audit_fields(params, identity)
        result = await conn.execute(text(get_mcp_sql("config.insert")), params)
        return int(result.lastrowid)
    params.update(id=data.id)
    fill_audit_fields(params, identity, is_update=True)
    await conn.execute(text(get_mcp_sql("config.update")), params)
    return data.id


async def transaction(statements: list[tuple[str, dict]]) -> None:
    if not db_client.engine:
        raise RuntimeError("数据库连接未初始化")
    async with db_client.engine.begin() as conn:
        for key, params in statements:
            await conn.execute(text(get_mcp_sql(key)), params)


async def save_bindings(identity: dict, data) -> None:
    await owned_skill(identity, data.skillId)
    if len({b.configId for b in data.bindings}) != len(data.bindings):
        raise ValueError("同一 MCP 服务不能重复绑定")
    statements = [("binding.delete_skill", scope(identity, skillId=data.skillId))]
    for binding in data.bindings:
        config = await owned_config(identity, binding.configId, active=True)
        selected = set(json_value(config["selectedToolsJson"], []))
        if len(set(binding.toolNames)) != len(binding.toolNames) or not set(binding.toolNames) <= selected:
            raise ValueError("技能只能绑定本人的 MCP 已选工具")
        statements.append(("binding.insert", scope(identity, skillId=data.skillId, configId=binding.configId,
                                                   toolNamesJson=json.dumps(binding.toolNames, ensure_ascii=False))))
    await transaction(statements)


async def runtime_selection(identity: dict, config_ids: list[int], skill_id: int | None):
    """私有技能只读取本人绑定；分享和技能库不会带出个人连接或凭据。"""
    selections: dict[int, set[str]] = {}
    rules = []
    if skill_id:
        master = await owned_skill(identity, skill_id, active=True)
        skills = [master]
        children = str(master.get("subSkillIds") or "").split(",") if master["levelType"] == 1 else []
        for child_id in children:
            if child_id.strip():
                child = await owned_skill(identity, int(child_id), active=True)
                if child["levelType"] != 2:
                    raise ValueError("关联子技能类型已变更，请重新配置")
                skills.append(child)
        for skill in skills:
            rules.append(f"【{'主' if skill['id'] == skill_id else '子'}技能：{skill['name']}】\n{skill['rules']}")
            bindings = await db_client.fetch_all(get_mcp_sql("binding.list"), scope(identity, skillId=skill["id"]))
            for binding in bindings:
                selections.setdefault(binding["configId"], set()).update(json_value(binding["toolNamesJson"], []))
    else:
        for config_id in config_ids:
            config = await owned_config(identity, config_id, active=True)
            selections[config_id] = set(json_value(config["selectedToolsJson"], []))
    if len(selections) > 5:
        raise ValueError("一次执行最多使用 5 个 MCP 服务")
    configs = []
    for config_id, names in selections.items():
        config = await owned_config(identity, config_id, active=True)
        if not names <= set(json_value(config["selectedToolsJson"], [])):
            raise ValueError("技能绑定的 MCP 工具已变更，请重新选择")
        if names:
            configs.append((config, names))
    return configs, "\n\n".join(rules)


async def cleanup_user(connection, org_id: int, user_ids: list[int]):
    for key in ("binding.delete_user", "config.delete_user"):
        await connection.execute(text(get_mcp_sql(key)), {"orgId": org_id, "userIds": ",".join(map(str, user_ids))})


async def verify_skill_binding_identity(request, context: dict, skill_type: int, owner_id=0):
    if request is None:
        raise HTTPException(401, "请重新登录后配置技能 MCP")
    actor = context.get("identity", context)
    if actor.get("userType") == "external":
        verified = await get_personal_identity(request)
        if skill_type != 3 or verified["id"] != owner_id or verified["orgId"] != context["orgId"]:
            raise HTTPException(403, "只能配置本人私有技能的 MCP")
    else:
        verified = await get_company_scope(request)
        if verified["orgId"] != context["orgId"] or verified["identity"]["id"] != actor["id"]:
            raise HTTPException(403, "技能与管理员公司或身份不一致")


async def replace_skill_bindings(conn, org_id, skill_id, skill_type, owner_id, bindings):
    if len({binding.configId for binding in bindings}) != len(bindings):
        raise ValueError("同一 MCP 服务不能重复绑定")
    for binding in sorted(bindings, key=lambda item: item.configId):
        config = (await conn.execute(text(get_mcp_sql("binding.config_lock")),
            {"orgId": org_id, "id": binding.configId})).mappings().first()
        if not config or config["enabled"] != 1:
            raise ValueError("绑定的 MCP 不存在、已停用或不属于当前公司")
        if skill_type in (1, 2):
            allowed = config["configScope"] == "company" and config["visibility"] == "public"
        else:
            allowed = (config["configScope"] == "personal" and config["userId"] == owner_id) or (
                config["configScope"] == "company" and (config["visibility"] == "public" or
                owner_id in json_value(config["accessUserIdsJson"], [])))
        if not allowed:
            raise ValueError("公共和项目组技能只能绑定公司公用 MCP；私有技能只能绑定所属用户有权使用的 MCP")
        if len(set(binding.toolNames)) != len(binding.toolNames) or not set(binding.toolNames) <= set(json_value(config["selectedToolsJson"], [])):
            raise ValueError("绑定工具已失效，请重新选择 MCP 工具")
    params = {"orgId": org_id, "skillId": skill_id, "userId": owner_id if skill_type == 3 else 0}
    await conn.execute(text(get_mcp_sql("binding.delete_all_skill")), params)
    for binding in bindings:
        await conn.execute(text(get_mcp_sql("binding.insert")), {**params, "configId": binding.configId,
            "toolNamesJson": json.dumps(binding.toolNames, ensure_ascii=False)})


async def persist_skill_with_bindings(statement, params, bindings, skill_type, owner_id=0, *, insert=False, before=()):
    """技能与工具绑定一起提交；旧客户端省略字段时继续使用原保存路径。"""
    async with db_client.engine.begin() as conn:
        if not insert:
            current = (await conn.execute(text(get_mcp_sql("binding.skill_lock")),
                {"orgId": params["orgId"], "skillId": params["id"]})).mappings().first()
            if not current or current["skillType"] != skill_type or (skill_type == 3 and current["userId"] != owner_id):
                raise ValueError("技能归属已发生变化，请刷新重试")
        for query, args in before:
            await conn.execute(text(query), args)
        result = await conn.execute(text(statement), params)
        skill_id = int(result.lastrowid) if insert else params["id"]
        await replace_skill_bindings(conn, params["orgId"], skill_id, skill_type, owner_id, bindings)
        return skill_id


async def shared_skill_selection(identity, skill_id, allowed_skill_ids, *, unit_skill_ids=None):
    """共享技能只能从当前智能体已绑定技能开始；子技能必须同公司、同类型及同技能组。"""
    if skill_id not in allowed_skill_ids:
        raise ValueError("该技能未绑定当前智能体")
    params = {"orgId": identity["orgId"], "skillId": skill_id}
    master = await db_client.fetch_one(get_mcp_sql("binding.skill_get"), params)
    if not master or master["enabled"] != 1 or master["skillType"] not in (1, 2):
        raise ValueError("共享技能不存在或已停用")
    if master['skillType'] == 2 and not await db_client.fetch_one(get_mcp_sql('binding.project_active'), {'orgId': identity['orgId'], 'id': master['projectGroupId']}):
        raise ValueError('技能所属项目组不存在或已停用')
    family = [master]
    if master["levelType"] == 1:
        for value in str(master["subSkillIds"] or "").split(','):
            if not value.strip():
                continue
            child = await db_client.fetch_one(get_mcp_sql("binding.skill_get"), {**params, "skillId": int(value)})
            if not child or child["enabled"] != 1 or child["levelType"] != 2 or child["skillType"] != master["skillType"] or child["projectGroupId"] != master["projectGroupId"]:
                raise ValueError("关联子技能已失效或不属于当前技能范围")
            family.append(child)
    from api.endpoints.skill.group_service import require_skill_access
    await require_skill_access(identity['orgId'], [int(row['id']) for row in family], identity)
    selections = {}
    for skill in family:
        if unit_skill_ids is not None and skill['id'] not in unit_skill_ids:
            continue
        for binding in await db_client.fetch_all(get_mcp_sql("binding.list"), {**params, "skillId": skill["id"], "userId": 0}):
            selections.setdefault(binding["configId"], set()).update(json_value(binding["toolNamesJson"], []))
    if len(selections) > 5:
        raise ValueError("技能及子技能最多使用 5 个 MCP 服务")
    configs = []
    for config_id, names in selections.items():
        config = await owned_config(identity, config_id, active=True)
        if config.get("configScope") != "company" or not names <= set(json_value(config["selectedToolsJson"], [])):
            raise ValueError("技能绑定的 MCP 权限或工具已变更")
        configs.append((config, names))
    return configs, '\n\n'.join(f"【技能：{skill['name']}】\n{skill['rules']}" for skill in family), family
