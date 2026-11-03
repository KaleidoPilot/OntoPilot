"""普通 HTTP 接口工具、存量 MCP 协议连接及有限工具循环。"""
import asyncio
import hashlib
import ipaddress
import json
import logging
import re
import socket
import time
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
from httpcore._backends.anyio import AnyIOBackend
from jsonschema import Draft202012Validator
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent
from openai import AsyncOpenAI
from sqlalchemy import text

from api.endpoints.mcp.service import cipher, json_value, scope, approval_actor
from api.endpoints.mcp.sql import get_mcp_sql
from utils.mysqldb import db_client

MAX_RESULT = 500000
APPROVAL_TTL = 300
logger = logging.getLogger(__name__)


async def public_addresses(host: str, port: int) -> list[str]:
    try:
        addresses = await asyncio.wait_for(asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM), 5)
    except (OSError, TimeoutError):
        raise ValueError("无法解析 MCP 服务地址") from None
    result = list(dict.fromkeys(item[4][0] for item in addresses))
    if not result or any(not ipaddress.ip_address(ip).is_global for ip in result):
        raise ValueError("MCP 仅支持公网地址，不能连接本机、内网或保留地址")
    return result


class PublicNetworkBackend(AnyIOBackend):
    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = await public_addresses(host.decode() if isinstance(host, bytes) else host, port)
        return await super().connect_tcp(addresses[0], port, timeout, local_address, socket_options)


async def http_addresses(host, port):
    """按用户要求允许公网、内网和回环地址；仍拒绝元数据、链路本地及非主机地址。"""
    try:
        addresses = await asyncio.wait_for(asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM), 5)
    except (OSError, TimeoutError):
        raise ValueError("无法解析 HTTP 服务地址") from None
    result = list(dict.fromkeys(item[4][0] for item in addresses))
    for address in result:
        ip = ipaddress.ip_address(address)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified or (ip.is_reserved and not ip.is_loopback) or str(ip) == '100.100.100.200':
            raise ValueError("不能访问链路本地、元数据或保留地址")
    if not result:
        raise ValueError("无法解析 HTTP 服务地址")
    return result


class HttpNetworkBackend(AnyIOBackend):
    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = await http_addresses(host.decode() if isinstance(host, bytes) else host, port)
        return await super().connect_tcp(addresses[0], port, timeout, local_address, socket_options)


class LimitedStream(httpx.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        size = 0
        async for chunk in self.stream:
            size += len(chunk)
            if size > 2_000_000:
                raise ValueError("MCP 响应过大，请缩小查询范围")
            yield chunk

    async def aclose(self):
        await self.stream.aclose()


class McpTransport(httpx.AsyncHTTPTransport):
    def __init__(self, url):
        super().__init__(retries=0)
        self.origin = urlsplit(url)
        # 钉住校验后的公网 IP，TLS SNI 仍使用原域名，不进行第二次 DNS 解析。
        self._pool._network_backend = PublicNetworkBackend()

    async def handle_async_request(self, request):
        origin = self.origin
        port = origin.port or (443 if origin.scheme == "https" else 80)
        request_port = request.url.port or (443 if request.url.scheme == "https" else 80)
        if request.url.scheme != origin.scheme or request.url.host != httpx.URL(origin.geturl()).host or request_port != port:
            raise ValueError("MCP 不允许转发认证信息到其他地址")
        response = await super().handle_async_request(request)
        response.stream = LimitedStream(response.stream)
        return response


class HttpToolTransport(McpTransport):
    def __init__(self, url):
        super().__init__(url)
        self._pool._network_backend = HttpNetworkBackend()


def http_definition(config):
    tools = json_value(config.get("toolsJson"), [])
    http_tools = [tool for tool in tools if "httpRequest" in tool]
    if not http_tools:
        return None
    if len(tools) != 1 or config['authType'] != 'none' or config.get('secretCipher'):
        raise ValueError("HTTP 工具配置无效，请重新保存")
    from api.endpoints.mcp.modular.mcp import HttpRequestConfig
    from api.endpoints.mcp.service import http_tool
    request = HttpRequestConfig.model_validate(http_tools[0]['httpRequest'])
    tool = http_tool(request, config['name'])
    if tool != http_tools[0]:
        raise ValueError("HTTP 参数定义已变化，请重新保存配置")
    return tool


_OMITTED = object()


def render_http(value, arguments):
    if isinstance(value, dict):
        rendered = {}
        for key, item in value.items():
            child = render_http(item, arguments)
            if child is not _OMITTED:
                rendered[key] = child
        return rendered
    if isinstance(value, list):
        rendered = []
        for item in value:
            child = render_http(item, arguments)
            if child is not _OMITTED:
                rendered.append(child)
        return rendered
    if not isinstance(value, str):
        return value
    pattern = r"\{\{([A-Za-z_][A-Za-z0-9_]{0,63})\}\}"
    # 必填参数已由 check_arguments 校验；可选参数缺失时省略整个字段，避免发送残缺文本。
    if any(name not in arguments for name in re.findall(pattern, value)):
        return _OMITTED
    match = re.fullmatch(pattern, value)
    if match:
        return arguments[match[1]]
    def replace(match):
        item = arguments[match[1]]
        return item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, allow_nan=False)
    return re.sub(pattern, replace, value)


