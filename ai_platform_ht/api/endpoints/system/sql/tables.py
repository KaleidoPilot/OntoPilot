from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table, Text


metadata = MetaData()

model_config_table = Table(
    "MODEL_CONFIG",
    metadata,
    Column("ID", Integer, primary_key=True, key="id"),
    Column("ORG_ID", BigInteger, nullable=False, key="orgId"),
    Column("MODEL", String(255), nullable=False, key="model"),
    Column("API_KEY", String(512), nullable=False, key="apiKey"),
    Column("BASE_URL", String(500), nullable=False, key="baseUrl"),
    Column("TYPE", Integer, nullable=False, key="type"),
    Column("ENABLED", Integer, nullable=False, key="enabled"),
    Column("REMOVED", Integer, nullable=False, key="removed"),
    Column("CREATE_USER_ID", Integer, key="createUserId"),
    Column("CREATE_USER_NAME", String(55), key="createUserName"),
    Column("CREATE_TIME", String(55), key="createTime"),
    Column("UPDATE_USER_ID", Integer, key="updateUserId"),
    Column("UPDATE_USER_NAME", String(55), key="updateUserName"),
    Column("UPDATE_TIME", String(55), key="updateTime"),
)


system_config_table = Table(
    "SYSTEM_CONFIG",
    metadata,
    Column("ID", BigInteger, primary_key=True, key="id"),
    Column("ORG_ID", BigInteger, nullable=False, key="orgId"),
    Column("CONFIG_TYPE", Integer, nullable=False, key="configType"),
    Column("CONFIG_NAME", String(100), nullable=False, key="configName"),
    Column("CONFIG_JSON", Text, nullable=False, key="configJson"),
    Column("ENABLED", Integer, nullable=False, key="enabled"),
    Column("REMOVED", Integer, nullable=False, key="removed"),
    Column("CREATE_USER_ID", BigInteger, key="createUserId"),
    Column("CREATE_USER_NAME", String(55), key="createUserName"),
    Column("CREATE_TIME", String(55), key="createTime"),
    Column("UPDATE_USER_ID", BigInteger, key="updateUserId"),
    Column("UPDATE_USER_NAME", String(55), key="updateUserName"),
    Column("UPDATE_TIME", String(55), key="updateTime"),
)
