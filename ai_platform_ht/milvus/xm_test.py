import logging
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from typing import List, Dict, Any
from pymilvus import FieldSchema, DataType
from utils.milvus_utils import create_milvus_collection, upsert_into_collection, search_collection, query_collection, delete_from_collection
from utils.ai_utils import get_embeddings, rerank_documents
from api.endpoints.hdxx.modular.hdxx import Hdxx
from core.config import yaml_config

logger = logging.getLogger(__name__)

COLLECTION_NAME = "ttxz_hdxx"

def setup_collection():
    """
    建立活动信息的 Milvus 集合
    """
    milvus_config = yaml_config.get("milvus_settings", {})
    vector_dim = milvus_config.get("vector_dim", 1536) # text-embedding-v4 默认维度是 1536
    
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, description="主键ID(与数据库一致)"),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512, description="活动标题"),
        FieldSchema(name="sourceName", dtype=DataType.VARCHAR, max_length=512, description="数据来源"),
        FieldSchema(name="version", dtype=DataType.INT64, description="数据版本号(对接Milvus)"),
        FieldSchema(name="full_text", dtype=DataType.VARCHAR, max_length=65535, description="拼接的完整文本"),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=vector_dim, description="文本向量")
    ]
    
    collection = create_milvus_collection(
        collection_name=COLLECTION_NAME,
        fields=fields,
        description="活动信息向量集合"
    )
    logger.info(f"成功初始化 Milvus 集合: {COLLECTION_NAME}")
    return collection

def build_hdxx_text(hdxx: Hdxx) -> str:
    """
    将活动信息字段拼接成供向量化的字符串
    """
    parts = []
    if hdxx.title: parts.append(f"活动标题: {hdxx.title}")
    if hdxx.sourceName: parts.append(f"数据来源: {hdxx.sourceName}")
    if hdxx.addTime: parts.append(f"添加时间: {hdxx.addTime}")
    if hdxx.activityContent: parts.append(f"活动内容: {hdxx.activityContent}")
    
    # 截取防止超出长度限制
    return ", ".join(parts)[:65535]

def sync_hdxx(hdxx_list: List[Hdxx]):
    """
    同步集合：将活动数据批量同步到 Milvus 集合
    逻辑：根据 id 查询 Milvus 中的 version，如果存在且 version 一致，则跳过；否则进行向量化并更新/插入。
    """
    if not hdxx_list:
        return
        
    ids = [item.id for item in hdxx_list]
    setup_collection()
    
    milvus_versions = {}
    batch_size = 1000
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        expr = f"id in {batch_ids}"
        existing_data = query_collection(COLLECTION_NAME, expr=expr, output_fields=["id", "version"])
        for item in existing_data:
            milvus_versions[item["id"]] = item.get("version", -1)
            
    items_to_sync = []
    processed_ids = set()
    
    for item in hdxx_list:
        if item.id in processed_ids:
            continue
            
        processed_ids.add(item.id)
        current_version = item.version or 0
        milvus_version = milvus_versions.get(item.id)
        
        if milvus_version is None or milvus_version != current_version:
            items_to_sync.append(item)
            
    if not items_to_sync:
        logger.info("所有活动数据均为最新版本，无需同步。")
        return
        
    logger.info(f"需要同步的活动数量: {len(items_to_sync)}")
    
    sync_ids = []
    titles = []
    source_names = []
    versions = []
    full_texts = []
    
    for item in items_to_sync:
        sync_ids.append(item.id)
        titles.append(item.title or "")
        source_names.append(item.sourceName or "")
        versions.append(item.version or 0)
        full_texts.append(build_hdxx_text(item))
        
    vectors = get_embeddings(full_texts)
    
    data = [
        sync_ids,
        titles,
        source_names,
        versions,
        full_texts,
        vectors
    ]
    
    upsert_into_collection(COLLECTION_NAME, data)
    logger.info(f"成功同步 {len(items_to_sync)} 条活动数据到集合 {COLLECTION_NAME}")

def delete_hdxx_from_milvus(ids: List[int]):
    """
    从 Milvus 集合中删除指定的活动向量
    """
    if not ids:
        return
    try:
        expr = f"id in {ids}"
        delete_from_collection(COLLECTION_NAME, expr)
        logger.info(f"成功从集合 {COLLECTION_NAME} 删除活动向量: {ids}")
    except Exception as e:
        logger.error(f"从 Milvus 删除活动向量失败: {e}")

def recall(query: str, top_k: int = 5, score_threshold: float = 0.5) -> List[Dict[str, Any]]:
    """
    问题召回：通过用户提问召回相关的活动信息
    """
    query_vector = get_embeddings([query])[0]
    recall_limit = max(top_k * 3, 20)
    search_results = search_collection(
        collection_name=COLLECTION_NAME,
        vector_field="vector",
        query_vectors=[query_vector],
        limit=recall_limit,
        output_fields=["id", "title", "sourceName", "full_text"]
    )
    
    if not search_results or not search_results[0]:
        return []
        
    hits = search_results[0]
    documents = []
    hit_map = {}
    
    for hit in hits:
        text = hit.entity.get("full_text")
        documents.append(text)
        hit_map[text] = {
            "id": hit.entity.get("id"),
            "title": hit.entity.get("title"),
            "sourceName": hit.entity.get("sourceName"),
            "full_text": text,
            "vector_distance": hit.distance
        }
        
    rerank_results = rerank_documents(query, documents, top_n=top_k)
    
    final_results = []
    for item in rerank_results:
        score = item.get("relevance_score", 0.0)
        if score < score_threshold:
            continue
            
        idx = item.get("index")
        doc_text = documents[idx]
        
        hit_info = hit_map[doc_text]
        hit_info["rerank_score"] = score
        final_results.append(hit_info)
        
    return final_results

async def sync_from_db():
    """
    从数据库查询所有活动数据并同步到 Milvus 集合
    """
    from utils.mysqldb import db_client
    from api.endpoints.hdxx.sql.tables import hdxx_table
    from sqlalchemy import select
    
    await db_client.init_pool()
    try:
        query = select(hdxx_table).where(
            hdxx_table.c.removed == 0,
            hdxx_table.c.enabled == 1
        )
        
        logger.info("正在从数据库查询活动数据...")
        rows = await db_client.fetch_all(query)
        
        if not rows:
            logger.info("未查询到需要同步的活动数据。")
            return
            
        logger.info(f"成功查询到 {len(rows)} 条活动数据，准备开始同步...")
        
        items = [Hdxx(**row) for row in rows]
        sync_hdxx(items)
        
    finally:
        await db_client.close_pool()

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.info("启动活动数据同步脚本...")
    asyncio.run(sync_from_db())
