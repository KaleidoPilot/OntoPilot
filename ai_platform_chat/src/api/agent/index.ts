import type { McpApproval } from '@/api/mcp'
import request, { isLoginExpired, leaveForLogin } from '@/util/request'

export interface PersonalAgent {
  id: number; agentName: string; agentDescription: string; agentKey: string
  agentType: 1 | 2; userId: number | null; enabled: 0 | 1; canManage: boolean
  mcpIds: string | null; tenantIds: string | null; createTime: string | null
}
export interface PersonalAgentForm {
  agentName: string; agentDescription: string; systemPrompt: string; userPromptTemplate: string
  temperature: number; topP: number; intentLlmId: number | undefined; taskLlmId: number | undefined
  executLlmId: number | undefined; summaryLlmId: number | undefined
  tenantIds: number[]; mcpIds: number[]; skillIds: number[]; tenantTopK: number; tenantScore: number; enabled: 0 | 1
}
export interface AgentShareRecord {
  id: number; agentId: number; shareUserId: number; receiveUserId: number
  realName: string | null; account: string | null; enabled: 0 | 1; createTime: string; updateTime: string
}
export interface AgentReceiver { id: number; realName: string; account: string }
export const getPersonalAgentPage = (params: { keyword?: string; source?: 'all' | 'mine' | 'received' | 'company'; pageNo: number; pageSize: number }) => request<{ list: PersonalAgent[]; total: number }>({ url: '/agent/personal/querylist', method: 'get', params })
export const getPersonalAgent = (id: number) => request<PersonalAgentForm & { id: number; shareUserIds: number[] }>({ url: `/agent/personal/${id}`, method: 'get' })
export const getPersonalAgentModels = () => request<{ models: Array<{ id: number; model: string; type: 1 | 2 | 3 | 4 }> }>({ url: '/agent/personal/options', method: 'get' })
export const createPersonalAgent = (data: PersonalAgentForm) => request<{ id: number }>({ url: '/agent/personal/insert', method: 'post', data })
export const updatePersonalAgent = (id: number, data: PersonalAgentForm) => request({ url: '/agent/personal/update', method: 'post', data: { id, ...data } })
export const deletePersonalAgent = (id: number) => request({ url: '/agent/personal/delete', method: 'post', data: { id } })
export const getAgentShares = (id: number) => request<{ list: AgentShareRecord[] }>({ url: `/agent/personal/${id}/shares`, method: 'get' })
export const getAgentShareUsers = (keyword = '') => request<{ list: AgentReceiver[]; total: number }>({ url: '/agent/personal/share-users', method: 'get', params: { keyword: keyword || undefined, pageNo: 1, pageSize: 100 } })
export const sharePersonalAgent = (id: number, receiveUserIds: number[]) => request({ url: '/agent/personal/share', method: 'post', data: { id, receiveUserIds } })

export interface AgentChatData {
  // 技能组已替代智能体作为第一层筛选：对话必须带上用户选定的技能组 ID
  skillGroupId: number
  // Auto 模式未匹配到专项技能组时为 true：由 KaleidoPilot 承接，只做基础回复与知识库查询
  autoAssistant?: boolean
  // 用户显式选择“知识库查询”：跳过技能组匹配与技能编排，一律按用户被授权的知识库做向量召回
  knowledgeOnly?: boolean
  // 当前用户所属用户组：服务端据此加载该用户可用的全部技能组与技能，供能力介绍使用
  userGroupId?: number
  query: string; mcpIds?: number[]; privateSkillId?: number; skillId?: number; tenantIds?: number[]
  mcpApproval?: Pick<McpApproval, 'configId' | 'id'>
  // 多轮上下文：最近若干轮对话（来自本地缓存，不含本次提问）+ 更早对话的记忆摘要
  history?: AgentChatHistoryItem[]
  memory?: string
}
// 一轮历史对话：仅用于让模型理解上下文，不做服务端持久化
export interface AgentChatHistoryItem { role: 'user' | 'assistant'; content: string }
export interface KnowledgeSource { id: number; version: number; tenantId: number; title: string; fileUrl: string; fileId: string; tenantName: string }
// 知识图谱参考：由后端在同一批知识库向量命中后补充，仅用于说明实体关联，
// files 是图谱回答实际引用的原文文件名，事实仍以 KnowledgeSource 的原文为准。
export interface KnowledgeGraphReference { tenantId: number; tenantName: string; question: string; answer: string; files: string[] }

