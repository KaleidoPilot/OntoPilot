import json
import uuid
import websocket
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger

from utils.skill_resolver import SkillResolver

FONT_RULE = (
    "\nFONT RULE (MANDATORY): The sandbox has already been configured with CJK-compatible fonts "
    "at session startup. Chinese, English, Japanese, Korean, and all languages render correctly by default. "
    "You MUST NOT set or configure any font in your code. Specifically:\n"
    "- Do NOT call configure_fonts_for_text() or any custom font function.\n"
    "- Do NOT modify plt.rcParams['font.family'], plt.rcParams['font.sans-serif'], "
    "or any font-related rcParams.\n"
    "- Do NOT import or register font files (ttf/otf).\n"
    "- Do NOT use FontProperties or font_manager.\n"
    "- Do NOT set plt.rcParams['axes.unicode_minus'] — it is already configured.\n"
    "- Just use matplotlib/seaborn/plotly directly — all languages display correctly.\n"
)

FONT_INIT_CODE = '''
import matplotlib.font_manager as fm
import matplotlib
import os

font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
if os.path.exists(font_path):
    try:
        font_prop = fm.FontProperties(fname=font_path)
        font_name = font_prop.get_name()
        if hasattr(fm.fontManager, 'addfont'):
            fm.fontManager.addfont(font_path)
        else:
            if hasattr(fm, '_rebuild'):
                fm._rebuild()
        current_sans = matplotlib.rcParams.get('font.sans-serif', [])
        if font_name not in current_sans:
            matplotlib.rcParams['font.sans-serif'] = [font_name] + list(current_sans)
        matplotlib.rcParams['axes.unicode_minus'] = False
        print(f"Font init OK: {font_name}")
    except Exception as e:
        matplotlib.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'DejaVu Sans']
        matplotlib.rcParams['axes.unicode_minus'] = False
        print(f"Font init fallback: {e}")
else:
    print("Font file not found, using defaults")
'''.strip()

FONT_GUARD_CODE = (
    "import matplotlib as _mpl_fg\n"
    "_fg_sans = _mpl_fg.rcParams.get('font.sans-serif', [])\n"
    "if not any('Noto' in str(_f) for _f in _fg_sans):\n"
    "    _mpl_fg.rcParams['font.sans-serif'] = "
    "['Noto Sans CJK SC'] + list(_fg_sans)\n"
    "    _mpl_fg.rcParams['axes.unicode_minus'] = False\n"
)

FONT_RULE_SHORT = (
    "\nFONT RULE: Sandbox fonts are pre-configured. "
    "Do NOT set any font-related rcParams, FontProperties, or font imports.\n"
)


class KernelClient:
    """
    Jupyter Kernel 客户端，用于通过 WebSocket 连接 Kernel 并执行代码。
    """
    def __init__(self, base_url: str, kernel_id: str, token: str | None = None):
        """
        初始化 Kernel 客户端。
        
        :param base_url: Jupyter Server 的基础 URL
        :param kernel_id: 要连接的 Kernel ID
        :param token: 认证 Token（可选）
        """
        self.base_url = base_url.rstrip("/")
        self.kernel_id = kernel_id
        self.token = token
        self.ws: websocket.WebSocket | None = None
        self.session_id = uuid.uuid4().hex

    def connect(self) -> None:
        """
        建立与 Jupyter Kernel 的 WebSocket 连接。
        """
        ws_scheme = "wss" if self.base_url.startswith("https") else "ws"
        host_part = self.base_url.split("://")[-1]
        
        ws_url = f"{ws_scheme}://{host_part}/api/kernels/{self.kernel_id}/channels"
        
        headers = [f"Origin: {self.base_url}"]
        if self.token:
            headers.append(f"Authorization: token {self.token}")
            
        logger.info(f"🔌 连接 Kernel: {ws_url}")
        try:
            # 设置 timeout 防止握手阶段无限阻塞
            self.ws = websocket.create_connection(ws_url, header=headers, timeout=10)
            # 设置后续 recv 的默认 timeout
            self.ws.settimeout(5)
            logger.info("🔗 WebSocket 已连接")
        except Exception as e:
            logger.error(f"❌ WebSocket 连接失败: {e}")
            raise

    def close(self) -> None:
        """
        关闭 WebSocket 连接。
        """
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
            logger.info("🧹 连接已关闭")

    def run_python(self, code: str, workdir: str | None = None, timeout_s: int = 120, max_retries: int = 3) -> str:
        """
        直接在 Python Kernel 中执行代码。
        
        :param code: 要执行的 Python 代码
        :param workdir: 执行代码时的起始工作目录（可选）
        :param timeout_s: 执行超时时间（秒）
        :param max_retries: 连接断开时的最大重试次数
        :return: 捕获的标准输出和错误信息
        """
        full_code = code
        if workdir:
            safe_workdir = workdir.replace("\\", "/").replace("'", "\\'")
            full_code = f"import os\nos.chdir('{safe_workdir}')\n{code}"

        for attempt in range(max_retries):
            try:
                if not self.ws or not self.ws.connected:
                    if attempt > 0:
                        logger.warning(f"WebSocket 未连接，尝试重连 (第 {attempt + 1}/{max_retries} 次)...")
                        self.connect()
                    elif not self.ws:
                        # 第一次调用如果未连接，尝试连接
                        logger.info("WebSocket 未连接，尝试建立连接...")
                        self.connect()

                msg_id = uuid.uuid4().hex
                msg = {
                    "header": {
                        "msg_id": msg_id,
                        "username": "client",
                        "session": self.session_id,
                        "msg_type": "execute_request",
                        "version": "5.3",
                        "date": datetime.now().isoformat()
                    },
                    "parent_header": {},
                    "metadata": {},
                    "content": {
                        "code": full_code,
                        "silent": False,
                        "store_history": True,
                        "user_expressions": {},
                        "allow_stdin": False
                    },
                    "channel": "shell"
                }

                self.ws.send(json.dumps(msg))

                deadline = time.time() + timeout_s
                full_output = []
                
                while time.time() < deadline:
                    try:
                        frame = self.ws.recv()
                        resp_msg = json.loads(frame)
                    except (websocket.WebSocketTimeoutException, TimeoutError):
                        # 正常超时，继续检查 deadline
                        continue
                    except (websocket.WebSocketException, ConnectionError) as e:
                        raise e
                    except Exception as e:
                        logger.warning(f"⚠️ 接收异常: {e}")
                        break

                    if resp_msg.get('channel') != 'iopub':
                        continue
                        
                    if resp_msg.get('parent_header', {}).get('msg_id') != msg_id:
                        continue

                    msg_type = resp_msg['msg_type']
                    content = resp_msg['content']

                    if msg_type == 'stream':
                        full_output.append(content['text'])
                    elif msg_type == 'execute_result':
                        full_output.append(content['data'].get('text/plain', '') + "\n")
                    elif msg_type == 'error':
                        full_output.append(f"❌ Error: {content['evalue']}\n" + "\n".join(content.get('traceback', [])) + "\n")
                    elif msg_type == 'status':
                        if content['execution_state'] == 'idle':
                            break
                else:
                    full_output.append("\n[Timeout]")

                return "".join(full_output).strip()

            except (websocket.WebSocketException, ConnectionError, OSError) as e:
                logger.warning(f"WebSocket 通信失败 (第 {attempt + 1}/{max_retries} 次): {e}")
                self.close()
                if attempt == max_retries - 1:
                    logger.error("重试次数耗尽，放弃执行。")
                    raise
                time.sleep(1)
        
        return ""


