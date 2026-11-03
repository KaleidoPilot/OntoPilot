import os
import yaml
import requests
import time
import uuid
import ast
from typing import List, Dict, Any
from openai import OpenAI
from core.config import yaml_config
import asyncio
import json
import re

# 获取当前文件所在目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROMPTS_FILE = os.path.join(CURRENT_DIR, "prompts.yaml")

def load_prompts(prompt_path: str = DEFAULT_PROMPTS_FILE) -> Dict[str, Any]:
    """加载提示词配置文件"""
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"提示词配置文件未找到: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _call_llm(messages: List[Dict[str, str]], llm_config: Dict[str, Any], temperature: float = 0.3) -> str:
    """
    通用模型调用方法
    """
    api_key = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    model = llm_config.get("model", "qwen3.7-plus")
    
    if not api_key or not base_url:
        raise ValueError("LLM configuration is missing api_key or base_url.")
        
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        extra_body={
            "enable_thinking": False
        },
    )
    
    return response.choices[0].message.content

def split_task(query: str, prompts: Dict[str, Any], knowledge: str = "", llm_config: Dict[str, Any] = None) -> str:
    """
    步骤1：使用 task_llm 拆分任务
    """
    config = llm_config or yaml_config.get("model_settings", {}).get("ai_process", {}).get("task_llm", {})
    prompt_cfg = prompts.get("task_split", {})
    
    system_base = prompt_cfg.get("system", "你是一个任务拆分助手。")
    if knowledge:
        # 将庞大的知识库/表结构放在 system message 头部，以利于大模型触发 Context Cache (记忆缓存)
        system_msg = f"{knowledge}\n\n【当前任务角色】：\n{system_base}"
    else:
        system_msg = system_base
        
    user_template = prompt_cfg.get("user_template", "{query}")
    # 动态的用户请求部分只放在 user message 中
    user_msg = user_template.format(query=query)
    
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]
    
    return _call_llm(messages, config)

def generate_code(task_info: str, prompts: Dict[str, Any], knowledge: str = "", llm_config: Dict[str, Any] = None) -> str:
    """
    步骤2：使用 execute_llm 生成代码
    """
    config = llm_config or yaml_config.get("model_settings", {}).get("ai_process", {}).get("execute_llm", {})
    prompt_cfg = prompts.get("execute_code", {})
    
    system_base = prompt_cfg.get("system", "你是一个代码生成助手。")
    if knowledge:
        # 将庞大的知识库/表结构放在 system message 头部，以利于大模型触发 Context Cache (记忆缓存)
        system_msg = f"{knowledge}\n\n【当前任务角色】：\n{system_base}"
    else:
        system_msg = system_base
        
    user_template = prompt_cfg.get("user_template", "{task}")
    # 动态的任务步骤部分只放在 user message 中
    user_msg = user_template.format(task=task_info)
    
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]
    
    return _call_llm(messages, config)

