import request from '@/util/request'
import type { McpBinding } from '@/api/mcp'

export type SkillLevelType = 1 | 2

export interface ManagedSkillGroup {
  id: number
  groupName: string
  description: string
  sortOrder: number
  enabled: 0 | 1
  skillCount: number
  userGroupIds: number[]
  userGroups: Array<{ id: number; groupName: string; enabled: 0 | 1 }>
}

export interface SkillGroupWrite {
  groupName: string
  description: string
  sortOrder: number
  enabled: 0 | 1
  userGroupIds: number[]
}

export interface ManagedGroupSkill {
  id: number
  skillName: string
  skillDescription: string | null
  skillType: 1 | 2
  projectGroupId?: number | null
  skillLevelType: SkillLevelType
  subSkillIds?: string | null
  ruleContent?: string
  enabled: 0 | 1
  projectSkillGroupName?: string | null
}

export interface SkillGroupPage<T> { list: T[]; total: number; pageNo: number; pageSize: number }
export interface SkillGroupPageQuery { keyword?: string; pageNo: number; pageSize: number }

export function getSkillGroups(params: SkillGroupPageQuery) {
  return request<SkillGroupPage<ManagedSkillGroup>>({ url: '/skill/groups', method: 'GET', params })
}
export function saveSkillGroup(data: SkillGroupWrite, id?: number) {
  return request<{ id: number }>({ url: id ? `/skill/groups/${id}` : '/skill/groups', method: id ? 'PUT' : 'POST', data })
}
export function deleteSkillGroup(id: number) {
  return request({ url: `/skill/groups/${id}/delete`, method: 'POST', data: { confirm: true } })
}
export function getManagedGroupSkills(id: number, params: SkillGroupPageQuery) {
  return request<SkillGroupPage<ManagedGroupSkill>>({ url: `/skill/groups/${id}/skills`, method: 'GET', params })
}
export function getUngroupedSkillOptions(params: SkillGroupPageQuery) {
  return request<SkillGroupPage<ManagedGroupSkill>>({ url: '/skill/groups/skill-options', method: 'GET', params })
}
export function attachManagedGroupSkills(id: number, skillIds: number[]) {
  return request({ url: `/skill/groups/${id}/skills`, method: 'POST', data: { skillIds } })
}
export function removeManagedGroupSkills(id: number, skillIds: number[]) {
  return request({ url: `/skill/groups/${id}/skills/remove`, method: 'POST', data: { skillIds, confirm: true } })
}
export function createManagedGroupSkill(id: number, data: PublicSkillCreate) {
  return request<{ id: number }>({ url: `/skill/groups/${id}/skills/create`, method: 'POST', data })
}

export interface SkillTableOption {
  id: number; tableName: string; tableCnName: string | null; columnsJson: string | Record<string, any>
  projectGroupId: number; projectGroupName: string; sandboxConfigId: number | null
}
export interface SkillExecutionWrite extends PublicSkillCreate {
  updateHierarchy?: boolean
  /** 四类模型与废弃的智能体保持一致：意图 / 任务分解 / 执行 / 总结 */
  intentLlmId: number | null
  taskLlmId: number | null
  executLlmId: number | null
  summaryLlmId: number | null
  temperature: number | null
  tableIds: number[]
  tenantIds: number[]
}
export interface SkillExecutionDetail extends ManagedGroupSkill {
  projectGroupId: number | null
  intentLlmId: number | null; taskLlmId: number | null; executLlmId: number | null; summaryLlmId: number | null
  temperature: number | null; tableIds: number[]; tenantIds: number[]
  resourceConfigured: 0 | 1; tables: SkillTableOption[]
}
export interface SkillResourceOptions {
  models: Array<{ id: number; model: string; type: number }>
  tenants: Array<{ id: number; tenantName: string; scopeType: 1 | 2 }>
  projectGroups: Array<{ id: number; groupName: string; libraryName: string | null }>
}
export function getSkillResourceOptions() {
  return request<SkillResourceOptions>({ url: '/skill/groups/resource-options', method: 'GET' })
}
export function getSkillTableOptions(params: SkillGroupPageQuery & { projectGroupId: number }) {
  return request<SkillGroupPage<SkillTableOption>>({ url: '/skill/groups/table-options', method: 'GET', params })
}
export function getSkillExecutionDetail(groupId: number, skillId: number) {
  return request<SkillExecutionDetail>({ url: `/skill/groups/${groupId}/skills/${skillId}`, method: 'GET' })
}
export function saveSkillExecution(groupId: number, skillId: number | undefined, data: SkillExecutionWrite) {
  return request<{ id: number }>({ url: skillId ? `/skill/groups/${groupId}/skills/${skillId}` : `/skill/groups/${groupId}/skills/create`, method: skillId ? 'PUT' : 'POST', data })
}

