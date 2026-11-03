import type { AgentChatData, KnowledgeGraphReference, KnowledgeSource } from '@/api/agent'
import type { McpApproval } from '@/api/mcp'

export interface LocalFileSource {
  path: string
  startLine: number
  endLine: number
  characters: number
  truncated: boolean
}

// 桌面端可以在发送前准备本地片段；普通网页版不提供该扩展。
export interface PreparedChatMessage {
  query: string
  localSources?: LocalFileSource[]
  onAccepted?: () => void
}
export interface ChatComposerExtension {
  prepareMessage(question: string, conversationId: string, signal: AbortSignal): Promise<PreparedChatMessage | null>
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  time: string
  agentName?: string
  intent?: string
  state?: 'streaming' | 'done' | 'error' | 'stopped' | 'confirmation'
  error?: string
  toolStatus?: string
  templateTaskId?: string
  confirmation?: McpApproval
  mcpRequest?: AgentChatData
  sources?: KnowledgeSource[]
  graphReferences?: KnowledgeGraphReference[]
  localSources?: LocalFileSource[]
  // 第二套执行逻辑（报告模板）命中的模板名称，仅用于展示
  templateName?: string
}

export interface Conversation {
  id: string
  messages: ChatMessage[]
  draft: string
  updatedAt: string
  // 更早对话由后端压缩成的记忆摘要，随本地历史一起缓存并回传服务端
  memory?: string
  // 已经被记忆摘要覆盖的消息条数：下一轮只回传该游标之后的对话，避免重复总结
  memoryCount?: number
}

export interface ChatHistory { activeId: string; conversations: Conversation[] }

export function createConversation(): Conversation {
  return { id: crypto.randomUUID(), messages: [], draft: '', updatedAt: new Date().toISOString() }
}

export function historyStorageKey(user: { id: number; account?: string; orgId?: number; agentId?: number }) {
  return `fijo-chat-history:${JSON.stringify([user.id, user.account || '', user.orgId || null, user.agentId || null])}`
}

export function readChatHistory(raw: string | null): ChatHistory {
  if (!raw) {
    const conversation = createConversation()
    return { activeId: conversation.id, conversations: [conversation] }
  }
  const value = JSON.parse(raw) as ChatHistory
  if (!value || typeof value.activeId !== 'string' || !Array.isArray(value.conversations) || !value.conversations.length) throw new Error('无效的对话记录')
  const ids = new Set<string>()
  for (const conversation of value.conversations) {
    if (!conversation || typeof conversation.id !== 'string' || ids.has(conversation.id) || typeof conversation.draft !== 'string' || typeof conversation.updatedAt !== 'string' || !Array.isArray(conversation.messages)) throw new Error('无效的会话')
    ids.add(conversation.id)
    // 记忆摘要与游标是可选字段：类型不合法时直接丢弃，不影响历史记录可读性
    if (conversation.memory !== undefined && (typeof conversation.memory !== 'string' || conversation.memory.length > 4000)) conversation.memory = undefined
    if (conversation.memoryCount !== undefined && (!Number.isSafeInteger(conversation.memoryCount) || conversation.memoryCount < 0)) conversation.memoryCount = undefined
    if (conversation.memoryCount !== undefined && conversation.memoryCount > conversation.messages.length) conversation.memoryCount = conversation.messages.length
    for (const message of conversation.messages) {
      if (!message || !Number.isSafeInteger(message.id) || !['user', 'assistant'].includes(message.role) || typeof message.content !== 'string' || typeof message.time !== 'string') throw new Error('无效的消息')
      for (const key of ['agentName', 'intent', 'error', 'templateName'] as const) {
        if (message[key] !== undefined && typeof message[key] !== 'string') throw new Error('无效的消息字段')
      }
      if (message.state !== undefined && !['streaming', 'done', 'error', 'stopped', 'confirmation'].includes(message.state)) throw new Error('无效的消息状态')
      if (message.sources !== undefined && (!Array.isArray(message.sources) || message.sources.length > 100 || message.sources.some(source => !source || !Number.isSafeInteger(source.id) || source.id <= 0 || !Number.isSafeInteger(source.tenantId) || source.tenantId <= 0 || !Number.isSafeInteger(source.version) || source.version < 0 || ['title', 'fileUrl', 'fileId', 'tenantName'].some(key => typeof source[key as keyof KnowledgeSource] !== 'string')))) throw new Error('无效的引用资料')
      if (message.graphReferences !== undefined && (!Array.isArray(message.graphReferences) || message.graphReferences.length > 3 || message.graphReferences.some(row => !row || !Number.isSafeInteger(row.tenantId) || row.tenantId <= 0 || typeof row.tenantName !== 'string' || typeof row.question !== 'string' || typeof row.answer !== 'string' || !row.answer || row.answer.length > 8000 || !Array.isArray(row.files) || row.files.length > 5 || row.files.some(file => typeof file !== 'string')))) throw new Error('无效的知识图谱参考')
      if (message.localSources !== undefined && (!Array.isArray(message.localSources) || message.localSources.length > 4 || message.localSources.some(source => !source || typeof source.path !== 'string' || !source.path || source.path.length > 2048 || !Number.isSafeInteger(source.startLine) || source.startLine < 1 || !Number.isSafeInteger(source.endLine) || source.endLine < source.startLine || !Number.isSafeInteger(source.characters) || source.characters < 0 || source.characters > 12000 || typeof source.truncated !== 'boolean'))) throw new Error('无效的本地文件来源')
      if (message.localSources?.length && message.state === 'confirmation' && !message.mcpRequest) {
        message.state = 'error'
        message.confirmation = undefined
        message.error = '文件正文未保存在历史中，请重新添加文件后发送。'
      }
      if (message.templateTaskId !== undefined && (typeof message.templateTaskId !== 'string' || !/^[a-f0-9]{24}$/.test(message.templateTaskId))) throw new Error('无效的模板任务')
      // 刷新不能恢复网络连接，保留已收到的内容并明确标记停止。
      if (message.state === 'streaming') message.state = 'stopped'
    }
  }
  if (!ids.has(value.activeId)) value.activeId = value.conversations[0].id
  return value
}

export function answerWithSources(message: ChatMessage): string {
  let content = message.content
  if (message.sources?.length) content += `\n\n引用资料（检索来源，请结合正文引用核对）：\n${message.sources.map((source, index) => `[资料${index + 1}] ${source.title || '未命名资料'}；知识库：${source.tenantName} #${source.tenantId}；记录 #${source.id}；版本 ${source.version}；文件：${source.fileUrl || '手动录入'}`).join('\n')}`
  if (message.graphReferences?.length) content += `\n\n知识图谱参考（关联梳理，事实请以上方引用资料原文为准）：\n${message.graphReferences.map(graph => `${graph.tenantName || `知识库 ${graph.tenantId}`}：${graph.answer}${graph.files.length ? `（图谱原文出处：${graph.files.join('、')}）` : ''}`).join('\n')}`
  if (message.localSources?.length) content += `\n\n本地文件（本次发送的片段）：\n${message.localSources.map(source => `${source.path}；第 ${source.startLine}—${source.endLine} 行${source.truncated ? '；部分内容' : ''}`).join('\n')}`
  return content
}

export function serializeChatHistory(history: ChatHistory): string {
  return JSON.stringify(history, (_key, value) => {
    if (value && typeof value === 'object' && Array.isArray(value.localSources) && value.localSources.length && value.mcpRequest) {
      const { mcpRequest: _request, ...metadata } = value
      return metadata
    }
    return value
  })
}
