from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table

metadata = MetaData()

user_table = Table(
    'USER_INFO', metadata,
    Column('ID', Integer, primary_key=True, key='id'),
    Column('REAL_NAME', String, key='realName'),
    Column('ACCOUNT', String, key='account'),
    Column('PASSWORD', String, key='password'),
    Column('PHONE', String, key='phone'),
    Column('DEPT_NAME', String, key='deptName'),
    Column('DEPT_LEVEL', Integer, nullable=False, key='deptLevel'),
    Column('ORG_ID', BigInteger, nullable=True, key='orgId'),
    Column('REMARKS', String, key='remarks'),
    Column('ENABLED', Integer, key='enabled'),
    Column('REMOVED', Integer, key='removed'),
    Column('CREATE_USER_ID', Integer, key='createUserId'),
    Column('CREATE_USER_NAME', String, key='createUserName'),
    Column('CREATE_TIME', String, key='createTime'),
    Column('UPDATE_USER_ID', Integer, key='updateUserId'),
    Column('UPDATE_USER_NAME', String, key='updateUserName'),
    Column('UPDATE_TIME', String, key='updateTime')
)

user_group_table = Table(
    "USER_GROUP", metadata,
    Column("ID", BigInteger, primary_key=True, key="id"),
    Column("ORG_ID", BigInteger, nullable=False, key="orgId"),
    Column("GROUP_NAME", String(100), nullable=False, key="groupName"),
    Column("AGENT_ID", String(1000), nullable=False, key="agentId"),
    Column("REMARKS", String(500), key="remarks"),
    Column("ENABLED", Integer, nullable=False, key="enabled"),
    Column("CREATE_USER_ID", BigInteger, key="createUserId"),
    Column("CREATE_USER_NAME", String(55), key="createUserName"),
    Column("CREATE_TIME", String(55), key="createTime"),
    Column("UPDATE_USER_ID", BigInteger, key="updateUserId"),
    Column("UPDATE_USER_NAME", String(55), key="updateUserName"),
    Column("UPDATE_TIME", String(55), key="updateTime"),
)

external_user_table = Table(
    "USER_INFO_WB", metadata,
    Column("ID", BigInteger, primary_key=True, key="id"),
    Column("GROUP_ID", BigInteger, nullable=False, key="groupId"),
    Column("REAL_NAME", String(55), nullable=False, key="realName"),
    Column("ACCOUNT", String(55), nullable=False, key="account"),
    Column("PASSWORD", String(128), nullable=False, key="password"),
    Column("PHONE", String(32), key="phone"),
    Column("REMARKS", String(500), key="remarks"),
    Column("ENABLED", Integer, nullable=False, key="enabled"),
    Column("CREATE_USER_ID", BigInteger, key="createUserId"),
    Column("CREATE_USER_NAME", String(55), key="createUserName"),
    Column("CREATE_TIME", String(55), key="createTime"),
    Column("UPDATE_USER_ID", BigInteger, key="updateUserId"),
    Column("UPDATE_USER_NAME", String(55), key="updateUserName"),
    Column("UPDATE_TIME", String(55), key="updateTime"),
)
