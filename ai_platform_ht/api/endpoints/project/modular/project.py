"""项目模块模型：基础字段由代码生成器生成，业务请求模型在其后补充。"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from api.endpoints.mcp.modular.mcp import McpBinding


class ProjectBase(BaseModel):
    """由 PROJECT_GROUP 表结构生成的基础模型。"""

    parentId: Optional[int] = Field(
        None,
        description="上级菜单ID（NULL表示根节点，逻辑关联本表ID）",
    )
    groupName: Optional[str] = Field(None, description="项目组/菜单名称")
    level: Optional[int] = Field(None, description="层级（0一级项目组，1二级技能组）")
    sortOrder: Optional[int] = Field(None, description="同级排序序号")
    libraryName: Optional[str] = Field(
        None,
        description="归属库名（只有一级项目组存值）",
    )
    enabled: Optional[int] = Field(None, description="是否有效（1有效，0无效）")
    removed: Optional[int] = Field(None, description="是否删除（1已删除，0未删除）")
    createUserId: Optional[int] = Field(None, description="创建人ID")
    createUserName: Optional[str] = Field(None, description="创建人姓名")
    createTime: Optional[str] = Field(
        None,
        description="创建时间（格式：YYYY-MM-DD HH:mm:ss）",
    )
    updateUserId: Optional[int] = Field(None, description="更新人ID")
    updateUserName: Optional[str] = Field(None, description="更新人姓名")
    updateTime: Optional[str] = Field(None, description="更新时间")


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ProjectBase):
    id: int = Field(..., description="主键")


class Project(ProjectBase):
    id: int = Field(..., description="主键")


class ProjectResponse(Project):
    pass


class ProjectQueryRequest(ProjectBase):
    pageNo: int = Field(1, description="当前页码")
    pageSize: int = Field(10, description="每页条数")


class TableManagementBase(BaseModel):
    """由 TABLE_MANAGEMENT 表结构生成的基础模型。"""

    projectGroupId: Optional[int] = Field(None, description="所属项目组ID")
    tableName: Optional[str] = Field(None, description="数据库物理表名")
    tableComment: Optional[str] = Field(None, description="表注释/业务描述")
    columnsJson: Optional[str] = Field(None, description="字段定义JSON")
    tableCnName: Optional[str] = Field(None, description="表中文名")
    enabled: Optional[int] = Field(None, description="是否有效")
    removed: Optional[int] = Field(None, description="是否删除")
    createUserId: Optional[int] = Field(None, description="创建人ID")
    createUserName: Optional[str] = Field(None, description="创建人姓名")
    createTime: Optional[str] = Field(None, description="创建时间")
    updateUserId: Optional[int] = Field(None, description="更新人ID")
    updateUserName: Optional[str] = Field(None, description="更新人姓名")
    updateTime: Optional[str] = Field(None, description="更新时间")


class TableManagementCreate(TableManagementBase):
    pass


class TableManagementUpdate(TableManagementBase):
    id: int = Field(..., description="主键")


class TableManagement(TableManagementBase):
    id: int = Field(..., description="主键")


class TableManagementResponse(TableManagement):
    pass


class TableManagementQueryRequest(TableManagementBase):
    pageNo: int = Field(1, description="当前页码")
    pageSize: int = Field(10, description="每页条数")


class TableRelationBase(BaseModel):
    """由 TABLE_RELATION 表结构生成的基础模型。"""

    projectGroupId: Optional[int] = Field(None, description="所属项目组ID")
    sourceTableId: Optional[int] = Field(None, description="源表ID")
    targetTableId: Optional[int] = Field(None, description="目标表ID")
    relationContent: Optional[str] = Field(None, description="关联类型描述")
    sourceColumn: Optional[str] = Field(None, description="源表关联字段名")
    targetColumn: Optional[str] = Field(None, description="目标表关联字段名")
    remarks: Optional[str] = Field(None, description="备注说明")
    enabled: Optional[int] = Field(None, description="是否有效")
    removed: Optional[int] = Field(None, description="是否删除")
    createUserId: Optional[int] = Field(None, description="创建人ID")
    createUserName: Optional[str] = Field(None, description="创建人姓名")
    createTime: Optional[str] = Field(None, description="创建时间")
    updateUserId: Optional[int] = Field(None, description="更新人ID")
    updateUserName: Optional[str] = Field(None, description="更新人姓名")
    updateTime: Optional[str] = Field(None, description="更新时间")


class TableRelationCreate(TableRelationBase):
    pass


class TableRelationUpdate(TableRelationBase):
    id: int = Field(..., description="主键")


class TableRelation(TableRelationBase):
    id: int = Field(..., description="主键")


class TableRelationResponse(TableRelation):
    pass


class TableRelationQueryRequest(TableRelationBase):
    pageNo: int = Field(1, description="当前页码")
    pageSize: int = Field(10, description="每页条数")


class SkillBase(BaseModel):
    """由 SKILL 表结构生成并合并到项目模块的基础模型。"""

    projectGroupId: Optional[int] = Field(None, description="所属项目组ID")
    skillName: Optional[str] = Field(None, description="技能名称")
    skillDescription: Optional[str] = Field(None, description="技能描述")
    skillType: Optional[int] = Field(None, description="技能类型")
    skillLevelType: Optional[int] = Field(None, description="技能层级类型：1主技能，2子技能")
    ruleContent: Optional[str] = Field(None, description="技能规则内容")
    tableIds: Optional[str] = Field(None, description="技能使用的数据表ID，逗号分隔")
    subSkillIds: Optional[str] = Field(None, description="主技能关联的子技能ID，逗号分隔")
    userId: Optional[int] = Field(None, description="私有技能用户ID")
    enabled: Optional[int] = Field(None, description="是否有效")
    removed: Optional[int] = Field(None, description="是否删除")
    createUserId: Optional[int] = Field(None, description="创建人ID")
    createUserName: Optional[str] = Field(None, description="创建人姓名")
    createTime: Optional[str] = Field(None, description="创建时间")
    updateUserId: Optional[int] = Field(None, description="更新人ID")
    updateUserName: Optional[str] = Field(None, description="更新人姓名")
    updateTime: Optional[str] = Field(None, description="更新时间")


class SkillCreate(SkillBase):
    pass


class SkillUpdate(SkillBase):
    id: int = Field(..., description="主键")


class Skill(SkillBase):
    id: int = Field(..., description="主键")


class SkillResponse(Skill):
    pass


class SkillQueryRequest(SkillBase):
    pageNo: int = Field(1, description="当前页码")
    pageSize: int = Field(10, description="每页条数")


class ProjectGroupMutableFields(BaseModel):
    groupName: str = Field(..., min_length=1, max_length=100)
    sandboxConfigId: Optional[int] = Field(default=None, ge=1)
    sortOrder: int = Field(default=0, ge=0)
    enabled: Literal[0, 1] = 1

    @field_validator("groupName")
    @classmethod
    def validate_group_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("项目组名称不能为空")
        return value

class ProjectGroupCreate(ProjectGroupMutableFields):
    parentId: Optional[int] = Field(default=None, ge=1)


class ProjectGroupUpdate(ProjectGroupMutableFields):
    id: int = Field(..., ge=1)


class ProjectGroupDelete(BaseModel):
    id: int = Field(..., ge=1)


class TableAssociationItem(BaseModel):
    tableName: str = Field(..., min_length=1, max_length=100)
    tableCnName: str = Field(..., min_length=1, max_length=255)
    tableComment: str = Field(default="", max_length=255)

    @field_validator("tableName", "tableCnName")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("物理表名和中文表名不能为空")
        return value

    @field_validator("tableComment")
    @classmethod
    def strip_table_comment(cls, value: str) -> str:
        return value.strip()


class TableAssociationSave(BaseModel):
    projectGroupId: int = Field(..., ge=1)
    libraryName: str = Field(..., min_length=1, max_length=255)
    tables: list[TableAssociationItem] = Field(default_factory=list, max_length=100)

    @field_validator("libraryName")
    @classmethod
    def validate_library_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("归属库名不能为空")
        return value

    @field_validator("tables")
    @classmethod
    def validate_unique_tables(
        cls,
        value: list[TableAssociationItem],
    ) -> list[TableAssociationItem]:
        table_names = [item.tableName for item in value]
        if len(table_names) != len(set(table_names)):
            raise ValueError("不能重复选择同一张物理表")
        return value


class TableColumnRemarkItem(BaseModel):
    columnName: str = Field(..., min_length=1, max_length=100)
    remark: str = Field(default="", max_length=500)

    @field_validator("columnName")
    @classmethod
    def validate_column_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("字段名不能为空")
        return value

    @field_validator("remark")
    @classmethod
    def strip_column_remark(cls, value: str) -> str:
        return value.strip()


class TableColumnRemarksSave(BaseModel):
    projectGroupId: int = Field(..., ge=1)
    tableManagementId: int = Field(..., ge=1)
    columns: list[TableColumnRemarkItem] = Field(
        ...,
        min_length=1,
        max_length=1000,
    )

    @field_validator("columns")
    @classmethod
    def validate_unique_columns(
        cls,
        value: list[TableColumnRemarkItem],
    ) -> list[TableColumnRemarkItem]:
        column_names = [item.columnName for item in value]
        if len(column_names) != len(set(column_names)):
            raise ValueError("同一字段不能重复保存备注")
        return value


class TableColumnsDeleteRequest(BaseModel):
    projectGroupId: int = Field(..., ge=1)
    tableManagementId: int = Field(..., ge=1)
    columnNames: list[str] = Field(..., min_length=1, max_length=1000)

    @field_validator("columnNames")
    @classmethod
    def validate_column_names(cls, value: list[str]) -> list[str]:
        normalized_names = [column_name.strip() for column_name in value]
        if any(not column_name for column_name in normalized_names):
            raise ValueError("字段名不能为空")
        if any(len(column_name) > 100 for column_name in normalized_names):
            raise ValueError("字段名不能超过100个字符")
        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError("同一字段不能重复删除")
        return normalized_names


class TableRelationMutableRequest(BaseModel):
    projectGroupId: int = Field(..., ge=1)
    sourceTableId: int = Field(..., ge=1)
    targetTableId: int = Field(..., ge=1)
    sourceColumn: str = Field(..., min_length=1, max_length=100)
    targetColumn: str = Field(..., min_length=1, max_length=100)
    relationContent: str = Field(..., min_length=1, max_length=200)

    @field_validator("sourceColumn", "targetColumn", "relationContent")
    @classmethod
    def validate_required_relation_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("表关系字段和关系内容不能为空")
        return value


class TableRelationCreateRequest(TableRelationMutableRequest):
    pass


class TableRelationUpdateRequest(TableRelationMutableRequest):
    id: int = Field(..., ge=1)


class TableRelationDeleteRequest(BaseModel):
    id: int = Field(..., ge=1)
    projectGroupId: int = Field(..., ge=1)


class TableRelationBatchDeleteRequest(BaseModel):
    projectGroupId: int = Field(..., ge=1)
    ids: list[int] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def validate_relation_ids(cls, value: list[int]) -> list[int]:
        if any(relation_id < 1 for relation_id in value):
            raise ValueError("表关系ID必须大于0")
        if len(value) != len(set(value)):
            raise ValueError("同一条表关系不能重复删除")
        return value


class TableRelationCandidateRequest(BaseModel):
    sourceTableId: int = Field(..., ge=1)
    targetTableId: int = Field(..., ge=1)
    sourceColumn: str = Field(..., min_length=1, max_length=100)
    targetColumn: str = Field(..., min_length=1, max_length=100)
    relationContent: str = Field(..., min_length=1, max_length=200)

    @field_validator("sourceColumn", "targetColumn", "relationContent")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("表关系字段和关系内容不能为空")
        return cleaned

    @model_validator(mode="after")
    def validate_different_tables(self):
        if self.sourceTableId == self.targetTableId:
            raise ValueError("源表和目标表不能相同")
        return self


class TableRelationBatchCreateRequest(BaseModel):
    projectGroupId: int = Field(..., ge=1)
    relations: list[TableRelationCandidateRequest] = Field(
        ...,
        min_length=1,
        max_length=6,
    )

    @model_validator(mode="after")
    def validate_unique_relations(self):
        relation_keys: set[tuple[tuple[int, str], tuple[int, str]]] = set()
        for relation in self.relations:
            endpoints = sorted(
                (
                    (relation.sourceTableId, relation.sourceColumn),
                    (relation.targetTableId, relation.targetColumn),
                )
            )
            key = (endpoints[0], endpoints[1])
            if key in relation_keys:
                raise ValueError("同一表关系不能重复创建")
            relation_keys.add(key)
        return self


class ProjectSkillMutableRequest(BaseModel):
    templateId: str | None = Field(default=None,pattern=r'^[0-9a-f]{24}$')

    @field_validator('templateId')
    @classmethod
    def no_template_binding(cls,value):
        if value is not None:raise ValueError('模板与技能已独立，请在生成模板时选择项目组')
        return value
    rootProjectGroupId: int = Field(..., ge=1)
    skillGroupId: int = Field(..., ge=1)
    skillName: str = Field(..., min_length=1, max_length=100)
    skillDescription: str = Field(default="", max_length=255)
    ruleContent: str = Field(..., min_length=1)
    tableIds: list[int] = Field(default_factory=list, max_length=50)
    skillLevelType: Literal[1, 2] = 1
    subSkillIds: list[int] = Field(default_factory=list, max_length=100)
    enabled: Literal[0, 1] = 1

    @field_validator("skillName", "ruleContent")
    @classmethod
    def validate_required_skill_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("技能名称和规则内容不能为空")
        if len(value.encode("utf-8")) > 65535:
            raise ValueError("技能规则内容超过数据库可保存长度")
        return value

    @field_validator("skillDescription")
    @classmethod
    def strip_skill_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("tableIds")
    @classmethod
    def validate_table_ids(cls, value: list[int]) -> list[int]:
        if any(table_id < 1 for table_id in value):
            raise ValueError("数据表ID必须大于0")
        if len(value) != len(set(value)):
            raise ValueError("同一张数据表不能重复选择")
        return value

    @field_validator("subSkillIds")
    @classmethod
    def validate_sub_skill_ids(cls, value: list[int]) -> list[int]:
        if any(skill_id < 1 for skill_id in value):
            raise ValueError("子技能ID必须大于0")
        if len(value) != len(set(value)):
            raise ValueError("同一个子技能不能重复选择")
        return value

    @model_validator(mode="after")
    def validate_skill_hierarchy(self):
        if self.skillLevelType == 2 and self.subSkillIds:
            raise ValueError("子技能不能继续绑定子技能")
        return self

class ProjectSkillCreateRequest(ProjectSkillMutableRequest):
    mcpBindings: list["McpBinding"] | None = Field(None, max_length=5)
    pass


class ProjectSkillUpdateRequest(ProjectSkillMutableRequest):
    id: int = Field(..., ge=1)
    mcpBindings: list["McpBinding"] | None = Field(None, max_length=5)


class ProjectSkillDeleteRequest(BaseModel):
    id: int = Field(..., ge=1)
    rootProjectGroupId: int = Field(..., ge=1)


class ProjectSkillBatchDeleteRequest(BaseModel):
    rootProjectGroupId: int = Field(..., ge=1)
    skillGroupId: int = Field(..., ge=1)
    ids: list[int] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def validate_skill_ids(cls, value: list[int]) -> list[int]:
        if any(skill_id < 1 for skill_id in value):
            raise ValueError("技能ID必须大于0")
        if len(value) != len(set(value)):
            raise ValueError("同一个技能不能重复删除")
        return value
