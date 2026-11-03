from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc, insert, update, delete
from utils.response import success, server_error
from utils.mysqldb import db_client
from utils.context import get_current_user, fill_audit_fields
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import json
import importlib
import logging

logger = logging.getLogger(__name__)

from api.endpoints.ai.modular.ai import (
    AiResponse, AiQueryRequest, AiCreate, AiUpdate
)
from api.endpoints.ai.sql.tables import ai_table
from api.endpoints.user.dependencies import get_super_administrator
from utils.ai_utils import call_llm
import asyncio
from api.endpoints.ai.util.queryTsg import search_books

import os

router = APIRouter()

QUICK_ACTIONS_FILE = os.path.join(os.path.dirname(__file__), "quick_actions.json")

class DeleteRequest(BaseModel):
    id: int

class ChatRequest(BaseModel):
    question: str = Field(..., description="用户提问")

class QuickActionItem(BaseModel):
    label: str
    text: str
    icon: str
    answer: Optional[str] = None

class QuickActionsUpdate(BaseModel):
    actions: List[QuickActionItem]

@router.get("/quick-actions/list", summary="获取快捷指令列表")
async def get_quick_actions():
    try:
        if not os.path.exists(QUICK_ACTIONS_FILE):
            return success(data=[])
        with open(QUICK_ACTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return success(data=data)
    except Exception as e:
        return server_error(f"获取快捷指令失败: {str(e)}")

@router.post("/quick-actions/save", summary="保存快捷指令列表", dependencies=[Depends(get_super_administrator)])
async def save_quick_actions(req: QuickActionsUpdate):
    try:
        actions_data = [item.model_dump() for item in req.actions]
        with open(QUICK_ACTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(actions_data, f, ensure_ascii=False, indent=2)
        return success(message="保存成功")
    except Exception as e:
        return server_error(f"保存快捷指令失败: {str(e)}")

KNOWLEDGE_BASES = [
    { 
        "name": "藏书知识库", 
        "desc": "存储全馆图书基础信息，包含书名、作者、出版社、ISBN、主题简介等文本数据；支持用户自然语言检索藏书，用于AI问答、智能图书检索场景", 
        "dbname": "ttxz_csgl", 
        "filename": "ttxz_csgl" 
    },
    {
        "name": "活动知识库",
        "desc": "存储图书馆内所有活动相关信息，包括活动标题、内容详情、时间及来源等；支持用户检索近期或历史举办的文化活动信息",
        "dbname": "ttxz_hdxx",
        "filename": "ttxz_hdxx"
    },
    {
        "name": "常见问题知识库",
        "desc": "存储办证流程、借阅规则、服务指南以及其他相关的规章制度与活动信息；用于回答用户在业务办理、规定和相关指南上的提问",
        "dbname": "ttxz_zsk",
        "filename": "ttxz_zsk"
    }
]

@router.post("/querylist", response_model=dict, summary="查询列表", dependencies=[Depends(get_super_administrator)])
async def query_ai_list(query: AiQueryRequest):
    try:
        base_query = select(ai_table)
        
        # 默认过滤逻辑删除和无效数据
        if hasattr(ai_table.c, 'removed'):
            base_query = base_query.where(ai_table.c.removed == 0)
        if hasattr(ai_table.c, 'enabled'):
            base_query = base_query.where(ai_table.c.enabled == 1)
            
        filter_data = query.model_dump(exclude={"pageNo", "pageSize"}, exclude_unset=True, exclude_none=True)
        
        for field, value in filter_data.items():
            if value is not None and value != "":
                column = getattr(ai_table.c, field, None)
                if column is not None:
                    if isinstance(value, str):
                        base_query = base_query.where(column.like(f"%{value}%"))
                    else:
                        base_query = base_query.where(column == value)
                        
        count_query = select(func.count()).select_from(base_query.subquery())
        total_records = await db_client.fetch_one(count_query)
        total = list(total_records.values())[0] if total_records else 0
        
        limit = query.pageSize
        offset = (query.pageNo - 1) * query.pageSize
        
        # 默认按创建时间倒序
        if hasattr(ai_table.c, 'createTime'):
            list_query = base_query.order_by(desc(ai_table.c.createTime)).limit(limit).offset(offset)
        else:
            list_query = base_query.limit(limit).offset(offset)
            
        records = await db_client.fetch_all(list_query)
        validated_records = [AiResponse(**record).model_dump() for record in records]
        
        return success(data={
            "total": total,
            "list": validated_records,
            "pageNo": query.pageNo,
            "pageSize": query.pageSize
        })
    except Exception as e:
        return server_error(f"查询失败: {str(e)}")

@router.post("/insert", summary="新增记录", dependencies=[Depends(get_super_administrator)])
async def insert_ai(data: AiCreate, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        insert_data = data.model_dump(exclude_unset=True, exclude_none=True)
        insert_data = fill_audit_fields(insert_data, user, is_update=False)
        stmt = insert(ai_table).values(**insert_data)
        await db_client.execute(stmt)
        return success(message="新增成功")
    except Exception as e:
        return server_error(f"新增失败: {str(e)}")

@router.post("/update", summary="修改记录", dependencies=[Depends(get_super_administrator)])
async def update_ai(data: AiUpdate, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        update_data = data.model_dump(exclude={"id"}, exclude_unset=True, exclude_none=True)
        if not update_data:
            return server_error("没有需要更新的字段")
            
        update_data = fill_audit_fields(update_data, user, is_update=True)
        stmt = update(ai_table).where(ai_table.c.id == getattr(data, 'id')).values(**update_data)
        affected = await db_client.execute(stmt)
        if affected > 0:
            return success(message="修改成功")
        return server_error("修改失败，记录不存在")
    except Exception as e:
        return server_error(f"修改失败: {str(e)}")

@router.post("/delete", summary="物理删除", dependencies=[Depends(get_super_administrator)])
async def delete_ai(req: DeleteRequest):
    try:
        stmt = delete(ai_table).where(ai_table.c.id == getattr(req, 'id'))
        affected = await db_client.execute(stmt)
        if affected > 0:
            return success(message="删除成功")
        return server_error("删除失败，记录不存在")
    except Exception as e:
        return server_error(f"删除失败: {str(e)}")

@router.post("/deleteLj", summary="逻辑删除", dependencies=[Depends(get_super_administrator)])
async def delete_lj_ai(req: DeleteRequest, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        if not hasattr(ai_table.c, 'removed') or not hasattr(ai_table.c, 'enabled'):
            return server_error("该表不支持逻辑删除(缺少 removed 或 enabled 字段)")
            
        update_data = {"removed": 1, "enabled": 0}
        update_data = fill_audit_fields(update_data, user, is_update=True)
        
        stmt = update(ai_table).where(ai_table.c.id == getattr(req, 'id')).values(**update_data)
        affected = await db_client.execute(stmt)
        if affected > 0:
            return success(message="逻辑删除成功")
        return server_error("逻辑删除失败，记录不存在")
    except Exception as e:
        return server_error(f"逻辑删除失败: {str(e)}")

@router.post("/chat", summary="AI问答(含意图识别与向量检索)")
async def ai_chat(req: ChatRequest):
    """
    接收用户提问，利用大模型识别匹配的知识库意图，
    并动态调用对应的 milvus 召回模块获取上下文，
    最后将上下文喂给大模型得到最终回答。
    """
    question = req.question.strip()
    if not question:
        return server_error("提问不能为空")
        
    # AI问答对外开放，不需要用户登录参数，直接使用默认占位标识
    user = {"id": -1, "username": "*"}
        
    try:
        # 1. 关键字提取 (仅提取一次)
        keyword_prompt = """你是一个搜索助手。请根据用户的问题，提取出用于检索的核心关键字（如书名、作者、活动名称等）。
        请以 JSON 格式返回结果：{"keyword": "提取的关键字，如果没有则为空"}
        注意：只能返回合法的 JSON 字符串，不要包含任何 markdown 格式或其他字符。
        """
        
        keyword_messages = [
            {"role": "system", "content": keyword_prompt},
            {"role": "user", "content": f"用户问题：{question}"}
        ]
        
        keyword_response = call_llm(keyword_messages, temperature=0.1).strip()
        # 清理可能存在的 markdown 标记
        if keyword_response.startswith("```json"):
            keyword_response = keyword_response[7:-3].strip()
        elif keyword_response.startswith("```"):
            keyword_response = keyword_response[3:-3].strip()
            
        try:
            keyword_data = json.loads(keyword_response)
            search_keyword = keyword_data.get("keyword", "")
        except json.JSONDecodeError:
            logger.error(f"关键字提取 JSON 解析失败，原始响应: {keyword_response}")
            search_keyword = ""
            
        # 2. 3个同步并行去查询
        def do_query(kb):
            filename = kb["filename"]
            if filename == "ttxz_csgl":
                kw = search_keyword if search_keyword else question
                try:
                    logger.info(f"正在查询藏书知识库，搜索关键字: {kw}")
                    return filename, search_books(kw, 5)
                except Exception as e:
                    logger.error(f"执行 search_books 异常: {e}")
                    return filename, []
            else:
                try:
                    logger.info(f"正在查询知识库 milvus.{filename}")
                    module = importlib.import_module(f"milvus.{filename}")
                    if hasattr(module, "recall"):
                        return filename, module.recall(query=question, top_k=5)
                except Exception as e:
                    logger.error(f"加载模块 milvus.{filename} 失败或执行召回异常: {e}")
                return filename, []
                
        # 使用 asyncio.gather 实现并行查询，采用 asyncio.to_thread 避免阻塞
        query_tasks = [asyncio.to_thread(do_query, kb) for kb in KNOWLEDGE_BASES]
        results_list = await asyncio.gather(*query_tasks)
        results_dict = dict(results_list)
        
        recall_results = []
        context_str = ""
        matched_filename = "none"
        matched_dbname = ""
        
        # 3. 根据顺序优先匹配（如果第一个有值那只会用第一个不要混合）
        for kb in KNOWLEDGE_BASES:
            filename = kb["filename"]
            res = results_dict.get(filename, [])
            if res:
                matched_filename = filename
                matched_dbname = kb["dbname"]
                recall_results = res
                
                logger.info(f"按顺序优先匹配到知识库: {filename}")
                
                # 格式化上下文
                if filename == "ttxz_csgl":
                    contexts = []
                    for idx, item in enumerate(recall_results):
                        book_info = (
                            f"【{idx+1}】 书名: {item.get('title', '')}, "
                            f"作者: {item.get('author', '')}, "
                            f"出版社: {item.get('publisher', '')}, "
                            f"索书号: {item.get('callNo', '')}, "
                            f"书架位置: {item.get('location', '')}"
                        )
                        contexts.append(book_info)
                    context_str = "\n".join(contexts)
                else:
                    contexts = [f"【{idx+1}】" + item.get("full_text", "") for idx, item in enumerate(recall_results)]
                    context_str = "\n".join(contexts)
                    
                break  # 匹配到第一个有值的知识库后直接跳出，不混合其他结果
        
        # 3. 生成最终回答
        if context_str:
            chat_prompt = f"""你是一个知识渊博、语气自然的智能助手。请解答用户的问题。
            
            内部知识片段如下（仅供你作为背景知识参考，在回答中绝对不要出现“根据参考信息”、“参考提供的内容”、“知识库显示”等暴露你读取了资料的字眼）：
            {context_str}
            
            要求：
            1. 语气亲切自然，像一个专业的顾问在与用户交流。
            2. 将知识片段中的信息自然地融入你的回答中，并做适当的归纳、总结和补充，帮助用户更好地了解情况。
            3. 如果有结构化的数据（如藏书列表、黄浦区活动详情等），请优先使用 Markdown 展示符合移动端样式布局，不要使用表格输出，请你使用**的markdown规范避免多输出或者少输出准确性一定要高，使其一目了然。
            4. 必须使用 Markdown 格式返回。
            5. 如果你不知道答案或内部知识没有提及，请用委婉的语气告诉用户暂时不清楚不要擅自回复任何内容。
            6. 如果知识片段中没有任何内容或无法解答用户的问题，请用委婉的语气告诉用户知识库暂无相关内容，一定非常重要。
            """
        else:
            chat_prompt = f"""你是一个智能问答助手。请回答用户的问题，答复时请用委婉的语气告诉用户知识库暂无相关内容，内容精简不要说废话且跟符合人类的回答。
            要求：
            1. 必须使用 Markdown 格式返回。
            2. 布局清晰，层次分明。
            3. 知识库中没有任何内容，请用委婉的语气告诉用户暂无相关内容，一定非常重要。
            4. 请优先使用 Markdown 展示符合移动端样式布局，不要使用表格输出，请你使用**的markdown规范避免多输出或者少输出准确性一定要高，使其一目了然。
            5. 请你委婉拒绝用户的提问因为该回答是因为知识库不存在，如果用户提问是图书馆内书籍类的可以提及但是请你告知用户这些书籍在图书馆中不存在，如果是其他的明确告知用户不清楚必须要拒绝。
            """
        
        print(chat_prompt)
        chat_messages = [
            {"role": "system", "content": chat_prompt},
            {"role": "user", "content": question}
        ]
        
        # 准备记录到数据库的函数，等流式输出完成后在后台执行
        async def save_to_db(full_answer: str):
            try:
                # 记录完整的向量召回结果
                insert_data = {
                    "userQuestion": question,
                    "vectorRecallResult": json.dumps(recall_results, ensure_ascii=False) if recall_results else "",
                    "intentDbname": matched_dbname,
                    "enabled": 1,
                    "removed": 0
                }
                # 这里使用默认系统用户的审计字段，因为流式结束后可能 Request 上下文已经变了
                insert_data = fill_audit_fields(insert_data, user, is_update=False)
                stmt = insert(ai_table).values(**insert_data)
                await db_client.execute(stmt)
            except Exception as e:
                logger.error(f"保存AI问答记录失败: {e}")
        
        async def generate():
            full_answer = ""
            try:
                # 优先返回意图和召回结果给前端作为 metadata，直接拿原封不动的召回结果
                metadata = {
                    "intent": matched_filename,
                    "recall": recall_results
                }
                yield f"data: {json.dumps({'type': 'metadata', 'data': metadata}, ensure_ascii=False)}\n\n"
                
                # 调用大模型流式接口
                response_stream = call_llm(chat_messages, stream=True, temperature=0.4)
                for chunk in response_stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_answer += content
                        yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"流式输出异常: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            finally:
                # 流式输出结束后，异步记录数据到 MySQL
                if full_answer:
                    import asyncio
                    asyncio.create_task(save_to_db(full_answer))
        
        return StreamingResponse(generate(), media_type="text/event-stream")
        
    except Exception as e:
        logger.error(f"AI问答失败: {e}")
        return server_error(f"AI问答失败: {str(e)}")

# 第一版本废弃
# @router.post("/chat", summary="AI问答(含意图识别与向量检索)")
# async def ai_chat(req: ChatRequest):
#     """
#     接收用户提问，利用大模型识别匹配的知识库意图，
#     并动态调用对应的 milvus 召回模块获取上下文，
#     最后将上下文喂给大模型得到最终回答。
#     """
#     question = req.question.strip()
#     if not question:
#         return server_error("提问不能为空")
        
#     # AI问答对外开放，不需要用户登录参数，直接使用默认占位标识
#     user = {"id": -1, "username": "*"}
        
#     try:
#         # 1. 意图识别
#         intent_prompt = f"""你是一个知识库路由助手。请根据用户的问题，从以下知识库中选择最匹配的一个。
#         只需返回匹配的 filename 字符串即可，不要包含其他任何字符。如果都不匹配，请返回 "none"。
#         知识库列表：
#         {json.dumps(KNOWLEDGE_BASES, ensure_ascii=False)}
#         """
        
#         intent_messages = [
#             {"role": "system", "content": intent_prompt},
#             {"role": "user", "content": f"用户问题：{question}"}
#         ]
        
#         matched_filename = call_llm(intent_messages, temperature=0.1).strip().strip('"').strip("'")
        
#         recall_results = []
#         context_str = ""
#         matched_dbname = ""
        
#         # 2. 如果匹配到知识库，进行向量召回
#         if matched_filename and matched_filename != "none":
#             kb_info = next((kb for kb in KNOWLEDGE_BASES if kb.get("filename") == matched_filename), None)
#             if kb_info:
#                 matched_dbname = kb_info["dbname"]
                
#             try:
#                 # 动态加载对应的 milvus 模块进行召回
#                 module = importlib.import_module(f"milvus.{matched_filename}")
#                 if hasattr(module, "recall"):
#                     recall_results = module.recall(query=question, top_k=5)
                    
#                     if recall_results:
#                         contexts = [f"【{idx+1}】" + item.get("full_text", "") for idx, item in enumerate(recall_results)]
#                         context_str = "\n".join(contexts)
#             except Exception as e:
#                 logger.error(f"加载模块 milvus.{matched_filename} 失败或执行召回异常: {e}")
        
#         # 3. 生成最终回答
#         if context_str:
#             chat_prompt = f"""你是一个知识渊博、语气自然的智能助手。请解答用户的问题。
            
#             内部知识片段如下（仅供你作为背景知识参考，在回答中绝对不要出现“根据参考信息”、“参考提供的内容”、“知识库显示”等暴露你读取了资料的字眼）：
#             {context_str}
            
#             要求：
#             1. 语气亲切自然，像一个专业的顾问在与用户交流。
#             2. 将知识片段中的信息自然地融入你的回答中，并做适当的归纳、总结和补充，帮助用户更好地了解情况。
#             3. 如果有结构化的数据（如藏书列表、活动详情等），请优先使用 Markdown 展示符合移动端样式布局，不要使用表格输出，请你使用**的markdown规范避免多输出或者少输出准确性一定要高，使其一目了然。
#             4. 必须使用 Markdown 格式返回。
#             5. 如果你不知道答案或内部知识没有提及，请用委婉的语气告诉用户暂时不清楚不要擅自回复任何内容。
#             6. 当{context_str}知识库没有任何内容时，请用委婉的语气告诉用户知识库暂无相关内容，一定非常重要。
#             """
#         else:
#             chat_prompt = f"""你是一个智能问答助手。请回答用户的问题，答复时请用委婉的语气告诉用户知识库暂无相关内容，内容精简不要说废话且跟符合人类的回答。
#             要求：
#             1. 必须使用 Markdown 格式返回。
#             2. 布局清晰，层次分明。
#             3. 当{context_str}知识库没有任何内容时，请用委婉的语气告诉用户知识库暂无相关内容，一定非常重要。
#             4. 请优先使用 Markdown 展示符合移动端样式布局，不要使用表格输出，请你使用**的markdown规范避免多输出或者少输出准确性一定要高，使其一目了然。
#             5. 请你委婉拒绝用户的提问因为该回答是因为知识库不存在，如果用户提问是图书馆内书籍类的可以提及但是请你告知用户这些书籍在图书馆中不存在，如果是其他的明确告知用户不清楚必须要拒绝
#             """
        
#         print(chat_prompt)
#         chat_messages = [
#             {"role": "system", "content": chat_prompt},
#             {"role": "user", "content": question}
#         ]
        
#         # 准备记录到数据库的函数，等流式输出完成后在后台执行
#         async def save_to_db(full_answer: str):
#             try:
#                 # 记录完整的向量召回结果
#                 insert_data = {
#                     "userQuestion": question,
#                     "vectorRecallResult": json.dumps(recall_results, ensure_ascii=False) if recall_results else "",
#                     "intentDbname": matched_dbname,
#                     "enabled": 1,
#                     "removed": 0
#                 }
#                 # 这里使用默认系统用户的审计字段，因为流式结束后可能 Request 上下文已经变了
#                 insert_data = fill_audit_fields(insert_data, user, is_update=False)
#                 stmt = insert(ai_table).values(**insert_data)
#                 await db_client.execute(stmt)
#             except Exception as e:
#                 logger.error(f"保存AI问答记录失败: {e}")
        
#         async def generate():
#             full_answer = ""
#             try:
#                 # 优先返回意图和召回结果给前端作为 metadata，直接拿原封不动的召回结果
#                 metadata = {
#                     "intent": matched_filename,
#                     "recall": recall_results
#                 }
#                 yield f"data: {json.dumps({'type': 'metadata', 'data': metadata}, ensure_ascii=False)}\n\n"
                
#                 # 调用大模型流式接口
#                 response_stream = call_llm(chat_messages, stream=True, temperature=0.4)
#                 for chunk in response_stream:
#                     if chunk.choices and chunk.choices[0].delta.content:
#                         content = chunk.choices[0].delta.content
#                         full_answer += content
#                         yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                
#                 yield "data: [DONE]\n\n"
#             except Exception as e:
#                 logger.error(f"流式输出异常: {e}")
#                 yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
#             finally:
#                 # 流式输出结束后，异步记录数据到 MySQL
#                 if full_answer:
#                     import asyncio
#                     asyncio.create_task(save_to_db(full_answer))
        
#         return StreamingResponse(generate(), media_type="text/event-stream")
        
#     except Exception as e:
#         logger.error(f"AI问答失败: {e}")
#         return server_error(f"AI问答失败: {str(e)}")
