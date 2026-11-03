import json
import hashlib
import logging
import threading
from functools import lru_cache
from typing import Any, Callable, Sequence

import requests
from openai import OpenAI
from pymilvus import MilvusClient

from core.config import yaml_config
from utils.ai_utils import get_embeddings, rerank_documents


KNOWLEDGE_MILVUS_DATABASE = "ai_platform"
KNOWLEDGE_COLLECTION = "ai_knowledge"
MILVUS_OUTPUT_FIELDS = ["id", "version", "file_id", "tenant_id", "full_text"]
MAX_RETRIEVAL_TENANTS = 20
_EMBEDDING_LOG_LOCK = threading.Lock()


def knowledge_folder_scope(rows: list[dict], folder_id: int) -> dict:
    """迭代遍历，无递归层数限制；同时检查孤立文档和循环。"""
    nodes={int(row['id']):dict(row) for row in rows}
    if folder_id and folder_id not in nodes:
        raise ValueError('文档不存在或不属于当前知识库')
    path=[];seen=set();current=folder_id
    while current:
        if current in seen or current not in nodes:
            raise ValueError('文档层级异常，请联系管理员')
        seen.add(current);path.append(nodes[current]);current=int(nodes[current]['parentId'])
    children={}
    for row in nodes.values():children.setdefault(int(row['parentId']),[]).append(row)
    pending=[folder_id];descendants=[];seen=set()
    while pending:
        current=pending.pop()
        if current in seen:raise ValueError('文档存在循环，请联系管理员')
        seen.add(current);descendants.append(current)
        pending.extend(int(row['id']) for row in children.get(current,[]))
    if not folder_id and len(seen)!=len(nodes)+1:
        raise ValueError('文档存在孤立或循环关系，请联系管理员')
    return {'folderId':folder_id,'breadcrumbs':list(reversed(path)),
        'children':children.get(folder_id,[]),'descendantIds':descendants,'allFolders':list(nodes.values()),
        'documentKeys':[nodes[node]['documentKey'] for node in descendants if node in nodes and nodes[node].get('documentKey')]}


def knowledge_document_key(record: dict) -> str:
    source='file:'+str(record['fileId']) if record.get('fileId') else 'record:'+str(int(record['id']))
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


