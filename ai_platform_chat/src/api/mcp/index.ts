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
export interface PersonalMcp { id: number; categoryId?: number | null; name: string; url: string; authType: 'none' | 'bearer'; enabled: 0 | 1; hasCredential: boolean; tools: McpTool[]; selectedTools: string[]; configScope?: 'personal' | 'company'; visibility?: 'public' | 'private'; canManage?: boolean; httpRequest?: HttpRequestConfig | null }
export interface McpSave { id?: number; categoryId?: number | null; name: string; url: string; authType: 'none' | 'bearer'; token?: string; enabled: 0 | 1; httpRequest?: HttpRequestConfig }
export interface McpCategory { id: number; name: string }
export const getMcpCategories = () => request<McpCategory[]>({ url: '/mcp/categories', method: 'get' })
export const loadSkillMcpCategories = (_personal = true) => getMcpCategories()
export interface McpBinding { configId: number; toolNames: string[]; available?: boolean }
export type SkillMcpOption = PersonalMcp
export const loadSkillMcpOptions = (_skillType: 1 | 2 | 3, _userId?: number, _personal = true) => getAvailableMcp()
export const loadSavedSkillMcp = (id: number, _personal = true) => getSkillMcpBindings(id)
export interface McpApproval { configId: number; id: string; toolName: string; serverName?: string; arguments: Record<string, unknown>; skillId?: number; privateSkillId?: number }

export const getMyMcp = () => request<PersonalMcp[]>({ url: '/mcp/personal', method: 'get' })
export const getAvailableMcp = () => request<PersonalMcp[]>({ url: '/mcp/available', method: 'get' })
export const saveMyMcp = (data: McpSave) => request<{ id: number }>({ url: '/mcp/personal/save', method: 'post', data })
export const testMyMcp = (id: number, args: Record<string, unknown> = {}) => request<{ tools: McpTool[]; result?: HttpTestResult }>({ url: '/mcp/personal/test', method: 'post', data: { id, arguments: args }, timeout: 65000 })
export const saveMyMcpTools = (id: number, toolNames: string[]) => request({ url: '/mcp/personal/tools', method: 'post', data: { id, toolNames } })
export const deleteMyMcp = (id: number) => request({ url: '/mcp/personal/delete', method: 'post', data: { id } })
export const getSkillMcpBindings = (skillId: number) => request<McpBinding[]>({ url: `/mcp/personal/skills/${skillId}`, method: 'get' })
export const saveSkillMcpBindings = (skillId: number, bindings: McpBinding[]) => request({ url: '/mcp/personal/skills/save', method: 'post', data: { skillId, bindings } })
export const rejectMcpApproval = (approval: McpApproval) => request({ url: '/mcp/personal/approvals/reject', method: 'post', data: { id: approval.id, configId: approval.configId } })
