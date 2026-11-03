"""知识库图谱的正式存储：MySQL 保存整图，Milvus 保存匹配用向量。"""

from __future__ import annotations

import base64
import asyncio
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml
from pymilvus import DataType, MilvusClient

from api.endpoints.system.service import get_company_runtime_config
from core.config import yaml_config
from utils.mysqldb import db_client

GRAPH_COLLECTION = "ai_knowledge_graph"
GRAPH_DATABASE = "ai_platform"


@lru_cache(maxsize=3)
def _sql(name: str) -> str:
    with (Path(__file__).parent / 'sql' / 'sql.yaml').open(encoding='utf-8') as handle:
        return yaml.safe_load(handle)['graph'][name]


def read_lightrag_vectors(directory: Path) -> list[dict]:
    """读取 LightRAG 临时索引里的实体、关系、文本块向量。"""
    data_dir = directory / "index" / "data"
    specs = (
        ("vdb_entities.json", "entity", lambda row: row.get("entity_name") or ""),
        ("vdb_relationships.json", "relation", lambda row: f"{row.get('src_id') or ''} -> {row.get('tgt_id') or ''}"),
        ("vdb_chunks.json", "chunk", lambda row: row.get("file_path") or ""),
    )
    records = []
    for filename, kind, name_of in specs:
        path = data_dir / filename
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("data") or []
        matrix = np.frombuffer(base64.b64decode(payload["matrix"]), dtype=np.float32).reshape(len(rows), int(payload["embedding_dim"]))
        for row, vector in zip(rows, matrix):
            records.append({
                "refId": str(row.get("__id__") or ""),
                "kind": kind,
                "name": str(name_of(row))[:200],
                "text": str(row.get("content") or "")[:2000],
                "sourceId": str(row.get("source_id") or row.get("full_doc_id") or "")[:250],
                "fileName": str(row.get("file_path") or "")[:250],
                "vector": vector.astype(float).tolist(),
            })
    return records


def one_graph_vector(org_id: int, tenant_id: int, documents: list[dict], vectors: list[dict], folder_id: int = 0) -> dict:
    """一个知识库图谱只保留一条向量，方便按库匹配，不把实体和关系拆成多行。"""
    from api.endpoints.knowledge.graph_service import GraphError
    try:
        matrix = np.array([row["vector"] for row in vectors], dtype=np.float32)
    except (ValueError, TypeError, KeyError):
        raise GraphError('图谱向量维度不一致', 'GRAPH_EMBEDDING_DIM') from None
    if matrix.ndim != 2 or not all(matrix.shape) or not np.isfinite(matrix).all():
        raise GraphError('图谱向量为空或含无效数值', 'GRAPH_EMBEDDING_DIM')
    centroid = matrix.mean(axis=0)
    norm = float(np.linalg.norm(centroid))
    if norm:
        centroid = centroid / norm
    files = [row["name"] for row in documents]
    entities = [row["name"] for row in vectors if row["kind"] == "entity"]
    relations = [row["name"] for row in vectors if row["kind"] == "relation"]
    summary = "文档：" + "、".join(files)
    if entities:
        summary += "\n实体：" + "、".join(entities[:40])
    if relations:
        summary += "\n关系：" + "、".join(relations[:40])
    return {
        "id": f"{int(org_id)}:{int(tenant_id)}" + (f":folder:{int(folder_id)}" if folder_id else ''),
        "org_id": int(org_id),
        "tenant_id": int(tenant_id),
        "kind": "graph",
        "name": "、".join(files)[:200],
        "sourceId": f"folder:{int(folder_id)}" if folder_id else "",
        "fileName": "、".join(files)[:250],
        "text": summary[:2000],
        "vector": centroid.astype(float).tolist(),
    }


def _documents(rows: list[dict]) -> str:
    return json.dumps([{"docId": row["docId"], "name": row["name"]} for row in rows], ensure_ascii=False)