class ExecutionMixin:
    """
    执行模块 Mixin：负责代码生成与沙箱执行。
    依赖主类提供: self.sandbox_url, self.sandbox_token, self.sandbox_kernel_id,
                  self.skills, self._get_skill_content(), self._call_llm(), self.workspace_root
    """

    _FONT_STRIP_PATTERNS = [
        r"rcParams\s*\[\s*['\"]font\.",
        r"rcParams\s*\[\s*['\"]axes\.unicode_minus",
        r"FontProperties\s*\(",
        r"fontManager\s*\.\s*addfont",
        r"fm\s*\.\s*_rebuild",
        r"configure_fonts",
        r"set_fontproperties\s*\(",
        r"font_manager\.findSystemFonts",
        r"\.rcdefaults\s*\(",
        r"plt\.style\.use\s*\(",
        r"matplotlib\.style\.use\s*\(",
    ]
    _SUMMARY_STEP_PATTERNS = [
        r"(综合|汇总|总结|撰写|生成).*(报告|正文|完整文本|结论|建议)",
        r"(报告|总结).*(生成|输出|撰写)",
        r"(final|comprehensive|formal)\s+report",
        r"(write|generate|produce)\s+.*(report|summary|conclusion)",
    ]

    @staticmethod
    def _sanitize_generated_code(code: str) -> str:
        """Strip LLM-generated font configuration and prepend correct CJK font setup."""
        lines = code.split('\n')
        filtered = []
        skip_block = False

        for line in lines:
            stripped = line.strip()

            if skip_block:
                if ']' in stripped:
                    skip_block = False
                continue

            if stripped.startswith('#'):
                filtered.append(line)
                continue

            is_font_line = any(
                re.search(pat, line, re.IGNORECASE)
                for pat in ExecutionMixin._FONT_STRIP_PATTERNS
            )
            if is_font_line:
                if '[' in stripped and ']' not in stripped:
                    skip_block = True
                continue

            filtered.append(line)

        sanitized = '\n'.join(filtered)

        uses_plotting = any(kw in sanitized for kw in [
            'matplotlib', 'plt.', 'seaborn', 'sns.', 'plotly',
        ])
        if uses_plotting:
            sanitized = FONT_GUARD_CODE + sanitized

        return sanitized

    @classmethod
    def _is_summary_step(cls, step: str) -> bool:
        text = str(step or "").strip().lower()
        if not text:
            return False
        for pattern in cls._SUMMARY_STEP_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _check_should_abort(self, task: str, output: str) -> tuple:
        """
        分析执行输出，判断错误是否因数据/资源根本不存在而应中止后续所有步骤。
        与可修复的代码 bug 区分开来。
        返回 (should_abort: bool, reason: str)
        """
        system_prompt = (
            "You are an error analysis assistant. Determine if the execution error indicates "
            "the target DATA or RESOURCE fundamentally DOES NOT EXIST.\n\n"
            "Examples of data-not-found (should ABORT):\n"
            "- HTTP 404/403 when downloading a file or accessing a URL\n"
            "- File/URL not accessible, server unreachable, connection refused\n"
            "- Dataset is completely empty or missing after download\n"
            "- API returns 'not found' / 'no data' / 'does not exist'\n"
            "- Downloaded file has no valid content or is corrupted\n"
            "- The user-provided data source simply does not exist\n\n"
            "Examples of code bugs (should NOT abort, can be fixed):\n"
            "- SyntaxError, NameError, ImportError, TypeError\n"
            "- Wrong variable names, missing imports, logic errors\n"
            "- Library/module issues, version incompatibilities\n"
            "- Code-level path typos in generated code\n"
            "- KeyError/IndexError during data processing\n\n"
            "Respond ONLY with valid JSON:\n"
            "If data/resource doesn't exist: {\"abort\": true, \"reason\": \"简要中文说明\"}\n"
            "If it's a fixable code bug: {\"abort\": false, \"reason\": \"\"}"
        )

        truncated_output = output[-2000:] if len(output) > 2000 else output
        user_prompt = f"Task: {task}\n\nExecution Output:\n{truncated_output}"

        response = self._call_llm("arrang_llm", system_prompt, user_prompt)

        try:
            json_match = re.search(r'\{.*?\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if result.get("abort"):
                    return True, result.get("reason", "数据或资源不存在")
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        return False, ""

    @staticmethod
    def _is_core_data(output: str, step_index: int, task: str) -> bool:
        """判断输出是否为核心数据（需要永久保留）"""
        # 前3步的数据加载优先级最高
        if step_index < 3:
            load_keywords = ['读取', '加载', 'read', 'load', 'parse', '解析', '下载', 'download']
            if any(kw in task.lower() for kw in load_keywords):
                return True

        # 检查是否包含大量结构化数据
        structure_indicators = [
            'DataFrame', 'shape:', 'columns:', 'dtypes:',
            '行数', '列数', '数据类型', 'Index:', 'RangeIndex'
        ]
        structure_count = sum(1 for ind in structure_indicators if ind in output)

        # 至少包含3个结构化数据指标，且长度>1000字符
        if structure_count >= 3 and len(output) > 1000:
            return True

        return False

    def _inject_file_chunked(self, client, local_path, remote_rel_path: str, sandbox_dir: str) -> bool:
        """
        分块注入文件到沙箱，避免大文件导致 WebSocket 阻塞或卡死。
        使用 Base64 传输以支持二进制文件。
        """
        import base64
        try:
            with open(local_path, "rb") as f:
                file_bytes = f.read()
            
            b64_data = base64.b64encode(file_bytes).decode('ascii')
            total_size = len(b64_data)
            chunk_size = 50 * 1024  # 50KB per chunk
            
            logger.info(f"Injecting file {remote_rel_path} ({len(file_bytes)} bytes) in {total_size // chunk_size + 1} chunks...")

            # 1. Prepare directory and clear existing file
            setup_cmd = (
                f"import os\n"
                f"p = '{remote_rel_path}'\n"
                f"os.makedirs(os.path.dirname(p), exist_ok=True)\n"
                f"if os.path.exists(p): os.remove(p)"
            )
            client.run_python(setup_cmd, workdir=sandbox_dir, timeout_s=15)
            
            # 2. Send chunks
            for i in range(0, total_size, chunk_size):
                chunk = b64_data[i : i + chunk_size]
                write_cmd = (
                    f"import base64\n"
                    f"with open('{remote_rel_path}', 'ab') as f:\n"
                    f"    f.write(base64.b64decode('{chunk}'))"
                )
                # Short timeout for small chunks
                output = client.run_python(write_cmd, workdir=sandbox_dir, timeout_s=15)
                if "Error" in output:
                    logger.error(f"Chunk upload failed: {output}")
                    return False
                    
            return True
        except Exception as e:
            logger.error(f"Failed to inject file chunked {local_path}: {e}")
            return False

    def execute_tasks(self, tasks: List[str], task_id: str, file_url: str = None, selected_skills: Optional[List[str]] = None, user_wants_chart: bool = False, user_wants_file: bool = False, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        使用技能 LLM 为每个子任务生成代码，并在沙箱环境中执行。

        :param tasks: 任务步骤列表
        :param task_id: 本次会话的唯一标识符
        :param file_url: 用户提供的文件URL（可选），如果提供则自动下载到沙箱
        :param selected_skills: 选中的技能列表
        :param user_wants_chart: 用户是否明确要求生成图表
        :param user_wants_file: 用户是否明确要求生成文件
        :param user_id: 用户ID（可选），用于区分工作空间
        :return: 包含每一步执行结果的列表
        """
        results = []
        client = KernelClient(self.sandbox_url, self.sandbox_kernel_id, self.sandbox_token)
        
        try:
            logger.info(f"Starting task execution session: {task_id}, User: {user_id}")
            client.connect()
#- 清空 Kernel 全局变量（保留 Python 必要内建），再继续本次任务流程。- 这样可以强制每次从“干净上下文”开始，避免串用上一次文件数据。
            reset_session_code = """
_keep = {"__name__", "__doc__", "__package__", "__loader__", "__spec__", "__builtins__"}
for _k in list(globals().keys()):
    if _k not in _keep:
        globals().pop(_k, None)
print("Kernel session reset")
""".strip()
            reset_output = client.run_python(reset_session_code, timeout_s=30)
            logger.info(f"Session reset: {reset_output}")
            
            # 使用用户特定的沙箱目录
            sandbox_user_dir = user_id if user_id else "default_user"
            sandbox_dir = f"/workspace/{sandbox_user_dir}/tasks/{task_id}"
            logger.info(f"Creating sandbox directory + font init: {sandbox_dir}")
            init_code = f"import os; os.makedirs('{sandbox_dir}', exist_ok=True)\n{FONT_INIT_CODE}"
            font_output = client.run_python(init_code)
            logger.info(f"Sandbox init: {font_output}")

            # 如果提供了文件URL，自动下载到沙箱目录
            downloaded_filename = None
            if file_url:
                logger.info(f"Downloading file from URL: {file_url}")
                # 从URL提取文件名
                import urllib.parse
                parsed_url = urllib.parse.urlparse(file_url)
                filename = parsed_url.path.split('/')[-1]
                if not filename or '.' not in filename:
                    # 如果无法从URL提取文件名，尝试从Content-Disposition获取
                    filename = "user_file.xlsx"  # 默认文件名

                # 使用字符串拼接避免 f-string 中的引号冲突
                download_code = """
import requests
import os
import re

url = '""" + file_url + """'
filename = '""" + filename + """'
filepath = os.path.join('""" + sandbox_dir + """', filename)

try:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    # 尝试从响应头获取文件名
    if 'content-disposition' in response.headers:
        cd = response.headers['content-disposition']
        fname_match = re.search(r'filename[^;=\\n]*=(([\\'\"]).*?\\2|[^;\\n]*)', cd)
        if fname_match:
            extracted_name = fname_match.group(1).strip('\\"\\' ')
            if extracted_name:
                filename = extracted_name
                filepath = os.path.join('""" + sandbox_dir + """', filename)

    with open(filepath, 'wb') as f:
        f.write(response.content)

    print(f"File downloaded successfully: {filename} ({len(response.content)} bytes)")
    print(f"File path: {filepath}")
except Exception as e:
    print(f"Download failed: {e}")
"""
                download_output = client.run_python(download_code, workdir=sandbox_dir, timeout_s=60)
                logger.info(f"File download result: {download_output}")

                # 从输出中提取文件名
                if "File downloaded successfully:" in download_output:
                    match = re.search(r"File downloaded successfully: (.+?) \(", download_output)
                    if match:
                        downloaded_filename = match.group(1)
                        logger.info(f"Downloaded file: {downloaded_filename}")

            logger.info(f"Total tasks to execute: {len(tasks)}")

            # 初始化 SkillResolver
            resolver = SkillResolver(self.skill_dir, self.skills)
            resolved_step_skills = resolver.resolve_selected_skills(selected_skills or [], user_wants_chart=user_wants_chart)
            if selected_skills:
                logger.info(f"Selected skills from arrangement: {selected_skills}")

            # skill_descriptions 不再注入 gen_system_prompt，step_skill_ref 已按步匹配

            # 动态图表指令（严格遵循用户意图或模板要求）
            if user_wants_chart:
                chart_instruction = (
                    "✅ VISUALIZATION ENABLED (User explicitly requested or Template requires it):\n"
                    "1. Generate charts as requested using ECharts option JSON (NOT image files).\n"
                    "2. NO ID/INDEX PLOTS: NEVER chart 'ID', 'No', 'Serial', 'Index', 'UUID', 'Name' or unique identifiers.\n"
                    "3. AGGREGATE BEFORE PLOTTING: For large datasets, always aggregate (count/mean/sum) before plotting.\n"
                    "4. TOP N CATEGORIES: If a categorical column has > 20 unique values, only plot Top 20 and group others as 'Others'.\n"
                    "5. DO NOT save charts as PNG/JPG/SVG.\n"
                    "6. For each chart, print exact markers in stdout:\n"
                    "   ECHART_OPTION_BEGIN\n"
                    "   {valid ECharts option JSON object}\n"
                    "   ECHART_OPTION_END\n"
                    "7. You may print multiple chart blocks if needed.\n"
                )
            else:
                chart_instruction = (
                    "🚫 VISUALIZATION STRICTLY FORBIDDEN:\n"
                    "- User and Template did NOT request charts, plots, or visualizations\n"
                    "- Do NOT import matplotlib, seaborn, plotly, or any plotting libraries\n"
                    "- Do NOT call plt.*, sns.*, go.Figure(), or any plotting functions\n"
                    "- Do NOT save any .png, .jpg, .svg image files\n"
                    "- Focus ONLY on data analysis and content extraction, print results to stdout\n"
                    "- If you generate ANY chart code, it will be considered a VIOLATION\n"
                )

            gen_system_prompt = (
                "🎯 PRIMARY RULE: When previous steps already extracted data, you MUST analyze it directly. "
                "DO NOT generate code to reload data that already exists in context.\n\n"
                "You are a versatile execution agent. You can either write Python code OR provide a direct text answer.\n\n"
                "🎯 DECISION CRITERIA (CRITICAL - READ CAREFULLY):\n"
                "1. DIRECT ANSWER (STRONGLY PREFERRED): Use direct text answer for:\n"
                "   - General questions, explanations, clarifications\n"
                "   - Qualitative analysis, reasoning, interpretation\n"
                "   - Summarizing or describing concepts\n"
                "   - Tasks that don't involve actual data processing\n"
                "   - When no file/data is provided and task doesn't require computation\n"
                "   - 🔥 MOST IMPORTANT: When previous steps already extracted data, analyze it directly!\n"
                "   DO NOT generate code for these cases!\n\n"
                "2. PYTHON CODE (ONLY WHEN NECESSARY): Use code ONLY for:\n"
                "   - Reading/parsing files for the FIRST time (Excel, CSV, JSON, etc.)\n"
                "   - Data analysis requiring NEW calculations not visible in existing data\n"
                "   - Data transformation, filtering, grouping on NEW data\n"
                "   - Generating charts/visualizations (ONLY if user explicitly requested)\n"
                "   - File operations (upload, download, format conversion)\n"
                "   - API calls or external system interactions\n\n"
                "3. NO PRINT-ONLY CODE: NEVER generate Python code that just prints hardcoded text. If the task is qualitative or data is missing, provide a DIRECT TEXT ANSWER.\n\n"
                "4. 🚨 NO REDUNDANT DATA LOADING: If data was already loaded in previous steps and is shown in context, DO NOT write code to reload it. Use your reasoning to analyze the existing data.\n\n"
                "STRICT DATA RULES:\n"
                "1. NO FABRICATION: You must use the provided data or file content. DO NOT invent numbers, dates, or facts. If data is missing, state it clearly.\n"
                "2. SOURCE REQUIRED: Any data used must come from the input file or context. Do not hardcode random data.\n\n"
                "DATA HANDLING (if writing code):\n"
                "1. Inspect data structure first: df.columns, df.head(), df.info()\n"
                "2. Discover column names from data - never assume\n"
                "3. Use flexible matching for field names (fuzzy matching or keyword search)\n"
                "4. Print key findings to stdout\n\n"
                "TASK EXECUTION:\n"
                "- The task description is HIGH-LEVEL. You must implement ALL necessary details.\n"
                "- Handle missing values and data cleaning automatically if needed.\n\n"
                f"{chart_instruction}\n"
                "OUTPUT FORMAT:\n"
                "- For Code: Output ONLY ```python``` code blocks.\n"
                "- For Direct Answer: Output PLAIN TEXT ONLY. NO markdown formatting whatsoever — no headers (#), no bold (**), no bullet lists (- or *), no tables, no code fences, no links. Just plain continuous text, no unnecessary line breaks.\n"
                "- Implement ONLY what the task requests.\n"
                "- NO extra error handling unless required.\n"
                "- NO intermediate files (only final outputs).\n"
                "- NO reports/summaries (print to stdout instead).\n"
                f"- Work in: {sandbox_dir}\n"
                f"{FONT_RULE_SHORT}"
            )

            fix_system_prompt = (
                "Fix the failed code. Output ONLY corrected Python code in ```python``` blocks.\n"
                f"All file operations in: {sandbox_dir}\n"
                "Use alternative libraries if imports fail. Add error handling.\n"
                "STRICT RULE: Do NOT invent data or generate fake reports to fix errors. If data is missing, print a simple error message.\n"
                "NO PRINT-ONLY CODE: Do not replace failed logic with hardcoded print statements.\n"
                "NO explanations, NO comments."
                f"{FONT_RULE_SHORT}"
            )

            # Update local task directory to match workspace structure
            local_user_dir = user_id if user_id else "default_user"
            # Note: We need to resolve the path relative to the project root workspace
            project_workspace = self.workspace_root.parent
            task_dir = project_workspace / local_user_dir / "tasks" / task_id
            task_dir.mkdir(parents=True, exist_ok=True)

            execution_aborted = False

            # 滚动上下文：保留所有前序步骤的关键摘要
            rolling_context = []
            # 三层数据记忆结构
            core_data = []           # 核心数据层：永久保留关键原始数据（最多50000字符）
            recent_data = []         # 近期数据层：最近5步完整输出（最多150000字符）
            historical_summary = []  # 历史摘要层：所有步骤的简短摘要（500字符/步）

            for i, task in enumerate(tasks):
                if self._is_summary_step(task):
                    logger.info(f"Skipping summary/report task at execution layer: {task}")
                    results.append({
                        "step": i + 1,
                        "task": task,
                        "code": "<!-- Skipped Summary Step -->",
                        "output": "Skipped: summary/report generation belongs to summarize layer",
                        "sandbox_dir": sandbox_dir
                    })
                    continue

                # 二次验证：检查步骤是否违反用户意图
                task_lower = task.lower()
                
                # Check for chart keywords with regex boundary for English words
                contains_chart_zh = any(kw in task_lower for kw in [
                    "图表", "可视化", "饼图", "柱状图", "折线图", "散点图", "热力图", "趋势图", "分布图", "雷达图", "绘制", "画图", "绘图", "出图", "建图"
                ])
                contains_chart_en = any(re.search(rf'\b{re.escape(kw)}\b', task_lower) for kw in [
                    "chart", "plot", "visualization", "graph", "pie", "bar", "line", "scatter", "heatmap", "figure"
                ])
                contains_chart = contains_chart_zh or contains_chart_en
                
                # Check for file keywords with regex boundary for English words
                contains_file_zh = any(kw in task_lower for kw in [
                    "保存", "导出", "生成文件", "生成报告", "生成文档", "下载", "报告", "文档", "上传"
                ])
                contains_file_en = any(re.search(rf'\b{re.escape(kw)}\b', task_lower) for kw in [
                    "save", "export", "download", "generate file", "report", "document", "upload"
                ])
                contains_file = contains_file_zh or contains_file_en

                if contains_chart and not user_wants_chart:
                    logger.warning(f"⚠️ Skipping chart-related step (user and template did not request charts): {task}")
                    results.append({
                        "step": i + 1,
                        "task": task,
                        "code": "<!-- Skipped: Chart generation not requested by user or template -->",
                        "output": "跳过：用户和模板未要求生成图表，此步骤被执行层拦截",
                        "sandbox_dir": sandbox_dir
                    })
                    continue

                is_upload_step = ("upload" in task_lower) or ("上传" in task)
                if contains_file and not user_wants_file and not (is_upload_step and user_wants_chart):
                    logger.warning(f"⚠️ Skipping file-related step (user and template did not request files): {task}")
                    results.append({
                        "step": i + 1,
                        "task": task,
                        "code": "<!-- Skipped: File generation not requested by user or template -->",
                        "output": "跳过：用户和模板未要求生成文件，此步骤被执行层拦截",
                        "sandbox_dir": sandbox_dir
                    })
                    continue

                logger.info(f"Executing Task {i+1}: {task}")

                # 使用 SkillResolver 从已选技能中匹配当前步骤相关技能
                step_skill_ref = ""
                matched_skills = resolver.pick_step_skills(task, resolved_step_skills)
                if matched_skills:
                    step_skill_ref = resolver.build_prompt_injection(matched_skills)
                    logger.info(f"Step {i+1} matched skills: {list(matched_skills.keys())}")

                # 构建滚动上下文：保留最近3步的摘要
                compact_context = ""
                if rolling_context:
                    compact_context = "\nPrevious steps summary:\n" + "\n".join(rolling_context[-3:]) + "\n"

                # 构建包含文件信息的上下文
                file_context = ""
                has_file_data = False
                if downloaded_filename:
                    file_context = f"\nAvailable File: {downloaded_filename} (already downloaded in working directory)\n"
                    has_file_data = True

                if core_data or recent_data:
                    has_file_data = True

                if has_file_data and step_skill_ref:
                    step_skill_ref += "\n🚨 CRITICAL RULE: Real data/files are available. You MUST process the actual data. STRICTLY PROHIBITED to use any sample data, mock data, or examples from the skill references! (当有真实文件或数据时，拒绝使用技能参考中的样本数据！)\n"

                # Upload API hint 仅在上传步骤注入
                upload_hint = ""
                task_lower = task.lower()
                if "upload" in task_lower or "上传" in task_lower:
                    upload_hint = (
                        "\nUpload API: POST http://emplat.fijo.com.cn/file/fileUplodNew (multipart/form-data)\n"
                        "MUST include form fields in every request: modular=AIWJ0001, tenant=AIWJ, orgCode=AIWJ.\n"
                        "MUST upload files one-by-one in a for-loop.\n"
                        "MUST parse URL safely from JSON keys: url, fileUrl, file_path, filePath, data.url, data.fileUrl, data.filePath.\n"
                        "MUST handle null/missing data safely and NEVER call .get on None.\n"
                        "CRITICAL: NEVER concatenate strings to build URLs (e.g., do not prepend domain to filenames). Use EXACTLY the URL returned in the JSON response (typically data.filePath which points to file.static.fijo.com.cn).\n"
                    )

                # 构建数据上下文：整合三层记忆
                data_context_prompt = ""
                if core_data or recent_data:
                    # 构建核心数据部分
                    core_section = ""
                    if core_data:
                        core_texts = [f"[Step {item['step']}: {item['task']}]\n{item['data']}"
                                      for item in core_data]
                        core_section = (
                            "\n━━━ CORE DATA (PERMANENT - ALWAYS AVAILABLE) ━━━\n"
                            f"{chr(10).join(core_texts)}\n"
                            "━━━ END OF CORE DATA ━━━\n"
                        )

                    # 构建近期数据部分
                    recent_section = ""
                    if recent_data:
                        recent_texts = [f"[Step {item['step']}: {item['task']}]\n{item['data']}"
                                        for item in recent_data]
                        recent_section = (
                            "\n━━━ RECENT DATA (LAST 5 STEPS) ━━━\n"
                            f"{chr(10).join(recent_texts)}\n"
                            "━━━ END OF RECENT DATA ━━━\n"
                        )

                    # 构建历史摘要部分
                    history_section = ""
                    if len(historical_summary) > 5:
                        history_section = (
                            "\n━━━ HISTORICAL SUMMARY (ALL STEPS) ━━━\n"
                            f"{chr(10).join(historical_summary)}\n"
                            "━━━ END OF SUMMARY ━━━\n"
                        )
                        

                    data_context_prompt = (
                        f"{core_section}{recent_section}{history_section}\n"
                        "🚨 CRITICAL RULE - READ CAREFULLY:\n"
                        "The above data was ALREADY extracted and processed in previous steps.\n"
                        "CORE DATA contains the original dataset - it is ALWAYS available throughout the task.\n"
                        "You MUST analyze this data directly using your reasoning capabilities.\n"
                        "DO NOT generate Python code to re-read files or re-process data.\n\n"
                        "✅ WHEN TO USE DIRECT TEXT ANSWER (STRONGLY PREFERRED):\n"
                        "- Analyzing trends, patterns, or insights from the data above\n"
                        "- Comparing values, finding max/min, calculating percentages\n"
                        "- Summarizing, interpreting, or answering questions about the data\n"
                        "- Generating reports or conclusions based on existing data\n"
                        "- ANY task that can be solved by reasoning over the data above\n\n"
                        "❌ ONLY GENERATE CODE IF:\n"
                        "- You need to read a DIFFERENT file not yet loaded\n"
                        "- You need complex statistical computations not visible in the data\n"
                        "- You need to generate charts/visualizations (and user requested them)\n"
                        "- You need to perform operations impossible with the data above\n\n"
                        "⚡ PERFORMANCE TIP: Using direct text answers is 10x faster than code execution.\n"
                    )

                # 单阶段：直接由 execution_llm 生成代码
                # 构建基础 prompt（不含数据上下文和最终指令）
                base_user_prompt = (
                    f"Task: {task}\n"
                    f"Step: {i+1}/{len(tasks)}\n"
                    f"Working Directory: {sandbox_dir}\n"
                    f"{file_context}"
                    f"{compact_context}"
                    f"{step_skill_ref}"
                    f"{upload_hint}\n"
                )

                # 动态生成最终指令：根据是否有数据记忆
                if core_data or recent_data:
                    # 有数据记忆：强制直接分析
                    final_instruction = (
                        f"{data_context_prompt}\n"
                        "🚨 MANDATORY DECISION:\n"
                        "Data shown above (especially CORE DATA) was already extracted.\n"
                        "Analyze it directly with your reasoning.\n"
                        "Provide DIRECT TEXT ANSWER unless you need: new file read, complex computation, or chart generation.\n"
                        "DO NOT write code to reload existing data.\n"
                    )
                else:
                    # 无前置数据：允许代码或直接回答
                    final_instruction = (
                        "PERFORMANCE TIP: Reuse variables from previous steps (e.g., 'df'). "
                        "Generate Python code OR direct text answer as appropriate."
                    )

                user_prompt = base_user_prompt + final_instruction

                logger.debug(f"Calling execution_llm for Task {i+1}")
                llm_response = self._call_llm("execution_llm", gen_system_prompt, user_prompt, temperature=0.3)
                
                code_match = re.search(r"```python(.*?)```", llm_response, re.DOTALL | re.IGNORECASE)
                
                if not code_match:
                    # No code block found -> Direct Text Response
                    logger.info(f"Task {i+1}: No Python code generated. Treating as direct text response.")
                    code = "<!-- No Code Execution Required -->"
                    output = llm_response
                else:
                    # Code block found -> Execute Code
                    code = code_match.group(1).strip()
                    
                    skill_usage_match = re.search(r"#\s*USE_SKILL:\s*(.*)", code, re.IGNORECASE)
                    if skill_usage_match:
                        logger.info(f"🔧 [Skill Usage Detected] {skill_usage_match.group(1).strip()}")

                    task_lower = task.lower()
                    upload_related = ("上传" in task) or ("upload" in task_lower)
                    if upload_related:
                        # 动态检查：如果没有生成新文件，则跳过上传
                        # 注意：需要转义花括号以适应f-string
                        check_files_code = f"""
import os
try:
    all_files = os.listdir('{sandbox_dir}')
except:
    all_files = []
input_file = '{downloaded_filename}' if '{downloaded_filename}' != 'None' else None
new_files = [f for f in all_files if f != input_file and not f.startswith('.')]
print(f"NEW_FILES: {{len(new_files)}}")
"""
                        check_output = client.run_python(check_files_code, workdir=sandbox_dir)
                        if "NEW_FILES: 0" in check_output:
                            logger.info("⚠️ [Upload Skipped] No new files generated in sandbox to upload.")
                            results.append({
                                "step": i + 1,
                                "task": task,
                                "code": "<!-- Skipped: No files generated -->",
                                "output": "跳过：未生成任何新文件，无需执行上传。",
                                "sandbox_dir": sandbox_dir
                            })
                            continue

                        missing_real_upload_call = ("requests.post" not in code) or ("fileUplodNew" not in code)
                        suspicious_url_concat = ("http://emplat.fijo.com.cn/file/" in code and "fileUplodNew" not in code)
                        missing_form_fields = any(field not in code for field in ["modular", "tenant", "orgCode"])
                        if missing_real_upload_call or suspicious_url_concat or missing_form_fields:
                            enforce_prompt = (
                                "Regenerate code for real API upload. NO URL concatenation (do not prepend domain to filenames).\n"
                                "POST to http://emplat.fijo.com.cn/file/fileUplodNew\n"
                                "Form fields: modular=AIWJ0001, tenant=AIWJ, orgCode=AIWJ\n"
                                "Use multipart/form-data with file stream. Loop for multiple files.\n"
                                "Parse URL from response JSON only (e.g. data.filePath which is on file.static.fijo.com.cn).\n"
                                "Handle response JSON safely when data is null or missing.\n"
                                "Never call .get on None.\n"
                                "Use fallback keys: url, fileUrl, file_path, filePath, data.url, data.fileUrl, data.filePath.\n"
                                "Output ONLY Python code."
                            )
                            enforce_input = (
                                f"Task: {task}\n\nPrevious code:\n{code}\n\n"
                                f"Target Directory: {sandbox_dir}\n\n"
                                "Do not reference any upload skill; follow endpoint requirements directly."
                            )
                            enforce_response = self._call_llm("execution_llm", enforce_prompt, enforce_input, temperature=0.3)
                            enforce_match = re.search(r"```python(.*?)```", enforce_response, re.DOTALL)
                            if enforce_match:
                                code = enforce_match.group(1).strip()
                            else:
                                code = enforce_response.replace("```", "").strip()
                    
                    code = self._sanitize_generated_code(code)
                    logger.debug(f"Generated Code for Task {i+1}:\n{code}")
                    
                    output = client.run_python(code, workdir=sandbox_dir)

                    if upload_related and ("NoneType" in output and "get" in output):
                        upload_fix_prompt = (
                            "The upload code failed because response JSON contains null fields.\n"
                            "Regenerate robust upload code with null-safe parsing.\n"
                            "Requirements:\n"
                            "- Keep endpoint: http://emplat.fijo.com.cn/file/fileUplodNew\n"
                            "- Include form fields modular=AIWJ0001, tenant=AIWJ, orgCode=AIWJ\n"
                            "- Upload files one by one in a loop\n"
                            "- Parse URL safely without calling .get on None\n"
                            "- Print each uploaded file and final URL (CRITICAL: Do not manually concatenate URLs, use exact returned URL from JSON)\n"
                            "Output ONLY Python code."
                        )
                        upload_fix_input = (
                            f"Task: {task}\n\nPrevious code:\n{code}\n\nError:\n{output}\n\n"
                            f"Target Directory: {sandbox_dir}"
                        )
                        upload_fix_response = self._call_llm("execution_llm", upload_fix_prompt, upload_fix_input, temperature=0.3)
                        upload_fix_match = re.search(r"```python(.*?)```", upload_fix_response, re.DOTALL)
                        if upload_fix_match:
                            code = upload_fix_match.group(1).strip()
                        else:
                            code = upload_fix_response.replace("```", "").strip()
                        code = self._sanitize_generated_code(code)
                        output = client.run_python(code, workdir=sandbox_dir)
                    
                    if "❌ Error" in output or "Traceback" in output:
                        should_abort, abort_reason = self._check_should_abort(task, output)
                        if should_abort:
                            logger.warning(f"⚠️ Task {i+1} 数据/资源不存在，中止后续执行: {abort_reason}")
                            results.append({
                                "step": i + 1, "task": task, "code": code, "output": output,
                                "sandbox_dir": sandbox_dir, "aborted": True, "abort_reason": abort_reason
                            })
                            execution_aborted = True
                            break
                    
                    max_fix_attempts = 3
                    for attempt in range(1, max_fix_attempts + 1):
                        if "❌ Error" not in output and "Traceback" not in output:
                            break

                        logger.warning(f"Task {i+1} failed (attempt {attempt}/{max_fix_attempts}), auto-fixing...")

                        fix_user_prompt = (
                            f"Failed code:\n```python\n{code}\n```\n\n"
                            f"Error:\n{output}\n\n"
                            f"Fix this code. Target Directory: {sandbox_dir}"
                        )

                        fix_response = self._call_llm("execution_llm", fix_system_prompt, fix_user_prompt, temperature=0.3)

                        fix_code_match = re.search(r"```python(.*?)```", fix_response, re.DOTALL)
                        if fix_code_match:
                            code = fix_code_match.group(1).strip()
                        else:
                            code = fix_response.replace("```", "").strip()

                        code = self._sanitize_generated_code(code)
                        logger.info(f"Fix attempt {attempt} for Task {i+1}:\n{code}")
                        output = client.run_python(code, workdir=sandbox_dir)
                    else:
                        if "❌ Error" in output or "Traceback" in output:
                            should_abort, abort_reason = self._check_should_abort(task, output)
                            if should_abort:
                                logger.warning(f"⚠️ Task {i+1} 修复重试后确认数据不存在，中止执行: {abort_reason}")
                                results.append({
                                    "step": i + 1, "task": task, "code": code, "output": output,
                                    "sandbox_dir": sandbox_dir, "aborted": True, "abort_reason": abort_reason
                                })
                                execution_aborted = True
                            else:
                                logger.error(f"Task {i+1} still failing after {max_fix_attempts} fix attempts.")
                
                if execution_aborted:
                    break
                
                logger.info(f"Task {i+1} Output:\n{output}")

                # 从输出中提取可能生成的文件名，供下一步使用
                if "saved to" in output.lower() or "written to" in output.lower() or "created" in output.lower():
                    # 尝试提取文件名模式
                    file_patterns = [
                        r"saved to[:\s]+([^\s\n]+\.\w+)",
                        r"written to[:\s]+([^\s\n]+\.\w+)",
                        r"created[:\s]+([^\s\n]+\.\w+)",
                        r"file[:\s]+([^\s\n]+\.\w+)",
                    ]
                    for pattern in file_patterns:
                        match = re.search(pattern, output, re.IGNORECASE)
                        if match:
                            potential_file = match.group(1)
                            # 只保留文件名，不包含路径
                            if '/' in potential_file:
                                potential_file = potential_file.split('/')[-1]
                            if potential_file and not downloaded_filename:
                                downloaded_filename = potential_file
                                logger.info(f"Detected generated file: {downloaded_filename}")
                            break

                step_result = {
                    "step": i + 1,
                    "task": task,
                    "code": code,
                    "output": output,
                    "sandbox_dir": sandbox_dir
                }
                results.append(step_result)

                # 追加滚动摘要
                summary_output = output[:150] if len(output) > 150 else output
                rolling_context.append(f"Step {i+1} ({task}): {summary_output}")

                # 捕获有实质数据内容的输出
                if output and len(output) > 200 and code != "<!-- No Code Execution Required -->":
                    is_status_only = any(output.strip().startswith(prefix) for prefix in [
                        "File downloaded", "Font init", "Sandbox init", "跳过：", "Skipped:"
                    ])

                    has_structured_data = any(indicator in output for indicator in [
                        'DataFrame', '列名', 'columns', '行数', 'shape', '统计', 'mean', 'sum', 'count',
                        '数据', '记录', 'records', 'Total', '合计'
                    ])

                    if not is_status_only or has_structured_data:
                        # 判断是否为核心数据
                        is_core = self._is_core_data(output, i, task)

                        if is_core:
                            # 核心数据：保留更多内容（50000字符）
                            core_snippet = output[:50000] if len(output) > 50000 else output
                            core_data.append({
                                'step': i + 1,
                                'task': task,
                                'data': core_snippet,
                                'length': len(core_snippet)
                            })
                            logger.info(f"💎 Captured CORE data from Step {i+1} ({len(core_snippet)} chars)")

                            # 核心数据容量管理：最多保留50000字符
                            total_core_size = sum(item['length'] for item in core_data)
                            while total_core_size > 50000 and len(core_data) > 1:
                                removed = core_data.pop(0)
                                total_core_size -= removed['length']
                                logger.info(f"⚠️ Core data capacity exceeded, removed Step {removed['step']}")

                        # 近期数据：保留最近5步（30000字符/步）
                        recent_snippet = output[:30000] if len(output) > 30000 else output
                        recent_data.append({
                            'step': i + 1,
                            'task': task,
                            'data': recent_snippet
                        })
                        if len(recent_data) > 5:
                            recent_data.pop(0)
                        logger.info(f"📊 Captured recent data from Step {i+1} ({len(recent_snippet)} chars)")

                        # 历史摘要：所有步骤的简短摘要（500字符）
                        summary_snippet = output[:500] if len(output) > 500 else output
                        historical_summary.append(f"[Step {i+1}: {task}] {summary_snippet}")

                # 精简上下文：不再累积所有历史，只保留必要信息
                # context 变量已不再使用，移除累积逻辑

                file_path = task_dir / f"step_{i+1}.txt"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"Task: {task}\n\nSandbox Directory: {sandbox_dir}\n\nCode:\n{code}\n\nOutput:\n{output}")
                    
        except Exception as e:
            logger.error(f"Execution failed: {str(e)}")
            results.append({"error": str(e)})
        finally:
            client.close()
            logger.info(f"Task execution session {task_id} completed")
            
        return results
