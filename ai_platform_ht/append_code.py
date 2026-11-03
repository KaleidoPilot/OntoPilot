import sys

code = '''
@router.post("/chat/stream", summary="智能体调用流式接口")
async def agent_chat_stream(req: AgentChatRequest):
    key = req.key.strip()
    question = req.query.strip()
    
    if not key or not question:
        return server_error("key或提问不能为空")
        
    try:
        # 1. 查询智能体配置
        agent_sql = "SELECT * FROM AI_AGENT WHERE `KEY` = :key AND ENABLED = 1 AND REMOVED = 0"
        agent_record = await db_client.fetch_one(text(agent_sql), {"key": key})
        
        if not agent_record:
            return server_error("智能体不存在或已被停用")
            
        agent = dict(agent_record)
        skill_ids = agent.get("skillIds") or ""
        system_prompt = agent.get("systemPrompt") or ""
        intent_llm_id = agent.get("intentLlmId")
        task_llm_id = agent.get("taskLlmId")
        execut_llm_id = agent.get("executLlmId")
        summary_llm_id = agent.get("summaryLlmId")
        tenant_ids = agent.get("tenantIds") or ""
        tenant_top_k = agent.get("tenantTopK") or 5
        tenant_score_str = agent.get("tenantScore") or "0.4"
        try:
            tenant_score = float(tenant_score_str)
        except:
            tenant_score = 0.4

        # 查询模型配置
        llm_ids = [idx for idx in [intent_llm_id, task_llm_id, execut_llm_id, summary_llm_id] if idx]
        models = {}
        if llm_ids:
            models_sql = f"SELECT ID, MODEL, API_KEY, BASE_URL FROM MODEL_CONFIG WHERE ID IN ({','.join(map(str, llm_ids))}) AND ENABLED = 1 AND REMOVED = 0"
            model_records = await db_client.fetch_all(text(models_sql))
            for m in model_records:
                models[m["ID"]] = m

        def get_model_cfg(llm_id):
            if llm_id in models:
                return {
                    "api_key": models[llm_id]["API_KEY"],
                    "base_url": models[llm_id]["BASE_URL"],
                    "model": models[llm_id]["MODEL"]
                }
            return None

        intent_cfg = get_model_cfg(intent_llm_id)
        task_cfg = get_model_cfg(task_llm_id)
        execut_cfg = get_model_cfg(execut_llm_id)
        summary_cfg = get_model_cfg(summary_llm_id)

        # 加载技能列表
        skills_info = []
        if skill_ids:
            valid_skill_ids = [s for s in skill_ids.split(",") if s.strip().isdigit()]
            if valid_skill_ids:
                skills_sql = f"SELECT ID, SKILL_NAME, SKILL_DESCRIPTION FROM SKILL WHERE ID IN ({','.join(valid_skill_ids)}) AND ENABLED = 1 AND REMOVED = 0"
                skills_records = await db_client.fetch_all(text(skills_sql))
                skills_info = [dict(r) for r in skills_records]

        async def generate():
            try:
                matched_skill_id = None
                
                # 2. 意图匹配是否存在合适的技能
                if skills_info and intent_cfg:
                    skills_desc = "\\n".join([f"技能ID: {s['ID']}, 名称: {s['SKILL_NAME']}, 描述: {s.get('SKILL_DESCRIPTION', '')}" for s in skills_info])
                    intent_prompt = f"你是一个意图识别助手。请根据用户的问题，从以下技能列表中选择最匹配的一个。只需返回匹配的技能ID（纯数字），如果都不匹配，请返回 'none'。\\n技能列表：\\n{skills_desc}"
                    
                    intent_messages = [
                        {"role": "system", "content": intent_prompt},
                        {"role": "user", "content": f"用户问题：{question}"}
                    ]
                    
                    client = OpenAI(api_key=intent_cfg["api_key"], base_url=intent_cfg["base_url"])
                    resp = client.chat.completions.create(
                        model=intent_cfg["model"],
                        messages=intent_messages,
                        temperature=0.1
                    )
                    intent_res = resp.choices[0].message.content.strip().strip('"').strip("'")
                    if intent_res != "none" and intent_res.isdigit():
                        matched_skill_id = intent_res

                # 3. 如果存在则进行任务编排执行
                if matched_skill_id:
                    # 模拟任务编排执行过程
                    # 实际可以调用 utils.ai-agent.tableAgent.agent 中的方法
                    yield f"data: {json.dumps({'type': 'metadata', 'data': {'intent': f'skill_{matched_skill_id}'}}, ensure_ascii=False)}\\n\\n"
                    
                    if not summary_cfg:
                        yield f"data: {json.dumps({'type': 'error', 'message': '缺少总结模型配置'}, ensure_ascii=False)}\\n\\n"
                        return

                    chat_prompt = f"{system_prompt}\\n\\n你正在使用技能 {matched_skill_id} 处理用户的问题。请用 Markdown 格式输出最终结果。"
                    chat_messages = [
                        {"role": "system", "content": chat_prompt},
                        {"role": "user", "content": question}
                    ]
                    client = OpenAI(api_key=summary_cfg["api_key"], base_url=summary_cfg["base_url"])
                    resp_stream = client.chat.completions.create(
                        model=summary_cfg["model"],
                        messages=chat_messages,
                        temperature=0.4,
                        stream=True
                    )
                    for chunk in resp_stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\\n\\n"
                    yield "data: [DONE]\\n\\n"
                    return

                # 分支 3: 如果不存在则调用（向量数据库）匹配选择的知识库
                context_str = ""
                if tenant_ids:
                    # 匹配选择的知识库
                    items = await asyncio.to_thread(
                        get_knowledge_store().retrieve,
                        question=question,
                        confidence=tenant_score,
                        top_k=tenant_top_k,
                        tenant_id=tenant_ids,
                    )
                    if items:
                        contexts = [f"【{idx+1}】" + item.get("full_text", "") for idx, item in enumerate(items)]
                        context_str = "\\n".join(contexts)

                # 4. （知识库）和（智能体提示词）正常回答 或者 如果知识库不存在则模型和（系统提示词）输出
                yield f"data: {json.dumps({'type': 'metadata', 'data': {'intent': 'knowledge_or_llm'}}, ensure_ascii=False)}\\n\\n"
                
                if not summary_cfg:
                    # 退级使用 intent_cfg
                    summary_cfg = intent_cfg
                
                if not summary_cfg:
                    yield f"data: {json.dumps({'type': 'error', 'message': '缺少模型配置'}, ensure_ascii=False)}\\n\\n"
                    return

                if context_str:
                    chat_prompt = f"{system_prompt}\\n\\n你是一个知识渊博、语气自然的智能助手。请解答用户的问题。\\n\\n内部知识片段如下（仅供你作为背景知识参考，在回答中绝对不要出现“根据参考信息”等暴露你读取了资料的字眼）：\\n{context_str}\\n\\n要求：\\n1. 必须使用 Markdown 格式返回。\\n2. 如果知识片段中没有任何内容或无法解答用户的问题，请用委婉的语气告诉用户知识库暂无相关内容。"
                else:
                    chat_prompt = f"{system_prompt}\\n\\n你是一个智能问答助手。请直接根据你的知识解答用户的问题，不要说废话。\\n要求：\\n1. 必须使用 Markdown 格式返回。\\n2. 如果不知道请委婉拒绝。"

                chat_messages = [
                    {"role": "system", "content": chat_prompt},
                    {"role": "user", "content": question}
                ]
                
                client = OpenAI(api_key=summary_cfg["api_key"], base_url=summary_cfg["base_url"])
                resp_stream = client.chat.completions.create(
                    model=summary_cfg["model"],
                    messages=chat_messages,
                    temperature=0.4,
                    stream=True
                )
                for chunk in resp_stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\\n\\n"
                yield "data: [DONE]\\n\\n"

            except Exception as e:
                logger.error(f"流式输出异常: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\\n\\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
        
    except Exception as e:
        logger.error(f"智能体问答失败: {e}")
        return server_error(f"智能体问答失败: {str(e)}")
'''

with open('d:/project/python/ai_platform/ai_platform_ht/api/endpoints/agent/api/agentApi.py', 'a', encoding='utf-8') as f:
    f.write('\n\n' + code + '\n')
