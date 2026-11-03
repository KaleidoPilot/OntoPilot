import requests
from typing import List, Dict, Any, Union
from core.config import yaml_config
from openai import OpenAI

def get_embeddings(texts: Union[str, List[str]]) -> List[List[float]]:
    """
    调用向量模型获取文本的向量表示
    自动支持批量分块请求（DashScope 通常限制单次请求文本数量，如 25）
    """
    if isinstance(texts, str):
        texts = [texts]
        
    all_embeddings = []
    batch_size = 10  # DashScope text-embedding-v4 限制最多10条
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        batch_embeddings = _get_embeddings_batch(batch_texts)
        all_embeddings.extend(batch_embeddings)
        
    return all_embeddings

def _get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    config = yaml_config.get("model_settings", {}).get("embedding", {})
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model", "text-embedding-v4")
    
    if not api_key or not base_url:
        raise ValueError("Embedding configuration is missing api_key or base_url.")
        
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    # 从配置获取指定的向量维度，保持与 Milvus 集合维度一致
    milvus_config = yaml_config.get("milvus_settings", {})
    vector_dim = milvus_config.get("vector_dim", 1536)
    
    resp = client.embeddings.create(
        model=model,
        input=texts,
        dimensions=vector_dim
    )
    
    # 提取向量，按照原始顺序排序（通常 OpenAI 库返回的结果已经是按序排列的，为了保险起见依然排序）
    items = sorted(resp.data, key=lambda x: x.index)
    embeddings = [item.embedding for item in items]
    
    return embeddings

def rerank_documents(query: str, documents: List[str], top_n: int = 5) -> List[Dict[str, Any]]:
    """
    调用 Rerank 模型对召回的文档进行重排
    复用配置中的 qwen3-rerank 模型
    """
    if not documents:
        return []
        
    config = yaml_config.get("model_settings", {}).get("rerank", {})
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model", "qwen3-rerank")
    
    if not api_key or not base_url:
        raise ValueError("Rerank configuration is missing api_key or base_url.")
        
    url = base_url
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "query": query,
        "documents": documents,
        "top_n": top_n,
        "return_documents": False
    }
    
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    results = data.get("results", [])
    return results

def call_llm(messages: List[Dict[str, str]], temperature: float = 0.3, stream: bool = False):
    """
    调用大语言模型进行对话
    """
    config = yaml_config.get("model_settings", {}).get("llm", {})
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model", "qwen3.7-plus")
    
    if not api_key or not base_url:
        raise ValueError("LLM configuration is missing api_key or base_url.")
        
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=stream,
        extra_body={
            "enable_thinking": False  # false = 关闭深度思考，直接输出答案
        },
    )
    
    if stream:
        return response
    return response.choices[0].message.content

