"""客户元数据只在项目绑定的沙箱内读取；平台不持有客户数据库连接。"""
import asyncio
import base64
import binascii
import importlib
import json
import uuid
import time
import zlib
import requests
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects import mysql

from api.endpoints.system.service import get_company_sandbox_config
from api.endpoints.project.sql import get_template_project_sql
from utils.mysqldb import db_client


class TemplateProjectError(ValueError):
    def __init__(self,message,status=403):
        super().__init__(message)
        self.status=status


async def load_template_project_context(identity, project_group_ids=None):
    """仅返回已导入的表结构和人工维护关系，不读取客户数据或连接凭据。"""
    if project_group_ids == []:
        return {'groups':[], 'warnings':[]}
    params = {'orgId':identity['orgId'],'userId':identity['id'],'userType':identity['userType']}
    available = await db_client.fetch_all(get_template_project_sql('groups'),params)
    if project_group_ids is None:
        return [{'id':int(g['id']),'groupName':g['groupName']} for g in available]
    if (not isinstance(project_group_ids,list) or len(project_group_ids)>20
            or any(type(v) is not int or v<=0 for v in project_group_ids)
            or len(set(project_group_ids)) != len(project_group_ids)):
        raise TemplateProjectError('项目组必须是最多20个不重复的正整数ID',400)
    by_id = {int(g['id']):g for g in available}
    if any(i not in by_id for i in project_group_ids):
        raise TemplateProjectError('所选项目组不存在、已停用或当前账号无权使用，请重新选择')
    context = {'groups':[], 'warnings':[]}
    for group_id in project_group_ids:
        group = by_id[group_id]
        scoped = {**params,'projectGroupId':group_id}
        tables = await db_client.fetch_all(get_template_project_sql('tables'),scoped)
        normalized = []
        for table in tables:
            try:
                columns = json.loads(table['columnsJson']) if isinstance(table['columnsJson'],str) else table['columnsJson']
            except (TypeError,json.JSONDecodeError):
                raise TemplateProjectError('项目组表结构格式无效，请先同步表结构',409) from None
            if not isinstance(columns,dict):
                raise TemplateProjectError('项目组表结构格式无效，请先同步表结构',409)
            normalized.append({'id':int(table['id']),'tableName':table['tableName'],
                'tableCnName':table.get('tableCnName') or '', 'comment':table.get('tableComment') or '',
                'columns':[{'name':name,'type':details.get('type',''),'comment':details.get('columnComment',''),
                            'remark':details.get('remark','')} for name,details in columns.items() if isinstance(details,dict)]})
        field_sets = {t['id']:{c['name'] for c in t['columns']} for t in normalized}
        relations = []
        for relation in await db_client.fetch_all(get_template_project_sql('relations'),scoped):
            if (relation['sourceColumn'] in field_sets.get(relation['sourceTableId'],set())
                    and relation['targetColumn'] in field_sets.get(relation['targetTableId'],set())):
                relations.append({k:relation[k] for k in ('id','sourceTableId','sourceColumn','targetTableId','targetColumn','relationContent','remarks')})
            elif identity['userType']=='internal':
                context['warnings'].append(f'项目组 {group["groupName"]} 的关系 {relation["id"]} 字段已失效，未用于来源匹配')
        context['groups'].append({'id':group_id,'groupName':group['groupName'],
            'databaseName':group.get('libraryName') or '', 'tables':normalized,'relations':relations})
    table_count = sum(len(g['tables']) for g in context['groups'])
    field_count = sum(len(t['columns']) for g in context['groups'] for t in g['tables'])
    if table_count>300 or field_count>4000 or len(json.dumps(context,ensure_ascii=False))>80000:
        raise TemplateProjectError('所选项目组结构过多，请减少项目组后生成模板',400)
    return context


