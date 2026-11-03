import warnings
from pymilvus import connections, CollectionSchema, DataType, Collection, utility
from core.config import yaml_config

# 忽略 PyMilvus 3.1 废弃 ORM 接口的警告
warnings.filterwarnings("ignore", category=UserWarning, module="pymilvus")

def connect_milvus():
    """连接到 Milvus 数据库"""
    milvus_config = yaml_config.get("milvus_settings", {})
    host = milvus_config.get("host", "127.0.0.1")
    port = milvus_config.get("port", 19530)
    db_name = milvus_config.get("db_name", "default")
    
    # 建立连接
    if not connections.has_connection("default"):
        connections.connect("default", host=host, port=port, db_name=db_name)

def create_milvus_collection(collection_name: str, fields: list, description: str = "") -> Collection:
    """
    通用方法：创建 Milvus 集合
    :param collection_name: 集合名称
    :param fields: FieldSchema 列表
    :param description: 集合描述
    """
    connect_milvus()
    
    schema = CollectionSchema(fields=fields, description=description, enable_dynamic_field=True)
    
    if utility.has_collection(collection_name):
        collection = Collection(collection_name)
        return collection
    
    collection = Collection(name=collection_name, schema=schema)
    
    # 查找向量字段，自动创建索引
    vector_field = None
    for f in fields:
        if f.dtype in [DataType.FLOAT_VECTOR, DataType.BINARY_VECTOR]:
            vector_field = f.name
            break
            
    if vector_field:
        milvus_config = yaml_config.get("milvus_settings", {})
        index_type = milvus_config.get("index_type", "IVF_FLAT")
        nlist = milvus_config.get("index_params", {}).get("nlist", 1000)
        
        index_params = {
            "metric_type": "COSINE", # text-embedding-v4 通常推荐 COSINE
            "index_type": index_type,
            "params": {"nlist": nlist}
        }
        collection.create_index(field_name=vector_field, index_params=index_params)
        
    return collection

def insert_into_collection(collection_name: str, data: list):
    """
    通用方法：插入数据到指定集合
    """
    connect_milvus()
    collection = Collection(collection_name)
    result = collection.insert(data)
    collection.flush()
    return result

def upsert_into_collection(collection_name: str, data: list):
    """
    通用方法：更新或插入数据到指定集合
    注意：Upsert 要求主键必须存在，且该集合必须支持 Upsert（不能有 auto_id=True）
    """
    connect_milvus()
    collection = Collection(collection_name)
    result = collection.upsert(data)
    collection.flush()
    return result

def query_collection(collection_name: str, expr: str, output_fields: list = None):
    """
    通用方法：通过表达式查询集合中的数据（标量查询）
    """
    connect_milvus()
    collection = Collection(collection_name)
    collection.load()
    
    results = collection.query(
        expr=expr,
        output_fields=output_fields
    )
    return results

def delete_from_collection(collection_name: str, expr: str):
    """
    通用方法：通过表达式删除集合中的数据
    """
    connect_milvus()
    collection = Collection(collection_name)
    result = collection.delete(expr)
    collection.flush()
    return result

def search_collection(collection_name: str, vector_field: str, query_vectors: list, limit: int = 10, output_fields: list = None, expr: str = None):
    """
    通用方法：在指定集合中进行向量检索
    """
    connect_milvus()
    collection = Collection(collection_name)
    collection.load()
    
    search_params = {
        "metric_type": "COSINE",
        "params": {"nprobe": 10}
    }
    
    results = collection.search(
        data=query_vectors,
        anns_field=vector_field,
        param=search_params,
        limit=limit,
        expr=expr,
        output_fields=output_fields
    )
    return results
