import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator
from api.endpoints.mcp.modular.mcp import McpBinding


EnabledFlag = Literal[0, 1]
SkillLevelType = Literal[1, 2]


class ImportedSkillWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: PositiveInt | None = None
    skillName: str = Field(min_length=1, max_length=100)
    skillDescription: str = Field(default='', max_length=255)
    ruleContent: str = Field(min_length=1, max_length=60000)
    enabled: EnabledFlag = 1

    @field_validator('skillName', 'ruleContent')
    @classmethod
    def required_text(cls, value):
        cleaned = value.strip()
        if not cleaned or '\x00' in cleaned:
            raise ValueError('技能名称和文本内容不能为空或包含空字符')
        if len(cleaned.encode('utf-8')) > 60000:
            raise ValueError('技能文本最多60000字节')
        return cleaned


class ImportedSkillDelete(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: PositiveInt


class TemplateAccessSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    userGroupIds: list[int] | None = Field(..., max_length=1000)

    @field_validator('userGroupIds', mode='before')
    @classmethod
    def valid_groups(cls, value):
        if value is not None and (not isinstance(value, list) or any(type(v) is not int or v <= 0 for v in value) or len(value) != len(set(value))):
            raise ValueError('用户组须为不重复的正整数ID，null表示全部用户组')
        return value


class TemplateAccessUpdate(TemplateAccessSelection):
    templateIds: list[str] = Field(min_length=1, max_length=100)

    @field_validator('templateIds')
    @classmethod
    def valid_templates(cls, value):
        if len(set(value)) != len(value) or any(not re.fullmatch(r'[0-9a-f]{24}', v) for v in value):
            raise ValueError('模板ID须为不重复的24位ID')
        return value


class TemplateAnswerAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answer: str = Field(min_length=1, max_length=18000)
    question: str = Field(default='', max_length=4000)

    @field_validator('answer', 'question')
    @classmethod
    def plain_text(cls, value, info):
        value = value.strip()
        if '\x00' in value or (info.field_name == 'answer' and not value):
            raise ValueError('回答不能为空，文本不能包含空字符')
        return value


class TemplateAnswerCreate(TemplateAnswerAssessment):
    skillName: str = Field(default='', max_length=100)
    projectGroupIds: list[int] = Field(default_factory=list, max_length=20)

    @field_validator('projectGroupIds', mode='before')
    @classmethod
    def valid_project_ids(cls, value):
        if not isinstance(value,list) or any(type(v) is not int or v<=0 for v in value) or len(value)!=len(set(value)):
            raise ValueError('项目组必须是不重复的正整数ID')
        return value

    @field_validator('skillName')
    @classmethod
    def clean_name(cls, value):
        if '\x00' in value:
            raise ValueError('模板名称不能包含空字符')
        return value.strip()


class TemplateDocumentOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requirements: str = Field(default='', max_length=4000)
    outputFormats: list[Literal['md', 'docx', 'pdf']] = Field(default_factory=lambda: ['md', 'docx'], min_length=1, max_length=3)
    skillVersion: PositiveInt | None = None
    sessionId: str | None = Field(default=None, max_length=128)

    @field_validator('outputFormats')
    @classmethod
    def distinct_formats(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('导出格式不能重复')
        return value

    @field_validator('requirements', 'sessionId')
    @classmethod
    def plain_text(cls, value):
        if value is not None and '\x00' in value:
            raise ValueError('文本不能包含空字符')
        return value.strip() if value is not None else None


class TemplateDelete(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: bool = Field(strict=True)

    @field_validator('confirmed')
    @classmethod
    def require_confirmation(cls, value):
        if not value:
            raise ValueError('请先确认物理删除模板')
        return value


class TemplateTaskRetry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expectedAttempt: int = Field(ge=1, strict=True)


class TemplateSkillGraphQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=2,max_length=3500)

    @field_validator('query')
    @classmethod
    def nonempty_query(cls,value):
        value=value.strip()
        if len(value)<2 or '\x00' in value:raise ValueError('查询至少两字且不能包含空字符')
        return value


class TemplateGraphQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=2,max_length=7500)
    mode: Literal['mix','local','global','hybrid'] = 'mix'
    topK: int = Field(default=40,ge=1,le=80)
    chunkTopK: int = Field(default=20,ge=1,le=40)

    @field_validator('question')
    @classmethod
    def nonempty_question(cls,value):
        value=value.strip()
        if len(value)<2 or '\x00' in value:raise ValueError('问题至少两字且不能包含空字符')
        return value


def _strip_required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name}不能为空")
    return cleaned


def _validate_sub_skill_ids(value: list[int]) -> list[int]:
    if any(skill_id < 1 for skill_id in value):
        raise ValueError("子技能ID必须大于0")
    if len(value) != len(set(value)):
        raise ValueError("同一子技能不能重复选择")
    return value


class SkillGroupWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    groupName: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=1000)
    sortOrder: int = Field(default=0, ge=0, le=1000000)
    enabled: Literal[0, 1] = 1
    userGroupIds: list[int] = Field(default_factory=list, max_length=100)

    @field_validator('groupName')
    @classmethod
    def group_name_required(cls, value):
        return _strip_required(value, '技能组名称')

    @field_validator('userGroupIds')
    @classmethod
    def valid_user_group_ids(cls, value):
        if any(i <= 0 for i in value) or len(set(value)) != len(value):
            raise ValueError('用户组ID必须为正数且不能重复')
        return value


class SkillGroupSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    skillIds: list[int] = Field(min_length=1, max_length=100)
    confirm: bool = False

    @field_validator('skillIds')
    @classmethod
    def valid_skill_ids(cls, value):
        if any(i <= 0 for i in value) or len(set(value)) != len(value):
            raise ValueError('技能ID必须为正数且不能重复')
        return value


class SkillGroupConfirm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirm: Literal[True]


class PublicSkillQuery(BaseModel):
    keyword: Optional[str] = Field(None, max_length=100, description="技能名称、描述或规则关键字")
    enabled: Optional[EnabledFlag] = Field(None, description="是否启用")
    skillLevelType: Optional[SkillLevelType] = Field(None, description="技能类型：1主技能，2子技能")
    pageNo: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(5, ge=1, le=100, description="每页条数")

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        return value.strip()


class PublicSkillCreate(BaseModel):
    templateId: str | None = Field(default=None,pattern=r'^[0-9a-f]{24}$')

    @field_validator('templateId')
    @classmethod
    def no_template_binding(cls,value):
        if value is not None:raise ValueError('模板与技能已独立，请在生成模板时选择项目组')
        return value
    mcpBindings: list[McpBinding] | None = Field(None, max_length=5)
    skillName: str = Field(..., min_length=1, max_length=100, description="技能名称")
    skillDescription: str = Field(default="", max_length=255, description="技能描述")
    ruleContent: str = Field(..., min_length=1, description="技能规则内容")
    skillLevelType: SkillLevelType = Field(1, description="技能类型：1主技能，2子技能")
    subSkillIds: list[int] = Field(default_factory=list, max_length=100)
    enabled: EnabledFlag = Field(1, description="是否启用")

    @field_validator("skillName")
    @classmethod
    def validate_skill_name(cls, value: str) -> str:
        return _strip_required(value, "技能名称")

    @field_validator("skillDescription")
    @classmethod
    def normalize_skill_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("ruleContent")
    @classmethod
    def validate_rule_content(cls, value: str) -> str:
        cleaned = _strip_required(value, "规则内容")
        if len(cleaned.encode("utf-8")) > 65535:
            raise ValueError("技能规则内容超过数据库可保存长度")
        return cleaned

    @field_validator("subSkillIds")
    @classmethod
    def validate_sub_skill_ids(cls, value: list[int]) -> list[int]:
        return _validate_sub_skill_ids(value)

    @model_validator(mode="after")
    def validate_hierarchy(self):
        if self.skillLevelType == 2 and self.subSkillIds:
            raise ValueError("子技能不能继续绑定子技能")
        return self


class PublicSkillUpdate(PublicSkillCreate):
    id: int = Field(..., ge=1, description="技能ID")


# 技能四模型角色：与废弃的智能体保持一致（1 意图 / 2 任务分解 / 3 执行代码 / 4 总结）
# 子技能不单独配置模型，统一由主技能的意图模型做筛选，其余角色沿用主技能配置。
SKILL_MODEL_ROLES = (
    ('intentLlmId', 1, '意图模型'),
    ('taskLlmId', 2, '任务分解模型'),
    ('executLlmId', 3, '执行模型'),
    ('summaryLlmId', 4, '总结模型'),
)


class SkillExecutionWrite(PublicSkillCreate):
    """技能执行配置写入模型：四类模型 + 温度 + 数据表/知识库资源。"""

    model_config = ConfigDict(extra='forbid')
    updateHierarchy: bool = False
    intentLlmId: PositiveInt | None = Field(None, description="意图模型ID，关联 MODEL_CONFIG.TYPE=1")
    taskLlmId: PositiveInt | None = Field(None, description="任务分解模型ID，关联 MODEL_CONFIG.TYPE=2")
    executLlmId: PositiveInt | None = Field(None, description="执行模型ID，关联 MODEL_CONFIG.TYPE=3")
    summaryLlmId: PositiveInt | None = Field(None, description="总结模型ID，关联 MODEL_CONFIG.TYPE=4")
    temperature: float | None = Field(None, ge=0, le=2, allow_inf_nan=False)
    tableIds: list[PositiveInt] = Field(default_factory=list, max_length=100)
    tenantIds: list[PositiveInt] = Field(default_factory=list, max_length=20)

    @field_validator('tableIds', 'tenantIds')
    @classmethod
    def unique_resources(cls, values):
        if len(set(values)) != len(values):
            raise ValueError('同一资源不能重复选择')
        return values


