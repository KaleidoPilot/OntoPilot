import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


EnabledFlag = Literal[0, 1]
ORG_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,63}$")


def _required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name}不能为空")
    return normalized


class OrganizationCreate(BaseModel):
    orgCode: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    remarks: str | None = Field(default=None, max_length=500)
    enabled: EnabledFlag = 1

    @field_validator("orgCode")
    @classmethod
    def validate_org_code(cls, value: str) -> str:
        normalized = _required(value, "公司编码").upper()
        if not ORG_CODE_PATTERN.fullmatch(normalized):
            raise ValueError("公司编码只能包含英文字母、数字、横线和下划线")
        return normalized

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _required(value, "公司名称")

    @field_validator("remarks")
    @classmethod
    def normalize_remarks(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


class OrganizationUpdate(BaseModel):
    id: int = Field(gt=0)
    orgCode: str | None = Field(default=None, min_length=2, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    remarks: str | None = Field(default=None, max_length=500)
    enabled: EnabledFlag | None = None

    @field_validator("orgCode")
    @classmethod
    def validate_org_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _required(value, "公司编码").upper()
        if not ORG_CODE_PATTERN.fullmatch(normalized):
            raise ValueError("公司编码只能包含英文字母、数字、横线和下划线")
        return normalized

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return None if value is None else _required(value, "公司名称")

    @field_validator("remarks")
    @classmethod
    def normalize_remarks(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


class OrganizationDelete(BaseModel):
    id: int = Field(gt=0)


class OrganizationQuery(BaseModel):
    keyword: str | None = Field(default=None, max_length=255)
    enabled: EnabledFlag | None = None
    pageNo: int = Field(default=1, ge=1)
    pageSize: int = Field(default=10, ge=1, le=100)

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()
