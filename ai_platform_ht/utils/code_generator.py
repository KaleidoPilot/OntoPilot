import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到 sys.path，以便能够导入 core.config
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, MetaData, Table
from core.config import yaml_config

def to_camel_case(snake_str):
    components = snake_str.lower().split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

def to_pascal_case(snake_str):
    components = snake_str.lower().split('_')
    return ''.join(x.title() for x in components)

def get_db_url():
    db_settings = yaml_config.get("database_settings", {})
    mysql_config = db_settings.get("mysql", {})
    host = mysql_config.get("host", "127.0.0.1")
    port = mysql_config.get("port", 3306)
    user = mysql_config.get("user", "root")
    password = mysql_config.get("password", "")
    db = mysql_config.get("db", "")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"

def generate(table_name: str, module_name: str, milvus_prefix: str = None):
    print(f"Connecting to database to reflect table: {table_name}...")
    engine = create_engine(get_db_url())
    metadata = MetaData()
    try:
        table = Table(table_name, metadata, autoload_with=engine)
    except Exception as e:
        print(f"❌ Failed to load table '{table_name}': {e}")
        return
    
    snake_name = module_name.lower()
    pascal_name = to_pascal_case(snake_name)
    
    # 查找主键
    pk_key = "id"
    for c in table.columns:
        if c.primary_key:
            pk_key = to_camel_case(c.name)
            break
            
    # 检查是否包含 version 字段 (Milvus 需要)
    has_version = False
    for c in table.columns:
        if to_camel_case(c.name) == "version":
            has_version = True
            break
            
    if milvus_prefix and not has_version:
        print(f"⚠️ 警告: 表 '{table_name}' 中未找到 'version' 字段。Milvus 同步需要此字段。")
    
    # 创建目录结构
    base_dir = Path(__file__).resolve().parent.parent / "api" / "endpoints" / snake_name
    api_dir = base_dir / "api"
    modular_dir = base_dir / "modular"
    sql_dir = base_dir / "sql"
    milvus_dir = Path(__file__).resolve().parent.parent / "milvus"
    
    for d in [base_dir, api_dir, modular_dir, sql_dir]:
        d.mkdir(parents=True, exist_ok=True)
        init_file = d / "__init__.py"
        if not init_file.exists():
            init_file.write_text("")
            
    if milvus_prefix:
        milvus_dir.mkdir(parents=True, exist_ok=True)
            
    # ==========================================
    # 1. 生成 modular 模型文件
    # ==========================================
    fields = []
    for c in table.columns:
        if c.primary_key:
            continue
        camel_name = to_camel_case(c.name)
        py_type = "str"
        ctype_str = str(c.type).upper()
        if "INT" in ctype_str:
            py_type = "int"
        elif "FLOAT" in ctype_str or "DECIMAL" in ctype_str or "DOUBLE" in ctype_str:
            py_type = "float"
        
        desc = (c.comment or c.name).replace('"', "'")
        fields.append(f'    {camel_name}: Optional[{py_type}] = Field(None, description="{desc}")')
    
    fields_str = "\n".join(fields)
    
    modular_content = f'''from pydantic import BaseModel, Field
from typing import Optional

class {pascal_name}Base(BaseModel):
{fields_str}

class {pascal_name}Create({pascal_name}Base):
    pass

class {pascal_name}Update({pascal_name}Base):
    {pk_key}: int = Field(..., description="主键")

class {pascal_name}({pascal_name}Base):
    {pk_key}: int = Field(..., description="主键")

class {pascal_name}Response({pascal_name}):
    pass

class {pascal_name}QueryRequest({pascal_name}Base):
    pageNo: int = Field(1, description="当前页码")
    pageSize: int = Field(10, description="每页条数")
'''
    with open(modular_dir / f"{snake_name}.py", "w", encoding="utf-8") as f:
        f.write(modular_content)
        
    # ==========================================
    # 2. 生成 sql/tables.py
    # ==========================================
    cols = []
    for c in table.columns:
        camel_key = to_camel_case(c.name)
        ctype_str = str(c.type).upper()
        col_type = "String"
        if "INT" in ctype_str:
            col_type = "Integer"
        elif "FLOAT" in ctype_str or "DECIMAL" in ctype_str or "DOUBLE" in ctype_str:
            col_type = "Float"
        elif "DATETIME" in ctype_str or "TIMESTAMP" in ctype_str:
            col_type = "DateTime"
        elif "DATE" in ctype_str:
            col_type = "Date"
            
        pk_str = ", primary_key=True" if c.primary_key else ""
        cols.append(f"    Column('{c.name}', {col_type}{pk_str}, key='{camel_key}')")
    
    columns_str = ",\n".join(cols)
    
    sql_content = f'''from sqlalchemy import Table, Column, Integer, String, Float, DateTime, Date, MetaData

metadata = MetaData()

{snake_name}_table = Table(
    '{table_name}', metadata,
{columns_str}
)
'''
    with open(sql_dir / "tables.py", "w", encoding="utf-8") as f:
        f.write(sql_content)
        
    # ==========================================
    # 3. 生成 milvus/{milvus_prefix}_{snake_name}.py (如果需要)
    # ==========================================
    if milvus_prefix:
        milvus_content = f'''import logging
import asyncio
from typing import List, Dict, Any
from pymilvus import FieldSchema, DataType
from utils.milvus_utils import create_milvus_collection, upsert_into_collection, search_collection, query_collection, delete_from_collection
from utils.ai_utils import get_embeddings, rerank_documents
from api.endpoints.{snake_name}.modular.{snake_name} import {pascal_name}
from core.config import yaml_config

logger = logging.getLogger(__name__)

COLLECTION_NAME = "{milvus_prefix}_{snake_name}"

def setup_collection():
    """
    建立 {module_name} 的 Milvus 集合
    """
    milvus_config = yaml_config.get("milvus_settings", {{}})
    vector_dim = milvus_config.get("vector_dim", 1536)
    
    fields = [
        FieldSchema(name="{pk_key}", dtype=DataType.INT64, is_primary=True, description="主键ID(与数据库一致)"),
        FieldSchema(name="version", dtype=DataType.INT64, description="数据版本号(对接Milvus)"),
        FieldSchema(name="full_text", dtype=DataType.VARCHAR, max_length=4096, description="拼接的完整文本"),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=vector_dim, description="文本向量")
    ]
    
    collection = create_milvus_collection(
        collection_name=COLLECTION_NAME,
        fields=fields,
        description="{module_name} 向量集合"
    )
    logger.info(f"成功初始化 Milvus 集合: {{COLLECTION_NAME}}")
    return collection

def build_{snake_name}_text(record: {pascal_name}) -> str:
    """
    将字段拼接成供向量化的字符串
    """
    parts = []
'''
        # 基础字段过滤列表
        EXCLUDED_FIELDS = [
            pk_key, "version", "createTime", "updateTime", "removed", "enabled", 
            "createBy", "updateBy", "createUserId", "createUserName", "updateUserId", "updateUserName"
        ]
        
        for c in table.columns:
            camel_name = to_camel_case(c.name)
            if camel_name in EXCLUDED_FIELDS:
                continue
            desc = (c.comment or c.name).replace('"', "'")
            milvus_content += f'    if record.{camel_name}: parts.append(f"{desc}: {{record.{camel_name}}}")\n'

        milvus_content += f'''    
    return ", ".join(parts)

async def _sync_worker(worker_id: int, queue: asyncio.Queue, results: list):
    """
    向量化同步 worker 协程
    """
    while True:
        try:
            batch_records = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        try:
            ids = []
            versions = []
            full_texts = []
            
            for record in batch_records:
                ids.append(getattr(record, '{pk_key}'))
                versions.append(record.version or 0)
                full_texts.append(build_{snake_name}_text(record))
                
            vectors = await asyncio.to_thread(get_embeddings, full_texts)
            
            data = [
                ids,
                versions,
                full_texts,
                vectors
            ]
            
            await asyncio.to_thread(upsert_into_collection, COLLECTION_NAME, data)
            results.append(len(batch_records))
            
            await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"[Sync-Worker-{{worker_id}}] 同步批次失败: {{str(e)}}")
        finally:
            queue.task_done()

def sync_{snake_name}(records: List[{pascal_name}]):
    """
    同步集合
    """
    if not records:
        return
        
    record_ids = [getattr(record, '{pk_key}') for record in records]
    
    setup_collection()
    
    milvus_versions = {{}}
    batch_size = 1000
    for i in range(0, len(record_ids), batch_size):
        batch_ids = record_ids[i:i + batch_size]
        expr = f"{pk_key} in {{batch_ids}}"
        existing_data = query_collection(COLLECTION_NAME, expr=expr, output_fields=["{pk_key}", "version"])
        for item in existing_data:
            milvus_versions[item["{pk_key}"]] = item.get("version", -1)
    
    records_to_sync = []
    processed_ids = set()
    
    for record in records:
        rid = getattr(record, '{pk_key}')
        if rid in processed_ids:
            continue
            
        processed_ids.add(rid)
        current_version = record.version or 0
        milvus_version = milvus_versions.get(rid)
        
        if milvus_version is None or milvus_version != current_version:
            records_to_sync.append(record)
            
    if not records_to_sync:
        logger.info("所有数据均为最新版本，无需同步。")
        return
        
    logger.info(f"需要同步的数据数量: {{len(records_to_sync)}}")
    
    ids = []
    versions = []
    full_texts = []
    
    for record in records_to_sync:
        ids.append(getattr(record, '{pk_key}'))
        versions.append(record.version or 0)
        full_texts.append(build_{snake_name}_text(record))
        
    vectors = get_embeddings(full_texts)
    
    data = [
        ids,
        versions,
        full_texts,
        vectors
    ]
    
    upsert_into_collection(COLLECTION_NAME, data)
    logger.info(f"成功同步 {{len(records_to_sync)}} 条数据到集合 {{COLLECTION_NAME}}")

async def sync_{snake_name}_async(records: List[{pascal_name}]):
    """
    异步并发同步集合
    """
    if not records:
        return
        
    record_ids = [getattr(record, '{pk_key}') for record in records]
    
    await asyncio.to_thread(setup_collection)
    
    milvus_versions = {{}}
    batch_size = 1000
    for i in range(0, len(record_ids), batch_size):
        batch_ids = record_ids[i:i + batch_size]
        expr = f"{pk_key} in {{batch_ids}}"
        existing_data = await asyncio.to_thread(query_collection, COLLECTION_NAME, expr=expr, output_fields=["{pk_key}", "version"])
        for item in existing_data:
            milvus_versions[item["{pk_key}"]] = item.get("version", -1)
    
    records_to_sync = []
    processed_ids = set()
    
    for record in records:
        rid = getattr(record, '{pk_key}')
        if rid in processed_ids:
            continue
            
        processed_ids.add(rid)
        current_version = record.version or 0
        milvus_version = milvus_versions.get(rid)
        
        if milvus_version is None or milvus_version != current_version:
            records_to_sync.append(record)
            
    if not records_to_sync:
        logger.info("所有数据均为最新版本，无需同步。")
        return
        
    logger.info(f"需要异步并发同步的数据数量: {{len(records_to_sync)}}")
    
    chunk_size = 20
    queue = asyncio.Queue()
    for i in range(0, len(records_to_sync), chunk_size):
        queue.put_nowait(records_to_sync[i:i + chunk_size])
        
    results = []
    workers = [
        asyncio.create_task(_sync_worker(i, queue, results))
        for i in range(100)
    ]
    
    await asyncio.gather(*workers)
    total_synced = sum(results)
    logger.info(f"成功异步并发同步 {{total_synced}} 条数据到集合 {{COLLECTION_NAME}}")

def delete_{snake_name}_from_milvus(record_ids: List[int]):
    if not record_ids:
        return
    try:
        expr = f"{pk_key} in {{record_ids}}"
        delete_from_collection(COLLECTION_NAME, expr)
        logger.info(f"成功从集合 {{COLLECTION_NAME}} 删除向量: {{record_ids}}")
    except Exception as e:
        logger.error(f"从 Milvus 删除向量失败: {{e}}")

def clear_milvus_collection():
    try:
        from pymilvus import utility
        if utility.has_collection(COLLECTION_NAME):
            utility.drop_collection(COLLECTION_NAME)
            logger.info(f"已清空/删除集合: {{COLLECTION_NAME}}")
        setup_collection()
    except Exception as e:
        logger.error(f"清空 Milvus 集合失败: {{e}}")

def recall(query: str, top_k: int = 5, score_threshold: float = 0.5) -> List[Dict[str, Any]]:
    query_vector = get_embeddings([query])[0]
    
    recall_limit = max(top_k * 3, 20)
    search_results = search_collection(
        collection_name=COLLECTION_NAME,
        vector_field="vector",
        query_vectors=[query_vector],
        limit=recall_limit,
        output_fields=["{pk_key}", "full_text"]
    )
    
    if not search_results or not search_results[0]:
        return []
        
    hits = search_results[0]
    documents = []
    hit_map = {{}}
    
    for hit in hits:
        text = hit.entity.get("full_text")
        documents.append(text)
        hit_map[text] = {{
            "{pk_key}": hit.entity.get("{pk_key}"),
            "full_text": text,
            "vector_distance": hit.distance
        }}
        
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
    from utils.mysqldb import db_client
    from api.endpoints.{snake_name}.sql.tables import {snake_name}_table
    from sqlalchemy import select
    
    await db_client.init_pool()
    
    try:
        base_query = select({snake_name}_table)
        if hasattr({snake_name}_table.c, 'removed'):
            base_query = base_query.where({snake_name}_table.c.removed == 0)
        if hasattr({snake_name}_table.c, 'enabled'):
            base_query = base_query.where({snake_name}_table.c.enabled == 1)
            
        logger.info("正在从数据库查询数据...")
        rows = await db_client.fetch_all(base_query)
        
        if not rows:
            logger.info("未查询到需要同步的数据。")
            return
            
        logger.info(f"成功查询到 {{len(rows)}} 条数据，准备开始同步...")
        
        records = [{pascal_name}(**row) for row in rows]
        
        sync_{snake_name}(records)
        
    finally:
        await db_client.close_pool()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("启动数据同步脚本...")
    asyncio.run(sync_from_db())
'''
        with open(milvus_dir / f"{milvus_prefix}_{snake_name}.py", "w", encoding="utf-8") as f:
            f.write(milvus_content)

    # ==========================================
    # 4. 生成 api/{module_name}.py
    # ==========================================
    # 生成导入导出字段映射
    field_map_lines = []
    for c in table.columns:
        if c.primary_key:
            continue
        camel_name = to_camel_case(c.name)
        desc = (c.comment or c.name).replace('"', "'")
        field_map_lines.append(f'    "{camel_name}": "{desc}"')
    
    field_map_str = ",\n".join(field_map_lines)

    # =============== API 代码公用模板生成区 ===============
    
    common_querylist = f'''
@router.post("/querylist", response_model=dict, summary="查询列表")
async def query_{snake_name}_list(query: {pascal_name}QueryRequest):
    try:
        base_query = select({snake_name}_table)
        
        # 默认过滤逻辑删除和无效数据
        if hasattr({snake_name}_table.c, 'removed'):
            base_query = base_query.where({snake_name}_table.c.removed == 0)
        if hasattr({snake_name}_table.c, 'enabled'):
            base_query = base_query.where({snake_name}_table.c.enabled == 1)
            
        filter_data = query.model_dump(exclude={{"pageNo", "pageSize"}}, exclude_unset=True, exclude_none=True)
        
        for field, value in filter_data.items():
            if value is not None and value != "":
                column = getattr({snake_name}_table.c, field, None)
                if column is not None:
                    if isinstance(value, str):
                        base_query = base_query.where(column.like(f"%{{value}}%"))
                    else:
                        base_query = base_query.where(column == value)
                        
        count_query = select(func.count()).select_from(base_query.subquery())
        total_records = await db_client.fetch_one(count_query)
        total = list(total_records.values())[0] if total_records else 0
        
        limit = query.pageSize
        offset = (query.pageNo - 1) * query.pageSize
        
        # 默认按创建时间倒序
        if hasattr({snake_name}_table.c, 'createTime'):
            list_query = base_query.order_by(desc({snake_name}_table.c.createTime)).limit(limit).offset(offset)
        else:
            list_query = base_query.limit(limit).offset(offset)
            
        records = await db_client.fetch_all(list_query)
        validated_records = [{pascal_name}Response(**record).model_dump() for record in records]
        
        return success(data={{
            "total": total,
            "list": validated_records,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize
        }})
    except Exception as e:
        return server_error(f"查询失败: {{str(e)}}")
'''
    common_export_download = f'''
@router.get("/downloadTemplate", summary="下载导入模板")
async def download_template_{snake_name}():
    try:
        # 生成空数据，仅包含表头
        df = pd.DataFrame(columns=list({snake_name.upper()}_FIELD_MAP.values()))
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='模板')
        output.seek(0)
        
        filename = quote(f"{pascal_name}导入模板.xlsx")
        headers = {{
            'Content-Disposition': f'attachment; filename="{{filename}}"',
            'Access-Control-Expose-Headers': 'Content-Disposition'
        }}
        return Response(content=output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
    except Exception as e:
        return server_error(f"下载模板失败: {{str(e)}}")

@router.post("/export", summary="导出数据")
async def export_{snake_name}(query: {pascal_name}QueryRequest):
    try:
        base_query = select({snake_name}_table)
        
        if hasattr({snake_name}_table.c, 'removed'):
            base_query = base_query.where({snake_name}_table.c.removed == 0)
        if hasattr({snake_name}_table.c, 'enabled'):
            base_query = base_query.where({snake_name}_table.c.enabled == 1)
            
        filter_data = query.model_dump(exclude={{"pageNo", "pageSize"}}, exclude_unset=True, exclude_none=True)
        
        for field, value in filter_data.items():
            if value is not None and value != "":
                column = getattr({snake_name}_table.c, field, None)
                if column is not None:
                    if isinstance(value, str):
                        base_query = base_query.where(column.like(f"%{{value}}%"))
                    else:
                        base_query = base_query.where(column == value)
                        
        if hasattr({snake_name}_table.c, 'createTime'):
            list_query = base_query.order_by(desc({snake_name}_table.c.createTime))
        else:
            list_query = base_query
            
        records = await db_client.fetch_all(list_query)
        
        export_data = []
        for record in records:
            row = {{}}
            record_dict = dict(record) if not hasattr(record, '_mapping') else dict(record._mapping)
            for field, col_name in {snake_name.upper()}_FIELD_MAP.items():
                row[col_name] = record_dict.get(field)
            export_data.append(row)
            
        df = pd.DataFrame(export_data)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='数据导出')
        output.seek(0)
        
        filename = quote(f"{pascal_name}数据导出_{{datetime.now().strftime('%Y%m%d%H%M%S')}}.xlsx")
        headers = {{
            'Content-Disposition': f'attachment; filename="{{filename}}"',
            'Access-Control-Expose-Headers': 'Content-Disposition'
        }}
        return Response(content=output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
    except Exception as e:
        return server_error(f"导出失败: {{str(e)}}")
'''

    if milvus_prefix:
        # ====== 包含 Milvus 向量化逻辑的模板 ======
        api_content = f'''from fastapi import APIRouter, Depends, UploadFile, File, Response, BackgroundTasks
from sqlalchemy import select, func, desc, insert, update, delete
from utils.response import success, server_error
from utils.mysqldb import db_client
from utils.context import get_current_user, fill_audit_fields
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import pandas as pd
import io
from urllib.parse import quote
from datetime import datetime
import asyncio
import logging

from api.endpoints.{snake_name}.modular.{snake_name} import (
    {pascal_name}, {pascal_name}Response, {pascal_name}QueryRequest, {pascal_name}Create, {pascal_name}Update
)
from api.endpoints.{snake_name}.sql.tables import {snake_name}_table
from milvus.{milvus_prefix}_{snake_name} import sync_{snake_name}, sync_{snake_name}_async, delete_{snake_name}_from_milvus, clear_milvus_collection, recall, sync_from_db

logger = logging.getLogger(__name__)

router = APIRouter()

# 字段映射配置，用于导入导出和模板下载
{snake_name.upper()}_FIELD_MAP = {{
{field_map_str}
}}

class DeleteRequest(BaseModel):
    {pk_key}: int

class RecallRequest(BaseModel):
    query: str = Field(..., description="用户的提问文本")
    top_k: int = Field(5, description="召回结果数量")
    score_threshold: float = Field(0.5, description="重排得分阈值，低于该值的将被过滤掉")

{common_querylist}

@router.post("/insert", summary="新增记录")
async def insert_{snake_name}(data: {pascal_name}Create, background_tasks: BackgroundTasks, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        insert_data = data.model_dump(exclude_unset=True, exclude_none=True)
        insert_data = fill_audit_fields(insert_data, user, is_update=False)
        if "version" not in insert_data:
            insert_data["version"] = 1
            
        stmt = insert({snake_name}_table).values(**insert_data)
        inserted_id = await db_client.execute_insert(stmt)
        
        if inserted_id:
            query = select({snake_name}_table).where({snake_name}_table.c.{pk_key} == inserted_id)
            record = await db_client.fetch_one(query)
            if record:
                item = {pascal_name}(**record)
                is_valid = True
                if hasattr(item, 'enabled') and item.enabled != 1:
                    is_valid = False
                if hasattr(item, 'removed') and item.removed != 0:
                    is_valid = False
                if is_valid:
                    background_tasks.add_task(sync_{snake_name}, [item])
                    
        return success(message="新增成功")
    except Exception as e:
        return server_error(f"新增失败: {{str(e)}}")

@router.post("/update", summary="修改记录")
async def update_{snake_name}(data: {pascal_name}Update, background_tasks: BackgroundTasks, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        update_data = data.model_dump(exclude={{"{pk_key}"}}, exclude_unset=True, exclude_none=True)
        if not update_data:
            return server_error("没有需要更新的字段")
            
        update_data = fill_audit_fields(update_data, user, is_update=True)
        if hasattr({snake_name}_table.c, 'version'):
            update_data["version"] = {snake_name}_table.c.version + 1
            
        stmt = update({snake_name}_table).where({snake_name}_table.c.{pk_key} == getattr(data, '{pk_key}')).values(**update_data)
        affected = await db_client.execute(stmt)
        if affected > 0:
            query = select({snake_name}_table).where({snake_name}_table.c.{pk_key} == getattr(data, '{pk_key}'))
            record = await db_client.fetch_one(query)
            if record:
                item = {pascal_name}(**record)
                is_valid = True
                if hasattr(item, 'enabled') and item.enabled != 1:
                    is_valid = False
                if hasattr(item, 'removed') and item.removed != 0:
                    is_valid = False
                if is_valid:
                    background_tasks.add_task(sync_{snake_name}, [item])
                else:
                    background_tasks.add_task(delete_{snake_name}_from_milvus, [getattr(item, '{pk_key}')])
                    
            return success(message="修改成功")
        return server_error("修改失败，记录不存在")
    except Exception as e:
        return server_error(f"修改失败: {{str(e)}}")

@router.post("/delete", summary="物理删除")
async def delete_{snake_name}(req: DeleteRequest, background_tasks: BackgroundTasks):
    try:
        stmt = delete({snake_name}_table).where({snake_name}_table.c.{pk_key} == getattr(req, '{pk_key}'))
        affected = await db_client.execute(stmt)
        if affected > 0:
            background_tasks.add_task(delete_{snake_name}_from_milvus, [getattr(req, '{pk_key}')])
            return success(message="删除成功")
        return server_error("删除失败，记录不存在")
    except Exception as e:
        return server_error(f"删除失败: {{str(e)}}")

@router.post("/deleteLj", summary="逻辑删除")
async def delete_lj_{snake_name}(req: DeleteRequest, background_tasks: BackgroundTasks, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        if not hasattr({snake_name}_table.c, 'removed') or not hasattr({snake_name}_table.c, 'enabled'):
            return server_error("该表不支持逻辑删除(缺少 removed 或 enabled 字段)")
            
        update_data = {{"removed": 1, "enabled": 0}}
        update_data = fill_audit_fields(update_data, user, is_update=True)
        
        stmt = update({snake_name}_table).where({snake_name}_table.c.{pk_key} == getattr(req, '{pk_key}')).values(**update_data)
        affected = await db_client.execute(stmt)
        if affected > 0:
            background_tasks.add_task(delete_{snake_name}_from_milvus, [getattr(req, '{pk_key}')])
            return success(message="逻辑删除成功")
        return server_error("逻辑删除失败，记录不存在")
    except Exception as e:
        return server_error(f"逻辑删除失败: {{str(e)}}")

{common_export_download}

def _parse_import_file(df: pd.DataFrame, user: Dict[str, Any], reverse_map: Dict[str, str]) -> List[Dict[str, Any]]:
    records = []
    for index, row in df.iterrows():
        insert_data = {{}}
        for ch_col, en_col in reverse_map.items():
            if ch_col in df.columns:
                val = row[ch_col]
                if pd.isna(val):
                    insert_data[en_col] = None
                else:
                    insert_data[en_col] = val
                    
        if not insert_data:
            continue
            
        insert_data = fill_audit_fields(insert_data, user, is_update=False)
        if "version" not in insert_data:
            insert_data["version"] = 1
        if "enabled" not in insert_data:
            insert_data["enabled"] = 1
        if "removed" not in insert_data:
            insert_data["removed"] = 0
        records.append(insert_data)
        
    return records

async def _delayed_sync_from_db():
    try:
        logger.info("等待 15 秒后开始同步数据到 Milvus 向量库...")
        await asyncio.sleep(15)
        
        query = select({snake_name}_table)
        if hasattr({snake_name}_table.c, 'removed'):
            query = query.where({snake_name}_table.c.removed == 0)
        if hasattr({snake_name}_table.c, 'enabled'):
            query = query.where({snake_name}_table.c.enabled == 1)
            
        rows = await db_client.fetch_all(query)
        if rows:
            records = [{pascal_name}(**row) for row in rows]
            await sync_{snake_name}_async(records)
            
        logger.info("后台延迟同步 Milvus 任务执行成功")
    except Exception as e:
        logger.error(f"后台延迟同步 Milvus 失败: {{str(e)}}")

async def _insert_worker(worker_id: int, queue: asyncio.Queue, success_list: list, records_to_sync: list):
    while True:
        try:
            insert_data = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        try:
            stmt = insert({snake_name}_table).values(**insert_data)
            inserted_id = await db_client.execute_insert(stmt)
            
            if inserted_id:
                success_list.append(1)
                insert_data["{pk_key}"] = inserted_id
                item = {pascal_name}(**insert_data)
                
                is_valid = True
                if hasattr(item, 'enabled') and item.enabled != 1:
                    is_valid = False
                if hasattr(item, 'removed') and item.removed != 0:
                    is_valid = False
                    
                if is_valid:
                    records_to_sync.append(item)
                    
            await asyncio.sleep(0.01)
        except Exception as e:
            if "1062" in str(e) or "Duplicate entry" in str(e):
                pass
            else:
                logger.error(f"[Worker-{{worker_id}}] 插入记录失败: {{str(e)}}")
        finally:
            queue.task_done()

@router.post("/import", summary="导入数据")
async def import_{snake_name}(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks(), user: Dict[str, Any] = Depends(get_current_user)):
    try:
        if not file.filename.endswith(('.csv', '.xls', '.xlsx')):
            return server_error("仅支持导入 .csv, .xls, .xlsx 格式的文件")
            
        contents = await file.read()
        import io
        if file.filename.endswith('.csv'):
            df = None
            for enc in ['utf-8', 'gb18030', 'utf-8-sig', 'gbk']:
                try:
                    df = pd.read_csv(io.BytesIO(contents), encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                df = pd.read_csv(io.BytesIO(contents), encoding='gb18030', encoding_errors='replace')
        else:
            df = pd.read_excel(io.BytesIO(contents))
            
        await db_client.execute(delete({snake_name}_table))
        clear_milvus_collection()
        
        reverse_map = {{v: k for k, v in {snake_name.upper()}_FIELD_MAP.items()}}
        records_to_insert = await asyncio.to_thread(_parse_import_file, df, user, reverse_map)
        
        queue = asyncio.Queue()
        for record in records_to_insert:
            queue.put_nowait(record)
            
        success_list = []
        records_to_sync = []
        workers = [
            asyncio.create_task(_insert_worker(i, queue, success_list, records_to_sync)) 
            for i in range(50)
        ]
        
        await asyncio.gather(*workers)
        success_count = sum(success_list)
        
        background_tasks.add_task(_delayed_sync_from_db)
            
        return success(message=f"成功导入 {{success_count}} 条记录")
    except Exception as e:
        logger.error(f"导入异常: {{e}}")
        return server_error(f"导入失败: {{str(e)}}")

@router.post("/recall", summary="AI问题召回")
async def ai_recall_{snake_name}(req: RecallRequest):
    try:
        if not req.query.strip():
            return server_error("提问内容不能为空")
            
        results = recall(query=req.query, top_k=req.top_k, score_threshold=req.score_threshold)
        return success(data=results, message="召回成功")
    except Exception as e:
        return server_error(f"AI召回失败: {{str(e)}}")

@router.post("/sync_milvus", summary="手动同步数据到向量库")
async def sync_{snake_name}_to_milvus():
    try:
        await sync_from_db()
        return success(message="数据同步任务已执行成功")
    except Exception as e:
        return server_error(f"同步失败: {{str(e)}}")
'''
    else:
        # ====== 不包含 Milvus 逻辑的纯净 CRUD 模板 ======
        api_content = f'''from fastapi import APIRouter, Depends, UploadFile, File, Response
from sqlalchemy import select, func, desc, insert, update, delete
from utils.response import success, server_error
from utils.mysqldb import db_client
from utils.context import get_current_user, fill_audit_fields
from pydantic import BaseModel
from typing import Dict, Any, List
import pandas as pd
import io
from urllib.parse import quote
from datetime import datetime

from api.endpoints.{snake_name}.modular.{snake_name} import (
    {pascal_name}, {pascal_name}Response, {pascal_name}QueryRequest, {pascal_name}Create, {pascal_name}Update
)
from api.endpoints.{snake_name}.sql.tables import {snake_name}_table

router = APIRouter()

# 字段映射配置，用于导入导出和模板下载
{snake_name.upper()}_FIELD_MAP = {{
{field_map_str}
}}

class DeleteRequest(BaseModel):
    {pk_key}: int

{common_querylist}

@router.post("/insert", summary="新增记录")
async def insert_{snake_name}(data: {pascal_name}Create, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        insert_data = data.model_dump(exclude_unset=True, exclude_none=True)
        insert_data = fill_audit_fields(insert_data, user, is_update=False)
        stmt = insert({snake_name}_table).values(**insert_data)
        await db_client.execute(stmt)
        return success(message="新增成功")
    except Exception as e:
        return server_error(f"新增失败: {{str(e)}}")

@router.post("/update", summary="修改记录")
async def update_{snake_name}(data: {pascal_name}Update, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        update_data = data.model_dump(exclude={{"{pk_key}"}}, exclude_unset=True, exclude_none=True)
        if not update_data:
            return server_error("没有需要更新的字段")
            
        update_data = fill_audit_fields(update_data, user, is_update=True)
        stmt = update({snake_name}_table).where({snake_name}_table.c.{pk_key} == getattr(data, '{pk_key}')).values(**update_data)
        affected = await db_client.execute(stmt)
        if affected > 0:
            return success(message="修改成功")
        return server_error("修改失败，记录不存在")
    except Exception as e:
        return server_error(f"修改失败: {{str(e)}}")

@router.post("/delete", summary="物理删除")
async def delete_{snake_name}(req: DeleteRequest):
    try:
        stmt = delete({snake_name}_table).where({snake_name}_table.c.{pk_key} == getattr(req, '{pk_key}'))
        affected = await db_client.execute(stmt)
        if affected > 0:
            return success(message="删除成功")
        return server_error("删除失败，记录不存在")
    except Exception as e:
        return server_error(f"删除失败: {{str(e)}}")

@router.post("/deleteLj", summary="逻辑删除")
async def delete_lj_{snake_name}(req: DeleteRequest, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        if not hasattr({snake_name}_table.c, 'removed') or not hasattr({snake_name}_table.c, 'enabled'):
            return server_error("该表不支持逻辑删除(缺少 removed 或 enabled 字段)")
            
        update_data = {{"removed": 1, "enabled": 0}}
        update_data = fill_audit_fields(update_data, user, is_update=True)
        
        stmt = update({snake_name}_table).where({snake_name}_table.c.{pk_key} == getattr(req, '{pk_key}')).values(**update_data)
        affected = await db_client.execute(stmt)
        if affected > 0:
            return success(message="逻辑删除成功")
        return server_error("逻辑删除失败，记录不存在")
    except Exception as e:
        return server_error(f"逻辑删除失败: {{str(e)}}")

{common_export_download}

@router.post("/import", summary="导入数据")
async def import_{snake_name}(file: UploadFile = File(...), user: Dict[str, Any] = Depends(get_current_user)):
    try:
        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            return server_error("请上传 Excel 或 CSV 文件")
            
        contents = await file.read()
        import io
        if file.filename.endswith('.csv'):
            df = None
            for enc in ['utf-8', 'gb18030', 'utf-8-sig', 'gbk']:
                try:
                    df = pd.read_csv(io.BytesIO(contents), encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                df = pd.read_csv(io.BytesIO(contents), encoding='gb18030', encoding_errors='replace')
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        reverse_map = {{v: k for k, v in {snake_name.upper()}_FIELD_MAP.items()}}
        
        success_count = 0
        error_list = []
        
        for index, row in df.iterrows():
            try:
                row_data = {{}}
                for col_name, val in row.items():
                    if col_name in reverse_map and pd.notna(val):
                        row_data[reverse_map[col_name]] = val
                        
                if not row_data:
                    continue
                    
                insert_data = fill_audit_fields(row_data, user, is_update=False)
                stmt = insert({snake_name}_table).values(**insert_data)
                await db_client.execute(stmt)
                success_count += 1
            except Exception as row_e:
                error_list.append(f"第 {{index + 2}} 行导入失败: {{str(row_e)}}")
                
        if error_list:
            return success(message=f"导入完成，成功 {{success_count}} 条，失败 {{len(error_list)}} 条", data={{"errors": error_list}})
        return success(message=f"导入成功，共 {{success_count}} 条")
    except Exception as e:
        return server_error(f"导入失败: {{str(e)}}")
'''

    with open(api_dir / f"{snake_name+'Api'}.py", "w", encoding="utf-8") as f:
        f.write(api_content)
        
    print(f"✅ 成功生成模块 '{snake_name}' (基于表 '{table_name}')")
    print(f"👉 目录结构已生成: {base_dir}")
    print(f"👉 请记得在 api/endpoints/__init__.py 中注册生成的 router")
    if milvus_prefix:
        print(f"👉 开启了 Milvus 支持，生成了 {milvus_dir}/{milvus_prefix}_{snake_name}.py")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="根据数据库表自动生成 CRUD API 代码结构")
    parser.add_argument("--table", required=True, help="数据库表名 (例如 BOOK_COLLECTION)")
    parser.add_argument("--module", required=True, help="模块命名 (例如 csgl)")
    parser.add_argument("--milvus", type=str, default=None, help="启用 Milvus 向量库同步并指定前缀名称 (例如 ttxz)")
    
    args = parser.parse_args()
    generate(args.table, args.module, args.milvus)
