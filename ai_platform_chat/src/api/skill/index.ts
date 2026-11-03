import request from '@/util/request'
import MarkdownIt from 'markdown-it'

export interface ManagedSkill {
  id:number; skillName:string; skillDescription:string; ruleContent:string; enabled:0|1
  skillLevelType:1|2; subSkillIds:number[]|string|null; tableIds:number[]|string|null; tenantIds:number[]|string|null
  intentLlmId:number|null; taskLlmId:number|null; executLlmId:number|null; summaryLlmId:number|null; temperature:number|null
}
export interface UsableSkillGroup { id:number; groupName:string; description:string }
export interface PersonalSkillForm {
  skillName:string; skillDescription:string; ruleContent:string; enabled:0|1; skillLevelType:1|2; subSkillIds:number[]
  intentLlmId:number|null; taskLlmId:number|null; executLlmId:number|null; summaryLlmId:number|null
  temperature:number|null; tableIds:number[]; tenantIds:number[]
}
export interface PersonalSkillResources {
  models:{id:number;model:string;type:number}[]
  tables:{id:number;tableName:string;tableCnName:string;projectGroupId:number;projectGroupName:string;columnsJson:string}[]
  tenants:{id:number;tenantName:string;scopeType:number}[]
  subSkills:{id:number;skillName:string}[]
}
export const getUsableSkillGroups=()=>request<{list:UsableSkillGroup[]}>({url:'/skill/groups/usable',method:'get'})
export const getUsableGroupSkills=(id:number,params:{keyword:string;pageNo:number;pageSize:number})=>request<{list:ManagedSkill[];total:number}>({url:`/skill/groups/usable/${id}/skills`,method:'get',params})
export const getMyManagedSkills=(params:{keyword:string;pageNo:number;pageSize:number})=>request<{list:ManagedSkill[];total:number}>({url:'/skill/personal/skills',method:'get',params})
export const getMyManagedSkill=(id:number)=>request<ManagedSkill>({url:`/skill/personal/skills/${id}`,method:'get'})
export const getPersonalSkillResources=()=>request<PersonalSkillResources>({url:'/skill/personal/resource-options',method:'get'})
export const saveMyManagedSkill=(data:PersonalSkillForm,id?:number)=>request<{id:number}>({url:`/skill/personal/skills${id?'/'+id:''}`,method:id?'put':'post',data})
export const deleteMyManagedSkill=(id:number)=>request({url:`/skill/personal/skills/${id}/delete`,method:'post',data:{confirm:true}})

export interface ImportedSkill {
  id: number; skillName: string; skillDescription: string; ruleContent: string; enabled: 0 | 1
}
export interface MarkdownSkillPreview {
  skillName: string; skillDescription: string; markdown: string; filename: string; ignoredFields: string[]
}
export const getImportedSkills = (params: { keyword?: string; enabled?: 0 | 1; pageNo: number; pageSize: number }) => request<{ list: ImportedSkill[]; total: number; pageNo: number; pageSize: number }>({ url: '/skill/imported/querylist', method: 'get', params })
export const getImportedSkillOptions = (pageNo: number) => request<{ list: Array<Pick<ImportedSkill, 'id' | 'skillName'>>; total: number }>({ url: '/skill/imported/options', method: 'get', params: { pageNo, pageSize: 100 } })
export const previewMarkdownSkill = (file: File) => {
  const data = new FormData(); data.append('file', file)
  return request<MarkdownSkillPreview>({ url: '/skill/imported/preview', method: 'post', data, headers: { 'Content-Type': 'multipart/form-data' } })
}
export const saveImportedSkill = (data: Omit<ImportedSkill, 'id'> & { id?: number }) => request<{ id: number }>({ url: '/skill/imported/save', method: 'post', data })
export const deleteImportedSkill = (id: number) => request({ url: '/skill/imported/delete', method: 'post', data: { id } })

export type SkillLevelType = 1 | 2

export interface PublicSkill {
  id: number
  skillName: string
  skillDescription: string | null
  skillLevelType: SkillLevelType
  subSkillIds: number[]
  ruleContent: string
  enabled: 0 | 1
}

export interface PublicSkillQuery {
  keyword?: string
  enabled?: 0 | 1
  skillLevelType?: SkillLevelType
  pageNo: number
  pageSize: number
}

