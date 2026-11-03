from fastapi import APIRouter, Depends, UploadFile, File, Response, Request, Query, Path
from sqlalchemy import select, func, desc, insert, update, delete
from utils.response import success, server_error, bad_request
from utils.mysqldb import db_client
from utils.context import get_current_user, fill_audit_fields
from pydantic import BaseModel, Field, PositiveInt
from api.endpoints.mcp.modular.mcp import McpApproval
from typing import Dict, Any, List, Literal
import pandas as pd
import io
import json
import re
import asyncio
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from openai import OpenAI, AsyncOpenAI
from sqlalchemy import text
from api.endpoints.knowledge.service import get_knowledge_store

class ChatHistoryItem(BaseModel):
    """一轮历史对话消息：仅用于让模型理解上下文，不做持久化。"""
    role: Literal["user", "assistant"] = Field(..., description="消息角色")
    content: str = Field(..., max_length=6000, description="消息内容")


class AgentChatRequest(BaseModel):
    """技能组对话请求。

    技能组已替代智能体成为第一层筛选入口：前端先选择用户可用的技能组，
    再把技能组 ID 传入本接口，由服务端加载该组内的主技能与子技能执行。
    """
    skillGroupId: PositiveInt = Field(..., description="技能组ID（替代原智能体key）")
    autoAssistant: bool = Field(
        False, description="Auto 模式未匹配到专项技能组时，由 KaleidoPilot 承接本次回答"
    )
    # 知识库查询模式：用户在入口处显式选择“知识库查询”，跳过技能组匹配与技能编排，
    # 一律按该用户被授权的全部知识库做向量召回，召回为空才用模型自身知识作答。
    knowledgeOnly: bool = Field(False, description="仅做知识库向量召回回答")
    query: str = Field(..., description="用户提问")
    session_id: str | None = None
    # 用户组 id：用于加载该用户在平台上可用的全部技能组与技能（能力介绍用，
    # 避免模型只认识本次命中的技能组、只介绍第一个技能）
    userGroupId: PositiveInt | None = Field(None, description="当前用户所属用户组ID")
    # —— 多轮对话上下文 ——
    # history：前端从本地缓存里截取的最近若干轮消息，保证“指代、追问”能被正确理解；
    # memory  ：更早对话由服务端压缩成的记忆摘要，前端随历史记录一起缓存并回传。
    history: List[ChatHistoryItem] = Field(
        default_factory=list, max_length=20, description="最近若干轮对话消息"
    )
    memory: str | None = Field(None, max_length=8000, description="更早对话的记忆摘要")
    tenantIds: List[PositiveInt] = Field(default_factory=list, max_length=20)
    mcpIds: List[PositiveInt] = Field(default_factory=list, max_length=5)
    privateSkillId: PositiveInt | None = None
    skillId: PositiveInt | None = None
    mcpApproval: McpApproval | None = None

from api.endpoints.agent.modular.agent import (
    Agent, AgentResponse, AgentQueryRequest, AgentCreate, AgentUpdate,
    PersonalAgentWrite, PersonalAgentUpdate, PersonalAgentShare,
)
from api.endpoints.mcp.service import get_personal_identity
from api.endpoints.knowledge.access import parse_id_list
from api.endpoints.agent.sql.tables import agent_table
from api.endpoints.organization.dependencies import get_organization_scope, get_internal_organization_scope
from api.endpoints.user.dependencies import get_super_administrator
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# 字段映射配置，用于导入导出和模板下载
AGENT_FIELD_MAP = {
    "agentName": "智能体名称（如：粤语客服助手）",
    "skillIds": "技能组ids（逻辑关联 SKILL.ID,号拼接多个id）",
    "templateIds": "绑定的模板ID（逻辑关联 TEMPLATE_GENERATION.ID，英文逗号拼接）",
    "agentDescription": "智能体描述",
    "systemPrompt": "系统提示词（定义角色、任务、约束等）",
    "userPromptTemplate": "用户提示词模板（支持变量占位，如{{text}}）",
    "temperature": "温度参数（0.0~2.0，控制随机性，越高越随机）",
    "topP": "Top-p 采样参数（0.0~1.0，核采样）",
    "key": "调用智能体的key值",
    "intentLlmId": "意图模型ID",
    "taskLlmId": "任务分解模型ID",
    "executLlmId": "执行任务（代码生成）ID",
    "summaryLlmId": "总结任务ID",
    "tenantIds": "知识库id（根据,拼接关联知识库）",
    "tenantTopK": "知识库返回数量",
    "tenantScore": "知识库返回的最低置信度（0.4代表百分之40）",
    "enabled": "是否有效（1有效，0无效）",
    "removed": "是否删除（1已删除，0未删除）",
    "createUserId": "创建人ID",
    "createUserName": "创建人姓名",
    "createTime": "创建时间",
    "updateUserId": "更新人ID",
    "updateUserName": "更新人姓名",
    "updateTime": "更新时间"
}

