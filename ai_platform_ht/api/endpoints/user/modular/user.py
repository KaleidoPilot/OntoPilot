from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

class UserBase(BaseModel):
    realName: Optional[str] = Field(None, description="姓名")
    account: Optional[str] = Field(None, description="登录账号")
    password: Optional[str] = Field(None, description="登录密码")
    phone: Optional[str] = Field(None, description="手机号")
    deptName: Optional[str] = Field(None, description="部门名称")
    deptLevel: Literal[0, 1] | None = Field(None, description='0最高权限，1企业管理员')
    orgId: int | None = Field(None, gt=0, description='所属公司ID')
    remarks: Optional[str] = Field(None, description="备注")
    enabled: Optional[int] = Field(None, description="是否有效")
    removed: Optional[int] = Field(None, description="是否删除")
    createUserId: Optional[int] = Field(None, description="创建人ID")
    createUserName: Optional[str] = Field(None, description="创建人姓名")
    createTime: Optional[str] = Field(None, description="创建时间")
    updateUserId: Optional[int] = Field(None, description="更新人ID")
    updateUserName: Optional[str] = Field(None, description="更新人姓名")
    updateTime: Optional[str] = Field(None, description="更新时间")

class UserCreate(UserBase):
    deptLevel: Literal[0, 1]

class UserUpdate(UserBase):
    id: int = Field(..., description="主键")

    @field_validator('deptLevel')
    @classmethod
    def require_level_when_supplied(cls, value):
        if value is None:
            raise ValueError('管理员等级不能为空')
        return value

class User(UserBase):
    id: int = Field(..., description="主键")

class UserResponse(User):
    password: str | None = Field(None, exclude=True)

class UserQueryRequest(UserBase):
    pageNo: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=100, description="每页条数")


EnabledFlag = Literal[0, 1]


class CompanyAdministratorQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    orgId: int = Field(gt=0)
    keyword: str = Field(default='', max_length=100)
    enabled: EnabledFlag | None = None
    pageNo: int = Field(default=1, ge=1)
    pageSize: int = Field(default=10, ge=1, le=100)


class CompanyAdministratorFields(BaseModel):
    model_config = ConfigDict(extra='forbid')
    orgId: int = Field(gt=0)
    realName: str = Field(min_length=1, max_length=55)
    account: str = Field(min_length=1, max_length=55)
    phone: str = Field(default='', max_length=32)
    deptName: str = Field(default='', max_length=100)
    remarks: str = Field(default='', max_length=500)
    enabled: EnabledFlag = 1

    @field_validator('realName', 'account')
    @classmethod
    def required_text(cls, value: str):
        if not value.strip():
            raise ValueError('姓名和账号不能为空')
        return value.strip()


def _validate_company_administrator_password(value: SecretStr | None, *, required: bool):
    raw = value.get_secret_value() if value else ''
    if not raw and not required:
        return None
    if not raw.strip() or not 8 <= len(raw.encode('utf-8')) <= 72:
        raise ValueError('密码长度必须为8至72字节，不能全部为空格')
    return value


class CompanyAdministratorCreate(CompanyAdministratorFields):
    password: SecretStr

    @field_validator('password')
    @classmethod
    def validate_password(cls, value):
        return _validate_company_administrator_password(value, required=True)


class CompanyAdministratorUpdate(CompanyAdministratorFields):
    id: int = Field(gt=0)
    password: SecretStr | None = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, value):
        return _validate_company_administrator_password(value, required=False)


class ExternalUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExternalUserGroupQuery(ExternalUserRequest):
    keyword: str | None = Field(default=None, max_length=100)
    enabled: EnabledFlag | None = None
    pageNo: int = Field(default=1, ge=1)
    pageSize: int = Field(default=10, ge=1, le=100)

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else ""
        return normalized or None


class ExternalUserGroupCreate(ExternalUserRequest):
    groupName: str = Field(min_length=1, max_length=100)
    agentId: str | int = Field(description="英文逗号分隔的智能体ID，兼容单个整数ID")
    remarks: str = Field(default="", max_length=500)
    enabled: EnabledFlag = 1

    @field_validator("agentId", mode="before")
    @classmethod
    def normalize_agent_ids(cls, value: str | int) -> str:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError("请选择有效的智能体ID")
        parts = str(value).split(",")
        if not 1 <= len(parts) <= 100:
            raise ValueError("请选择1至100个智能体")
        ids = []
        for part in parts:
            part = part.strip()
            if not part.isascii() or not part.isdigit() or not 0 < int(part) <= 2147483647:
                raise ValueError("智能体ID必须是有效的正整数")
            agent_id = str(int(part))
            if agent_id not in ids:
                ids.append(agent_id)
        normalized = ",".join(ids)
        if len(normalized) > 1000:
            raise ValueError("智能体ID总长度不能超过1000")
        return normalized

    @field_validator("groupName")
    @classmethod
    def normalize_group_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("用户组名称不能为空")
        return normalized

    @field_validator("remarks")
    @classmethod
    def normalize_remarks(cls, value: str) -> str:
        return value.strip()


class ExternalUserGroupUpdate(ExternalUserGroupCreate):
    id: int = Field(gt=0)


class ExternalUserGroupDelete(ExternalUserRequest):
    id: int = Field(gt=0)


class ExternalUserQuery(ExternalUserRequest):
    keyword: str | None = Field(default=None, max_length=100)
    groupId: int | None = Field(default=None, gt=0)
    enabled: EnabledFlag | None = None
    pageNo: int = Field(default=1, ge=1)
    pageSize: int = Field(default=10, ge=1, le=100)

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else ""
        return normalized or None


class ExternalUserCreate(ExternalUserRequest):
    groupId: int = Field(gt=0)
    realName: str = Field(min_length=1, max_length=55)
    account: str = Field(min_length=1, max_length=55)
    password: str = Field(min_length=8, max_length=72)
    phone: str = Field(default="", max_length=32)
    remarks: str = Field(default="", max_length=500)
    enabled: EnabledFlag = 1

    @field_validator("realName", "account")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("姓名和登录账号不能为空")
        return normalized

    @field_validator("phone", "remarks")
    @classmethod
    def normalize_optional_text(cls, value: str) -> str:
        return value.strip()


class ExternalUserUpdate(ExternalUserRequest):
    id: int = Field(gt=0)
    groupId: int = Field(gt=0)
    realName: str = Field(min_length=1, max_length=55)
    account: str = Field(min_length=1, max_length=55)
    phone: str = Field(default="", max_length=32)
    remarks: str = Field(default="", max_length=500)
    enabled: EnabledFlag = 1

    @field_validator("realName", "account")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("姓名和登录账号不能为空")
        return normalized

    @field_validator("phone", "remarks")
    @classmethod
    def normalize_optional_text(cls, value: str) -> str:
        return value.strip()


class ExternalUserDelete(ExternalUserRequest):
    id: int = Field(gt=0)


class ExternalUserBatchDelete(ExternalUserRequest):
    ids: list[int] = Field(min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, value: list[int]) -> list[int]:
        if any(user_id <= 0 for user_id in value):
            raise ValueError("用户ID必须大于0")
        if len(value) != len(set(value)):
            raise ValueError("不能重复选择同一用户")
        return value


class ExternalUserResetPassword(ExternalUserRequest):
    id: int = Field(gt=0)
    newPassword: str = Field(min_length=8, max_length=72)


class ExternalUserChangePassword(ExternalUserRequest):
    oldPassword: str = Field(min_length=1, max_length=72)
    newPassword: str = Field(min_length=8, max_length=72)
