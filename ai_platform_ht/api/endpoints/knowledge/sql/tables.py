from sqlalchemy import BigInteger, Column, DateTime, Integer, MetaData, String, Table, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT


metadata = MetaData()

knowledge_folder_table = Table(
    'AI_KNOWLEDGE_FOLDER', metadata,
    Column('ID', BigInteger, primary_key=True, key='id'),
    Column('ORG_ID', BigInteger, nullable=False, key='orgId'),
    Column('TENANT_ID', BigInteger, nullable=False, key='tenantId'),
    Column('PARENT_ID', BigInteger, nullable=False, server_default='0', key='parentId'),
    Column('FOLDER_NAME', String(100), nullable=False, key='folderName'),
    Column('DOCUMENT_KEY', String(64), nullable=True, key='documentKey'),
    Column('CREATE_USER_ID', BigInteger, key='createUserId'), Column('CREATE_USER_NAME', String(55), key='createUserName'),
    Column('CREATE_TIME', String(55), key='createTime'), Column('UPDATE_USER_ID', BigInteger, key='updateUserId'),
    Column('UPDATE_USER_NAME', String(55), key='updateUserName'), Column('UPDATE_TIME', String(55), key='updateTime'),
)

knowledge_graph_table = Table(
    'AI_KNOWLEDGE_GRAPH', metadata,
    Column('ID', BigInteger, primary_key=True, key='id'),
    Column('ORG_ID', BigInteger, nullable=False, key='orgId'),
    Column('TENANT_ID', BigInteger, nullable=False, key='tenantId'),
    Column('FOLDER_ID', BigInteger, nullable=False, server_default='0', key='folderId'),
    Column('STATUS', String(20), nullable=False, key='status'),
    Column('FINGERPRINT', String(64), nullable=False, key='fingerprint'),
    Column('DOCUMENT_JSON', MEDIUMTEXT, nullable=False, key='documentJson'), Column('GRAPH_JSON', MEDIUMTEXT, key='graphJson'),
    Column('ERROR_MESSAGE', String(300), key='errorMessage'),
    Column('CREATE_TIME', DateTime, nullable=False, key='createTime'), Column('UPDATE_TIME', DateTime, nullable=False, key='updateTime'),
)

knowledge_tenant_table = Table(
    "AI_TENANT",
    metadata,
    Column("ID", BigInteger, primary_key=True, key="id"),
    Column("ORG_ID", BigInteger, nullable=False, key="orgId"),
    Column("SCOPE_TYPE", Integer, nullable=False, key="scopeType"),
    Column("OWNER_USER_ID", BigInteger, key="ownerUserId"),
    Column("ACCESS_USER_IDS", String(4000), key="accessUserIds"),
    Column("ACCESS_GROUP_IDS", String(4000), key="accessGroupIds"),
    Column("TENANT_NAME", String(255), nullable=False, key="tenantName"),
    Column("REMARKS", String(500), key="remarks"),
    Column("ENABLED", Integer, nullable=False, key="enabled"),
    Column("REMOVED", Integer, nullable=False, key="removed"),
    Column("CREATE_USER_ID", BigInteger, key="createUserId"),
    Column("CREATE_TIME", DateTime, nullable=False, key="createTime"),
    Column("UPDATE_TIME", DateTime, nullable=False, key="updateTime"),
)

knowledge_record_table = Table(
    "AI_KNOWLEDGE",
    metadata,
    Column("ID", BigInteger, primary_key=True, key="id"),
    Column("TITLE", String(255), key="title"),
    Column("CONTENT", Text, key="content"),
    Column("FILE_URL", String(300), key="fileUrl"),
    Column("FILE_ID", String(255), key="fileId"),
    Column("VERSION", Integer, key="version"),
    Column("TYPE", Integer, nullable=False, key="type"),
    Column("TENANT", String(255), key="tenant"),
    Column("TENANT_ID", BigInteger, key="tenantId"),
    Column("FOLDER_ID", BigInteger, nullable=False, server_default='0', key="folderId"),
    Column("ENABLED", Integer, key="enabled"),
    Column("REMOVED", Integer, key="removed"),
    Column("CREATE_USER_ID", Integer, key="createUserId"),
    Column("CREATE_USER_NAME", String(255), key="createUserName"),
    Column("CREATE_TIME", String(255), key="createTime"),
    Column("UPDATE_USER_ID", Integer, key="updateUserId"),
    Column("UPDATE_USER_NAME", String(255), key="updateUserName"),
    Column("UPDATE_TIME", String(255), key="updateTime"),
)