class KnowledgeFolders:
    """文档与文档归属；与资料新增共用知识库行锁，权限在路由沿用库权限。"""
    def __init__(self,client=None):
        from utils.mysqldb import db_client
        self.client=client or db_client

    @staticmethod
    @lru_cache(maxsize=30)
    def sql(key):
        from pathlib import Path
        import yaml
        with (Path(__file__).parent/'sql/sql.yaml').open(encoding='utf-8') as handle:
            data=yaml.safe_load(handle)
        section,separator,name=key.partition('.')
        return data[section][name] if separator else data['folder'][key]

    async def scope(self,org_id,tenant_id,folder_id=0):
        rows=await self.client.fetch_all(self.sql('list'),{'orgId':org_id,'tenantId':tenant_id})
        return knowledge_folder_scope(rows,folder_id)

    async def open_document(self,actor,tenant_id,record_id):
        """从真实资料推导文档入口，不移动/复制正文；只读用户也可打开已授权资料。"""
        from sqlalchemy import text
        from pathlib import Path
        from utils.context import fill_audit_fields
        params={'orgId':actor['orgId'],'tenantId':tenant_id,'recordId':record_id}
        async with self.client.engine.begin() as conn:
            if not (await conn.execute(text(self.sql('tenant_lock')),params)).mappings().first():
                raise ValueError('知识库不存在')
            record=(await conn.execute(text(self.sql('source_record')),params)).mappings().first()
            if not record:raise ValueError('文档不存在或不属于当前知识库')
            rows=(await conn.execute(text(self.sql('list')),params)).mappings().all()
            parent_id=int(record.get('folderId') or 0)
            knowledge_folder_scope(rows,parent_id)
            key=knowledge_document_key(record)
            current=next((row for row in rows if row.get('documentKey')==key),None)
            params.update(parentId=parent_id,documentKey=key,
                folderName=(Path(str(record.get('fileUrl') or '')).name or str(record.get('title') or '未命名文档'))[:100])
            if current:
                if parent_id in knowledge_folder_scope(rows,int(current['id']))['descendantIds']:
                    raise ValueError('文档上下级关联异常，请联系管理员')
                folder_id=int(current['id'])
                if current['folderName']!=params['folderName'] or int(current['parentId'])!=parent_id:
                    fill_audit_fields(params,actor,is_update=True)
                    await conn.execute(text(self.sql('update')),{**params,'folderId':folder_id})
            else:
                fill_audit_fields(params,actor,is_update=False)
                result=await conn.execute(text(self.sql('insert')),params)
                folder_id=int(result.lastrowid)
        return {'id':folder_id,'recordId':record_id}

    async def rebind_document(self,actor,tenant_id,old_record,new_record):
        from sqlalchemy import text
        from pathlib import Path
        from utils.context import fill_audit_fields
        params={'orgId':actor['orgId'],'tenantId':tenant_id,'documentKey':knowledge_document_key(old_record),
            'newDocumentKey':knowledge_document_key(new_record),
            'folderName':(Path(str(new_record.get('fileUrl') or '')).name or str(new_record.get('title') or '未命名文档'))[:100]}
        fill_audit_fields(params,actor,is_update=True)
        async with self.client.engine.begin() as conn:
            await conn.execute(text(self.sql('tenant_lock')),params)
            await conn.execute(text(self.sql('document_rebind')),params)

    async def save(self,actor,tenant_id,data,folder_id=None):
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError
        from utils.context import fill_audit_fields
        params={'orgId':actor['orgId'],'tenantId':tenant_id,'folderId':folder_id,'documentKey':None,**data.model_dump()}
        fill_audit_fields(params,actor,is_update=folder_id is not None)
        try:
            async with self.client.engine.begin() as conn:
                if not (await conn.execute(text(self.sql('tenant_lock')),params)).mappings().first():
                    raise ValueError('知识库不存在')
                rows=(await conn.execute(text(self.sql('list')),params)).mappings().all()
                knowledge_folder_scope(rows,data.parentId)
                if folder_id is not None:
                    current=knowledge_folder_scope(rows,folder_id)
                    if current['breadcrumbs'][-1].get('documentKey'):
                        raise ValueError('文件文档请从文件列表编辑或移动')
                    if data.parentId in current['descendantIds']:
                        raise ValueError('不能把文档移动到自身或下级文档')
                    if (await conn.execute(text(self.sql('duplicate_name')),params)).mappings().first():
                        raise ValueError('当前层级已存在同名文档')
                    await conn.execute(text(self.sql('update')),params)
                else:
                    if (await conn.execute(text(self.sql('duplicate_name')),params)).mappings().first():
                        raise ValueError('当前层级已存在同名文档')
                    result=await conn.execute(text(self.sql('insert')),params)
                    folder_id=int(result.lastrowid)
        except IntegrityError:
            raise ValueError('当前层级已存在同名文档') from None
        return {'id':folder_id}

    async def delete(self,actor,tenant_id,folder_id):
        from sqlalchemy import text
        params={'orgId':actor['orgId'],'tenantId':tenant_id,'folderId':folder_id}
        async with self.client.engine.begin() as conn:
            await conn.execute(text(self.sql('tenant_lock')),params)
            rows=(await conn.execute(text(self.sql('list')),params)).mappings().all()
            current=knowledge_folder_scope(rows,folder_id)
            if current['breadcrumbs'][-1].get('documentKey'):
                raise ValueError('请从文件列表删除该文档')
            count=(await conn.execute(text(self.sql('references')),params)).mappings().first()
            if current['children'] or int(count['total']):
                raise ValueError('文档仍有子文档或资料，请先移出后再删除')
            # 未过期的构建仍持有资料；不在此处取消共享任务。
            graph=(await conn.execute(text(self.sql('graph.read')),params)).mappings().first()
            if graph and graph['status']=='building':raise ValueError('文档图谱正在建立，请完成后再删除')
            if graph:
                from api.endpoints.knowledge.graph_catalog import DatabaseGraphCatalog
                await DatabaseGraphCatalog(folder_id).remove_vectors(actor['orgId'],tenant_id)
            await conn.execute(text(self.sql('graph_delete')),params)
            await conn.execute(text(self.sql('delete')),params)
        return {'id':folder_id}

    async def delete_document(self,actor,tenant_id,record,store):
        """有下级的父文档不允许直接删除；空文档的内容和入口在同一事务删除。"""
        from sqlalchemy import text
        import asyncio
        params={'orgId':actor['orgId'],'tenantId':tenant_id,'recordId':record['id'],
            'fileId':str(record.get('fileId') or '')}
        rows=await self.client.fetch_all(self.sql('list'),params)
        key=knowledge_document_key(record)
        if not any(row.get('documentKey')==key for row in rows):return None
        async with self.client.engine.begin() as conn:
            await conn.execute(text(self.sql('tenant_lock')),params)
            rows=(await conn.execute(text(self.sql('list')),params)).mappings().all()
            node=next((row for row in rows if row.get('documentKey')==key),None)
            if not node:raise ValueError('文档关联已变化，请刷新后重试')
            params['folderId']=int(node['id'])
            current=knowledge_folder_scope(rows,params['folderId'])
            count=(await conn.execute(text(self.sql('references')),params)).mappings().first()
            if current['children'] or int(count['total']):
                raise ValueError('该文档包含下级文档或文件，请先移出或删除下级内容')
            graph=(await conn.execute(text(self.sql('graph.read')),params)).mappings().first()
            if graph and graph['status']=='building':raise ValueError('文档图谱正在建立，请完成后再删除')
            source=(await conn.execute(text(self.sql('source_record')),params)).mappings().first()
            if not source or knowledge_document_key(source)!=key:
                raise ValueError('原文件已变化，请刷新后重试')
            if graph:
                from api.endpoints.knowledge.graph_catalog import DatabaseGraphCatalog
                await DatabaseGraphCatalog(params['folderId']).remove_vectors(actor['orgId'],tenant_id)
            if params['fileId']:
                parts=(await conn.execute(text(self.sql('record.ids_by_file')),params)).mappings().all()
                ids=[int(row['id']) for row in parts]
                delete_sql=self.sql('record.physical_delete_by_file')
            else:
                ids=[int(record['id'])];delete_sql=self.sql('record.physical_delete')
            deleted_vectors=await asyncio.to_thread(store.delete_ids,ids)
            result=await conn.execute(text(delete_sql),params)
            if result.rowcount<1:raise ValueError('文档删除状态已变化，请刷新')
            await conn.execute(text(self.sql('graph_delete')),params)
            await conn.execute(text(self.sql('delete')),params)
        return {'deletedRows':result.rowcount,'deletedVectors':deleted_vectors}

    async def move(self,actor,tenant_id,data):
        from sqlalchemy import text
        from utils.context import fill_audit_fields
        params={'orgId':actor['orgId'],'tenantId':tenant_id,'folderId':data.folderId,
            'recordIds':','.join(map(str,sorted(data.recordIds)))}
        fill_audit_fields(params,actor,is_update=True)
        async with self.client.engine.begin() as conn:
            await conn.execute(text(self.sql('tenant_lock')),params)
            rows=(await conn.execute(text(self.sql('list')),params)).mappings().all()
            knowledge_folder_scope(rows,data.folderId)
            records=(await conn.execute(text(self.sql('records_lock')),params)).mappings().all()
            if {int(row['id']) for row in records}!=set(data.recordIds):
                raise ValueError('所选文档已变化或不属于当前知识库')
            selected_keys={knowledge_document_key(row) for row in records}
            selected_nodes=[row for row in rows if row.get('documentKey') in selected_keys]
            for node in selected_nodes:
                if data.folderId in knowledge_folder_scope(rows,int(node['id']))['descendantIds']:
                    raise ValueError('不能把文档移动到自身或下级文档')
            for node in selected_nodes:
                await conn.execute(text(self.sql('update')),{**params,'folderId':int(node['id']),
                    'parentId':data.folderId,'folderName':node['folderName']})
            params['fileIds']=','.join(sorted({str(row['fileId']) for row in records if row.get('fileId')}))
            result=await conn.execute(text(self.sql('move_documents')),params)
        return {'folderId':data.folderId,'movedRecords':result.rowcount}