class DeleteRequest(BaseModel):
    id: int


@router.post("/querylist", response_model=dict, summary="查询列表")
async def query_agent_list(query: AgentQueryRequest, scope: dict = Depends(get_organization_scope)):
    try:
        if scope['identity'].get('userType') != 'internal':
            return bad_request(message='请通过个人智能体入口查询')
        params = {'orgId': scope['orgId'], 'id': query.id, 'key': query.key or None,
            'agentName': query.agentName or None, 'enabled': query.enabled if query.enabled is not None else 1}
        count = await db_client.fetch_one(get_sql('agent.admin_count'), params)
        records = await db_client.fetch_all(get_sql('agent.admin_list'),
            {**params, 'limit': query.pageSize, 'offset': (query.pageNo - 1) * query.pageSize})
        return success(data={'total': int(count['total']) if count else 0, 'list': jsonable_encoder(records),
            'pageNo': query.pageNo, 'pageSize': query.pageSize})
    except Exception:
        logger.exception('查询公司智能体失败')
        return server_error('查询公司智能体失败')

import uuid
import os
import yaml

def get_sql(sql_id: str) -> str:
    """
    根据 namespace.sql_id 从 sql.yaml 获取 SQL 语句
    """
    try:
        namespace, name = sql_id.split(".")
        # 获取当前模块的 sql.yaml 路径
        yaml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sql", "sql.yaml")
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"SQL file not found: {yaml_path}")
            
        with open(yaml_path, 'r', encoding='utf-8') as f:
            sql_dict = yaml.safe_load(f)
            
        if namespace in sql_dict and name in sql_dict[namespace]:
            return sql_dict[namespace][name]
        else:
            raise KeyError(f"SQL statement '{sql_id}' not found in {yaml_path}")
    except Exception as e:
        raise Exception(f"Failed to load SQL statement '{sql_id}': {str(e)}")

@router.get("/skill_tree", summary="获取项目组与技能树")
async def get_skill_tree(scope: dict = Depends(get_internal_organization_scope)):
    try:
        groups = await db_client.fetch_all(get_sql("agent.project_group_list"), {'orgId': scope['orgId']})
        skills = await db_client.fetch_all(get_sql("agent.skill_list"), {'orgId': scope['orgId']})
        nodes = {}
        for g in groups:
            gid = f"group_{g['id']}"
            nodes[gid] = {
                "id": gid,
                "label": g["name"],
                "type": "group",
                "level": g["level"],
                "originalId": g["id"],
                "parentId": f"group_{g['parentId']}" if g["parentId"] else None,
                "children": []
            }
            
        for s in skills:
            sid = f"skill_{s['id']}"
            nodes[sid] = {
                "id": sid,
                "label": s["name"],
                "type": "skill",
                "originalId": s["id"],
                "parentId": f"group_{s['parentId']}" if s["parentId"] else None,
                "children": []
            }
            
        # 组装树
        tree = []
        for node_id, node in nodes.items():
            pid = node["parentId"]
            if pid and pid in nodes:
                nodes[pid]["children"].append(node)
            else:
                # 只有根节点（parentId为空或者找不到的）加到 tree 里
                tree.append(node)
                
        def process_nodes(node_list):
            for node in node_list:
                if node["type"] == "group":
                    # 所有组节点均不可被勾选，只有技能可以勾选
                    node["disabled"] = True
                    process_nodes(node["children"])
            return node_list
            
        tree = process_nodes(tree)
                 
        return success(data=tree)
    except Exception as e:
        return server_error(f"获取技能树失败: {str(e)}")

@router.get("/tenant_list", summary="获取知识库列表")
async def get_tenant_list(scope: dict = Depends(get_organization_scope)):
    try:
        if scope.get("identity", {}).get("userType") != "internal":
            return bad_request(message="仅内部管理员可选择公司知识库")
        tenants = await db_client.fetch_all(get_sql("agent.tenant_list"), {"orgId": scope["orgId"]})
        return success(data=tenants)
    except Exception as e:
        return server_error(f"获取知识库列表失败: {str(e)}")

AGENT_WRITE_FIELDS = ('agentName','skillIds','templateIds','agentDescription','systemPrompt','userPromptTemplate','temperature','topP','key',
    'intentLlmId','taskLlmId','executLlmId','summaryLlmId','tenantIds','tenantTopK','tenantScore','enabled')
MODEL_ROLES = (('intentLlmId',1,'意图模型'),('taskLlmId',2,'任务分解模型'),('executLlmId',3,'执行模型'),('summaryLlmId',4,'总结模型'))


async def validate_model_choices(conn, org_id, data):
    choices = [(field, kind, label, getattr(data, field)) for field, kind, label in MODEL_ROLES if field in data.model_fields_set and getattr(data, field) is not None]
    if not choices: return
    rows = (await conn.execute(text(get_sql('agent.model_choice')), {'orgId': org_id, 'modelIds': ','.join(str(item[3]) for item in choices)})).mappings().all()
    models = {row['id']: row for row in rows}
    for field, kind, label, model_id in choices:
        if model_id not in models or models[model_id]['type'] != kind:
            raise ValueError(f'{label}必须选择当前公司已启用、已配置密钥且用途匹配的模型')


