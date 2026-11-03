from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")


class KnowledgeFolderWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    folderName: str = Field(min_length=1,max_length=100)
    parentId: int = Field(default=0,ge=0)

    @field_validator('folderName')
    @classmethod
    def folder_name(cls,value):
        value=value.strip()
        if not value or any(c in value for c in ('\x00','/','\\')):
            raise ValueError('文档名称不能为空，也不能包含斜杠或空字符')
        return value


class KnowledgeFolderDelete(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: bool = Field(...,strict=True)


class KnowledgeDocumentMove(BaseModel):
    model_config = ConfigDict(extra='forbid')
    recordIds: list[int] = Field(min_length=1,max_length=100)
    folderId: int = Field(ge=0)

    @field_validator('recordIds',mode='before')
    @classmethod
    def positive_ids(cls,value):
        if not isinstance(value,list) or any(type(v) is not int or v<=0 for v in value) or len(set(value))!=len(value):
            raise ValueError('请选择不重复的文档ID')
        return value


class KnowledgeGraphQuestion(KnowledgeRequest):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator('question')
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('问题不能为空')
        return value


class KnowledgeRetrievalRequest(KnowledgeRequest):
    folderId: int | None = Field(default=None,ge=0,description='文档范围，指定时只允许一个知识库；包含所有下级')
    question: str = Field(min_length=1, max_length=2_000)
    confidence: float = Field(
        ge=0,
        le=1,
        allow_inf_nan=False,
        description="最低置信度，范围为 0 到 1",
    )
    topK: int = Field(
        ge=1,
        le=50,
        description="最多返回的知识条数",
    )
    tenant_id: str = Field(
        min_length=1,
        max_length=255,
        description="一个或多个知识库 ID，多个 ID 使用英文逗号分隔",
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("问题不能为空")
        return normalized

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("知识库 ID 不能为空")
        return normalized


class TenantCreate(KnowledgeRequest):
    tenantName: str = Field(min_length=1, max_length=255)
    remarks: str | None = Field(default=None, max_length=500)
    scopeType: int = Field(default=1, ge=1, le=2, description="1公司公有，2公司私有；个人库由服务端固定为3")
    accessUserIds: list[int] = Field(default_factory=list, max_length=100)
    accessGroupIds: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("tenantName")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("知识库名称不能为空")
        return normalized

    @field_validator("accessUserIds", "accessGroupIds")
    @classmethod
    def validate_grant_ids(cls, value: list[int]) -> list[int]:
        if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in value):
            raise ValueError("授权 ID 必须是正整数")
        unique: list[int] = []
        for item in value:
            if item not in unique:
                unique.append(item)
        return unique


class TenantUpdate(TenantCreate):
    id: int = Field(gt=0)
    enabled: int = Field(default=1, ge=0, le=1)
    scopeType: int | None = Field(default=None, ge=1, le=2)


class TenantDelete(KnowledgeRequest):
    id: int = Field(gt=0)


class KnowledgeRecordUpdate(KnowledgeRequest):
    id: int = Field(gt=0)
    expectedVersion: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=60_000)
    fileUrl: str = Field(default="", max_length=300)
    tenantId: int = Field(gt=0)
    enabled: int = Field(default=1, ge=0, le=1)


class KnowledgeDocumentContent(KnowledgeRequest):
    content: str = Field(min_length=1, max_length=600_000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("文档内容不能为空")
        return normalized


class KnowledgeRecordCreate(KnowledgeRequest):
    folderId: int = Field(default=0,ge=0)
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=60_000)

    @field_validator("title", "content")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("资料标题和知识正文不能为空")
        return normalized


class KnowledgeRecordDelete(KnowledgeRequest):
    id: int = Field(gt=0)
    tenantId: int = Field(gt=0)