def get_embeddings_without_debug(texts: list[str]) -> list[list[float]]:
    loggers = [logging.getLogger(name) for name in ("openai", "httpcore", "httpx")]
    with _EMBEDDING_LOG_LOCK:
        previous_levels = [logger.level for logger in loggers]
        try:
            for logger in loggers:
                logger.setLevel(logging.WARNING)
            return get_embeddings(texts)
        finally:
            for logger, level in zip(loggers, previous_levels, strict=True):
                logger.setLevel(level)


def _configured_embedder(
    model_settings: dict[str, Any],
    milvus_settings: dict[str, Any],
) -> Callable[[list[str]], list[list[float]]]:
    config = model_settings.get("embedding") or {}
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model", "text-embedding-v4")
    vector_dim = int(milvus_settings.get("vector_dim") or 1536)
    if not api_key or not base_url:
        raise ValueError("当前公司未配置可用的 Embedding 模型")

    def embed(texts: list[str]) -> list[list[float]]:
        loggers = [logging.getLogger(name) for name in ("openai", "httpcore", "httpx")]
        with _EMBEDDING_LOG_LOCK:
            previous_levels = [logger.level for logger in loggers]
            try:
                for logger in loggers:
                    logger.setLevel(logging.WARNING)
                client = OpenAI(api_key=api_key, base_url=base_url)
                embeddings: list[list[float]] = []
                for start in range(0, len(texts), 10):
                    response = client.embeddings.create(
                        model=model,
                        input=texts[start : start + 10],
                        dimensions=vector_dim,
                    )
                    embeddings.extend(
                        item.embedding for item in sorted(response.data, key=lambda item: item.index)
                    )
                return embeddings
            finally:
                for logger, level in zip(loggers, previous_levels, strict=True):
                    logger.setLevel(level)

    return embed


