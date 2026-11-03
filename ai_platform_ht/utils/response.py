from typing import Any, Optional
from fastapi.responses import JSONResponse
from core.response_config import ResponseCode, get_response_template, ResponseStructure

class ResponseBuilder:
    """统一返回格式构建器"""
    
    @staticmethod
    def build(
        code: ResponseCode = ResponseCode.SUCCESS,
        message: Optional[str] = None,
        data: Any = None,
        http_status_code: Optional[int] = None
    ) -> JSONResponse:
        """
        生成统一返回格式
        :param code: 响应码枚举（必填）
        :param message: 自定义提示文案（可选，覆盖枚举中的默认文案）
        :param data: 返回数据（可选）
        :param http_status_code: HTTP状态码（可选，默认使用枚举中的code）
        :return: JSONResponse
        """
        # 获取基础模板
        template = get_response_template(code)
        
        # 覆盖自定义文案
        if message:
            template["message"] = message
        
        # 设置返回数据
        template["data"] = data if data is not None else ResponseStructure.DEFAULT_DATA
        
        # 确定HTTP状态码（优先使用传入的，否则用枚举的code）
        final_http_code = http_status_code if http_status_code else code.value[0]
        # 确保HTTP状态码是合法的（1xx-5xx）
        if not (100 <= final_http_code <= 599):
            final_http_code = 200 if code == ResponseCode.SUCCESS else 500
        
        # 返回统一格式的JSON响应
        return JSONResponse(
            content=template,
            status_code=final_http_code
        )

# ========== 快捷函数（简化调用，无需记住枚举） ==========
def success(data: Any = None, message: str = None) -> JSONResponse:
    """成功返回（默认200）"""
    return ResponseBuilder.build(
        code=ResponseCode.SUCCESS,
        message=message,
        data=data
    )

def bad_request(
    code: ResponseCode = ResponseCode.BAD_REQUEST,
    message: str = None,
    data: Any = None
) -> JSONResponse:
    """客户端错误（默认400，可传自定义业务码）"""
    return ResponseBuilder.build(
        code=code,
        message=message,
        data=data,
        http_status_code=400  # 固定HTTP状态码为400，业务码在content里
    )

def server_error(message: str = None) -> JSONResponse:
    """服务器错误（默认500）"""
    return ResponseBuilder.build(
        code=ResponseCode.INTERNAL_ERROR,
        message=message,
        http_status_code=500
    )
