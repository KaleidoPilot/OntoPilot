import request, { isLoginExpired, leaveForLogin } from '@/util/request'


export interface KnowledgeTenant {
  id: number
  tenantName: string
  remarks: string | null
  enabled: 0 | 1
  scopeType: 1 | 2 | 3
  accessUserIds?: number[]
  accessGroupIds?: number[]
  knowledgeCount: number
  createTime: string | null
  updateTime: string | null
}

export interface KnowledgeGrantOptions {
  users: Array<{ id: number; realName: string; account: string; groupName: string }>
  groups: Array<{ id: number; groupName: string }>
}

export interface KnowledgeRecord {
  id: number
  title: string
  content?: string
  fileUrl: string
  fileId: string
  version: number
  milvusVersion: number | null
  syncStatus: 'synced' | 'missing' | 'outdated' | 'orphaned'
  tenantId: number
  enabled: 0 | 1
  createTime: string | null
  updateTime: string | null
}

export interface PageResult<T> {
  list: T[]
  total: number
  pageNo: number
  pageSize: number
}

export interface TenantPageQuery {
  keyword?: string
  enabled?: 0 | 1
  pageNo: number
  pageSize: number
}

export interface TenantRecordPageQuery {
  folderId?: number
  keyword?: string
  syncStatus?: 'synced' | 'pending'
  pageNo: number
  pageSize: number
}

export interface TenantCreateParams {
  tenantName: string
  remarks: string
  scopeType: 1 | 2
  accessUserIds: number[]
  accessGroupIds: number[]
}

export interface TenantUpdateParams extends TenantCreateParams {
  id: number
  enabled: 0 | 1
}

export interface KnowledgeRecordUpdateParams {
  id: number
  expectedVersion: number
  title: string
  content: string
  fileUrl: string
  tenantId: number
  enabled: 0 | 1
}

export interface KnowledgeRecordCreateParams {
  folderId?: number
  title: string
  content: string
}

export interface SyncResult {
  total: number
  synced: number
  skipped: number
  deletedOrphans: number
  tenantId: number
}

export function getKnowledgeGrantOptions() {
  return request<KnowledgeGrantOptions>({
    url: '/knowledge/tenant/grant-options',
    method: 'get'
  })
}

function knowledgeAuthHeaders() {
  const headers = new Headers()
  const token = localStorage.getItem('token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')
    if (userInfo.id) headers.set('x-user-id', String(userInfo.id))
    if (userInfo.account) headers.set('x-user-name', userInfo.account)
    if (userInfo.userType) headers.set('x-user-type', userInfo.userType)
    if (userInfo.groupId) headers.set('x-group-id', String(userInfo.groupId))
    if (userInfo.mcpToken) headers.set('x-mcp-token', userInfo.mcpToken)
    const fixedOrganization = userInfo.userType === 'external' || userInfo.deptLevel === 1
    if (fixedOrganization && userInfo.orgId) headers.set('x-org-id', String(userInfo.orgId))
    if (!fixedOrganization) {
      const organization = JSON.parse(localStorage.getItem('currentOrganization') || '{}')
      if (organization.id) headers.set('x-org-id', String(organization.id))
    }
  } catch { /* 登录信息损坏时由后端拒绝下载 */ }
  return headers
}

export interface KnowledgeGraphNode {
  id: string
  label?: string
  type?: string
  description?: string
  evidenceIds?: string[]
  source?: string
  target?: string
}
export interface KnowledgeGraphView {
  status: 'empty' | 'not_created' | 'building' | 'ready' | 'failed'
  documents: Array<{ docId: string; name: string; recordId?:number }>
  nodes: KnowledgeGraphNode[]
  edges: KnowledgeGraphNode[]
  nodeCount: number
  edgeCount: number
  isTruncated?: boolean
  error?: { message: string }
}
export const getKnowledgeGraph = (tenantId: number, folderId = 0) => request<KnowledgeGraphView>({ url: `/knowledge/tenant/${tenantId}/graph`, method: 'get', params: { folderId } })
export const buildKnowledgeGraph = (tenantId: number, folderId = 0) => request<KnowledgeGraphView>({ url: `/knowledge/tenant/${tenantId}/graph`, method: 'post', params: { folderId }, timeout: 30000 })
export interface KnowledgeGraphAnswer {
  question: string
  answer: string
  sourceIds: string[]
  context: {
    entities: Array<KnowledgeGraphNode & { sourceIds: string[] }>
    relationships: Array<KnowledgeGraphNode & { refId: string; sourceIds: string[] }>
    sources: Array<{ id: string; evidenceId: string; fileName: string; text: string; isExcerpt: boolean }>
    isTruncated: boolean
  }
}
export const askKnowledgeGraph = (tenantId: number, question: string, folderId = 0) => request<KnowledgeGraphAnswer>({
  url: `/knowledge/tenant/${tenantId}/graph/query`, method: 'post', params: { folderId }, data: { question }, timeout: 100000
})
export const getKnowledgeGraphEvidence = (tenantId: number, id: string, folderId = 0) => request<{ text: string; fileName: string }>({ url: `/knowledge/tenant/${tenantId}/graph/evidence/${encodeURIComponent(id)}`, method: 'get', params: { folderId } })