async def send_http(config, arguments):
    tool = http_definition(config)
    if not tool:
        raise ValueError("该配置不是 HTTP 工具")
    check_arguments(tool, arguments)
    request = tool['httpRequest']
    params = []
    for param in request['params']:
        if param['enabled']:
            value = render_http(param['value'], arguments)
            if value is _OMITTED:
                continue
            params.append((param['key'], value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, allow_nan=False)))
    # 地址里不允许带查询参数，查询串只按 Params 重建；模型不能改变主机、路径或方法。
    # 这样也能兜住历史配置里残留的 ?parameters= 这类文档占位。
    url = httpx.URL(config['url']).copy_with(params=params)
    body = render_http(request['body'], arguments)
    if len(str(url)) > 16000 or len(json.dumps(body, ensure_ascii=False, allow_nan=False)) > 64000:
        raise ValueError("替换后的请求参数过大，请减少 Params 或 JSON Body")
    async with asyncio.timeout(40):
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10), transport=HttpToolTransport(config['url']),
                follow_redirects=False, trust_env=False) as client:
            started = time.monotonic()
            response = await client.request(request['method'], url,
                **({'json': body} if request['method'] == 'POST' and body is not None else {}))
            try:
                data = response.json()
            except ValueError:
                data = response.text
            # 只要接口返回了内容就按调用成功处理；状态码、业务错误码这些交给模型结合接口用途判断，
            # 否则 400/500 里带的可读返回会被直接丢掉，模型也没机会说明原因。
            has_data = data not in (None, "")
            return {'statusCode': response.status_code, 'durationMs': round((time.monotonic()-started)*1000),
                'isError': not has_data, 'data': data}


class HttpToolSession:
    def __init__(self, config): self.config = config

    async def call_tool(self, name, arguments):
        if name != 'http_request':
            raise ValueError("HTTP 工具名称无效")
        result = await send_http(self.config, arguments)
        return CallToolResult(is_error=result['isError'], structured_content=result,
            content=[TextContent(type='text', text=json.dumps(result, ensure_ascii=False))])


@asynccontextmanager
async def connection(config):
    if http_definition(config):
        yield HttpToolSession(config)
        return
    origin = urlsplit(config["url"])
    await public_addresses(origin.hostname, origin.port or (443 if origin.scheme == "https" else 80))
    headers = {}
    if config["authType"] == "bearer":
        try:
            headers["Authorization"] = "Bearer " + cipher().decrypt(config["secretCipher"].encode()).decode()
        except Exception:
            raise ValueError("MCP 凭据无法解密，请重新填写 Token") from None

    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(30, connect=15), transport=McpTransport(config["url"]),
                                 follow_redirects=False, trust_env=False) as client:
        async with streamable_http_client(config["url"], http_client=client) as streams:
            async with ClientSession(streams[0], streams[1], read_timeout_seconds=timedelta(seconds=30)) as session:
                await session.initialize()
                yield session