def execute_company_source_code(code: str, sandbox_config: dict[str, Any], kernel_id: str | None = None, *, strict: bool = True, timeout_s: int = 120) -> str:
    """在业务适配层构造连接；凭据只发往沙箱，不传入模型上下文。"""
    agent = importlib.import_module("utils.ai-agent.tableAgent.agent")
    if sandbox_config.get("database"):
        database = sandbox_config["database"]
        options = {
            "host": database["host"], "port": database["port"],
            "user": database["username"], "password": database["password"],
            "charset": "utf8mb4",
            "connect_timeout": 10, "read_timeout": 30, "write_timeout": 30,
        }
        bootstrap = "import pymysql\n" + f"def get_connection():\n    return pymysql.connect(**{options!r})\n" + f"exec({code!r})"
        code = f"exec({bootstrap!r}, {{}})"
        strict = True  # 含凭据的执行载荷不得写入共享内核历史。
    return agent.execute_in_sandbox(code, sandbox_config, kernel_id, strict=strict, timeout_s=timeout_s)


async def resolve_company_source_kernel(config: dict[str, Any]) -> str:
    """选择已初始化客户数据访问函数的内核，不创建无法访问客户数据的空内核。"""
    agent = importlib.import_module("utils.ai-agent.tableAgent.agent")
    if config.get("database"):
        try:
            return await asyncio.to_thread(agent.resolve_kernel_id, config["url"], config.get("token", ""))
        except Exception:
            raise ValueError("沙箱内核连接失败，请检查 URL、Token 和服务状态") from None
    def resolve():
        headers = {"Authorization": "token " + config["token"]} if config.get("token") else {}
        kernels = None
        # 首次连接沙箱时服务/网关可能抖动，内核列表读取带重试
        for attempt in range(1, 4):
            try:
                response = requests.get(
                    config["url"].rstrip("/") + "/api/kernels",
                    headers=headers, timeout=10,
                )
                response.raise_for_status()
                kernels = response.json()
                break
            except Exception:
                if attempt == 3:
                    raise ValueError("沙箱内核列表读取失败，请检查 URL、Token 和服务状态") from None
                time.sleep(0.8 * attempt)
        if not isinstance(kernels, list):
            raise ValueError("沙箱内核列表读取失败，请检查 URL、Token 和服务状态")
        deadline = time.monotonic() + 30
        uncertain = False
        for kernel in kernels:
            if not isinstance(kernel, dict) or kernel.get("name") != "python3" or not kernel.get("id"):
                continue
            # 新建/启动中的内核首次探测会失败，等待就绪后重试一次，避免误判为不可用
            for attempt in range(2):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    uncertain = True
                    break
                try:
                    output = agent.execute_in_sandbox(
                        "print('__FIJO_SOURCE_READY__' if callable(globals().get('get_connection')) else '__FIJO_SOURCE_MISSING__')",
                        config, kernel["id"], strict=True, timeout_s=min(8, remaining),
                    )
                    if "__FIJO_SOURCE_READY__" in output.splitlines():
                        return kernel["id"]
                    break
                except agent.SandboxExecutionError:
                    uncertain = True
                    if attempt == 0:
                        time.sleep(1.0)
        if uncertain:
            raise ValueError("未能确认可用的数据访问内核，部分内核忙碌或连接失败，请稍后重试")
        raise ValueError("沙箱中没有初始化 get_connection() 的 Python 内核，请由沙箱维护方初始化客户数据连接")
    return await asyncio.to_thread(resolve)