def csv_ids(ids):
    value = ','.join(str(item) for item in parse_id_list(ids))
    if len(value) > 255:
        raise ValueError('绑定参数超出长度限制')
    return value


def template_csv(template_ids):
    """
    模板 ID 是 24 位字符串（不是数字），所以不能复用 csv_ids 的数字校验。
    这里只做去空、去重和长度保护，真正的归属校验交给 validate_template_ids。
    """
    ids = list(dict.fromkeys(item.strip() for item in str(template_ids or '').split(',') if item.strip()))
    if len(ids) > 20:
        raise ValueError('最多绑定20个模板')
    value = ','.join(ids)
    if len(value) > 1000:
        raise ValueError('模板绑定超出长度限制')
    return value or None


async def validate_template_ids(conn, org_id, template_ids):
    """校验模板是否属于当前公司且已生成完成（STATUS=ready）。"""
    ids = [item.strip() for item in str(template_ids or '').split(',') if item.strip()]
    if not ids:
        return
    rows = (await conn.execute(text(get_sql('agent.bound_templates')),
        {'orgId': org_id, 'templateIds': ','.join(ids)})).mappings().all()
    if {row['id'] for row in rows} != set(ids):
        raise ValueError('绑定的模板不存在、未生成完成或不属于当前公司')


async def validate_agent_bindings(conn, identity, mcp_ids, tenant_ids, *, public=False):
    from api.endpoints.mcp.sql import get_mcp_sql
    from api.endpoints.knowledge.api.knowledgeApi import get_sql as knowledge_sql
    from api.endpoints.mcp.service import json_value

    mcps, tenants = parse_id_list(mcp_ids), parse_id_list(tenant_ids)
    if len(mcps) > 5 or len(tenants) > 20:
        raise ValueError('最多绑定5个MCP和20个知识库')
    org_id = identity['orgId']
    if public:
        available = (await conn.execute(text(get_mcp_sql('binding.public_options')), {'orgId': org_id})).mappings().all()
        found = {int(row['id']) for row in available if json_value(row['selectedToolsJson'], [])}
        if not set(mcps) <= found:
            raise ValueError('公有智能体只能绑定本公司启用且已选择工具的公用MCP')
        available_tenants = (await conn.execute(text(get_sql('agent.tenant_list')), {'orgId': org_id})).mappings().all()
        if not set(tenants) <= {int(row['id']) for row in available_tenants}:
            raise ValueError('只能绑定本公司启用的公司知识库')
    else:
        for config_id in mcps:
            config = (await conn.execute(text(get_mcp_sql('available.get')),
                {'orgId': org_id, 'userId': identity['id'], 'id': config_id})).mappings().first()
            if not config or config['enabled'] != 1 or not json_value(config['selectedToolsJson'], []):
                raise ValueError('绑定的MCP不存在、未配置工具或无权使用')
        if tenants:
            rows = (await conn.execute(text(knowledge_sql('tenant.ids_usable')),
                {'orgId': org_id, 'userId': identity['id'], 'groupId': identity['groupId'],
                 'userType': 'external', 'tenantIds': csv_ids(tenants)})).mappings().all()
            if {int(row['id']) for row in rows} != set(tenants):
                raise ValueError('绑定的知识库不存在、已停用或无权使用')


@router.get('/binding-options', summary='公有智能体可绑定的MCP、知识库和模板')
async def public_binding_options(scope=Depends(get_internal_organization_scope)):
    from api.endpoints.mcp.sql import get_mcp_sql
    from api.endpoints.mcp.service import json_value
    mcps = await db_client.fetch_all(get_mcp_sql('binding.public_options'), {'orgId': scope['orgId']})
    tenants = await db_client.fetch_all(get_sql('agent.tenant_list'), {'orgId': scope['orgId']})
    templates = await db_client.fetch_all(get_sql('agent.template_options'), {'orgId': scope['orgId']})
    return success(data={
        'mcps': [{'id': row['id'], 'name': row['name']} for row in mcps if json_value(row['selectedToolsJson'], [])],
        'tenants': tenants,
        'templates': templates,
    })


@router.get('/personal/options', summary='个人可选择的公司模型，不返回密钥')
async def personal_model_options(identity=Depends(get_personal_identity)):
    rows = await db_client.fetch_all(get_sql('personal.model_options'), {'orgId': identity['orgId']})
    return success(data={'models': rows})


