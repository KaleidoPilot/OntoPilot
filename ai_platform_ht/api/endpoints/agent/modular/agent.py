from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator
from typing import Optional

class AgentBase(BaseModel):
    orgId: Optional[int] = Field(None, description="组织ID")
    agentName: Optional[str] = Field(None, description="智能体名称（如：粤语客服助手）")
    skillIds: Optional[str] = Field(None, description="技能组ids（逻辑关联 SKILL.ID,号拼接多个id）")
    templateIds: Optional[str] = Field(None, description="绑定的模板ID，英文逗号分隔（逻辑关联 TEMPLATE_GENERATION.ID）")
    mcpIds: Optional[str] = Field(None, description="绑定 MCP ID，英文逗号分隔")
    agentType: Optional[int] = Field(None, description="1公有，2私有；服务端根据创建者固定")
    userId: Optional[int] = Field(None, description="私有智能体所属外部用户")
    shareUserIds: Optional[str] = Field(None, description="分享接收人 ID，英文逗号分隔")
    agentDescription: Optional[str] = Field(None, description="智能体描述")
    systemPrompt: Optional[str] = Field(None, description="系统提示词（定义角色、任务、约束等）")
    userPromptTemplate: Optional[str] = Field(None, description="用户提示词模板（支持变量占位，如{{text}}）")
    temperature: Optional[float] = Field(None, description="温度参数（0.0~2.0，控制随机性，越高越随机）")
    topP: Optional[float] = Field(None, description="Top-p 采样参数（0.0~1.0，核采样）")
    key: Optional[str] = Field(None, description="调用智能体的key值")
    intentLlmId: Optional[int] = Field(None, description="意图模型ID（任务类型为1）")
    taskLlmId: Optional[int] = Field(None, description="任务分解模型ID（任务类型为2）")
    executLlmId: Optional[int] = Field(None, description="执行任务（代码生成）ID（任务类型3）")
    summaryLlmId: Optional[int] = Field(None, description="总结任务ID（4总结模型）")
    tenantIds: Optional[str] = Field(None, description="知识库id（根据,拼接关联知识库）")
    tenantTopK: Optional[int] = Field(None, description="知识库返回数量")
    tenantScore: Optional[float] = Field(None, description="知识库返回的最低置信度（0.4代表百分之40）")
    enabled: Optional[int] = Field(None, description="是否有效（1有效，0无效）")
    removed: Optional[int] = Field(None, description="是否删除（1已删除，0未删除）")
    createUserId: Optional[int] = Field(None, description="创建人ID")
    createUserName: Optional[str] = Field(None, description="创建人姓名")
    createTime: Optional[str] = Field(None, description="创建时间")
    updateUserId: Optional[int] = Field(None, description="更新人ID")
    updateUserName: Optional[str] = Field(None, description="更新人姓名")
    updateTime: Optional[str] = Field(None, description="更新时间")

class AgentCreate(AgentBase):
    pass

class AgentUpdate(AgentBase):
    id: int = Field(..., description="主键")

class Agent(AgentBase):
    id: int = Field(..., description="主键")

class AgentResponse(Agent):
    pass

class AgentQueryRequest(AgentBase):
    id: PositiveInt | None = None
    pageNo: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=100, description="每页条数")


class PersonalAgentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agentName: str = Field(min_length=1, max_length=100)
    agentDescription: str = Field(default="", max_length=255)
    systemPrompt: str = Field(min_length=1, max_length=60000)
    userPromptTemplate: str = Field(default="", max_length=60000)
    temperature: float = Field(default=0.7, ge=0, le=2, allow_inf_nan=False)
    topP: float = Field(default=0.9, ge=0, le=1, allow_inf_nan=False)
    intentLlmId: PositiveInt
    taskLlmId: PositiveInt
    executLlmId: PositiveInt
    summaryLlmId: PositiveInt
    tenantIds: list[PositiveInt] = Field(default_factory=list, max_length=20)
    mcpIds: list[PositiveInt] = Field(default_factory=list, max_length=5)
    skillIds: list[PositiveInt] | None = Field(default=None, max_length=20)
    tenantTopK: int = Field(default=5, ge=1, le=50)
    tenantScore: float = Field(default=0.4, ge=0, le=1, allow_inf_nan=False)
    enabled: int = Field(default=1, ge=0, le=1)

    @field_validator("agentName", "systemPrompt")
    @classmethod
    def required_text(cls, value):
        if not value.strip():
            raise ValueError("智能体名称和系统提示词不能为空")
        return value.strip()

    @field_validator("systemPrompt", "userPromptTemplate")
    @classmethod
    def prompt_size(cls, value):
        if len(value.encode('utf-8')) > 60000:
            raise ValueError('提示词不能超过60000字节')
        return value

    @field_validator("tenantIds", "mcpIds", "skillIds")
    @classmethod
    def unique_ids(cls, value):
        return list(dict.fromkeys(value)) if value is not None else None


class PersonalAgentUpdate(PersonalAgentWrite):
    id: PositiveInt


class PersonalAgentShare(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: PositiveInt
    receiveUserIds: list[PositiveInt] = Field(max_length=100)

    @field_validator("receiveUserIds")
    @classmethod
    def unique_ids(cls, value):
        return list(dict.fromkeys(value))