export interface PublicSkillPage {
  list: PublicSkill[]
  total: number
  pageNo: number
  pageSize: number
}

export interface PublicSkillCreate {
  skillName: string
  skillDescription: string
  skillLevelType: SkillLevelType
  subSkillIds: number[]
  ruleContent: string
  enabled: 0 | 1
}

export interface PublicSkillUpdate extends PublicSkillCreate {
  id: number
}

export function getPublicSkillPage(data: PublicSkillQuery) {
  return request<PublicSkillPage>({
    url: '/skill/public/querylist',
    method: 'post',
    data
  })
}

export function createPublicSkill(data: PublicSkillCreate) {
  return request<{ id: number }>({
    url: '/skill/public/insert',
    method: 'post',
    data
  })
}

export function updatePublicSkill(data: PublicSkillUpdate) {
  return request<{ id: number }>({
    url: '/skill/public/update',
    method: 'post',
    data
  })
}

export function deletePublicSkill(data: { id: number }) {
  return request({
    url: '/skill/public/delete',
    method: 'post',
    data
  })
}

export function batchDeletePublicSkills(data: { ids: number[] }) {
  return request<{ deletedCount: number }>({
    url: '/skill/public/batch-delete',
    method: 'post',
    data
  })
}

export interface PrivateSkill {
  id: number
  skillName: string
  skillDescription: string | null
  skillLevelType: SkillLevelType
  subSkillIds: number[]
  ruleContent: string
  userId: number
  userName: string
  account: string
  groupId: number
  groupName: string
  enabled: 0 | 1
}

export interface SkillShare {
  id: number
  sourceSkillId: number
  sourceUserId: number
  sourceUserName: string
  targetUserId: number
  targetUserName: string
  skillName: string
  skillDescription: string | null
  skillLevelType: SkillLevelType
  ruleContent: string
  receiveStatus: 0 | 1 | 2 | 3
  acceptedSkillId: number | null
  createTime: string | null
  responseTime: string | null
}

export interface SkillLibraryItem {
  id: number
  sourceSkillId: number
  publisherUserId: number
  publisherUserName: string
  groupId: number
  groupName: string
  skillName: string
  skillDescription: string | null
  skillLevelType: SkillLevelType
  ruleContent: string
  enabled: 0 | 1
  createTime: string | null
}

export interface PrivateSkillPage<T> {
  list: T[]
  total: number
  pageNo: number
  pageSize: number
}

export interface PrivateSkillQuery {
  skillName?: string
  userName?: string
  groupId?: number
  account?: string
  enabled?: 0 | 1
  skillLevelType?: SkillLevelType
  pageNo: number
  pageSize: number
}

export interface PrivateSkillCreate {
  mcpBindings?: import('@/api/mcp').McpBinding[]
  userId?: number
  skillName: string
  skillDescription: string
  ruleContent: string
  skillLevelType: SkillLevelType
  subSkillIds: number[]
  enabled: 0 | 1
}

export interface PrivateSkillUpdate extends PrivateSkillCreate {
  id: number
}

export interface SubSkillOption {
  id: number
  skillName: string
  skillDescription: string | null
  enabled: 0 | 1
}

export function getPublicSubSkillOptions() {
  return request<{ list: SubSkillOption[]; total: number }>({
    url: '/skill/public/sub-skill-options',
    method: 'get'
  })
}

export function getPrivateSubSkillOptions(data: { userId?: number }) {
  return request<{ list: SubSkillOption[]; total: number }>({
    url: '/skill/private/sub-skill-options',
    method: 'post',
    data
  })
}

export function getPrivateSkillPage(data: PrivateSkillQuery) {
  return request<PrivateSkillPage<PrivateSkill>>({ url: '/skill/private/querylist', method: 'post', data })
}

export function createPrivateSkill(data: PrivateSkillCreate) {
  return request<{ id: number }>({ url: '/skill/private/insert', method: 'post', data })
}

export function updatePrivateSkill(data: PrivateSkillUpdate) {
  return request<{ id: number }>({ url: '/skill/private/update', method: 'post', data })
}

export function deletePrivateSkill(data: { id: number }) {
  return request({ url: '/skill/private/delete', method: 'post', data })
}

