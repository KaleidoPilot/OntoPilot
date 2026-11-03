from enum import Enum
from typing import Dict, Any

# 1. 状态码枚举（HTTP状态码 + 自定义业务码）
class ResponseCode(Enum):
    """统一响应码枚举"""
    # HTTP基础码
    SUCCESS = (200, "操作成功", True)
    BAD_REQUEST = (400, "请求参数错误", False)
    UNAUTHORIZED = (401, "未授权，请先登录", False)
    INTERNAL_ERROR = (500, "服务器内部错误，请稍后重试", False)
    
    # 自定义业务码（建议业务码与HTTP码区分，如4xxx开头）
    TASK_LIMIT_EXCEEDED = (40001, "任务数超过上限", False)
    TASK_TIMEOUT = (40002, "任务执行超时", False)
    TASK_TYPE_ERROR = (40003, "不支持的任务类型", False)

# 2. 全局返回结构配置
class ResponseStructure:
    """返回结构固定配置"""
    REQUIRED_FIELDS = ["code", "message", "success", "data"]
    DEFAULT_DATA = {}  # data字段默认值

# 3. 快捷获取响应模板的工具函数
def get_response_template(code: ResponseCode) -> Dict[str, Any]:
    """根据枚举值获取响应模板"""
    return {
        "code": code.value[0],
        "message": code.value[1],
        "success": code.value[2],
        "data": ResponseStructure.DEFAULT_DATA
    }
