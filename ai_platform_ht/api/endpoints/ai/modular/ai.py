from pydantic import BaseModel, Field
from typing import Optional

class AiBase(BaseModel):
    userQuestion: Optional[str] = Field(None, description="用户提问的原始问题文本")
    vectorRecallResult: Optional[str] = Field(None, description="向量库召回结果")
    intentDbname: Optional[str] = Field(None, description="意图匹配到的知识库集合名称")
    enabled: Optional[int] = Field(None, description="是否有效")
    removed: Optional[int] = Field(None, description="是否删除")
    createUserId: Optional[int] = Field(None, description="创建人ID")
    createUserName: Optional[str] = Field(None, description="创建人姓名")
    createTime: Optional[str] = Field(None, description="创建时间")
    updateUserId: Optional[int] = Field(None, description="更新人ID")
    updateUserName: Optional[str] = Field(None, description="更新人姓名")
    updateTime: Optional[str] = Field(None, description="更新时间")

class AiCreate(AiBase):
    pass

class AiUpdate(AiBase):
    id: int = Field(..., description="主键")

class Ai(AiBase):
    id: int = Field(..., description="主键")

class AiResponse(Ai):
    pass

class AiQueryRequest(AiBase):
    pageNo: int = Field(1, description="当前页码")
    pageSize: int = Field(10, description="每页条数")