class FileGraphCatalog:
    """测试用的文件目录，不连接 MySQL 或 Milvus。"""

    requires_vectors = False

    def __init__(self, root: Path, folder_id: int = 0):
        self.folder_id=folder_id
        self.root = root

    def _directory(self, org_id: int, tenant_id: int) -> Path:
        path=self.root / str(int(org_id)) / str(int(tenant_id))
        return path / 'folders' / str(self.folder_id) if self.folder_id else path

    def for_folder(self,folder_id):
        return FileGraphCatalog(self.root,folder_id)

    async def read(self, org_id: int, tenant_id: int) -> tuple[dict | None, dict | None]:
        directory = self._directory(org_id, tenant_id)
        meta = _read_json(directory / "meta.json")
        snapshot = _read_json(directory / "graph.json") if meta and meta.get("status") == "ready" else None
        return meta, snapshot

    async def write_status(self, org_id: int, tenant_id: int, fingerprint: str, status: str, documents: list[dict], error: str | None = None) -> None:
        _write_json(self._directory(org_id, tenant_id) / "meta.json", {
            "orgId": int(org_id), "tenantId": int(tenant_id), "fingerprint": fingerprint, "status": status,
            "documents": json.loads(_documents(documents)), "error": error,
        })

    async def write_ready(self, org_id: int, tenant_id: int, fingerprint: str, documents: list[dict], snapshot: dict, vectors: list[dict]) -> None:
        directory = self._directory(org_id, tenant_id)
        _write_json(directory / "graph.json", snapshot)
        await self.write_status(org_id, tenant_id, fingerprint, "ready", documents)

    async def write_failed(self, org_id: int, tenant_id: int, fingerprint: str, documents: list[dict], error: str) -> None:
        await self.write_status(org_id, tenant_id, fingerprint, "failed", documents, error[:300])