export function getPrivateSkillShareTargets(data: any) {
  return request<PrivateSkillPage<any>>({ url: '/skill/private/share/targets', method: 'post', data })
}

export function sharePrivateSkill(data: { skillId: number; targetUserIds: number[] }) {
  return request<{ sharedCount: number }>({ url: '/skill/private/share', method: 'post', data })
}

export function getPrivateSkillSharePage(data: any) {
  return request<PrivateSkillPage<SkillShare>>({ url: '/skill/private/share/querylist', method: 'post', data })
}

export function acceptPrivateSkillShare(data: { id: number }) {
  return request<{ shareId: number; skillId: number }>({ url: '/skill/private/share/accept', method: 'post', data })
}

export function rejectPrivateSkillShare(data: { id: number }) {
  return request({ url: '/skill/private/share/reject', method: 'post', data })
}

export function revokePrivateSkillShare(data: { id: number }) {
  return request({ url: '/skill/private/share/revoke', method: 'post', data })
}

export function publishPrivateSkill(data: { skillId: number }) {
  return request<{ id: number }>({ url: '/skill/private/library/publish', method: 'post', data })
}

export function getGroupSkillLibraryPage(data: any) {
  return request<PrivateSkillPage<SkillLibraryItem>>({ url: '/skill/private/library/querylist', method: 'post', data })
}

export function addGroupSkillToMine(data: { id: number }) {
  return request<{ skillId: number }>({ url: '/skill/private/library/add', method: 'post', data })
}

export function deleteGroupSkillLibraryItem(data: { id: number }) {
  return request({ url: '/skill/private/library/delete', method: 'post', data })
}

export interface TemplateSkill {
  ownerType?: 'company' | 'personal'
  id: string; skillName: string; description: string; version: number; createdAt: string; inputRequirements: string[]
  status?: 'ready' | 'deleting'
  projectGroups?: { id:number; groupName:string }[]
  warnings?: string[]
  mappedDataNeeds?: number
}
export const deleteTemplateSkill = (id: string) => request<{ id: string }>({ url: `/skill/templates/${encodeURIComponent(id)}/delete`, method: 'post', data: { confirmed: true }, timeout: 60000 })
export interface TemplateTask {
  taskId: string; type: string; status: 'queued' | 'running' | 'completed' | 'failed' | 'interrupted'
  stage: string; progress: string; attempt: number; skillId?: string; warnings?: string[]
  error?: { code: string; message: string }
}
export interface TemplateAnswerAssessment {
  suitable: boolean; reason: string; suggestedName: string; documentType: string
}
export interface TemplateGraphItem { id: string; label?: string; source?: string; target?: string; description?: string; evidenceIds: string[] }
export interface TemplateGraph {
  status: 'not_created' | 'queued' | 'running' | 'failed' | 'interrupted' | 'ready'; sourceRole: 'template'
  task?: TemplateTask; nodes: TemplateGraphItem[]; edges: TemplateGraphItem[]; nodeCount?: number; edgeCount?: number; isTruncated?: boolean
}
export const getTemplateGraph = (id: string) => request<TemplateGraph>({ url: `/skill/templates/${encodeURIComponent(id)}/graph`, method: 'get' })
export const buildTemplateGraph = (id: string) => request<TemplateGraph>({ url: `/skill/templates/${encodeURIComponent(id)}/graph`, method: 'post', timeout: 30000 })
export const getTemplateGraphEvidence = (taskId: string, id: string) => request<{ text: string; fileName: string }>({ url: `/skill/template-tasks/${encodeURIComponent(taskId)}/graph/evidence/${encodeURIComponent(id)}`, method: 'get' })
export const assessTemplateAnswer = (data: { answer: string; question: string }, signal?: AbortSignal) => request<TemplateAnswerAssessment>({ url: '/skill/templates/assess', method: 'post', data, timeout: 50000, signal })
export const createTemplateFromAnswer = (data: { answer: string; question: string; skillName: string }, requestKey: string) => request<TemplateTask>({ url: '/skill/templates/from-answer', method: 'post', data, timeout: 60000, headers: { 'Idempotency-Key': requestKey } })
export const getTemplateSkills = (params: { keyword?: string; pageNo: number; pageSize: number }) => request<{ list: TemplateSkill[]; total: number }>({ url: '/skill/templates', method: 'get', params })
export interface TemplateWritingSkill {
  title: string
  purpose?: string
  sections: Array<{
    id: string
    heading: string
    intent?: string
    instruction?: string
    format?: string
    formats?: string[]
    analysis?: string[]
    dataNeeds?: string[]
    requirements?: { instruction: string }[]
    dataSources?: Array<{ dataNeed?: string; kind?: string; derivation?: string; sources?: { tableName?: string; columnName?: string }[] }>
    dataInputs?: Array<{ dataNeed: string; kind: string; reason?: string }>
  }>
}
export const getTemplateSkill = (id: string) => request<{ meta: TemplateSkill; skill: TemplateWritingSkill; skillMarkdown: string }>({ url: `/skill/templates/${encodeURIComponent(id)}`, method: 'get' })
export const getTemplateCapabilities = () => request<{ templateFormats: string[]; officeAvailable: boolean }>({ url: '/skill/templates/capabilities', method: 'get', timeout: 30000 })
export const createTemplateSkill = (file: File, skillName: string, requestKey: string) => {
  const data = new FormData(); data.append('file', file); data.append('skillName', skillName)
  return request<TemplateTask>({ url: '/skill/templates', method: 'post', data, timeout: 60000, headers: { 'Content-Type': 'multipart/form-data', 'Idempotency-Key': requestKey } })
}
export const getTemplateTask = (id: string) => request<TemplateTask>({ url: `/skill/template-tasks/${encodeURIComponent(id)}`, method: 'get' })
export const retryTemplateTask = (id: string, expectedAttempt: number) => request<TemplateTask>({ url: `/skill/template-tasks/${encodeURIComponent(id)}/retry`, method: 'post', data: { expectedAttempt }, timeout: 30000 })

