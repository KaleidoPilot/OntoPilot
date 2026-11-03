import json
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class HttpParam(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(default="", max_length=4000)
    enabled: bool = True
    description: str = Field(default="", max_length=500)
    type: Literal["string", "integer", "number", "boolean", "array", "object", "null"] = "string"
    required: bool = True


class HttpVariable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
    type: Literal["string", "integer", "number", "boolean", "array", "object", "null"] = "string"
    description: str = Field(default="", max_length=500)
    example: Any = None
    required: bool = True

    @model_validator(mode="after")
    def validate_example(self):
        if self.example is not None:
            from jsonschema import Draft202012Validator
            if len(json.dumps(self.example, ensure_ascii=False, allow_nan=False)) > 4000:
                raise ValueError("参数示例最多 4000 字符")
            if not Draft202012Validator({"type": self.type}).is_valid(self.example):
                raise ValueError("参数示例必须符合所选类型")
        return self


class HttpRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["GET", "POST"] = "GET"
    params: list[HttpParam] = Field(default_factory=list, max_length=60)
    body: dict[str, Any] | list[Any] | None = None
    description: str = Field(default="", max_length=2000)
    variables: list[HttpVariable] = Field(default_factory=list, max_length=30)
    inactiveVariables: list[HttpVariable] = Field(default_factory=list, max_length=30)
    bodyNotes: dict[str, str] = Field(default_factory=dict, max_length=60)
    bodyFields: list[HttpParam] = Field(default_factory=list, max_length=60)
    testValues: dict[str, Any] = Field(default_factory=dict, max_length=30)

    @model_validator(mode="after")
    def validate_template(self):
        if self.bodyFields:
            keys = [item.key.strip() for item in self.bodyFields]
            if any(not key or '{{' in key or '}}' in key for key in keys) or len(set(keys)) != len(keys):
                raise ValueError("JSON 参数名不能为空、重复或使用模板")
            if self.method == "GET":
                raise ValueError("GET 请求不配置 JSON 参数")
        if any(len(key) > 1000 or len(value) > 500 for key, value in self.bodyNotes.items()):
            raise ValueError("JSON 字段备注过长")
        if self.method == "GET" and self.body is not None:
            raise ValueError("GET 请求不发送 JSON Body，请使用 Params")
        serialized = json.dumps(self.body, ensure_ascii=False, allow_nan=False)
        if len(serialized) > 32000:
            raise ValueError("JSON Body 最多 32000 字符")
        names = set()
        pattern = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]{0,63})\}\}")
        def scan(value):
            if isinstance(value, str):
                names.update(pattern.findall(value))
                if "{{" in pattern.sub("", value) or "}}" in pattern.sub("", value):
                    raise ValueError("动态参数请使用 {{参数名}}，参数名只允许英文、数字和下划线")
            elif isinstance(value, dict):
                for key, item in value.items():
                    if "{{" in key or "}}" in key:
                        raise ValueError("JSON 字段名不能使用动态参数")
                    scan(item)
            elif isinstance(value, list):
                for item in value: scan(item)
        scan(self.body)
        for param in self.params:
            if "{{" in param.key or "}}" in param.key or not param.key.strip():
                raise ValueError("Params 字段名不能为空或使用动态参数")
            if param.enabled: scan(param.value)
        declared = [item.name for item in self.variables]
        if len(set(declared)) != len(declared) or set(declared) != names:
            raise ValueError("动态参数定义必须与 Params 和 Body 中的占位符一致")
        inactive_names = [item.name for item in self.inactiveVariables]
        disabled_names = {name for param in self.params if not param.enabled for name in pattern.findall(param.value)} - names
        if len(set(inactive_names)) != len(inactive_names) or not set(inactive_names).issubset(disabled_names):
            raise ValueError("停用参数定义必须对应未启用的 Params")
        if len(declared) + len(inactive_names) > 30:
            raise ValueError("动态参数最多 30 个")
        definitions = {item.name: item for item in self.variables + self.inactiveVariables}
        if not self.testValues.keys() <= definitions.keys():
            raise ValueError("测试值必须对应已配置参数")
        from jsonschema import Draft202012Validator
        for name, value in self.testValues.items():
            if len(json.dumps(value, ensure_ascii=False, allow_nan=False)) > 4000 or not Draft202012Validator({"type": definitions[name].type}).is_valid(value):
                raise ValueError("测试值必须符合参数类型且不超过 4000 字符")
        return self


class McpConfigSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int | None = Field(None, gt=0)
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2048)
    authType: Literal["none", "bearer"] = "none"
    token: SecretStr | None = None
    enabled: Literal[0, 1] = 1
    httpRequest: HttpRequestConfig | None = None
    categoryId: int | None = Field(None, gt=0)

    @field_validator("name", "url")
    @classmethod
    def strip_required(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("名称和地址不能为空")
        return value

    @model_validator(mode="after")
    def validate_address(self):
        url = urlsplit(self.url)
        try:
            port = url.port
        except ValueError:
            raise ValueError("服务端口不正确") from None
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or (url.query and self.httpRequest is None) or url.fragment:
            raise ValueError("请填写不含账号、密码、查询参数或片段的 HTTP/HTTPS MCP 地址")
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("服务端口不正确")
        if self.authType == "bearer" and url.scheme != "https":
            raise ValueError("Bearer Token 认证必须使用 HTTPS")
        if self.token and (len(self.token.get_secret_value()) > 4096 or any(c in self.token.get_secret_value() for c in "\r\n")):
            raise ValueError("Token 格式不正确")
        if self.httpRequest is not None and (self.authType != "none" or self.token):
            raise ValueError("HTTP 工具不使用认证或 Token")
        return self


class McpId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(gt=0)


class McpTest(McpId):
    arguments: dict[str, Any] = Field(default_factory=dict)


class McpToolsSave(McpId):
    toolNames: list[str] = Field(default_factory=list, max_length=60)

    @field_validator("toolNames")
    @classmethod
    def unique_tools(cls, value):
        if len(value) != len(set(value)) or any(not v or len(v) > 256 for v in value):
            raise ValueError("工具名称无效或重复")
        return value


class McpBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    configId: int = Field(gt=0)
    toolNames: list[str] = Field(min_length=1, max_length=60)


class McpBindingsSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skillId: int = Field(gt=0)
    bindings: list[McpBinding] = Field(default_factory=list, max_length=5)


class McpApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    configId: int = Field(gt=0)
    id: str = Field(pattern=r"^[a-f0-9]{32}$")


class CompanyMcpSave(McpConfigSave):
    visibility: Literal["public", "private"] = "private"
    accessUserIds: list[int] = Field(default_factory=list, max_length=1000)
    confirmVisibilityChange: bool = False

    @model_validator(mode="after")
    def validate_access(self):
        if any(user_id <= 0 for user_id in self.accessUserIds) or len(set(self.accessUserIds)) != len(self.accessUserIds):
            raise ValueError("授权用户无效或重复")
        if self.visibility == "private" and not self.accessUserIds:
            raise ValueError("私有 MCP 必须选择至少一位用户")
        if self.visibility == "public" and self.accessUserIds:
            raise ValueError("公用 MCP 不需要指定用户")
        return self


class CompanyMcpQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pageNo: int = Field(1, ge=1)
    pageSize: int = Field(10, ge=1, le=100)
    keyword: str | None = Field(None, max_length=100)
    visibility: Literal["public", "private"] | None = None
    enabled: Literal[0, 1] | None = None
    categoryId: int | None = Field(None, ge=0)


class McpCategorySave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int | None = Field(None, gt=0)
    name: str = Field(min_length=1, max_length=100)

    @field_validator('name')
    @classmethod
    def strip_name(cls, value):
        if not value.strip():
            raise ValueError('请输入分类名称')
        return value.strip()


class McpUserQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyword: str | None = Field(None, max_length=100)
    ids: list[int] = Field(default_factory=list, max_length=1000)


class SkillMcpOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skillType: Literal[1, 2, 3]
    userId: int | None = Field(None, gt=0)
