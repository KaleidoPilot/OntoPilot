"""由四张项目业务表生成并合并的 SQLAlchemy 字段映射。"""

from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table, Text


metadata = MetaData()


project_table = Table(
    "PROJECT_GROUP",
    metadata,
    Column("ID", Integer, primary_key=True, key="id"),
    Column("ORG_ID", BigInteger, nullable=False, key="orgId"),
    Column("PARENT_ID", Integer, key="parentId"),
    Column("GROUP_NAME", String, key="groupName"),
    Column("LEVEL", Integer, key="level"),
    Column("SORT_ORDER", Integer, key="sortOrder"),
    Column("LIBRARY_NAME", String, key="libraryName"),
    Column("SANDBOX_CONFIG_ID", BigInteger, key="sandboxConfigId"),
    Column("ENABLED", Integer, key="enabled"),
    Column("REMOVED", Integer, key="removed"),
    Column("CREATE_USER_ID", Integer, key="createUserId"),
    Column("CREATE_USER_NAME", String, key="createUserName"),
    Column("CREATE_TIME", String, key="createTime"),
    Column("UPDATE_USER_ID", Integer, key="updateUserId"),
    Column("UPDATE_USER_NAME", String, key="updateUserName"),
    Column("UPDATE_TIME", String, key="updateTime"),
)


table_management_table = Table(
    "TABLE_MANAGEMENT",
    metadata,
    Column("ID", Integer, primary_key=True, key="id"),
    Column("PROJECT_GROUP_ID", Integer, key="projectGroupId"),
    Column("TABLE_NAME", String, key="tableName"),
    Column("TABLE_COMMENT", String, key="tableComment"),
    Column("COLUMNS_JSON", Text, key="columnsJson"),
    Column("TABLE_CN_NAME", String, key="tableCnName"),
    Column("ENABLED", Integer, key="enabled"),
    Column("REMOVED", Integer, key="removed"),
    Column("CREATE_USER_ID", Integer, key="createUserId"),
    Column("CREATE_USER_NAME", String, key="createUserName"),
    Column("CREATE_TIME", String, key="createTime"),
    Column("UPDATE_USER_ID", Integer, key="updateUserId"),
    Column("UPDATE_USER_NAME", String, key="updateUserName"),
    Column("UPDATE_TIME", String, key="updateTime"),
)


table_relation_table = Table(
    "TABLE_RELATION",
    metadata,
    Column("ID", Integer, primary_key=True, key="id"),
    Column("PROJECT_GROUP_ID", Integer, key="projectGroupId"),
    Column("SOURCE_TABLE_ID", Integer, key="sourceTableId"),
    Column("TARGET_TABLE_ID", Integer, key="targetTableId"),
    Column("RELATION_CONTENT", String, key="relationContent"),
    Column("SOURCE_COLUMN", String, key="sourceColumn"),
    Column("TARGET_COLUMN", String, key="targetColumn"),
    Column("REMARKS", String, key="remarks"),
    Column("ENABLED", Integer, key="enabled"),
    Column("REMOVED", Integer, key="removed"),
    Column("CREATE_USER_ID", Integer, key="createUserId"),
    Column("CREATE_USER_NAME", String, key="createUserName"),
    Column("CREATE_TIME", String, key="createTime"),
    Column("UPDATE_USER_ID", Integer, key="updateUserId"),
    Column("UPDATE_USER_NAME", String, key="updateUserName"),
    Column("UPDATE_TIME", String, key="updateTime"),
)


skill_table = Table(
    "SKILL",
    metadata,
    Column("ID", Integer, primary_key=True, key="id"),
    Column("ORG_ID", BigInteger, nullable=False, key="orgId"),
    Column("PROJECT_GROUP_ID", Integer, key="projectGroupId"),
    Column("SKILL_NAME", String, key="skillName"),
    Column("SKILL_DESCRIPTION", String, key="skillDescription"),
    Column("TEMPLATE_ID", String(24), key="templateId"),
    Column("SKILL_TYPE", Integer, key="skillType"),
    Column("SKILL_LEVEL_TYPE", Integer, key="skillLevelType"),
    Column("RULE_CONTENT", Text, key="ruleContent"),
    Column("TABLE_IDS", Text, key="tableIds"),
    Column("SUB_SKILL_IDS", String, key="subSkillIds"),
    Column("USER_ID", BigInteger, key="userId"),
    Column("ENABLED", Integer, key="enabled"),
    Column("REMOVED", Integer, key="removed"),
    Column("CREATE_USER_ID", Integer, key="createUserId"),
    Column("CREATE_USER_NAME", String, key="createUserName"),
    Column("CREATE_TIME", String, key="createTime"),
    Column("UPDATE_USER_ID", Integer, key="updateUserId"),
    Column("UPDATE_USER_NAME", String, key="updateUserName"),
    Column("UPDATE_TIME", String, key="updateTime"),
)
