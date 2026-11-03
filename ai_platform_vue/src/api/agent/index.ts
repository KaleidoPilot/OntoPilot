import request from '@/util/request'

export interface AgentCreate {
  agentName: string
  projectGroupIds?: string
  skillIds?: string
  templateIds?: string
  agentDescription?: string
  systemPrompt: string
  userPromptTemplate?: string
  temperature?: number
  topP?: number
  key?: string
  intentLlmId?: number | null
  taskLlmId?: number | null
  executLlmId?: number | null
  summaryLlmId?: number | null
  tenantIds?: string
  mcpIds?: string
  tenantTopK?: number
  tenantScore?: number
  enabled?: number
}

// 可绑定的 MCP / 知识库 / 报告模板（模板来自 TEMPLATE_GENERATION，按公司查询）
export const getAgentBindings = () => request<{
  mcps: Array<{ id: number; name: string }>
  tenants: Array<{ id: number; name: string }>
  templates: Array<{ id: string; skillName: string; description?: string; status?: string; createTime?: string }>
}>({ url: '/agent/binding-options', method: 'get' })

// 查询智能体列表
export const getAgentList = (data: any) => {
  return request({
    url: '/agent/querylist',
    method: 'post',
    data
  })
}

// 获取项目组与技能树
export const getSkillTree = () => {
  return request({
    url: '/agent/skill_tree',
    method: 'get'
  })
}

// 获取知识库列表
export const getTenantList = () => {
  return request({
    url: '/agent/tenant_list',
    method: 'get'
  })
}

// 新增智能体
export const insertAgent = (data: AgentCreate) => {
  return request({
    url: '/agent/insert',
    method: 'post',
    data
  })
}

// 更新智能体
export const updateAgent = (data: any) => {
  return request({
    url: '/agent/update',
    method: 'post',
    data
  })
}

// 逻辑删除智能体
export const deleteLjAgent = (data: { id: number }) => {
  return request({
    url: '/agent/deleteLj',
    method: 'post',
    data
  })
}