export interface PublicSkill {
  templateId?: string | null
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
  templateId?: string | null
  mcpBindings?: McpBinding[]
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

export interface CompanyTemplate { id:string; skillName:string; description:string; version:number; createdAt:string; inputRequirements:string[]; status?:'ready'|'deleting'; projectGroups?:{id:number;groupName:string}[]; warnings?:string[]; mappedDataNeeds?:number; accessUserGroupIds?:number[]|null }
export const updateCompanyTemplateAccess=(templateIds:string[],userGroupIds:number[]|null)=>request<{updatedCount:number}>({url:'/skill/company/templates/access',method:'post',data:{templateIds,userGroupIds}})
export interface TemplateProjectGroupOption { id:number; groupName:string }
export const getCompanyTemplateProjectGroups=()=>request<{list:TemplateProjectGroupOption[]}>({url:'/skill/company/templates/project-groups',method:'get'})
export const deleteCompanyTemplate=(id:string)=>request<{id:string}>({url:`/skill/company/templates/${encodeURIComponent(id)}/delete`,method:'post',data:{confirmed:true},timeout:60000})
export interface CompanyTemplateTask { taskId:string; status:'queued'|'running'|'completed'|'failed'|'interrupted'; progress:string; attempt:number; skillId?:string; error?:{message:string}; warnings?:string[] }
export interface CompanyTemplateGraphItem { id:string; label?:string; source?:string; target?:string; description?:string; evidenceIds:string[] }
export interface CompanyTemplateGraph {
  status:'not_created'|'queued'|'running'|'failed'|'interrupted'|'ready'; sourceRole:'template'
  task?:CompanyTemplateTask; nodes:CompanyTemplateGraphItem[]; edges:CompanyTemplateGraphItem[]
  nodeCount?:number; edgeCount?:number; isTruncated?:boolean
}
export interface TemplateBinding { id:number; skillName:string; skillType:1|2; skillGroupName?:string; enabled:0|1 }
export const getCompanyTemplateGraph=(id:string)=>request<CompanyTemplateGraph>({url:`/skill/company/templates/${encodeURIComponent(id)}/graph`,method:'get'})
export const buildCompanyTemplateGraph=(id:string)=>request<CompanyTemplateGraph>({url:`/skill/company/templates/${encodeURIComponent(id)}/graph`,method:'post',timeout:30000})
export const getCompanyTemplateGraphEvidence=(taskId:string,id:string)=>request<{text:string;fileName:string}>({url:`/skill/company/template-tasks/${encodeURIComponent(taskId)}/graph/evidence/${encodeURIComponent(id)}`,method:'get'})
export const getCompanyTemplates=(params:{keyword?:string;pageNo:number;pageSize:number})=>request<{list:CompanyTemplate[];total:number}>({url:'/skill/company/templates',method:'get',params})
export interface CompanyWritingSkill {
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
export const getCompanyTemplate=(id:string)=>request<{meta:CompanyTemplate;skill:CompanyWritingSkill;skillMarkdown:string}>({url:`/skill/company/templates/${encodeURIComponent(id)}`,method:'get'})
export const getCompanyTemplateBindings=(id:string,pageNo=1)=>request<{list:TemplateBinding[];total:number}>({url:`/skill/company/templates/${encodeURIComponent(id)}/bindings`,method:'get',params:{pageNo,pageSize:20}})
export const getCompanyTemplateTask=(id:string)=>request<CompanyTemplateTask>({url:`/skill/company/template-tasks/${encodeURIComponent(id)}`,method:'get'})
export const retryCompanyTemplateTask=(id:string,expectedAttempt:number)=>request<CompanyTemplateTask>({url:`/skill/company/template-tasks/${encodeURIComponent(id)}/retry`,method:'post',data:{expectedAttempt},timeout:30000})
export const getCompanyTemplateCapabilities=()=>request<{templateFormats:string[]}>({url:'/skill/company/templates/capabilities',method:'get',timeout:30000})
export const uploadCompanyTemplate=(file:File,skillName:string,key:string,projectGroupIds:number[]=[],accessUserGroupIds:number[]|null=null)=>{const data=new FormData();data.append('file',file);data.append('skillName',skillName);projectGroupIds.forEach(id=>data.append('projectGroupIds',String(id)));data.append('accessUserGroupIds',JSON.stringify(accessUserGroupIds));return request<CompanyTemplateTask>({url:'/skill/company/templates',method:'post',data,timeout:60000,headers:{'Content-Type':'multipart/form-data','Idempotency-Key':key}})}