@router.get('/personal/querylist', summary='个人可用的公有、本人私有和接收分享的智能体')
async def personal_agent_list(keyword: str | None = Query(None, max_length=100),
    source: Literal['all', 'mine', 'received', 'company'] = Query('all'),
    pageNo: int = Query(1, ge=1), pageSize: int = Query(10, ge=1, le=100),
    identity=Depends(get_personal_identity)):
    params = {'orgId': identity['orgId'], 'userId': identity['id'], 'source': source,
        'keyword': keyword.strip() or None if keyword else None}
    count = await db_client.fetch_one(get_sql('personal.count_visible'), params)
    rows = await db_client.fetch_all(get_sql('personal.visible'), {**params, 'limit': pageSize, 'offset': (pageNo - 1) * pageSize})
    rows = [{**row, 'canManage': bool(row['canManage'])} for row in rows]
    return success(data={'list': jsonable_encoder(rows), 'total': int(count['total']) if count else 0, 'pageNo': pageNo, 'pageSize': pageSize})


@router.get('/personal/share-users', summary='同公司可接收分享的用户')
async def agent_share_users(keyword: str | None = Query(None, max_length=100),
    pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
    identity=Depends(get_personal_identity)):
    params = {'orgId': identity['orgId'], 'userId': identity['id'], 'keyword': keyword.strip() or None if keyword else None}
    count = await db_client.fetch_one(get_sql('personal.share_user_count'), params)
    rows = await db_client.fetch_all(get_sql('personal.share_users'), {**params, 'limit': pageSize, 'offset': (pageNo - 1) * pageSize})
    return success(data={'list': rows, 'total': int(count['total']) if count else 0, 'pageNo': pageNo, 'pageSize': pageSize})


async def owned_agent(identity, agent_id):
    return await db_client.fetch_one(get_sql('personal.own'), {'orgId': identity['orgId'], 'userId': identity['id'], 'id': agent_id})


@router.get('/personal/{agent_id}', summary='读取本人私有智能体配置')
async def personal_agent_detail(agent_id: int = Path(gt=0), identity=Depends(get_personal_identity)):
    row = await owned_agent(identity, agent_id)
    if not row:
        return bad_request(message='只能查看本人创建的私有智能体配置')
    row = dict(row)
    for field in ('tenantIds', 'mcpIds', 'shareUserIds', 'skillIds'):
        row[field] = parse_id_list(row.get(field))
    return success(data=jsonable_encoder(row))


async def persist_personal_agent(data, identity, *, update_existing=False):
    values = data.model_dump()
    values.update(orgId=identity['orgId'], userId=identity['id'], agentType=2, skillIds=None, templateIds=None,
        key=uuid.uuid4().hex, mcpIds=csv_ids(data.mcpIds), tenantIds=csv_ids(data.tenantIds))
    fill_audit_fields(values, identity, is_update=update_existing)
    async with db_client.engine.begin() as conn:
        previous = None
        if update_existing:
            previous = (await conn.execute(text(get_sql('personal.lock')), values)).mappings().first()
            if not previous:
                raise ValueError('只能编辑本人创建的私有智能体')
        skill_ids = data.skillIds if data.skillIds is not None else parse_id_list(previous.get('skillIds') if previous else None)
        skill_csv = csv_ids(skill_ids)
        if len(skill_csv) > 200:
            raise ValueError('技能绑定超出可保存长度，请减少技能数量')
        if skill_ids:
            from api.endpoints.skill.api.skillApi import get_sql as skill_sql, imported_rules_text
            selected = (await conn.execute(text(skill_sql('imported.binding_choices')),
                {'orgId': identity['orgId'], 'userId': identity['id'], 'skillIds': skill_csv})).mappings().all()
            imported_rules_text(selected, skill_ids)
        values['skillIds'] = skill_csv or None
        await validate_model_choices(conn, identity['orgId'], data)
        await validate_agent_bindings(conn, identity, data.mcpIds, data.tenantIds)
        result = await conn.execute(text(get_sql('personal.update' if update_existing else 'agent.insert')), values)
        return data.id if update_existing else int(result.lastrowid)


@router.post('/personal/insert', summary='创建本人私有智能体')
async def create_personal_agent(data: PersonalAgentWrite, identity=Depends(get_personal_identity)):
    try:
        agent_id = await persist_personal_agent(data, identity)
        return success(data={'id': agent_id}, message='私有智能体已创建')
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception('创建私有智能体失败')
        return server_error('创建私有智能体失败')


@router.post('/personal/update', summary='编辑本人私有智能体')
async def update_personal_agent(data: PersonalAgentUpdate, identity=Depends(get_personal_identity)):
    try:
        await persist_personal_agent(data, identity, update_existing=True)
        return success(message='私有智能体已保存')
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception('编辑私有智能体失败')
        return server_error('编辑私有智能体失败')


@router.get('/personal/{agent_id}/shares', summary='本人智能体分享记录')
async def personal_agent_shares(agent_id: int = Path(gt=0), identity=Depends(get_personal_identity)):
    if not await owned_agent(identity, agent_id):
        return bad_request(message='只能管理本人创建的智能体分享')
    rows = await db_client.fetch_all(get_sql('personal.share_list'), {'orgId': identity['orgId'], 'userId': identity['id'], 'id': agent_id})
    return success(data={'list': jsonable_encoder(rows)})