export interface AgentStreamEvent {
  type: 'metadata' | 'content' | 'error' | 'tool_status' | 'confirmation' | 'sources'
  content?: string
  message?: string
  // metadata 事件：intent 标识本次走哪条执行链路，templateName 仅模板链路下发；
  //                  memory / memoryConsumed 为服务端压缩后的对话记忆摘要与已消费的消息条数
  // sources 事件：sources 为引用资料，graphReferences 为知识图谱参考（可能不存在）
  data?: { intent?: string; name?: string; status?: string; templateName?: string; memory?: string; memoryConsumed?: number; sources?: KnowledgeSource[]; graphReferences?: KnowledgeGraphReference[] } & Partial<McpApproval>
}

// 用户组可用的技能组（名称 + id + 描述），替代原智能体列表
export interface SkillGroupOption {
  id: number
  groupName: string
  description?: string
}

// 按用户组查询可用技能组；autoMode=true 表示支持 Auto 自动匹配
export function fetchGroupSkillGroups(groupId: number) {
  return request<{ autoMode: boolean; list: SkillGroupOption[] }>({
    url: 'agent/group/skill-groups', method: 'POST', data: { groupId }
  })
}

// Auto 模式：根据「用户问题 + 用户组」匹配唯一最合适的技能组；
// matched=false 表示模型判断所有候选都不相关，此时 skillGroup 为 null，
// 前端应改用 KaleidoPilot 承接（autoAssistant=true），而不是报错。
export function matchGroupSkillGroup(groupId: number, question: string) {
  return request<{ matched: boolean; skillGroup: SkillGroupOption | null; list: SkillGroupOption[] }>({
    url: 'agent/group/skill-groups/match', method: 'POST', data: { groupId, question }
  })
}

// 与后端 AgentChatRequest 及 SSE 事件保持一致，不使用旧 chatbot 服务。
export async function streamAgentChat(
  data: AgentChatData,
  signal: AbortSignal,
  onEvent: (event: AgentStreamEvent) => void
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'text/event-stream' }
  const token = localStorage.getItem('fijo-chat-token')
  if (token) headers.Authorization = `Bearer ${token}`
  try {
    const user = JSON.parse(localStorage.getItem('fijo-chat-userInfo') || '{}')
    if (user.mcpToken) headers['x-mcp-token'] = user.mcpToken
    if (user.id) headers['x-user-id'] = String(user.id)
    if (user.account) headers['x-user-name'] = user.account
    if (user.userType) headers['x-user-type'] = user.userType
  } catch { /* 损坏的登录信息交给后端校验 */ }
  const response = await fetch(`${(import.meta.env.VITE_APP_BASE_URL || '').replace(/\/$/, '')}/agent/chat/stream`, {
    method: 'POST', headers, body: JSON.stringify(data), signal
  })
  if (!response.ok || !response.headers.get('content-type')?.includes('text/event-stream')) {
    const error = await response.json().catch(() => null)
    if (isLoginExpired(response.status, error)) {
      leaveForLogin()
      return new Promise(() => undefined)
    }
    throw new Error(String(error?.message || error?.detail || `对话服务暂不可用（${response.status}）`).replace(/智能体/g, '技能组'))
  }
  if (!response.body) throw new Error('当前浏览器无法接收流式回答')
  await readAgentStream(response.body, onEvent)
}

export async function readAgentStream(body: ReadableStream<Uint8Array>, onEvent: (event: AgentStreamEvent) => void) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false
  const parseFrame = (frame: string) => {
    const data = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n')
    if (!data) return
    if (data.trim() === '[DONE]') { completed = true; return }
    const event = JSON.parse(data) as AgentStreamEvent
    if (event.type === 'error') {
      if (isLoginExpired(undefined, { message: event.message })) {
        leaveForLogin()
        completed = true
        return
      }
      throw new Error((event.message || '技能组执行失败').replace(/智能体/g, '技能组'))
    }
    onEvent(event)
  }
  try {
    while (!completed) {
      const { done, value } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        parseFrame(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (completed) break
      }
      if (done) {
        if (buffer.trim()) parseFrame(buffer)
        if (!completed) throw new Error('连接已中断，回答可能不完整。请检查已有结果后再决定是否重新发送。')
        break
      }
    }
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}


