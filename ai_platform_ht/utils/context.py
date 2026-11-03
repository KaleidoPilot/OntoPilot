from fastapi import Request, Depends
from typing import Optional, Dict, Any
from datetime import datetime

# 模拟从 Header 或 Token 中解析当前登录用户信息
# 实际项目中这里应该解析 JWT token
def get_current_user(request: Request) -> Dict[str, Any]:
    """
    从请求中获取当前登录用户信息。
    """
    user_id = request.headers.get("x-user-id")
    user_name = request.headers.get("x-user-name")
    
    # 如果没有传递自定义 Header，尝试从 Authorization Token 中解析
    if not user_id or not user_name:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer token-"):
            parts = auth_header.split("-")
            if len(parts) >= 3:
                user_id = parts[1]
                user_name = parts[2]

    return {
        "id": int(user_id) if user_id and str(user_id).isdigit() else 1,
        "name": user_name if user_name else "admin"
    }

def fill_audit_fields(data_dict: dict, user: Dict[str, Any], is_update: bool = False):
    """
    自动填充审计字段（创建人、创建时间、更新人、更新时间）
    :param data_dict: 将要插入或更新的数据字典
    :param user: 当前登录用户字典
    :param is_update: 是否为更新操作
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not is_update:
        # 新增操作：强制使用当前操作人和当前时间覆盖
        data_dict['createUserId'] = user.get('id')
        data_dict['createUserName'] = user.get('name')
        data_dict['createTime'] = current_time
    else:
        # 更新操作：强制使用当前操作人和当前时间进行覆盖，避免前端传旧值导致无法更新
        data_dict['updateUserId'] = user.get('id')
        data_dict['updateUserName'] = user.get('name')
        data_dict['updateTime'] = current_time
            
    return data_dict
