from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


ModelType = Literal[1, 2, 3, 4]
EnabledFlag = Literal[0, 1]


def _strip_required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name}不能为空")
    return cleaned


def _validate_base_url(value: str) -> str:
    cleaned = _strip_required(value, "基础URL")
    if not cleaned.startswith(("http://", "https://")):
        raise ValueError("基础URL必须以http://或https://开头")
    return cleaned.rstrip("/")


class ModelConfigCreate(BaseModel):
    model: str = Field(..., max_length=255, description="模型标识")
    apiKey: str = Field(..., max_length=512, description="模型服务API密钥")
    baseUrl: str = Field(..., max_length=500, description="模型服务基础地址")
    type: ModelType = Field(..., description="模型类型")
    enabled: EnabledFlag = Field(1, description="是否启用")

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        return _strip_required(value, "模型标识")

    @field_validator("apiKey")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        return _strip_required(value, "API密钥")

    @field_validator("baseUrl")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return _validate_base_url(value)


class ModelConfigUpdate(BaseModel):
    id: int = Field(..., ge=1, description="主键ID")
    model: Optional[str] = Field(None, max_length=255, description="模型标识")
    apiKey: Optional[str] = Field(None, max_length=512, description="模型服务API密钥")
    baseUrl: Optional[str] = Field(None, max_length=500, description="模型服务基础地址")
    type: Optional[ModelType] = Field(None, description="模型类型")
    enabled: Optional[EnabledFlag] = Field(None, description="是否启用")

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _strip_required(value, "模型标识")

    @field_validator("apiKey")
    @classmethod
    def validate_api_key(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        return value.strip()

    @field_validator("baseUrl")
    @classmethod
    def validate_base_url(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _validate_base_url(value)


class ModelConfigQuery(BaseModel):
    model: Optional[str] = Field(None, max_length=255, description="模型标识")
    type: Optional[ModelType] = Field(None, description="模型类型")
    enabled: Optional[EnabledFlag] = Field(None, description="是否启用")
    pageNo: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(5, ge=1, le=100, description="每页条数")

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        return value.strip()


class ModelConfigDelete(BaseModel):
    id: int = Field(..., ge=1, description="主键ID")


class ModelConfigBatchDelete(BaseModel):
    ids: list[Annotated[int, Field(gt=0, strict=True)]] = Field(
        min_length=1, max_length=100, description="待删除的模型ID，最多100条"
    )

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("模型ID不能重复")
        return value


SystemConfigType = Literal[1, 2, 3, 4]


class SystemConfigCreate(BaseModel):
    configType: SystemConfigType
    configName: str = Field(min_length=1, max_length=100)
    configJson: dict[str, Any]
    enabled: EnabledFlag = 1

    @field_validator("configName")
    @classmethod
    def validate_config_name(cls, value: str) -> str:
        return _strip_required(value, "配置名称")


class SystemConfigUpdate(BaseModel):
    id: int = Field(gt=0)
    configType: SystemConfigType | None = None
    configName: str | None = Field(default=None, min_length=1, max_length=100)
    configJson: dict[str, Any] | None = None
    enabled: EnabledFlag | None = None

    @field_validator("configName")
    @classmethod
    def validate_config_name(cls, value: str | None) -> str | None:
        return None if value is None else _strip_required(value, "配置名称")


class SystemConfigDelete(BaseModel):
    id: int = Field(gt=0)


class SystemConfigSecretReveal(BaseModel):
    id: int = Field(gt=0)
    secretPath: Literal[
        "mysql.password",
        "llm.api_key",
        "embedding.api_key",
        "rerank.api_key",
        "api_key",
        "token",
    ]


class SystemConfigQuery(BaseModel):
    configName: str | None = Field(default=None, max_length=100)
    configType: SystemConfigType | None = None
    enabled: EnabledFlag | None = None
    pageNo: int = Field(default=1, ge=1)
    pageSize: int = Field(default=10, ge=1, le=100)

    @field_validator("configName")
    @classmethod
    def normalize_config_name(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()
