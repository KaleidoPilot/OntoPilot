from sqlalchemy import BigInteger, Column, Integer, MetaData, Numeric, String, Table, Text
from sqlalchemy.dialects.mysql import LONGTEXT


metadata = MetaData()

skill_group_table = Table(
    'SKILL_GROUP', metadata,
    Column('ID', Integer, primary_key=True), Column('ORG_ID', BigInteger, nullable=False),
    Column('GROUP_NAME', String(100), nullable=False), Column('DESCRIPTION', String(1000), nullable=False),
    Column('SORT_ORDER', Integer, nullable=False), Column('ENABLED', Integer, nullable=False),
    Column('CREATE_USER_ID', BigInteger), Column('CREATE_USER_NAME', String(55)), Column('CREATE_TIME', String(55)),
    Column('UPDATE_USER_ID', BigInteger), Column('UPDATE_USER_NAME', String(55)), Column('UPDATE_TIME', String(55)),
)

skill_group_user_group_table = Table(
    'SKILL_GROUP_USER_GROUP', metadata,
    Column('ID', BigInteger, primary_key=True), Column('ORG_ID', BigInteger, nullable=False),
    Column('SKILL_GROUP_ID', Integer, nullable=False), Column('USER_GROUP_ID', BigInteger, nullable=False),
)

template_generation_table = Table(
    'TEMPLATE_GENERATION', metadata,
    Column('ID', String(24), primary_key=True),
    Column('ORG_ID', BigInteger, nullable=False),
    Column('USER_ID', BigInteger, nullable=False),
    Column('OWNER_TYPE', String(16), nullable=False),
    Column('SKILL_NAME', String(100), nullable=False),
    Column('DESCRIPTION', String(1000), nullable=False),
    Column('SOURCE_TASK_ID', String(24), nullable=False),
    Column('KNOWLEDGE_GRAPH_ID', BigInteger, nullable=True),
    Column('PROJECT_GROUP_IDS_JSON', Text, nullable=False),
    Column('SKILL_JSON', LONGTEXT, nullable=False),
    Column('SKILL_MARKDOWN', LONGTEXT, nullable=False),
    Column('META_JSON', LONGTEXT, nullable=False),
    Column('STATUS', String(16), nullable=False, server_default='ready'),
    Column('CREATE_USER_ID', BigInteger), Column('CREATE_USER_NAME', String(55)),
    Column('CREATE_TIME', String(55), nullable=False),
    Column('UPDATE_USER_ID', BigInteger), Column('UPDATE_USER_NAME', String(55)),
    Column('UPDATE_TIME', String(55)),
)

skill_table = Table(
    "SKILL",
    metadata,
    Column("ID", Integer, primary_key=True, key="id"),
    Column("ORG_ID", BigInteger, nullable=False, key="orgId"),
    Column("SKILL_GROUP_ID", Integer, nullable=True, key="accessGroupId"),
    # 四模型：与废弃的智能体一致（1 意图 / 2 任务分解 / 3 执行代码 / 4 总结）
    Column('INTENT_LLM_ID', Integer, nullable=True, key='intentLlmId'),
    Column('TASK_LLM_ID', Integer, nullable=True, key='taskLlmId'),
    Column('EXECUT_LLM_ID', Integer, nullable=True, key='executLlmId'),
    Column('SUMMARY_LLM_ID', Integer, nullable=True, key='summaryLlmId'),
    Column('TEMPERATURE', Numeric(3, 2), nullable=True, key='temperature'),
    # TENANT_IDS：知识库ID列表；TABLE_IDS：数据表ID列表
    Column('TENANT_IDS', Text, nullable=True, key='tenantIds'),
    Column('TABLE_IDS', Text, nullable=True, key='tableIds'),
    Column('RESOURCE_CONFIGURED', Integer, nullable=False, server_default='0', key='resourceConfigured'),
    Column("PROJECT_GROUP_ID", Integer, key="projectGroupId"),
    Column("SKILL_NAME", String, key="skillName"),
    Column("SKILL_DESCRIPTION", String, key="skillDescription"),
    Column("TEMPLATE_ID", String(24), nullable=True, key="templateId"),
    Column("SKILL_TYPE", Integer, key="skillType"),
    Column("SKILL_LEVEL_TYPE", Integer, key="skillLevelType"),
    Column("RULE_CONTENT", String, key="ruleContent"),
    Column("SUB_SKILL_IDS", String, key="subSkillIds"),
    Column("USER_ID", Integer, key="userId"),
    Column("ENABLED", Integer, key="enabled"),
    Column("REMOVED", Integer, key="removed"),
    Column("CREATE_USER_ID", Integer, key="createUserId"),
    Column("CREATE_USER_NAME", String, key="createUserName"),
    Column("CREATE_TIME", String, key="createTime"),
    Column("UPDATE_USER_ID", Integer, key="updateUserId"),
    Column("UPDATE_USER_NAME", String, key="updateUserName"),
    Column("UPDATE_TIME", String, key="updateTime"),
)