def _configured_reranker(
    model_settings: dict[str, Any],
) -> Callable[[str, list[str], int], list[dict[str, Any]]]:
    config = model_settings.get("rerank") or {}
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model", "qwen3-rerank")
    if not api_key or not base_url:
        raise ValueError("当前公司未配置可用的 Rerank 模型")

    def rerank(query: str, documents: list[str], top_n: int) -> list[dict[str, Any]]:
        response = requests.post(
            base_url,
            json={
                "model": model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
                "return_documents": False,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("results", [])

    return rerank


def derive_sync_status(
    *,
    enabled: int,
    source_version: int,
    vector_version: int | None,
) -> str:
    if enabled:
        if vector_version is None:
            return "missing"
        if vector_version != source_version:
            return "outdated"
        return "synced"
    return "orphaned" if vector_version is not None else "synced"


def normalize_tenant_ids(tenant_id: str) -> list[int]:
    if not isinstance(tenant_id, str):
        raise ValueError("知识库 ID 必须使用英文逗号分隔")
    parts = [part.strip() for part in tenant_id.split(",")]
    if not parts or any(not part for part in parts):
        raise ValueError("知识库 ID 必须是英文逗号分隔的正整数")

    normalized: list[int] = []
    seen: set[int] = set()
    for part in parts:
        try:
            value = int(part)
        except ValueError as error:
            raise ValueError("知识库 ID 必须是英文逗号分隔的正整数") from error
        if value <= 0:
            raise ValueError("知识库 ID 必须是正整数")
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    if len(normalized) > MAX_RETRIEVAL_TENANTS:
        raise ValueError(f"单次最多查询 {MAX_RETRIEVAL_TENANTS} 个知识库 ID")
    return normalized


class KnowledgeVectorStore:
    def __init__(
        self,
        *,
        client=None,
        embedder: Callable[[list[str]], list[list[float]]] | None = None,
        reranker: Callable[[str, list[str], int], list[dict[str, Any]]] | None = None,
        milvus_settings: dict[str, Any] | None = None,
        model_settings: dict[str, Any] | None = None,
    ) -> None:
        resolved_milvus = milvus_settings or yaml_config.get("milvus_settings", {})
        if client is None:
            host = resolved_milvus.get("host", "127.0.0.1")
            port = resolved_milvus.get("port", 19530)
            client = MilvusClient(
                uri=f"http://{host}:{port}",
                db_name=resolved_milvus.get("db_name") or KNOWLEDGE_MILVUS_DATABASE,
            )
        self._client = client
        self._collection_name = (
            resolved_milvus.get("collection_name") or KNOWLEDGE_COLLECTION
        )
        resolved_models = model_settings
        self._embedder = embedder or (
            _configured_embedder(resolved_models, resolved_milvus)
            if resolved_models is not None
            else get_embeddings_without_debug
        )
        self._reranker = reranker or (
            _configured_reranker(resolved_models)
            if resolved_models is not None
            else rerank_documents
        )

    def get_versions(self, record_ids: Sequence[int]) -> dict[int, int]:
        normalized_ids = list(dict.fromkeys(int(record_id) for record_id in record_ids))
        if not normalized_ids:
            return {}
        rows: list[dict] = []
        for start in range(0, len(normalized_ids), 1000):
            batch = normalized_ids[start : start + 1000]
            rows.extend(
                self._client.query(
                    collection_name=self._collection_name,
                    filter=f"id in {json.dumps(batch)}",
                    output_fields=["id", "version"],
                )
            )
        return {int(row["id"]): int(row.get("version") or 0) for row in rows}

    def get_tenant_versions(self, tenant_id: int) -> dict[int, int]:
        rows = self._client.query(
            collection_name=self._collection_name,
            filter=f"tenant_id == {int(tenant_id)}",
            output_fields=["id", "version"],
        )
        return {int(row["id"]): int(row.get("version") or 0) for row in rows}

    @staticmethod
    def build_text(record: dict) -> str:
        parts = []
        for key, label in (
            ("title", "标题"),
            ("content", "内容"),
            ("fileUrl", "附件"),
            ("tenantName", "Tenant"),
        ):
            value = record.get(key)
            if value:
                parts.append(f"{label}: {value}")
        return "\n".join(parts)[:65_000]

    def sync_records(self, records: list[dict]) -> dict[str, int]:
        if not records:
            return {"total": 0, "synced": 0, "skipped": 0}
        versions = self.get_versions([int(record["id"]) for record in records])
        changed = [
            record
            for record in records
            if versions.get(int(record["id"])) != int(record.get("version") or 0)
        ]
        if changed:
            texts = [self.build_text(record) for record in changed]
            vectors = self._embedder(texts)
            payload = [
                {
                    "id": int(record["id"]),
                    "version": int(record.get("version") or 0),
                    "file_id": str(record.get("fileId") or "")[:128],
                    "tenant_id": int(record["tenantId"]),
                    "full_text": text,
                    "vector": vector,
                }
                for record, text, vector in zip(changed, texts, vectors, strict=True)
            ]
            self._client.upsert(collection_name=self._collection_name, data=payload)
            self._client.flush(collection_name=self._collection_name)
        return {
            "total": len(records),
            "synced": len(changed),
            "skipped": len(records) - len(changed),
        }

    def delete_ids(self, record_ids: Sequence[int]) -> int:
        normalized_ids = list(dict.fromkeys(int(record_id) for record_id in record_ids))
        if not normalized_ids:
            return 0
        result = self._client.delete(
            collection_name=self._collection_name,
            ids=normalized_ids,
        )
        self._client.flush(collection_name=self._collection_name)
        return int(result.get("delete_count", len(normalized_ids)))

    def retrieve(
        self,
        *,
        question: str,
        confidence: float,
        top_k: int,
        tenant_id: str,
        record_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("问题不能为空")
        if not 0 <= confidence <= 1:
            raise ValueError("置信度必须在 0 到 1 之间")
        if not 1 <= top_k <= 50:
            raise ValueError("返回条数必须在 1 到 50 之间")
        tenant_ids = normalize_tenant_ids(tenant_id)
        if record_ids is not None and not record_ids:return []
        scoped_filter=f"tenant_id in {json.dumps(tenant_ids)}"
        if record_ids is not None:
            if any(type(value) is not int or value<=0 for value in record_ids):raise ValueError('资料范围ID不合法')
            scoped_filter+=f" and id in {json.dumps(record_ids)}"

        question_vector = self._embedder([normalized_question])[0]
        search_results = self._client.search(
            collection_name=self._collection_name,
            data=[question_vector],
            anns_field="vector",
            filter=scoped_filter,
            limit=max(top_k * 3, 6),
            output_fields=MILVUS_OUTPUT_FIELDS,
            search_params={"metric_type": "COSINE", "params": {"nprobe": 10}},
        )
        hits = search_results[0] if search_results else []
        if not hits:
            return []

        candidates: list[dict[str, Any]] = []
        documents: list[str] = []
        for hit in hits:
            entity = hit.get("entity") or hit
            full_text = str(entity.get("full_text") or "")
            if not full_text:
                continue
            documents.append(full_text)
            candidates.append(
                {
                    "id": int(entity.get("id", hit.get("id"))),
                    "version": int(entity.get("version") or 0),
                    "fileId": str(entity.get("file_id") or ""),
                    "tenantId": int(entity.get("tenant_id") or 0),
                    "fullText": full_text,
                    "embeddingScore": float(hit.get("distance") or 0.0),
                }
            )
        if not documents:
            return []

        reranked = self._reranker(normalized_question, documents, top_k)
        results: list[dict[str, Any]] = []
        for item in reranked:
            index = item.get("index")
            score = float(item.get("relevance_score") or 0.0)
            if not isinstance(index, int) or not 0 <= index < len(candidates):
                continue
            if score < confidence:
                continue
            results.append({**candidates[index], "rerankScore": score})
        results.sort(key=lambda item: item["rerankScore"], reverse=True)
        return results[:top_k]


@lru_cache(maxsize=32)
def get_knowledge_store(
    model_settings_json: str | None = None,
    milvus_settings_json: str | None = None,
) -> KnowledgeVectorStore:
    if model_settings_json is None and milvus_settings_json is None:
        return KnowledgeVectorStore()
    model_settings = json.loads(model_settings_json or "{}")
    milvus_settings = json.loads(milvus_settings_json or "{}")
    if not isinstance(model_settings, dict) or not isinstance(milvus_settings, dict):
        raise ValueError("公司 AI/向量库配置必须是 JSON 对象")
    if not milvus_settings.get("host"):
        raise ValueError("当前公司未配置可用的向量库")
    return KnowledgeVectorStore(
        model_settings=model_settings,
        milvus_settings=milvus_settings,
    )