def _http_with_retry(method: str, url: str, *, headers: Dict[str, str] = None,
                     payload: Dict[str, Any] = None, timeout: int = 10,
                     attempts: int = 3, backoff: float = 0.8):
    """沙箱 HTTP 调用统一重试：首次连接沙箱时服务/网关偶发抖动，重试可避免直接失败。"""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.request(method, url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as error:
            last_error = error
            if attempt < attempts:
                time.sleep(backoff * attempt)
    raise last_error


def wait_kernel_ready(base_url: str, kernel_id: str, headers: Dict[str, str],
                      *, timeout_s: float = 30.0, interval: float = 0.5) -> bool:
    """等待内核进入 idle。

    新建的内核会先处于 starting，复用被占用的内核可能处于 busy；
    若不等就绪就直接执行，首次调用几乎必然失败。
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/api/kernels/{kernel_id}", headers=headers, timeout=5)
            if response.status_code == 200:
                state = (response.json() or {}).get("execution_state")
                if state == "idle":
                    return True
                if state == "dead":
                    return False
        except Exception:
            pass
        time.sleep(interval)
    return False


def resolve_kernel_id(url: str, token: str = "") -> str:
    """
    规则：
        1. 先 GET {url}/api/kernels 查询内核列表（带重试）；
        2. 列表中筛选 name == "python3" 的内核，优先复用空闲(idle)的，跳过已死亡(dead)的；
        3. 若没有可复用的 python3 内核 → POST {url}/api/kernels 创建 {"name": "python3"}，
           并等待内核就绪(idle)后再返回其 id。

    :param url: 沙箱基础地址，例如 http://127.0.0.1:7080
    :param token: 访问沙箱的 token，可选
    :return: 可用的 kernel_id
    :raises RuntimeError: 查询或创建内核失败时抛出
    """
    base_url = url.rstrip("/")
    headers = {}
    if token:
        # Jupyter 的鉴权头格式固定为 "token xxx"
        headers["Authorization"] = f"token {token}"

    # 1. 查询是否存在可用内核（首次连接可能抖动，带重试）
    try:
        kernels = _http_with_retry("GET", f"{base_url}/api/kernels", headers=headers, timeout=10).json()
    except Exception as e:
        raise RuntimeError(f"查询沙箱内核列表失败: {e}")

    # 2. 只认可 python3 类型内核：优先复用空闲的，其余等待就绪后再复用
    if isinstance(kernels, list):
        python3_kernels = [
            kernel for kernel in kernels
            if isinstance(kernel, dict) and kernel.get("name") == "python3" and kernel.get("id")
        ]
        for kernel in python3_kernels:
            # 空闲内核可直接复用，避免等待
            if kernel.get("execution_state") == "idle":
                return kernel["id"]
        for kernel in python3_kernels:
            # 正在启动/执行的内核，等待其就绪后复用，避免重复创建内核
            if kernel.get("execution_state") == "dead":
                continue
            if wait_kernel_ready(base_url, kernel["id"], headers, timeout_s=15):
                return kernel["id"]

    # 3. 没有可用的 python3 内核，自动创建一个，并等待其就绪后再使用
    try:
        kernel = _http_with_retry(
            "POST", f"{base_url}/api/kernels", headers=headers,
            payload={"name": "python3"}, timeout=15,
        ).json()
    except Exception as e:
        raise RuntimeError(f"自动创建沙箱内核失败: {e}")

    kernel_id = (kernel or {}).get("id")
    if not kernel_id:
        raise RuntimeError("沙箱创建内核后未返回 id。")
    # 新建内核通常处于 starting，立即执行会失败，这里等其变为 idle
    wait_kernel_ready(base_url, kernel_id, headers, timeout_s=30)
    return kernel_id


class SandboxExecutionError(RuntimeError):
    def __init__(self, message: str, kind: str = "execution"):
        super().__init__(message)
        self.kind = kind


# 沙箱执行完但没有任何输出时的占位文案；主流程会把它当成失败触发重试
EMPTY_OUTPUT_MARK = "代码已执行，无控制台输出。"


def execute_in_sandbox(code: str, sandbox_config: Dict[str, Any] = None,
                       kernel_id: str = None, *, strict: bool = False,
                       timeout_s: int = 120) -> str:
    """
    步骤3：调用沙箱执行代码
    参考 execution_mixin.py 重构的沙箱 WebSocket 通信与执行逻辑。
    """
    sandbox_config = yaml_config.get("sandbox", {}) if sandbox_config is None else sandbox_config
    url = sandbox_config.get("url")
    token = sandbox_config.get("token", "")

    if not url:
        raise ValueError("Sandbox configuration is missing url.")

    # 动态解析可用内核 ID（复用已有内核 / 无则自动创建）
    try:
        kernel_id = kernel_id or resolve_kernel_id(url, token)
    except Exception as e:
        if strict:
            raise SandboxExecutionError("沙箱内核连接失败，请检查 URL、Token 和服务状态", "connection") from None
        return f"获取沙箱内核失败: {str(e)}"

    import uuid
    import websocket
    import json
    from datetime import datetime

    ws_scheme = "wss" if url.startswith("https") else "ws"
    host_part = url.split("://")[-1].rstrip("/")
    ws_url = f"{ws_scheme}://{host_part}/api/kernels/{kernel_id}/channels"

    headers = [f"Origin: {url.rstrip('/')}"]
    if token:
        headers.append(f"Authorization: token {token}")

    ws = None
    last_error = None
    # 首次连接沙箱（握手）偶发失败，重试 3 次并退避，避免首个请求直接报错
    for attempt in range(1, 4):
        try:
            ws = websocket.create_connection(ws_url, header=headers, timeout=10)
            ws.settimeout(5)
            break
        except Exception as e:
            last_error = e
            ws = None
            if attempt < 3:
                time.sleep(0.8 * attempt)
    if ws is None:
        if strict:
            raise SandboxExecutionError("沙箱 WebSocket 连接失败，请检查服务与网关配置", "connection") from None
        return f"WebSocket 连接失败: {str(last_error)}"

    session_id = uuid.uuid4().hex
    msg_id = uuid.uuid4().hex

    # 包装代码以防无输出
    safe_code = code

    msg = {
        "header": {
            "msg_id": msg_id,
            "username": "client",
            "session": session_id,
            "msg_type": "execute_request",
            "version": "5.3",
            "date": datetime.now().isoformat()
        },
        "parent_header": {},
        "metadata": {},
        "content": {
            "code": safe_code,
            "silent": False,
            "store_history": not strict,
            "user_expressions": {},
            "allow_stdin": False
        },
        "channel": "shell"
    }

    try:
        ws.send(json.dumps(msg))
        deadline = time.time() + timeout_s
        full_output = []
        execution_error = None

        while time.time() < deadline:
            try:
                frame = ws.recv()
                resp_msg = json.loads(frame)
            except (websocket.WebSocketTimeoutException, TimeoutError):
                continue
            except Exception as e:
                if strict:
                    raise SandboxExecutionError("沙箱通信中断，执行结果未确认，请稍后重试", "connection") from None
                full_output.append(f"⚠️ 接收异常: {e}")
                break

            if resp_msg.get('channel') != 'iopub':
                continue
                
            if resp_msg.get('parent_header', {}).get('msg_id') != msg_id:
                continue

            msg_type = resp_msg['msg_type']
            content = resp_msg['content']

            if msg_type == 'stream':
                full_output.append(content['text'])
            elif msg_type in ('execute_result', 'display_data', 'update_display_data'):
                # 统一采集普通 print 之外的“单元格结果/富文本展示”：
                # 例如 IPython 的 display(df) 会以 display_data 推送 DataFrame 的 text/plain，
                # 若不采集，最终总结将拿不到数据内容（只看到“共找到 N 条记录”）。
                data = content.get('data') or {}
                plain = data.get('text/plain')
                if plain:
                    full_output.append(str(plain) + "\n")
                elif data.get('text/html'):
                    # 兜底：缺少纯文本时把 HTML（如表格式 div）粗略转成可读文本，避免结果丢失
                    html_text = re.sub(r'<[^>]+>', ' ', data['text/html'])
                    html_text = re.sub(r'[ \t]+', ' ', html_text)
                    html_text = re.sub(r'\n\s*\n+', '\n', html_text).strip()
                    if html_text:
                        full_output.append(html_text + "\n")
            elif msg_type == 'error':
                execution_error = f"{content.get('ename', 'Error')}: {content.get('evalue', '执行失败')}"
                full_output.append(f"❌ Error: {content['evalue']}\n" + "\n".join(content.get('traceback', [])) + "\n")
            elif msg_type == 'status':
                if content['execution_state'] == 'idle':
                    break
        else:
            if strict:
                raise SandboxExecutionError("沙箱执行超时，执行结果未确认，请稍后重试", "timeout")
            full_output.append("\n[Timeout]")

        if strict and execution_error:
            raise SandboxExecutionError(execution_error)

        return "".join(full_output).strip() or EMPTY_OUTPUT_MARK

    except SandboxExecutionError:
        raise
    except Exception as e:
        if strict:
            raise SandboxExecutionError("沙箱执行通信失败，请检查服务状态", "connection") from None
        return f"执行通信失败: {str(e)}"
    finally:
        if ws:
            ws.close()

def summarize_result(query: str, result: str, prompts: Dict[str, Any], llm_config: Dict[str, Any] = None) -> str:
    """
    步骤4：使用 summary_llm 总结执行结果
    """
    config = llm_config or yaml_config.get("model_settings", {}).get("ai_process", {}).get("summary_llm", {})
    prompt_cfg = prompts.get("summary", {})
    
    system_msg = prompt_cfg.get("system", "你是一个业务数据解读专家。")
    user_msg = prompt_cfg.get("user_template", "查询：{query}\n结果：{result}").format(query=query, result=result)
    
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]
    
    return _call_llm(messages, config)

def _extract_handoff(res: str) -> Dict[str, Any]:
    """
    从某一步的执行输出中解析 __HANDOFF__ 协议行，得到结构化衔接参数。

    协议格式（由代码生成提示词约束）：
        print('__HANDOFF__' + json.dumps({'键名': 简单值}))

    :param res: 沙箱执行输出文本
    :return: 解析得到的参数 dict；未命中或解析失败返回空 dict
    """
    # 只匹配独立一行的 __HANDOFF__ 协议（json.dumps 默认单行输出），
    # 避免误吞输出文本里其他位置的括号。
    match = re.search(r"(?m)^\s*__HANDOFF__\s*(\{.*\})\s*$", res)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _has_empty_branch(payload: Any) -> bool:
    """
    判断衔接参数里是否存在空的分支（空列表/空字典）。

    __HANDOFF__ 是上一步真实查到的结构化结果。若其中出现空列表/空字典，
    通常说明该步的查询条件没有命中（例如用户给的 SKU 与库里的商品编码不一致），
    此时若直接放行，后续步骤只会打印“No products found”之类的空结果，
    最终把“没查到”误当成“业务上没有数据”。因此这里识别为需要重试的信号。
    """
    if isinstance(payload, dict):
        return any(_has_empty_branch(value) for value in payload.values())
    if isinstance(payload, (list, tuple, set)):
        return len(payload) == 0 or any(_has_empty_branch(value) for value in payload)
    return False


def _defines_get_connection(code: str) -> bool:
    """
    判断生成代码是否在模块顶层重新定义了 get_connection。

    沙箱执行时通过 exec 的命名空间注入 get_connection；若模型代码里写了
    def get_connection(): pass 这类占位实现，会覆盖注入的连接工厂，
    使 conn 变成 None，最终报 "'NoneType' object has no attribute 'cursor'"。
    因此在真正执行前拦截，交给 AI 自我修复，而不是执行后才暴露难懂的报错。
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # 语法错误由沙箱执行阶段报出并走修复流程，这里不重复处理
        return False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "get_connection":
            return True
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "get_connection" for target in node.targets
        ):
            return True
    return False