def tool_view(tool) -> dict:
    def check_refs(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("$ref", "$dynamicRef") and (not isinstance(item, str) or not item.startswith("#")):
                    raise ValueError("工具参数定义不允许引用外部 Schema")
                check_refs(item)
        elif isinstance(value, list):
            for item in value:
                check_refs(item)
    # mcp 的模型字段是蛇形命名（input_schema / read_only_hint），这里统一转成平台自己的结构保存。
    check_refs(tool.input_schema)
    Draft202012Validator.check_schema(tool.input_schema)
    return {"name": tool.name, "description": (tool.description or "")[:2000], "inputSchema": tool.input_schema,
            "readOnly": bool(tool.annotations and tool.annotations.read_only_hint)}


async def catalog(session) -> list[dict]:
    if isinstance(session, HttpToolSession):
        return [http_definition(session.config)]
    tools, cursor = [], None
    for _ in range(5):
        page = await session.list_tools(cursor=cursor)
        tools.extend(tool_view(tool) for tool in page.tools)
        if len(tools) > 100 or len(json.dumps(tools)) > 128000:
            raise ValueError("服务工具定义过多或过大，请使用范围更小的 MCP 服务")
        cursor = page.next_cursor
        if not cursor:
            break
    else:
        raise ValueError("工具列表超过允许分页范围")
    if len({tool["name"] for tool in tools}) != len(tools):
        raise ValueError("服务返回了重复的工具名称")
    return tools


async def discover(config) -> list[dict]:
    async with asyncio.timeout(60):
        async with connection(config) as session:
            return await catalog(session)


def alias(config_id: int, tool_name: str) -> str:
    return f"mcp_{config_id}_{hashlib.sha256(tool_name.encode()).hexdigest()[:16]}"


def fingerprint(tool: dict) -> str:
    return hashlib.sha256(json.dumps(tool, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def request_hash(question, config_ids, skill_id, rules="") -> str:
    return hashlib.sha256(json.dumps([question, sorted(config_ids), skill_id, rules], ensure_ascii=False).encode()).hexdigest()


async def approval_state(identity, config_id, *, create=None, claim=None, reject=None):
    """行锁原子消费确认；执行前即消费，断连或重试不会再次执行写入。"""
    params = scope(identity, id=config_id)
    async with db_client.engine.begin() as conn:
        row = (await conn.execute(text(get_mcp_sql("available.lock")), params)).mappings().first()
        if not row or row["enabled"] != 1:
            raise ValueError("MCP 配置不存在或已停用")
        now = time.time()
        states = {k: v for k, v in json_value(row["callStateJson"], {}).items() if now - v["created"] < APPROVAL_TTL}
        result = None
        if create:
            if sum(v.get("actor", f"external:{v.get('userId')}") == approval_actor(identity) for v in states.values()) >= 20:
                raise ValueError("待处理操作过多，请稍后重试")
            approval_id = uuid.uuid4().hex
            states[approval_id] = {**create, "created": now, "status": "pending", "userId": identity["id"], "actor": approval_actor(identity)}
            result = {"configId": config_id, "id": approval_id, "toolName": create["toolName"], "arguments": create["arguments"]}
        elif claim or reject:
            operation = claim or reject
            state = states.get(operation["id"])
            if not state or state.get("actor", f"external:{state.get('userId')}") != approval_actor(identity) or state["status"] != "pending":
                raise ValueError("操作确认已过期或已处理，请勿重复执行")
            if claim and (state["requestHash"] != claim["requestHash"] or state["fingerprint"] != claim["fingerprint"]):
                raise ValueError("任务或工具定义已变更，不能执行旧的确认")
            state["status"] = "consumed" if claim else "rejected"
            result = state
        serialized = json.dumps(states, ensure_ascii=False)
        if create and len(serialized) > 2000000:
            raise ValueError("服务待确认任务过多，请稍后重试")
        await conn.execute(text(get_mcp_sql("available.state")), {**params, "callStateJson": serialized})
        return result


async def pending_approval(identity, config_id, approval_id):
    from api.endpoints.mcp.service import owned_config
    row = await owned_config(identity, config_id, active=True)
    state = json_value(row["callStateJson"], {}).get(approval_id)
    if not state or state.get("actor", f"external:{state.get('userId')}") != approval_actor(identity) or state["status"] != "pending" or time.time() - state["created"] >= APPROVAL_TTL:
        raise ValueError("操作确认已过期或已处理")
    return state


def result_text(result) -> str:
    # mcp 的返回对象属性是 is_error / structured_content，camelCase 只是序列化别名。
    value = {"isError": result.is_error, "structuredContent": result.structured_content,
             "content": [block.text for block in result.content if getattr(block, "type", None) == "text"]}
    output = json.dumps(value, ensure_ascii=False, default=str)
    if len(output) > MAX_RESULT:
        return json.dumps({"isError": result.is_error, "truncated": True, "content": output[:MAX_RESULT],
                           "message": "返回结果已截断，请缩小范围或分页查询"}, ensure_ascii=False)
    return output


def result_hint(value):
    """
    只在 HTTP 工具完全没有返回内容时补一句提示。

    接口只要有返回数据就按调用成功处理，数据对不对交给模型按接口用途判断；
    这里不再根据状态码下结论，避免把带业务错误信息的正常响应误判成调用失败。
    """
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return value
    structured = payload.get("structuredContent") if isinstance(payload, dict) else None
    if not isinstance(structured, dict) or "statusCode" not in structured:
        return value
    if structured.get("data") in (None, "", [], {}):
        return value + "\n\n【调用提示】接口没有返回任何内容。请核对参数取值后重试一次；仍为空就如实说明，不要编造数据。"
    return value


def preview(value, limit=1000):
    """日志里只留一段预览，避免参数或返回过大刷屏。"""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else f"{text[:limit]}...（共 {len(text)} 字符）"


def check_arguments(tool, arguments):
    if not isinstance(arguments, dict) or len(json.dumps(arguments)) > 16000:
        raise ValueError("工具参数必须为大小受限的 JSON 对象")
    if next(Draft202012Validator(tool["inputSchema"]).iter_errors(arguments), None):
        raise ValueError("工具参数不符合服务定义")


async def chat_events(identity, selections, cfg, messages, context_hash, approval=None, local_tools=(), authorization_check=None, execution_context=None):
    async with AsyncExitStack() as stack:
        registry, definitions = {}, []
        for config, selected in selections:
            session = await stack.enter_async_context(connection(config))
            current = {tool["name"]: tool for tool in await catalog(session)}
            saved = {tool["name"]: tool for tool in json_value(config["toolsJson"], [])}
            for name in sorted(selected):
                tool = current.get(name)
                if not tool or name not in saved or fingerprint(tool) != fingerprint(saved[name]):
                    raise ValueError("MCP 工具定义已变化，请先测试连接并重新核对工具")
                wire_name = alias(config["id"], name)
                registry[wire_name] = (config, session, tool)
                # 接口用途、参数备注和返回说明都写在 description 里，标注清楚才好让模型先读说明再组装参数。
                definitions.append({"type": "function", "function": {"name": wire_name,
                    "description": f"【{config['name']}】{name}\n{tool['description']}", "parameters": tool["inputSchema"]}})
        for tool, callback in local_tools:
            if not selections and not tool.get('readOnly'):
                raise ValueError("技能数据分析缺少 MCP 确认配置")
            config = selections[0][0] if selections else None
            wire_name = alias(config["id"], tool["name"]) if config else 'platform_' + tool['name']
            if wire_name in registry:
                raise ValueError("平台工具与 MCP 工具名称冲突")
            registry[wire_name] = (config, callback, tool)
            definitions.append({"type": "function", "function": {"name": wire_name,
                "description": tool["description"], "parameters": tool["inputSchema"]}})
        if len(definitions) > 60:
            raise ValueError("一次执行最多使用 60 个工具，请减少选择")
        yield {"type": "metadata", "data": {"intent": "personal_mcp"}}
        client = await stack.enter_async_context(AsyncOpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=60, max_retries=0))
        calls = 0

        async def invoke(wire_name, args):
            config, session, tool = registry[wire_name]
            check_arguments(tool, args)
            from api.endpoints.mcp.service import owned_config
            local = callable(session)
            if authorization_check:
                await authorization_check(config['id'] if config else None, tool['name'], local)
            if config is None:
                if not local or not tool.get('readOnly'):
                    raise ValueError('独立平台工具必须为只读操作')
                serialized = json.dumps(await session(args), ensure_ascii=False, default=str)
                if len(serialized) > MAX_RESULT:
                    raise ValueError('取数结果过大，请减少字段或返回行数，不能用截断结果代替完整统计')
                return serialized
            current = await owned_config(identity, config["id"], active=True)
            if any(current[k] != config[k] for k in ("url", "authType", "secretCipher", "toolsJson")) or (not local and tool["name"] not in json_value(current["selectedToolsJson"], [])):
                raise ValueError("MCP 配置或工具权限已变更，请重新提交任务")
            logger.info("调用工具：%s 参数=%s", tool["name"], preview(args))
            if local:
                value = await session(args)
                serialized = json.dumps(value, ensure_ascii=False, default=str)
                if tool.get('strictResult') and len(serialized) > MAX_RESULT:
                    raise ValueError('取数结果过大，请减少字段或返回行数，不能用截断结果代替完整统计')
                logger.info("工具返回：%s %s", tool["name"], preview(serialized, 2000))
                return serialized if len(serialized) <= MAX_RESULT else json.dumps({'isError': value.get('isError', False), 'truncated': True, 'content': serialized[:MAX_RESULT]}, ensure_ascii=False)
            try:
                value = result_text(await session.call_tool(tool["name"], args))
                if config["authType"] == "bearer":
                    secret = cipher().decrypt(config["secretCipher"].encode()).decode()
                    value = value.replace(secret, "[已隐藏凭据]")
                # 原始返回和状态码都落日志，方便核对接口到底回了什么、参数是不是给错了。
                logger.info("工具返回：%s %s", tool["name"], preview(value, 2000))
                return result_hint(value)
            except Exception as exc:
                logger.exception("工具调用失败：%s", tool["name"])
                # 把错误类型和原因回给模型，让它有机会修正参数重试，而不是直接放弃。
                detail = f"{type(exc).__name__}: {str(exc)}"[:300]
                return json.dumps({"isError": True, "message": f"工具调用失败：{detail}。"
                    "请先按工具说明核对字段名、类型和必填项，修正参数后重试；属于外部系统故障或超时才如实说明失败原因。"},
                    ensure_ascii=False)

        if approval:
            state = await pending_approval(identity, approval.configId, approval.id)
            wire_name = alias(approval.configId, state["toolName"])
            if wire_name not in registry:
                raise ValueError("确认的工具已不在当前授权范围内")
            config, session, tool = registry[wire_name]
            check_arguments(tool, state["arguments"])
            await approval_state(identity, approval.configId, claim={"id": approval.id, "requestHash": context_hash, "fingerprint": fingerprint(tool)})
            messages = state.get("history") or messages
            yield {"type": "tool_status", "data": {"name": tool.get("displayName", tool["name"]), "status": "running"}}
            value = await invoke(wire_name, state["arguments"])
            messages.extend([{"role": "assistant", "tool_calls": [{"id": approval.id, "type": "function", "function": {
                "name": wire_name, "arguments": json.dumps(state["arguments"], ensure_ascii=False)}}]},
                {"role": "tool", "tool_call_id": approval.id, "content": value}])
            yield {"type": "tool_status", "data": {"name": tool.get("displayName", tool["name"]), "status": "done"}}
            calls += 1

        for turn in range(7):
            if len(json.dumps(messages, ensure_ascii=False)) > 600000:
                raise ValueError("任务上下文过大，请缩小查询范围")
            can_call = turn < 6 and calls < 12 and bool(definitions)
            response = await client.chat.completions.create(model=cfg["model"], messages=messages,
                **({"tools": definitions, "tool_choice": "auto" if can_call else "none"} if definitions else {}),
                temperature=cfg.get('temperature', 0.3),
                **({'top_p': cfg['top_p']} if 'top_p' in cfg else {}), max_tokens=4096)
            message = response.choices[0].message
            if not message.tool_calls:
                if not message.content or not message.content.strip():
                    raise ValueError("模型未返回回答，请检查模型配置")
                yield {"type": "content", "content": message.content}
                return
            if not can_call:
                raise ValueError("工具调用达到上限，请缩小任务范围")
            assistant_index = len(messages)
            messages.append(message.model_dump(exclude_none=True, include={"role", "content", "tool_calls"}))
            for call in message.tool_calls:
                if calls >= 32:
                    raise ValueError("工具调用达到上限，请缩小任务范围")
                name = call.function.name
                if name not in registry:
                    raise ValueError("模型请求了未授权工具")
                config, session, tool = registry[name]
                try:
                    arguments = json.loads(call.function.arguments)
                    check_arguments(tool, arguments)
                except ValueError as exc:
                    # 参数不合法的常见原因是字段名、类型或必填项填错；返回给模型一轮修正机会，
                    # 而不是让整次任务直接失败。
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(
                        {"isError": True, "message": f"工具参数不合法：{exc}。"
                            "请按接口用途和字段备注重新组装参数后再调用，不要向用户复述这条错误。"}, ensure_ascii=False)})
                    continue
                if not tool["readOnly"]:
                    history = messages[:assistant_index]
                    completed = messages[assistant_index + 1:]
                    if completed:
                        completed_ids = {item["tool_call_id"] for item in completed}
                        history.append({"role": "assistant", "tool_calls": [item.model_dump() for item in message.tool_calls if item.id in completed_ids]})
                        history.extend(completed)
                    proposed = await approval_state(identity, config["id"], create={"toolName": tool["name"], "arguments": arguments,
                        "fingerprint": fingerprint(tool), "requestHash": context_hash, "history": history,
                        **({'executionContext': execution_context} if execution_context is not None else {})})
                    proposed["serverName"] = '平台' if callable(session) else config["name"]
                    proposed["toolName"] = tool.get("displayName", tool["name"])
                    yield {"type": "confirmation", "data": proposed}
                    return
                yield {"type": "tool_status", "data": {"name": tool["name"], "status": "running"}}
                value = await invoke(name, arguments)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": value})
                yield {"type": "tool_status", "data": {"name": tool["name"], "status": "done"}}
                calls += 1
