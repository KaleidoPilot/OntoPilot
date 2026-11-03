from sqlalchemy import Table, Column, Integer, String, Float, DateTime, Date, MetaData

metadata = MetaData()

ai_table = Table(
    'AI_QUESTION_RECORD', metadata,
    Column('ID', Integer, primary_key=True, key='id'),
    Column('USER_QUESTION', String, key='userQuestion'),
    Column('VECTOR_RECALL_RESULT', String, key='vectorRecallResult'),
    Column('INTENT_DBNAME', String, key='intentDbname'),
    Column('ENABLED', Integer, key='enabled'),
    Column('REMOVED', Integer, key='removed'),
    Column('CREATE_USER_ID', Integer, key='createUserId'),
    Column('CREATE_USER_NAME', String, key='createUserName'),
    Column('CREATE_TIME', String, key='createTime'),
    Column('UPDATE_USER_ID', Integer, key='updateUserId'),
    Column('UPDATE_USER_NAME', String, key='updateUserName'),
    Column('UPDATE_TIME', String, key='updateTime')
)
