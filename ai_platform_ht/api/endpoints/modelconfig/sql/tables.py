from sqlalchemy import Table, Column, Integer, String, Float, DateTime, Date, MetaData

metadata = MetaData()

modelconfig_table = Table(
    'MODEL_CONFIG', metadata,
    Column('ID', Integer, primary_key=True, key='id'),
    Column('MODEL', String, key='model'),
    Column('API_KEY', String, key='apiKey'),
    Column('BASE_URL', String, key='baseUrl'),
    Column('TYPE', Integer, key='type'),
    Column('ENABLED', Integer, key='enabled'),
    Column('REMOVED', Integer, key='removed'),
    Column('CREATE_USER_ID', Integer, key='createUserId'),
    Column('CREATE_USER_NAME', String, key='createUserName'),
    Column('CREATE_TIME', String, key='createTime'),
    Column('UPDATE_USER_ID', Integer, key='updateUserId'),
    Column('UPDATE_USER_NAME', String, key='updateUserName'),
    Column('UPDATE_TIME', String, key='updateTime')
)