export interface KnowledgeFolder { id:number; parentId:number; folderName:string; documentKey?:string|null }
export interface KnowledgeFolderScope { folderId:number; children:KnowledgeFolder[]; breadcrumbs:KnowledgeFolder[]; allFolders:KnowledgeFolder[] }
export const getKnowledgeFolders=(tenantId:number,folderId=0)=>request<KnowledgeFolderScope>({url:`/knowledge/tenant/${tenantId}/folders`,method:'get',params:{folderId}})
export const openKnowledgeDocument=(tenantId:number,recordId:number)=>request<{id:number;recordId:number}>({url:`/knowledge/tenant/${tenantId}/records/${recordId}/open`,method:'post'})
export const saveKnowledgeFolder=(tenantId:number,data:{folderName:string;parentId:number},id?:number)=>request<{id:number}>({url:`/knowledge/tenant/${tenantId}/folders${id ? '/'+id : ''}`,method:id?'put':'post',data})
export const deleteKnowledgeFolder=(tenantId:number,id:number)=>request({url:`/knowledge/tenant/${tenantId}/folders/${id}/delete`,method:'post',data:{confirmed:true}})
export const moveKnowledgeDocuments=(tenantId:number,recordIds:number[],folderId:number)=>request({url:`/knowledge/tenant/${tenantId}/records/move`,method:'post',data:{recordIds,folderId}})

function downloadFileName(header: string | null, suggested?: string) {
  const matched = /filename\*=UTF-8''([^;]+)/i.exec(header || '')
  if (matched) return decodeURIComponent(matched[1])
  const name = (suggested || '').replace(/[\\/:*?"<>|\r\n]/g, ' ').trim()
  if (!name) return '知识资料.txt'
  return /\.[A-Za-z0-9]{1,8}$/.test(name) ? name : `${name}.txt`
}

export async function downloadKnowledgeRecord(recordId: number, suggestedName?: string) {
  const response = await fetch(`${import.meta.env.VITE_APP_BASE_URL || ''}/knowledge/record/${recordId}/download`, {
    headers: knowledgeAuthHeaders()
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    if (isLoginExpired(response.status, body)) {
      leaveForLogin()
      return new Promise(() => undefined)
    }
    throw new Error(body?.message || body?.detail || '下载失败')
  }
  const blob = await response.blob()
  const filename = downloadFileName(response.headers.get('content-disposition'), suggestedName)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export function getTenantPage(params: TenantPageQuery) {
  return request<PageResult<KnowledgeTenant>>({
    url: '/knowledge/tenant/querylist',
    method: 'get',
    params
  })
}

export function getTenantDetail(tenantId: number) {
  return request<KnowledgeTenant>({
    url: `/knowledge/tenant/${tenantId}`,
    method: 'get'
  })
}

export function getTenantRecordPage(tenantId: number, params: TenantRecordPageQuery) {
  return request<PageResult<KnowledgeRecord> & { tenant: KnowledgeTenant }>({
    url: `/knowledge/tenant/${tenantId}/records`,
    method: 'get',
    params
  })
}

export function getKnowledgeRecord(recordId: number) {
  return request<KnowledgeRecord>({
    url: `/knowledge/record/${recordId}`,
    method: 'get'
  })
}

export function createTenant(data: TenantCreateParams) {
  return request<{ id: number }>({
    url: '/knowledge/tenant/insert',
    method: 'post',
    data
  })
}

export function updateTenant(data: TenantUpdateParams) {
  return request<{ id: number; affectedRecords: number }>({
    url: '/knowledge/tenant/update',
    method: 'post',
    data
  })
}

export function deleteTenant(id: number) {
  return request<{ id: number }>({
    url: '/knowledge/tenant/delete',
    method: 'post',
    data: { id }
  })
}

export function getKnowledgeDocument(tenantId: number, recordId: number) {
  return request<{ id: number; title: string; fileUrl: string; content: string }>({
    url: `/knowledge/tenant/${tenantId}/records/${recordId}/content`,
    method: 'get'
  })
}

export function saveKnowledgeDocument(tenantId: number, recordId: number, content: string) {
  return request<{ id: number }>({
    url: `/knowledge/tenant/${tenantId}/records/${recordId}/content`,
    method: 'post',
    data: { content },
    timeout: 180_000
  })
}

export function replaceKnowledgeRecord(tenantId: number, recordId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request<{ fileName: string; warnings?: string[] }>({
    url: `/knowledge/tenant/${tenantId}/records/${recordId}/replace`,
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180_000
  })
}

export function uploadTenantRecords(tenantId: number, files: File[], folderId = 0) {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  return request<{ inserted: number; files?: number; warnings?: string[] }>({
    url: `/knowledge/tenant/${tenantId}/upload`,
    method: 'post',
    params: { folderId },
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180_000
  })
}

export function createKnowledgeRecord(tenantId: number, data: KnowledgeRecordCreateParams) {
  return request<{ record: KnowledgeRecord }>({
    url: `/knowledge/tenant/${tenantId}/records/insert`,
    method: 'post',
    data,
    timeout: 180_000
  })
}

export function updateKnowledgeRecord(data: KnowledgeRecordUpdateParams) {
  return request<{ record: KnowledgeRecord }>({
    url: '/knowledge/record/update',
    method: 'post',
    data,
    timeout: 180_000
  })
}

export function deleteKnowledgeRecord(id: number, tenantId: number) {
  return request({
    url: '/knowledge/record/delete',
    method: 'post',
    data: { id, tenantId }
  })
}

export function syncTenantRecords(tenantId: number) {
  return request<SyncResult>({
    url: `/knowledge/tenant/${tenantId}/sync`,
    method: 'post',
    timeout: 180_000
  })
}