async def process_table_query(query: str, knowledge: str = "", prompt_path: str = DEFAULT_PROMPTS_FILE,
                        task_cfg: Dict[str, Any] = None, execut_cfg: Dict[str, Any] = None,
                        sandbox_config: Dict[str, Any] = None, kernel_id: str = None,
                        prompts: Dict[str, Any] = None, sandbox_executor=None,
                        compact_knowledge: str = ""):
    """
    主控方法：根据query和提示词路径，调度 Table Agent 流程
    这是一个异步生成器，实时返回执行日志，最后返回最终执行结果。

    步骤衔接设计（重要）：
        - 优先要求“单条 SQL 一步完成”，从源头减少多余的跨步骤传参；
        - 确实需要多步时，参数不经过大模型从打印表格里“抄写”，而是由上一步代码按
          `__HANDOFF__` 协议打印 → 本流程解析后直接写入沙箱变量（每次请求唯一命名），
          后续步骤代码在运行时从该变量取值（数值全程不经大模型转述，避免遗漏/臆造）。

    token 优化：
        compact_knowledge 非空时，第 1 步仍用完整的 knowledge（含章节/口径等大段说明），
        后续步骤改用 compact_knowledge（通常只含表结构与关联关系），
        避免每一步都重复灌入整份模板说明。技能链路不传该参数，行为保持不变。
    """
    # 1. 读取提示词 YAML 
    prompts = load_prompts(prompt_path) if prompts is None else prompts
    strict = sandbox_config is not None
    if strict and not kernel_id:
        try:
            kernel_id = await asyncio.to_thread(resolve_kernel_id, sandbox_config["url"], sandbox_config.get("token", ""))
        except Exception:
            raise SandboxExecutionError("沙箱内核连接失败，请检查 URL、Token 和服务状态", "connection") from None
    
    yield {"status": "log", "message": "⏳ 正在分析需求并拆解任务步骤..."}
    
    # 2. 任务拆分
    task_info_str = await asyncio.to_thread(split_task, query, prompts, knowledge, task_cfg)
    
    # 尝试解析 JSON 数组
    tasks = []
    try:
        # 提取 JSON 数组部分
        match = re.search(r'\[.*\]', task_info_str, re.DOTALL)
        if match:
            tasks = json.loads(match.group(0))
        else:
            tasks = [task_info_str]
    except Exception:
        tasks = [task_info_str]
        
    # 限制最多 8 步：复杂报表可能确实需要多段取数，但也要防止模型把简单需求拆碎
    max_steps = 8
    if isinstance(tasks, list):
        tasks = tasks[:max_steps]
    else:
        tasks = [str(tasks)][:max_steps]
        
    yield {"status": "log", "message": f"✅ 任务拆解完成，共划分为 {len(tasks)} 步。开始依次独立执行："}
        
    execution_results = []
    # —— 跨步骤衔接状态 ——
    # handoff_params：上一步代码按 __HANDOFF__ 协议打印、被解析后的结构化参数；
    #                 会写入沙箱变量（每次请求使用唯一命名，避免与其他请求/会话串数据）。
    handoff_params: Dict[str, Any] = {}
    handoff_var = "_HANDOFF_" + uuid.uuid4().hex[:10]  # 本次请求专用的衔接参数字典变量名
    total_steps = len(tasks)

    # 3 & 4. 循环编排并执行代码
    for i, task in enumerate(tasks):
        step_num = i + 1
        has_next = step_num < total_steps
        yield {"status": "log", "message": f"\n▶️ **正在执行第 {step_num} 步**: {task}"}

        # —— 组装本步代码生成上下文 ——
        ctx_lines = [f"【用户原始请求】: {query}\n"]

        if step_num > 1 and handoff_params:
            # 只给参数键与结构供理解，明确要求运行时从沙箱变量读取，
            # 禁止把具体数值抄进代码或从打印表格中人工摘取（防遗漏/防臆造）。
            ctx_lines.append(
                "【上一步落盘的衔接参数】\n"
                f"上一步执行后，其 __HANDOFF__ 参数已写入沙箱变量 `{handoff_var}`（Python dict）。\n"
                f"{handoff_var} 内容（仅示意键与结构，切勿把其中的具体数值抄进代码）："
                f"{json.dumps(handoff_params, ensure_ascii=False)}\n"
                "如本步需要上一步的数据（如记录 ID 列表），请在代码中直接运行时读取，例如：\n"
                f"ids = {handoff_var}['<键名>']\n"
                "严禁再从任何打印出来的结果表格文本中摘抄数值作为本步条件。\n"
            )

        ctx_lines.append(f"当前执行步骤 ({step_num}/{total_steps}): {task}\n")

        if has_next:
            # 只要不是最后一步，就要求按协议把后续步骤需要的参数“打印”出来，
            # 由流程落盘给下一步，而不是靠下一步模型去读上一步的大表格。
            ctx_lines.append(
                "【本步输出协议】本步之后还有后续步骤：若本步产生了后续步骤需要复用的关键结果\n"
                "（例如从明细中筛选出的记录 ID 列表、查询范围等），请在代码最后追加打印一行协议：\n"
                "print('__HANDOFF__' + json.dumps({'含义清晰的名字(如 contract_ids)': 结果值}))\n"
                "要求：参数必须是 JSON 可序列化的简单对象（int/str/其列表等），不要放入 DataFrame/Decimal；"
                "不要为了让后续步骤‘看到数据’而打印整张结果大表。\n"
            )
        else:
            # 最后一步没有“下游”，重点是把最终数据用纯文本交给后台，供总结模型使用
            ctx_lines.append(
                "【本步为最后一步】无需打印 __HANDOFF__。\n"
                "本步的结果数据必须用 print 输出为纯文本（如 print(df.to_string(index=False))"
                " 或逐行 print），供最终总结直接使用；不要只依赖 display()/图表等富文本而不输出文本。\n"
            )

        current_task_context = "\n".join(ctx_lines)

        # 第 1 步用完整知识（章节/口径/表结构）；后续步骤用精简上下文，减少重复 token
        step_knowledge = knowledge if step_num == 1 or not compact_knowledge else compact_knowledge

        yield {"status": "log", "message": f"   - 🤖 正在思考并生成处理代码..."}
        code = await asyncio.to_thread(generate_code, current_task_context, prompts, step_knowledge, execut_cfg)
        
        # 执行重试分两类：代码报错走 AI 修复，沙箱连接抖动走重连，次数互不占用，
        # 避免一次断线就把修复机会用光。
        max_attempts = 3    # 执行总次数：首次 + 最多 2 次 AI 修复
        max_reconnects = 2  # 连接/超时后的重连次数上限
        attempt = 0
        reconnects = 0
        while attempt < max_attempts:
            # 去除 Markdown 标记
            if code.startswith("```python"):
                code = code[9:]
            elif code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
            code = code.strip()

            yield {"status": "log", "message": f"   - ⚙️ 正在沙箱中独立执行代码 (尝试 {attempt + 1}/{max_attempts})..."}
            # 代码执行
            execution_failed = False
            try:
                # 沙箱已预置 get_connection：生成代码若重新定义/占位实现，会覆盖注入函数，
                # 导致连接为 None 并在执行时报 "'NoneType' object has no attribute 'cursor'"。
                # 这里在执行前拦截并直接进入 AI 修复流程。
                if strict and _defines_get_connection(code):
                    raise SandboxExecutionError(
                        "生成代码中定义了 get_connection()。该函数由沙箱预置，"
                        "禁止重新定义或写占位实现，请直接调用 get_connection()。",
                        kind="execution",
                    )
                execution_code = code
                if strict:
                    # 每步使用独立命名空间；衔接数据显式传入，不污染共享内核或其他对话。
                    execution_code = (
                        f"exec({code!r}, {{'get_connection': globals().get('get_connection'), "
                        f"{handoff_var!r}: {handoff_params!r}}})"
                    )
                res = await asyncio.to_thread(sandbox_executor or execute_in_sandbox, execution_code, sandbox_config, kernel_id, strict=strict)
            except SandboxExecutionError as error:
                # 连接/超时说明沙箱抖动，与代码本身无关：换内核重连，不触发 AI 改代码
                if error.kind in {"connection", "timeout"} and reconnects < max_reconnects:
                    reconnects += 1
                    yield {"status": "log", "message": f"   - 🔌 沙箱连接异常，正在重新连接内核后重试 ({reconnects}/{max_reconnects})..."}
                    kernel_id = None  # 下一次执行重新解析可用内核
                    await asyncio.sleep(1.0 * reconnects)
                    continue
                if error.kind != "execution" or attempt == max_attempts - 1:
                    raise
                execution_failed = True
                res = f"Error: {error}"

            # 没有打印任何内容时不能算成功：后续步骤和总结都依赖这里的文本数据。
            # 抛给下面的修复逻辑，让模型补上 print 后重新执行。
            if not execution_failed and res.strip() in {"", EMPTY_OUTPUT_MARK}:
                execution_failed = True
                res = "【无输出】代码执行完成，但没有产生任何控制台输出，本步数据无法传递给后续步骤和总结。"
            
            # 判断是否报错：strict 模式下沙箱异常通常以 error 帧抛出，
            # 但生成代码常用 try/except 把异常 print 成 "Error: ..." 或完整 Traceback，
            # 这类输出同样必须判为失败，否则会被误当作执行成功直接进入总结。
            runtime_error = bool(
                "Traceback (most recent call last)" in res
                or "Error during execution" in res
                or "Error executing query" in res
                or re.search(r"(?m)^\s*(?:Error|Exception)\s*[:：]", res)
            )
            # 衔接参数里出现空列表/空字典，说明本步查询没命中：若直接放行，
            # 后续步骤只会输出“No products found”之类的空结果，最终把“没查到”
            # 误报成“业务上没有数据”。这里识别为失败并触发一次匹配修正。
            step_handoff = _extract_handoff(res)
            if has_next and not execution_failed and _has_empty_branch(step_handoff):
                execution_failed = True
                res = (
                    "【衔接参数为空】本步输出给后续步骤的 __HANDOFF__ 参数中存在空列表/空字典："
                    f"{json.dumps(step_handoff, ensure_ascii=False)}。"
                    "说明查询没有命中数据，请确认用户给的编码/名称与数据库中的真实值是否一致"
                    "（商品编码、商品名称、规格型号等），必要时先用 LIKE 模糊探查再精确查询。"
                )

            if execution_failed or runtime_error:
                if attempt < max_attempts - 1:
                    yield {"status": "log", "message": f"   - ⚠️ 发现执行报错，正在触发 AI 自我修复机制..."}
                    # 报错，发起自我修复请求
                    fix_prompt = (
                        f"你生成的 Python 代码在沙箱中执行时发生了报错。\n"
                        f"【原始任务】: {task}\n"
                        f"【你的代码】:\n```python\n{code}\n```\n"
                        f"【执行报错】:\n{res}\n\n"
                        f"请仔细分析报错原因并修复代码。注意：\n"
                        f"1. 如果是 SQL 语法或字段找不到错误，请检查 JOIN 条件、表别名或使用的数据表字段名是否正确。\n"
                        f"2. 如果是 Pandas 数据处理报错，请检查 DataFrame 的类型或缺失值。\n"
                        f"3. 如果是 __HANDOFF__ 打印报错（如 json 序列化失败），请只放入可 JSON 序列化的简单参数"
                        f"（int/float/str/列表），并把 DataFrame 等对象排除在外。\n"
                        f"4. 如果报错涉及 decimal.Decimal 与 float 混算（unsupported operand type(s) for /、+、-、*），"
                        f"说明 MySQL 的 DECIMAL 列或 SUM/AVG 聚合结果返回的是 Decimal，"
                        f"必须在参与除法、百分比等运算前转成 float：单值用 float(x)；"
                        f"pandas 整列用 df[col] = df[col].astype(float) 或 "
                        f"df = df.apply(pd.to_numeric, errors='coerce') 后再运算，"
                        f"不要在未转换的 Series 上直接做算术；round() 之后也要 float() 才能 json.dumps。\n"
                        f"5. 如果提示“无输出”，说明代码执行完没有 print 任何内容。请补上 print(...)，"
                        f"把本步结果（如 df.to_string(index=False) 或关键数值）以纯文本打印出来，"
                        f"否则后续步骤和最终总结拿不到数据。\n"
                        f"6. 如果报错提到“定义了 get_connection()”或 "
                        f"'NoneType' object has no attribute 'cursor'，说明你在代码里"
                        f"自己定义或占位实现了 get_connection。该函数由沙箱预置，"
                        f"必须删掉你的 def get_connection，直接调用 get_connection()，"
                        f"也不要给 get_connection 赋值。\n"
                        f"7. 如果提示“衔接参数为空”，说明本步 SQL 条件没匹配到数据：用户给的编号/名称"
                        f"可能只是规格或名称片段，与库里的商品编码并不一致。请先用 LIKE 对商品编码、"
                        f"商品名称、规格型号等字段做模糊探查，确认数据库里真实存在的值后再精确查询，"
                        f"并确保 __HANDOFF__ 里传入的是真实命中的非空结果，不要直接输出空列表。\n"
                        f"请输出修复后的纯 Python 代码内容，不要包含任何 Markdown 标记（如 ```python 等）。"
                    )
                    repair_system = "你是一个精通Python和数据处理的AI修复助手。请只输出纯Python代码。"
                    if strict:
                        # 修复时仍使用当前步骤的真实表结构和沙箱访问约定。
                        repair_system = f"{step_knowledge}\n\n{prompts.get('execute_code', {}).get('system', '')}\n\n{repair_system}"
                    messages = [
                        {"role": "system", "content": repair_system},
                        {"role": "user", "content": fix_prompt}
                    ]
                    # 调用 LLM 修复
                    code = await asyncio.to_thread(_call_llm, messages, execut_cfg or yaml_config.get("model_settings", {}).get("ai_process", {}).get("execute_llm", {}))
                    attempt += 1
                    continue
                else:
                    yield {"status": "log", "message": f"   - ❌ 修复重试耗尽，该步执行抛出异常。"}
                    # 重试耗尽，保留报错结果
                    res = f"【执行多次仍报错，请检查规则或数据】\n{res}"
            else:
                if attempt == 0:
                    yield {"status": "log", "message": f"   - ✅ 代码执行成功！"}
                else:
                    yield {"status": "log", "message": f"   - ✅ 自动修复后执行成功！"}
            
            # 执行成功或重试耗尽，跳出重试循环
            break
        
        # —— 解析本步输出的 __HANDOFF__ 参数并落盘到沙箱变量 ——
        step_handoff = _extract_handoff(res)
        if step_handoff:
            # 直接向沙箱写入赋值语句完成持久化：数值原样进入内核，不经过大模型转抄。
            if not strict:
                await asyncio.to_thread(
                    execute_in_sandbox, f"{handoff_var} = " + repr(step_handoff), sandbox_config, kernel_id
                )
            handoff_params.update(step_handoff)

        # 剔除 __HANDOFF__ 协议行，避免把衔接噪音带进“步骤记录/最终总结”
        display_res = "\n".join(
            line for line in res.splitlines() if not line.strip().startswith("__HANDOFF__")
        )
        # 把本步在沙箱中的真实执行结果作为日志帧下发，
        # 前端展开执行过程时可直接看到每一步的代码产出与数据结果。
        yield {"status": "log", "message": (
            f"   - 📊 第 {step_num} 步执行结果：\n"
            f"```text\n{display_res}\n```"
        )}
        step_record = f"### 步骤 {step_num}: {task}\n**执行代码**:\n```python\n{code}\n```\n**执行结果**:\n```text\n{display_res}\n```\n"
        execution_results.append(step_record)
        
    final_execution_result = "\n".join(execution_results)
    
    yield {
        "status": "done",
        "query": query,
        "knowledge": knowledge,
        "task_info": task_info_str,
        "code": "多步执行，详见 execution_result",
        "execution_result": final_execution_result
    }