skill_share_table = Table(
    "SKILL_SHARE",
    metadata,
    Column("ID", BigInteger, primary_key=True, key="id"),
    Column("ORG_ID", BigInteger, nullable=False, key="orgId"),
    Column("SOURCE_SKILL_ID", Integer, nullable=False, key="sourceSkillId"),
    Column("SOURCE_USER_ID", BigInteger, nullable=False, key="sourceUserId"),
    Column("TARGET_USER_ID", BigInteger, nullable=False, key="targetUserId"),
    Column("SKILL_NAME", String(100), nullable=False, key="skillName"),
    Column("SKILL_DESCRIPTION", String(255), key="skillDescription"),
    Column("SKILL_TYPE", Integer, nullable=False, key="skillType"),
    Column("SKILL_LEVEL_TYPE", Integer, nullable=False, key="skillLevelType"),
    Column("SUB_SKILLS_JSON", Text, key="subSkillsJson"),
    Column("RULE_CONTENT", Text, nullable=False, key="ruleContent"),
    Column("ENABLED", Integer, nullable=False, key="enabled"),
    Column("RECEIVE_STATUS", Integer, nullable=False, key="receiveStatus"),
    Column("ACCEPTED_SKILL_ID", Integer, key="acceptedSkillId"),
    Column("RESPONSE_TIME", String(55), key="responseTime"),
    Column("CREATE_USER_ID", BigInteger, key="createUserId"),
    Column("CREATE_USER_NAME", String(55), key="createUserName"),
    Column("CREATE_TIME", String(55), key="createTime"),
    Column("UPDATE_USER_ID", BigInteger, key="updateUserId"),
    Column("UPDATE_USER_NAME", String(55), key="updateUserName"),
    Column("UPDATE_TIME", String(55), key="updateTime"),
)

skill_library_table = Table(
    "SKILL_LIBRARY",
    metadata,
    Column("ID", BigInteger, primary_key=True, key="id"),
    Column("ORG_ID", BigInteger, nullable=False, key="orgId"),
    Column("SOURCE_SKILL_ID", Integer, nullable=False, key="sourceSkillId"),
    Column("PUBLISHER_USER_ID", BigInteger, nullable=False, key="publisherUserId"),
    Column("GROUP_ID", BigInteger, nullable=False, key="groupId"),
    Column("SKILL_NAME", String(100), nullable=False, key="skillName"),
    Column("SKILL_DESCRIPTION", String(255), key="skillDescription"),
    Column("SKILL_TYPE", Integer, nullable=False, key="skillType"),
    Column("SKILL_LEVEL_TYPE", Integer, nullable=False, key="skillLevelType"),
    Column("SUB_SKILLS_JSON", Text, key="subSkillsJson"),
    Column("RULE_CONTENT", Text, nullable=False, key="ruleContent"),
    Column("ENABLED", Integer, nullable=False, key="enabled"),
    Column("CREATE_USER_ID", BigInteger, key="createUserId"),
    Column("CREATE_USER_NAME", String(55), key="createUserName"),
    Column("CREATE_TIME", String(55), key="createTime"),
    Column("UPDATE_USER_ID", BigInteger, key="updateUserId"),
    Column("UPDATE_USER_NAME", String(55), key="updateUserName"),
    Column("UPDATE_TIME", String(55), key="updateTime"),
)
