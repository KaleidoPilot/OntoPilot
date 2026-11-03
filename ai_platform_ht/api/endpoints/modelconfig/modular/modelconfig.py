from pydantic import BaseModel, Field
from typing import Optional

class ModelconfigBase(BaseModel):
    model: Optional[str] = Field(None, description="模型标识")
    apiKey: Optional[str] = Field(None, description="模型服务API密钥（由应用层加密后存储）")
    baseUrl: Optional[str] = Field(None, description="模型服务基础地址")
    type: Optional[int] = Field(None, description="模型类型：1意图，2任务分解模型，3执行模型（代码），4总结模型")
    enabled: Optional[int] = Field(None, description="是否启用：1启用，0禁用")
    removed: Optional[int] = Field(None, description="是否删除：1已删除，0未删除")
    createUserId: Optional[int] = Field(None, description="创建人ID")
    createUserName: Optional[str] = Field(None, description="创建人姓名")
    createTime: Optional[str] = Field(None, description="创建时间")
    updateUserId: Optional[int] = Field(None, description="更新人ID")
    updateUserName: Optional[str] = Field(None, description="更新人姓名")
    updateTime: Optional[str] = Field(None, description="更新时间")

class ModelconfigCreate(ModelconfigBase):
    pass

class ModelconfigUpdate(ModelconfigBase):
    id: int = Field(..., description="主键")

class Modelconfig(ModelconfigBase):
    id: int = Field(..., description="主键")

class ModelconfigResponse(Modelconfig):
    pass

class ModelconfigQueryRequest(ModelconfigBase):
    pageNo: int = Field(1, description="当前页码")
    pageSize: int = Field(10, description="每页条数")