@router.post('/personal/share', summary='设置本人智能体分享接收人；空列表撤销全部分享')
async def share_personal_agent(data: PersonalAgentShare, identity=Depends(get_personal_identity)):
    try:
        params = {'id': data.id, 'orgId': identity['orgId'], 'userId': identity['id'],
            'receiveUserIds': ','.join(map(str, data.receiveUserIds)), 'name': identity['name']}
        fill_audit_fields(params, identity, is_update=True)
        async with db_client.engine.begin() as conn:
            if not (await conn.execute(text(get_sql('personal.lock')), params)).mappings().first():
                raise ValueError('只能分享本人创建的私有智能体')
            if data.receiveUserIds:
                users = (await conn.execute(text(get_sql('personal.validate_receivers')), params)).mappings().all()
                if {int(row['id']) for row in users} != set(data.receiveUserIds):
                    raise ValueError('只能分享给同公司其他已启用用户')
            await conn.execute(text(get_sql('personal.deactivate_shares')), params)
            for user_id in data.receiveUserIds:
                await conn.execute(text(get_sql('personal.activate_share')), {**params, 'receiveUserId': user_id})
            await conn.execute(text(get_sql('personal.save_receivers')), params)
        return success(message='分享名单已保存')
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception('智能体分享失败')
        return server_error('智能体分享失败，原分享名单保持不变')


@router.post('/personal/delete', summary='删除本人私有智能体并撤销分享')
async def delete_personal_agent(data: DeleteRequest, identity=Depends(get_personal_identity)):
    try:
        params = fill_audit_fields({'id': data.id, 'orgId': identity['orgId'], 'userId': identity['id']}, identity, is_update=True)
        async with db_client.engine.begin() as conn:
            if not (await conn.execute(text(get_sql('personal.lock')), params)).mappings().first():
                raise ValueError('只能删除本人创建的私有智能体')
            await conn.execute(text(get_sql('personal.deactivate_shares')), params)
            await conn.execute(text(get_sql('personal.delete')), params)
        return success(message='智能体已删除，分享已撤销')
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception('删除私有智能体失败')
        return server_error('删除私有智能体失败')


@router.post("/insert", summary="新增记录")
async def insert_agent(data: AgentCreate, scope: dict = Depends(get_organization_scope)):
    try:
        actor = scope['identity']
        if actor.get('userType') != 'internal': return bad_request(message='仅内部管理员可管理智能体')
        if not data.agentName or not data.agentName.strip(): return bad_request(message='请填写智能体名称')
        values = {key: getattr(data, key) for key in AGENT_WRITE_FIELDS}
        values.update(orgId=scope['orgId'], key=data.key or uuid.uuid4().hex[:14],
            agentType=1, userId=None, mcpIds=None, templateIds=template_csv(data.templateIds),
            temperature=data.temperature if data.temperature is not None else 1, topP=data.topP if data.topP is not None else 1,
            enabled=data.enabled if data.enabled is not None else 1)
        fill_audit_fields(values, actor)
        async with db_client.engine.begin() as conn:
            await validate_model_choices(conn, scope['orgId'], data)
            if values['templateIds']:
                await validate_template_ids(conn, scope['orgId'], values['templateIds'])
            if data.tenantIds is not None:
                await validate_agent_bindings(conn, {**actor, 'orgId': scope['orgId']}, None, data.tenantIds, public=True)
                values['tenantIds'] = csv_ids(data.tenantIds)
            result = await conn.execute(text(get_sql('agent.insert')), values)
        return success(data={'id': int(result.lastrowid)}, message='新增成功')
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception('新增智能体失败')
        return server_error('新增智能体失败')

@router.post("/update", summary="修改记录")
async def update_agent(data: AgentUpdate, scope: dict = Depends(get_organization_scope)):
    try:
        actor = scope['identity']
        if actor.get('userType') != 'internal': return bad_request(message='仅内部管理员可管理智能体')
        if not data.model_fields_set.intersection(AGENT_WRITE_FIELDS): return bad_request(message='没有需要更新的字段')
        values = {key: getattr(data, key) if key in data.model_fields_set else None for key in AGENT_WRITE_FIELDS}
        values.update(orgId=scope['orgId'], id=data.id, mcpIds=None)
        # 模板绑定允许清空：显式传了字段才覆盖，没传保持原值
        values['setTemplate'] = int('templateIds' in data.model_fields_set)
        if values['setTemplate']:
            values['templateIds'] = template_csv(data.templateIds)
        for field, flag in [('intentLlmId','setIntent'),('taskLlmId','setTask'),('executLlmId','setExecut'),('summaryLlmId','setSummary')]:
            values[flag] = int(field in data.model_fields_set)
        fill_audit_fields(values, actor, is_update=True)
        async with db_client.engine.begin() as conn:
            if not (await conn.execute(text(get_sql('agent.lock_for_update')), values)).mappings().first():
                return bad_request(message='智能体不存在或不属于当前公司')
            await validate_model_choices(conn, scope['orgId'], data)
            if values['templateIds']:
                await validate_template_ids(conn, scope['orgId'], values['templateIds'])
            if data.tenantIds is not None:
                # 校验实际变更的绑定；省略字段保留原值。
                await validate_agent_bindings(conn, {**actor, 'orgId': scope['orgId']}, None, data.tenantIds, public=True)
                values['tenantIds'] = csv_ids(data.tenantIds)
            await conn.execute(text(get_sql('agent.update')), values)
        return success(message='修改成功')
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception:
        logger.exception('修改智能体失败')
        return server_error('修改智能体失败')

