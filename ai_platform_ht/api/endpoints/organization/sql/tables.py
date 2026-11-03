from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table


metadata = MetaData()

organization_table = Table(
    "ORGANIZATION",
    metadata,
    Column("ID", BigInteger, primary_key=True, key="id"),
    Column("ORG_CODE", String(64), nullable=False, key="orgCode"),
    Column("NAME", String(255), nullable=False, key="name"),
    Column("REMARKS", String(500), key="remarks"),
    Column("ENABLED", Integer, nullable=False, key="enabled"),
    Column("REMOVED", Integer, nullable=False, key="removed"),
    Column("CREATE_USER_ID", BigInteger, key="createUserId"),
    Column("CREATE_USER_NAME", String(55), key="createUserName"),
    Column("CREATE_TIME", String(55), key="createTime"),
    Column("UPDATE_USER_ID", BigInteger, key="updateUserId"),
    Column("UPDATE_USER_NAME", String(55), key="updateUserName"),
    Column("UPDATE_TIME", String(55), key="updateTime"),
)