def build_metadata_code(query: str, params: dict[str, Any], marker: str) -> str:
    # SQL 来自 project/sql/sql.yaml；只编译占位符，参数始终单独传递。
    compiled = text(query).compile(dialect=mysql.dialect(paramstyle="pyformat"))
    payload = json.dumps({"query": str(compiled), "params": params}, ensure_ascii=False)
    body = f'''import json, base64, zlib
if not callable(get_connection):
    raise RuntimeError("沙箱未初始化 get_connection()，请由沙箱维护方配置客户数据访问")
payload = json.loads({payload!r})
connection = get_connection()
if connection is None:
    raise RuntimeError("沙箱 get_connection() 未返回连接，请检查是否被生成代码覆盖或内核未初始化")
try:
    with connection.cursor() as cursor:
        cursor.execute(payload["query"], payload["params"])
        names = [column[0] for column in cursor.description or []]
        rows = cursor.fetchall()
        result = [dict(row) if isinstance(row, dict) else dict(zip(names, row)) for row in rows]
    serialized = json.dumps(result, ensure_ascii=False, default=str).encode('utf-8')
    print({marker!r} + base64.b64encode(zlib.compress(serialized)).decode('ascii'))
finally:
    try:
        connection.rollback()
    finally:
        connection.close()
'''
    return f"exec({body!r}, {{'get_connection': globals().get('get_connection')}})"


def _decode_metadata_payload(payload: str):
    # 限制解压体积，避免异常沙箱响应造成无界内存分配。
    limit = 16 * 1024 * 1024
    if len(payload) > limit * 2:
        raise ValueError("沙箱元数据响应过大")
    try:
        packed = base64.b64decode(payload, validate=True)
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(packed, limit + 1)
        if len(decoded) > limit or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
            raise ValueError("沙箱元数据响应不完整或过大")
        return json.loads(decoded)
    except (binascii.Error, zlib.error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("沙箱元数据响应格式错误") from error


async def _execute_company_source(
    org_id: int, query: str, params: dict[str, Any], *, first: bool,
    sandbox_config_id: int, sandbox_config: dict[str, Any] | None = None,
    kernel_id: str | None = None,
):
    config = sandbox_config if sandbox_config is not None else await get_company_sandbox_config(org_id, sandbox_config_id)
    agent = importlib.import_module("utils.ai-agent.tableAgent.agent")
    marker = "__FIJO_METADATA_" + uuid.uuid4().hex + "__"
    payload = build_metadata_code(query, params, marker)

    # 沙箱偶发抖动（网关断开、内核被回收、执行超时）会让一次读取直接失败。
    # 这类失败与 SQL 本身无关，重新挑一个可用内核再取即可；最多 3 次，避免一次抖动打断整条技能链路。
    attempts = 3
    for attempt in range(attempts):
        try:
            target_kernel = kernel_id or await resolve_company_source_kernel(config)
            output = await asyncio.to_thread(
                execute_company_source_code, payload, config, target_kernel, strict=True, timeout_s=45,
            )
        except (ValueError, agent.SandboxExecutionError) as error:
            # 只有连接/超时类失败值得重试；SQL 或权限问题重试也不会变好
            retryable = not isinstance(error, agent.SandboxExecutionError) or error.kind in {"connection", "timeout"}
            if not retryable or attempt == attempts - 1:
                if isinstance(error, agent.SandboxExecutionError) and error.kind == "execution":
                    raise ValueError("沙箱读取客户数据失败，请检查沙箱内 get_connection() 的配置及数据库访问权限") from None
                raise ValueError(str(error)) from None
            # 原内核可能已经失联，下一次重新选择内核
            kernel_id = None
            await asyncio.sleep(1.0 + attempt)
            continue

        line = next((line[len(marker):] for line in output.splitlines() if line.startswith(marker)), None)
        try:
            rows = _decode_metadata_payload(line) if line is not None else None
        except (TypeError, ValueError):
            rows = None
        if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
            return (rows[0] if rows else None) if first else rows

        # 输出缺失或格式损坏，多半是连接中途断开导致结果不完整，重新取一次再判定
        if attempt < attempts - 1:
            kernel_id = None
            await asyncio.sleep(1.0 + attempt)
            continue
        raise ValueError("沙箱未返回有效的表结构数据，请检查沙箱执行结果")


async def fetch_company_source_one(org_id: int, query: str, params: dict[str, Any], **kwargs):
    return await _execute_company_source(org_id, query, params, first=True, **kwargs)


async def fetch_company_source_all(org_id: int, query: str, params: dict[str, Any], **kwargs):
    return await _execute_company_source(org_id, query, params, first=False, **kwargs)