@router.post("/delete", summary="物理删除")
async def delete_agent(req: DeleteRequest, scope: dict = Depends(get_internal_organization_scope)):
    try:
        affected = await db_client.execute(get_sql('agent.physical_delete'), {'id': req.id, 'orgId': scope['orgId']})
        if affected > 0:
            return success(message="删除成功")
        return bad_request(message='智能体不存在或不属于当前公司')
    except Exception:
        logger.exception('删除智能体失败')
        return server_error('删除智能体失败')

@router.post("/deleteLj", summary="逻辑删除")
async def delete_lj_agent(req: DeleteRequest, scope: dict = Depends(get_internal_organization_scope)):
    try:
        params = fill_audit_fields({'id': req.id, 'orgId': scope['orgId']}, scope['identity'], is_update=True)
        affected = await db_client.execute(get_sql('agent.logical_delete'), params)
        if affected > 0:
            return success(message="逻辑删除成功")
        return bad_request(message='智能体不存在或不属于当前公司')
    except Exception:
        logger.exception('停用智能体失败')
        return server_error('停用智能体失败')


@router.get("/downloadTemplate", summary="下载导入模板")
async def download_template_agent():
    try:
        # 生成空数据，仅包含表头
        df = pd.DataFrame(columns=list(AGENT_FIELD_MAP.values()))
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='模板')
        output.seek(0)
        
        filename = quote(f"Agent导入模板.xlsx")
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Access-Control-Expose-Headers': 'Content-Disposition'
        }
        return Response(content=output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
    except Exception as e:
        return server_error(f"下载模板失败: {str(e)}")

@router.post("/export", summary="导出数据", dependencies=[Depends(get_super_administrator)])
async def export_agent(query: AgentQueryRequest):
    try:
        records = await db_client.fetch_all(get_sql('agent.export_public'),
            {'orgId': query.orgId, 'id': query.id, 'agentName': query.agentName or None})

        export_data = []
        for record in records:
            row = {}
            record_dict = dict(record) if not hasattr(record, '_mapping') else dict(record._mapping)
            for field, col_name in AGENT_FIELD_MAP.items():
                row[col_name] = record_dict.get(field)
            export_data.append(row)
            
        df = pd.DataFrame(export_data)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='数据导出')
        output.seek(0)
        
        filename = quote(f"Agent数据导出_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx")
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Access-Control-Expose-Headers': 'Content-Disposition'
        }
        return Response(content=output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
    except Exception as e:
        return server_error(f"导出失败: {str(e)}")


@router.post("/import", summary="导入数据", dependencies=[Depends(get_super_administrator)])
async def import_agent(file: UploadFile = File(...), user: Dict[str, Any] = Depends(get_current_user)):
    try:
        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            return server_error("请上传 Excel 或 CSV 文件")
            
        contents = await file.read()
        import io
        if file.filename.endswith('.csv'):
            df = None
            for enc in ['utf-8', 'gb18030', 'utf-8-sig', 'gbk']:
                try:
                    df = pd.read_csv(io.BytesIO(contents), encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                df = pd.read_csv(io.BytesIO(contents), encoding='gb18030', encoding_errors='replace')
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        reverse_map = {v: k for k, v in AGENT_FIELD_MAP.items()}
        
        success_count = 0
        error_list = []
        
        for index, row in df.iterrows():
            try:
                row_data = {}
                for col_name, val in row.items():
                    if col_name in reverse_map and pd.notna(val):
                        row_data[reverse_map[col_name]] = val
                        
                if not row_data:
                    continue
                    
                insert_data = fill_audit_fields(row_data, user, is_update=False)
                stmt = insert(agent_table).values(**insert_data)
                await db_client.execute(stmt)
                success_count += 1
            except Exception as row_e:
                error_list.append(f"第 {index + 2} 行导入失败: {str(row_e)}")
                
        if error_list:
            return success(message=f"导入完成，成功 {success_count} 条，失败 {len(error_list)} 条", data={"errors": error_list})
        return success(message=f"导入成功，共 {success_count} 条")
    except Exception as e:
        return server_error(f"导入失败: {str(e)}")


# ============================================================
# 用户组技能组筛选接口（Auto 模式）
# ------------------------------------------------------------
# 场景：技能组已替代智能体作为第一层筛选。外部用户所属用户组可绑定多个技能组，
# 用户对话前需先确定使用哪个技能组：
#   · 接口A /group/skill-groups：传入用户组id，返回该组可用的技能组「名称 + id」列表；
#   · 接口B /group/skill-groups/match：传入「用户问题 + 用户组id」，使用组内主技能的
#     意图模型（未配置时回落公司默认大模型）挑出唯一最匹配的技能组 id；
#   · 模型判定“都不匹配”时返回 matched=false，前端不走技能编排，
#     改为携带 autoAssistant=true 调用 /chat/stream，由 KaleidoPilot 做基础回复与知识库查询；
#   · 非 Auto 时，前端直接把技能组 id 传入 /chat/stream（见本文件末尾）即可。
# ============================================================

class SkillGroupRequest(BaseModel):
    groupId: int = Field(..., gt=0, description="用户组ID")


class SkillGroupMatchRequest(SkillGroupRequest):
    question: str = Field(..., description="用户问题")


SKILL_GROUP_MATCH_SYSTEM_PROMPT = (
    "你是技能组调度助手。请根据用户问题，结合候选技能组各自的名称与描述，"
    "挑选唯一最匹配、最合适的一个。"
    "只能返回一个技能组ID（纯数字），不要输出任何解释、标点或多余文字。"
    "若用户问题与所有候选的职责都不相关（例如闲聊、询问平台能做什么），请只返回0。"
)


async def _load_group_skill_groups(group_id: int, org_id: int) -> List[Dict[str, Any]]:
    """按用户组id查询该组可用的技能组（id + 名称 + 描述），按技能组排序返回。"""
    return await db_client.fetch_all(
        get_sql("agent.user_group_skill_groups"), {"groupId": group_id, "orgId": org_id},
    )


async def _skill_group_match_model(org_id: int, rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """Auto 匹配使用的模型：取组内主技能（SKILL_LEVEL_TYPE=1）的意图模型。

    子技能不单独配置模型，若组内主技能都未配置意图模型，则回落公司默认大模型。
    返回统一为 snake_case（api_key / base_url / model），便于直接调用 AsyncOpenAI。
    """
    for row in rows:
        if int(row.get("skillLevelType") or 0) != 1 or not row.get("intentLlmId"):
            continue
        model = await db_client.fetch_one(
            get_sql("agent.runtime_models"), {"orgId": org_id, "modelIds": str(row["intentLlmId"])},
        )
        if model and model.get("apiKey"):
            return {"api_key": model["apiKey"], "base_url": model["baseUrl"], "model": model["model"]}
    from api.endpoints.system.service import get_company_runtime_config
    return (await get_company_runtime_config(org_id)).models.get("llm")


@router.post("/group/skill-groups", summary="按用户组查询可用技能组（含Auto模式）")
async def query_group_skill_groups(req: SkillGroupRequest, scope: dict = Depends(get_organization_scope)):
    try:
        rows = await _load_group_skill_groups(req.groupId, scope["orgId"])
        # autoMode=true 表示前端可在列表中额外提供「Auto 自动匹配」选项，
        # 选择 Auto 时改调用 /group/skill-groups/match 由大模型挑选技能组。
        return success(data={"autoMode": True, "list": rows})
    except Exception:
        logger.exception("查询用户组技能组失败")
        return server_error("用户组技能组加载失败")


@router.post("/group/skill-groups/match", summary="Auto模式：按用户问题与用户组匹配唯一技能组")
async def match_group_skill_group(req: SkillGroupMatchRequest, scope: dict = Depends(get_organization_scope)):
    question = (req.question or "").strip()
    if not question:
        return bad_request(message="用户问题不能为空")
    try:
        rows = await _load_group_skill_groups(req.groupId, scope["orgId"])
        if not rows:
            return bad_request(message="该用户组未配置可用技能组")

        # 候选文本携带技能组描述，便于模型按能力范围匹配
        candidates = "\n".join(
            f"{row['id']}：{row['groupName']}（{(row.get('description') or '').strip() or '暂无描述'}）"
            for row in rows
        )
        messages = [
            {"role": "system", "content": SKILL_GROUP_MATCH_SYSTEM_PROMPT},
            {"role": "user", "content": f"候选技能组（ID：名称（描述））：\n{candidates}\n\n用户问题：{question}\n\n请只返回最匹配的技能组ID（都不匹配返回0）："},
        ]
        cfg = await _skill_group_match_model(scope["orgId"], rows)
        if not cfg or not all(cfg.get(key) for key in ("api_key", "base_url", "model")):
            return server_error("技能组未配置可用的意图模型，无法自动匹配")
        client = AsyncOpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
        response = await client.chat.completions.create(
            model=cfg["model"], messages=messages, temperature=0.1,
            extra_body={"enable_thinking": False},
        )
        answer = (response.choices[0].message.content or "").strip()

        matched_ids = re.findall(r"\d+", answer)
        matched = next((row for row in rows if str(row["id"]) in matched_ids), None)
        if not matched:
            logger.info(
                "Auto 模式未匹配到技能组: groupId=%s, question=%r",
                req.groupId, question[:60],
            )
            return success(data={"matched": False, "skillGroup": None, "list": rows})
        return success(data={"matched": True, "skillGroup": matched, "list": rows})
    except Exception:
        logger.exception("Auto匹配技能组失败")
        return server_error("技能组匹配失败")


# ============================================================
# 技能组流式对话接口
# ------------------------------------------------------------
# 说明：路由层只保留「参数校验 → 准备配置 → 组装 SSE 流式响应」的轻量编排，
#       真正的分步业务流程（意图识别 / 技能编排 / 知识库召回 / 总结）
#       已拆分到 stream_service.py 的 AgentChatStreamService 中，
#       便于对每个步骤独立维护与局部改造。
# ============================================================
from api.endpoints.agent.api.stream_service import AgentChatStreamService


@router.post("/chat/stream", summary="技能组问答流式接口")
async def agent_chat_stream(req: AgentChatRequest, request: Request):
    # 步骤0：参数清洗与合法性校验（去除首尾空格后必须非空）
    skill_group_id = int(req.skillGroupId)
    question = req.query.strip()

    if not question:
        return bad_request(message="提问不能为空")

    personal_identity = None
    if req.mcpIds or req.tenantIds or req.privateSkillId or req.skillId or req.mcpApproval or request.headers.get("x-mcp-token"):
        if (req.mcpIds or req.privateSkillId or req.skillId or req.mcpApproval) and len(question) > 6000:
            return bad_request(message="MCP 技能提问最多 6000 字")
        from api.endpoints.mcp.service import get_personal_identity, get_runtime_identity
        personal_identity = await (get_personal_identity(request) if req.privateSkillId else get_runtime_identity(request))
        if personal_identity.get("userType") != "internal":
            # 外部用户只能使用所属用户组被授权的技能组
            allowed = await db_client.fetch_all(
                get_sql("agent.user_group_skill_group_access"),
                {"groupId": skill_group_id, "orgId": personal_identity.get("orgId"),
                 "userId": personal_identity["id"]},
            )
            if not allowed:
                return bad_request(message="不能使用未授权的技能组")

    try:
        # --------------------------------------------------------
        # 准备阶段：在进入流式响应前同步完成，失败可直接返回 JSON 错误
        # --------------------------------------------------------
        service = AgentChatStreamService(
            skill_group_id=skill_group_id,
            question=question,
            session_id=req.session_id,
        )
        service.personal_identity = personal_identity
        service.mcp_ids = list(dict.fromkeys(req.mcpIds))
        service.private_skill_id = req.privateSkillId
        service.shared_skill_id = req.skillId
        service.mcp_approval = req.mcpApproval
        # Auto 模式未匹配到专项技能组时，由 KaleidoPilot 承接：
        # 不执行技能编排，只做基础回复与知识库查询（技能组仅提供知识库与模型配置）。
        service.auto_assistant = bool(req.autoAssistant)
        # 知识库查询模式：同样不走意图识别与技能编排，只做向量召回回答
        service.knowledge_only = bool(req.knowledgeOnly)
        # 用户可用技能全貌：KaleidoPilot 介绍能力时要覆盖该用户能用的全部技能，而不只是本次命中的技能组
        service.user_group_id = int(req.userGroupId) if req.userGroupId else None
        # 多轮上下文：最近几轮原文 + 更早对话的记忆摘要，交给服务端拼进各环节提示词
        service.history = [item.model_dump() for item in req.history]
        service.memory = (req.memory or "").strip()

        # ① 加载技能组配置；查无有效配置时返回明确错误提示
        if not await service.load_skill_group_config():
            return server_error("技能组不存在或已被停用")
        if req.tenantIds:
            service.tenant_ids = ",".join(str(item) for item in dict.fromkeys(req.tenantIds))

        # ② 加载技能组内的技能（主技能 + 子技能），四类模型的配置来源是主技能
        await service.load_skills()

        # ②' 加载该用户组被授权的全部技能组与技能：供 KaleidoPilot 介绍平台完整能力
        await service.load_accessible_skills()

        # ③ 加载四类大模型配置（意图 / 任务拆分 / 代码执行 / 总结）
        await service.load_model_configs()

        # ④ 组装 SSE 流式响应（分步流程见 AgentChatStreamService.generate）
        return StreamingResponse(service.generate(), media_type="text/event-stream")

    except ValueError as e:
        return bad_request(message=str(e))
    except Exception as e:
        logger.error(f"技能组问答失败: {e}")
        return server_error(f"技能组问答失败: {str(e)}")