class PersonalSkillWrite(SkillExecutionWrite):
    """用户技能沿用后台资源配置，但不开放 MCP 绑定。"""
    mcpBindings: Literal[None] = None


class PublicSkillDelete(BaseModel):
    id: int = Field(..., ge=1, description="技能ID")


class PublicSkillBatchDelete(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=100, description="技能ID列表")

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, value: list[int]) -> list[int]:
        if any(skill_id < 1 for skill_id in value):
            raise ValueError("技能ID必须大于0")
        if len(value) != len(set(value)):
            raise ValueError("同一技能不能重复删除")
        return value


ShareStatus = Literal[0, 1, 2, 3]


class PrivateSkillQuery(BaseModel):
    skillName: Optional[str] = Field(None, max_length=100)
    userName: Optional[str] = Field(None, max_length=55)
    groupId: Optional[int] = Field(None, ge=1)
    account: Optional[str] = Field(None, max_length=55)
    enabled: Optional[EnabledFlag] = None
    skillLevelType: Optional[SkillLevelType] = None
    pageNo: int = Field(1, ge=1)
    pageSize: int = Field(10, ge=1, le=100)

    @field_validator("skillName", "userName", "account")
    @classmethod
    def normalize_filters(cls, value: Optional[str]) -> Optional[str]:
        normalized = value.strip() if value else ""
        return normalized or None


class PrivateSkillCreate(BaseModel):
    mcpBindings: list[McpBinding] | None = Field(None, max_length=5)
    userId: Optional[int] = Field(None, ge=1)
    skillName: str = Field(..., min_length=1, max_length=100)
    skillDescription: str = Field(default="", max_length=255)
    ruleContent: str = Field(..., min_length=1)
    skillLevelType: SkillLevelType = 1
    subSkillIds: list[int] = Field(default_factory=list, max_length=100)
    enabled: EnabledFlag = 1

    @field_validator("skillName", "ruleContent")
    @classmethod
    def normalize_required_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("技能名称和规则内容不能为空")
        return normalized

    @field_validator("skillDescription")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("subSkillIds")
    @classmethod
    def validate_sub_skill_ids(cls, value: list[int]) -> list[int]:
        return _validate_sub_skill_ids(value)

    @model_validator(mode="after")
    def validate_hierarchy(self):
        if self.skillLevelType == 2 and self.subSkillIds:
            raise ValueError("子技能不能继续绑定子技能")
        return self


class PrivateSkillUpdate(PrivateSkillCreate):
    id: int = Field(..., ge=1)


class PrivateSkillDelete(BaseModel):
    id: int = Field(..., ge=1)


class PrivateSubSkillOptionQuery(BaseModel):
    userId: Optional[int] = Field(None, ge=1)


class PrivateSkillShare(BaseModel):
    skillId: int = Field(..., ge=1)
    targetUserIds: list[int] = Field(..., min_length=1, max_length=100)

    @field_validator("targetUserIds")
    @classmethod
    def validate_target_user_ids(cls, value: list[int]) -> list[int]:
        if any(user_id <= 0 for user_id in value):
            raise ValueError("接收人ID必须大于0")
        if len(value) != len(set(value)):
            raise ValueError("不能重复选择同一接收人")
        return value


class PrivateSkillShareTargetQuery(BaseModel):
    keyword: Optional[str] = Field(None, max_length=100)
    groupId: Optional[int] = Field(None, ge=1)
    pageNo: int = Field(1, ge=1)
    pageSize: int = Field(20, ge=1, le=100)

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: Optional[str]) -> Optional[str]:
        normalized = value.strip() if value else ""
        return normalized or None


class SkillShareQuery(BaseModel):
    keyword: Optional[str] = Field(None, max_length=100)
    receiveStatus: Optional[ShareStatus] = None
    direction: Literal["inbox", "outbox", "all"] = "inbox"
    pageNo: int = Field(1, ge=1)
    pageSize: int = Field(10, ge=1, le=100)

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: Optional[str]) -> Optional[str]:
        normalized = value.strip() if value else ""
        return normalized or None


class SkillShareAction(BaseModel):
    id: int = Field(..., ge=1)


class SkillLibraryPublish(BaseModel):
    skillId: int = Field(..., ge=1)


class SkillLibraryQuery(BaseModel):
    keyword: Optional[str] = Field(None, max_length=100)
    groupId: Optional[int] = Field(None, ge=1)
    pageNo: int = Field(1, ge=1)
    pageSize: int = Field(10, ge=1, le=100)

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: Optional[str]) -> Optional[str]:
        normalized = value.strip() if value else ""
        return normalized or None


class SkillLibraryAction(BaseModel):
    id: int = Field(..., ge=1)