// 读取 Markdown 语法节点，保留代码、表格、链接和转义后的原文。
export function markdownSkillText(source: string): string {
  const parser = new MarkdownIt({ html: false, linkify: false })
  const inlineText = (tokens: ReturnType<typeof parser.parse>): string => {
    let value = ''
    const links: string[] = []
    for (const token of tokens) {
      if (token.type === 'text' || token.type === 'code_inline') value += token.content
      else if (token.type === 'softbreak' || token.type === 'hardbreak') value += '\n'
      else if (token.type === 'link_open') links.push(token.attrGet('href') || '')
      else if (token.type === 'link_close') { const url = links.pop(); if (url) value += ` (${url})` }
      else if (token.type === 'image') value += `${token.children ? inlineText(token.children) : token.content} (${token.attrGet('src') || ''})`
      else if (token.children) value += inlineText(token.children)
    }
    return value
  }
  let output = '', inTable = false
  const blocks: string[] = []
  const lists: Array<{ ordered: boolean; next: number }> = []
  for (const token of parser.parse(source, {})) {
    if (token.type === 'inline') output += inlineText(token.children || [])
    else if (token.type === 'fence' || token.type === 'code_block') {
      blocks.push(output.replace(/\n{3,}/g, '\n\n'), token.content, '\n\n')
      output = ''
    }
    else if (token.type === 'bullet_list_open' || token.type === 'ordered_list_open') lists.push({ ordered: token.type === 'ordered_list_open', next: Number(token.attrGet('start') || 1) })
    else if (token.type === 'bullet_list_close' || token.type === 'ordered_list_close') lists.pop()
    else if (token.type === 'list_item_open') { const list = lists.at(-1)!; output += `\n${'  '.repeat(lists.length - 1)}${list.ordered ? `${list.next++}.` : '-'} ` }
    else if (token.type === 'table_open') inTable = true
    else if (token.type === 'table_close') { inTable = false; output += '\n' }
    else if (token.type === 'th_close' || token.type === 'td_close') output += '\t'
    else if (token.type === 'tr_close') output = output.replace(/\t$/, '') + '\n'
    else if (token.type === 'heading_close' || (token.type === 'paragraph_close' && !inTable)) output += '\n\n'
  }
  const text = (blocks.join('') + output.replace(/\n{3,}/g, '\n\n')).trim()
  if (!text) throw new Error('Markdown 正文没有可转换的文本')
  if (new TextEncoder().encode(text).length > 60000) throw new Error('转换后的技能文本超过60000字节，请缩短内容')
  return text
}