class DatabaseGraphCatalog:
    """正式存储。图谱正文进 MySQL，匹配向量进独立的 Milvus 集合。"""

    requires_vectors = True
    collection_name = GRAPH_COLLECTION

    def __init__(self,folder_id: int = 0):
        self.folder_id=folder_id

    def for_folder(self,folder_id):
        return DatabaseGraphCatalog(folder_id)

    async def read(self, org_id: int, tenant_id: int) -> tuple[dict | None, dict | None]:
        row = await db_client.fetch_one(
            _sql('read'),
            {"orgId": int(org_id), "tenantId": int(tenant_id), "folderId":self.folder_id},
        )
        if not row:
            return None, None
        meta = {
            "orgId": int(org_id), "tenantId": int(tenant_id), "status": row["status"], "fingerprint": row["fingerprint"],
            "documents": json.loads(row["documentJson"] or "[]"), "error": row.get("errorMessage"),
        }
        snapshot = json.loads(row["graphJson"]) if row.get("status") == "ready" and row.get("graphJson") else None
        return meta, snapshot

    async def write_status(self, org_id: int, tenant_id: int, fingerprint: str, status: str, documents: list[dict], error: str | None = None) -> None:
        await db_client.execute(
            _sql('write_status'),
            {"orgId": int(org_id), "tenantId": int(tenant_id), "folderId":self.folder_id, "status": status, "fingerprint": fingerprint,
             "documents": _documents(documents), "error": error},
        )

    async def write_ready(self, org_id: int, tenant_id: int, fingerprint: str, documents: list[dict], snapshot: dict, vectors: list[dict]) -> None:
        if not vectors:
            from api.endpoints.knowledge.graph_service import GraphError
            raise GraphError("图谱向量为空，未写入数据库", "GRAPH_VECTOR_EMPTY")
        await self._replace_vectors(org_id, tenant_id, documents, vectors)
        await db_client.execute(
            _sql('write_ready'),
            {"orgId": int(org_id), "tenantId": int(tenant_id), "folderId":self.folder_id, "fingerprint": fingerprint, "documents": _documents(documents),
             "graph": json.dumps(snapshot, ensure_ascii=False)},
        )

    async def write_failed(self, org_id: int, tenant_id: int, fingerprint: str, documents: list[dict], error: str) -> None:
        await self.write_status(org_id, tenant_id, fingerprint, "failed", documents, error[:300])

    async def _client(self, org_id: int) -> MilvusClient:
        config = await get_company_runtime_config(org_id)
        vector = config.vector if isinstance(config.vector, dict) else {}
        fallback = yaml_config.get("milvus_settings", {})
        host = vector.get("host") or fallback.get("host") or "127.0.0.1"
        port = vector.get("port") or fallback.get("port") or 19530
        database = vector.get("db_name") or GRAPH_DATABASE
        return await asyncio.to_thread(MilvusClient, uri=f"http://{host}:{port}", db_name=database)

    async def _replace_vectors(self, org_id: int, tenant_id: int, documents: list[dict], vectors: list[dict]) -> None:
        row = one_graph_vector(org_id, tenant_id, documents, vectors,self.folder_id)
        client = await self._client(org_id)
        try:
            await asyncio.to_thread(self._upsert_vector, client, row)
        finally:
            await asyncio.to_thread(client.close)

    async def remove_vectors(self,org_id,tenant_id):
        client=await self._client(org_id)
        key=f'{int(org_id)}:{int(tenant_id)}'+(f':folder:{int(self.folder_id)}' if self.folder_id else '')
        try:
            if await asyncio.to_thread(client.has_collection,self.collection_name):
                await asyncio.to_thread(client.delete,collection_name=self.collection_name,ids=[key])
        finally:
            await asyncio.to_thread(client.close)

    def _upsert_vector(self, client: MilvusClient, row: dict) -> None:
        dimension = len(row['vector'])
        self._ensure_collection(client, dimension)
        # 已有主键覆盖写，失败时保留旧向量；VARCHAR 上限按 UTF-8 字节计算。
        def bounded(value: str, limit: int) -> str:
            return value.encode('utf-8')[:limit].decode('utf-8', errors='ignore')
        client.upsert(collection_name=self.collection_name, data=[{
            "id": row["id"],
            "org_id": row["org_id"],
            "tenant_id": row["tenant_id"],
            "kind": row["kind"],
            "name": bounded(row["name"], 512),
            "source_id": bounded(row["sourceId"], 256),
            "file_name": bounded(row["fileName"], 255),
            "text": row["text"],
            "vector": row["vector"],
        }])
        client.flush(self.collection_name)

    def _ensure_collection(self, client: MilvusClient, dimension: int) -> None:
        if client.has_collection(self.collection_name):
            fields = client.describe_collection(self.collection_name).get('fields') or []
            actual = next((int(field.get('params', {}).get('dim', 0)) for field in fields if field.get('name') == 'vector'), 0)
            if actual != dimension:
                from api.endpoints.knowledge.graph_service import GraphError
                raise GraphError('图谱集合维度与当前Embedding不符，请管理员检查配置', 'GRAPH_EMBEDDING_DIM')
            return
        schema = client.create_schema(auto_id=False, enable_dynamic_field=False, description="知识库图谱的实体、关系和文本块向量")
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=160)
        schema.add_field("org_id", DataType.INT64)
        schema.add_field("tenant_id", DataType.INT64)
        schema.add_field("kind", DataType.VARCHAR, max_length=16)
        schema.add_field("name", DataType.VARCHAR, max_length=512)
        schema.add_field("source_id", DataType.VARCHAR, max_length=256)
        schema.add_field("file_name", DataType.VARCHAR, max_length=255)
        schema.add_field("text", DataType.VARCHAR, max_length=8192)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
        index = client.prepare_index_params()
        index.add_index(field_name="vector", metric_type="COSINE", index_type="AUTOINDEX")
        client.create_collection(collection_name=self.collection_name, schema=schema, index_params=index)


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
