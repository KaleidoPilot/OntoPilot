import request from '@/util/request'

export interface McpTool { name: string; description: string; inputSchema: Record<string, unknown>; readOnly: boolean }
export interface HttpRequestConfig {
  method: 'GET' | 'POST'; params: { key: string; value: string; enabled: boolean; description?: string; type?: 'string' | 'integer' | 'number' | 'boolean' | 'array' | 'object' | 'null'; required?: boolean }[]
  body: Record<string, unknown> | unknown[] | null; description: string
  bodyNotes?: Record<string, string>
  bodyFields?: HttpRequestConfig['params']
  testValues?: Record<string, unknown>
  variables: { name: string; type: 'string' | 'integer' | 'number' | 'boolean' | 'array' | 'object' | 'null'; description: string; example?: unknown; required?: boolean }[]
  inactiveVariables?: HttpRequestConfig['variables']
}
export interface HttpTestResult { statusCode: number; durationMs: number; isError: boolean; data: unknown }
export interface McpTestResponse { success: boolean; message?: string; data: { tools: McpTool[]; result?: HttpTestResult } }
export interface McpBinding { configId: number; toolNames: string[] }
export interface SkillMcpOption { id: number; categoryId?: number | null; name: string; enabled: 0 | 1; tools: McpTool[]; selectedTools: string[] }
export const loadSkillMcpOptions = (skillType: 1 | 2 | 3, userId?: number, personal = false) => request<SkillMcpOption[]>({ url: personal ? '/mcp/available' : '/mcp/company/skills/options', method: personal ? 'get' : 'post', ...(personal ? {} : { data: { skillType, userId } }) })
export const loadSavedSkillMcp = (id: number, personal = false) => request<McpBinding[]>({ url: personal ? `/mcp/personal/skills/${id}` : `/mcp/company/skills/${id}`, method: 'get' })
export interface CompanyMcp {
  categoryId: number | null
  id: number; name: string; url: string; authType: 'none' | 'bearer'; enabled: 0 | 1
  visibility: 'public' | 'private'; accessUserIds: number[]; hasCredential: boolean
  tools: McpTool[]; selectedTools: string[]
  httpRequest?: HttpRequestConfig | null
}
export interface CompanyMcpSave {
  categoryId?: number | null
  id?: number; name: string; url: string; authType: 'none' | 'bearer'; token?: string; enabled: 0 | 1
  visibility: 'public' | 'private'; accessUserIds: number[]; confirmVisibilityChange?: boolean
  httpRequest?: HttpRequestConfig
}
export interface McpUser { id: number; realName: string; account: string; groupName: string }
export interface CompanyMcpQuery { pageNo: number; pageSize: number; keyword?: string; visibility?: 'public' | 'private'; enabled?: 0 | 1; categoryId?: number }
export interface McpCategory { id: number; name: string; total?: number }
export const loadSkillMcpCategories = (personal = false) => request<McpCategory[]>({ url: personal ? '/mcp/categories' : '/mcp/company/categories', method: 'get' })
export const getMcpCategories = () => request<McpCategory[]>({ url: '/mcp/company/categories', method: 'get' })
export const saveMcpCategory = (data: {id?: number; name: string}) => request<{id: number}>({ url: '/mcp/company/categories/save', method: 'post', data })
export const deleteMcpCategory = (id: number) => request({ url: '/mcp/company/categories/delete', method: 'post', data: {id} })

export const getCompanyMcpPage = (data: CompanyMcpQuery) => request<{ list: CompanyMcp[]; total: number }>({ url: '/mcp/company/querylist', method: 'post', data })
export const getCompanyMcpUsers = (keyword?: string, ids: number[] = []) => request<{ list: McpUser[] }>({ url: '/mcp/company/users', method: 'post', data: { keyword: keyword || undefined, ids } })
export const saveCompanyMcp = (data: CompanyMcpSave) => request<{ id: number }>({ url: '/mcp/company/save', method: 'post', data })
export const testCompanyMcp = (id: number, args: Record<string, unknown> = {}) => request<{ tools: McpTool[]; result?: HttpTestResult }>({ url: '/mcp/company/test', method: 'post', data: { id, arguments: args }, timeout: 65000 })
export const saveCompanyMcpTools = (id: number, toolNames: string[]) => request({ url: '/mcp/company/tools', method: 'post', data: { id, toolNames } })
export const deleteCompanyMcp = (id: number) => request({ url: '/mcp/company/delete', method: 'post', data: { id } })
