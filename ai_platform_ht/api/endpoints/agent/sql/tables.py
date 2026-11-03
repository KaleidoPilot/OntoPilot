from sqlalchemy import Table, Column, Integer, String, Float, DateTime, Date, MetaData, BigInteger

metadata = MetaData()

agent_table = Table(
    'AI_AGENT', metadata,
    Column('ID', Integer, primary_key=True, key='id'),
    Column('ORG_ID', BigInteger, key='orgId'),
    Column('AGENT_TYPE', Integer, key='agentType'),
    Column('USER_ID', BigInteger, key='userId'),
    Column('SHARE_USER_IDS', String, key='shareUserIds'),
    Column('MCP_IDS', String, key='mcpIds'),
    Column('AGENT_NAME', String, key='agentName'),
    Column('SKILL_IDS', String, key='skillIds'),
    Column('TEMPLATE_IDS', String, key='templateIds'),
    Column('AGENT_DESCRIPTION', String, key='agentDescription'),
    Column('SYSTEM_PROMPT', String, key='systemPrompt'),
    Column('USER_PROMPT_TEMPLATE', String, key='userPromptTemplate'),
    Column('TEMPERATURE', Float, key='temperature'),
    Column('TOP_P', Float, key='topP'),
    Column('KEY', String, key='key'),
    Column('INTENT_LLM_ID', Integer, key='intentLlmId'),
    Column('TASK_LLM_ID', Integer, key='taskLlmId'),
    Column('EXECUT_LLM_ID', Integer, key='executLlmId'),
    Column('SUMMARY_LLM_ID', Integer, key='summaryLlmId'),
    Column('TENANT_IDS', String, key='tenantIds'),
    Column('TENANT_TOP_K', Integer, key='tenantTopK'),
    Column('TENANT_SCORE', Float, key='tenantScore'),
    Column('ENABLED', Integer, key='enabled'),
    Column('REMOVED', Integer, key='removed'),
    Column('CREATE_USER_ID', Integer, key='createUserId'),
    Column('CREATE_USER_NAME', String, key='createUserName'),
    Column('CREATE_TIME', String, key='createTime'),
    Column('UPDATE_USER_ID', Integer, key='updateUserId'),
    Column('UPDATE_USER_NAME', String, key='updateUserName'),
    Column('UPDATE_TIME', String, key='updateTime')
)

agent_share_table = Table(
    'AGENT_SHARE', metadata,
    Column('ID', BigInteger, primary_key=True, key='id'),
    Column('ORG_ID', BigInteger, nullable=False, key='orgId'),
    Column('AGENT_ID', Integer, nullable=False, key='agentId'),
    Column('SHARE_USER_ID', BigInteger, nullable=False, key='shareUserId'),
    Column('RECEIVE_USER_ID', BigInteger, nullable=False, key='receiveUserId'),
    Column('ENABLED', Integer, nullable=False, key='enabled'),
    Column('CREATE_TIME', DateTime, nullable=False, key='createTime'),
    Column('UPDATE_TIME', DateTime, nullable=False, key='updateTime'),
)
