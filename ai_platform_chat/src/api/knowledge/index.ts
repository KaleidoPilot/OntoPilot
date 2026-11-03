import request, { isLoginExpired, leaveForLogin } from '@/util/request'

export interface UsableTenant {
  id: number
  tenantName: string
  remarks: string | null
  enabled: 0 | 1
  scopeType: 1 | 2 | 3
  knowledgeCount: number
}

export interface KnowledgeRecord {
  id: number
  title: string
  content?: string
  fileUrl: string
  fileId: string
  version: number
  tenantId: number
  enabled: 0 | 1
}

export function getUsableTenants(params: { keyword?: string; section?: 'company' | 'personal'; pageNo: number; pageSize: number }) {
  return request<{ company: UsableTenant[]; personal: UsableTenant[]; companyTotal: number; personalTotal: number; pageNo: number; pageSize: number }>({
    url: '/knowledge/tenant/usable',
    method: 'get',
    params
  })
}

export function getVisibleTenantPage(params: { keyword?: string; scopeType?: 1 | 2 | 3; pageNo: number; pageSize: number }) {
  return request<{ list: UsableTenant[]; total: number; pageNo: number; pageSize: number }>({
    url: '/knowledge/tenant/usable',
    method: 'get',
    params: { ...params, section: 'all' }
  })
}

export function createPersonalTenant(data: { tenantName: string; remarks: string }) {
  return request<{ id: number; scopeType: number }>({ url: '/knowledge/tenant/insert', method: 'post', data })
}

export function updatePersonalTenant(data: { id: number; tenantName: string; remarks: string; enabled: 0 | 1 }) {
  return request({ url: '/knowledge/tenant/update', method: 'post', data })
}

export function deletePersonalTenant(id: number) {
  return request({ url: '/knowledge/tenant/delete', method: 'post', data: { id } })
}

export function getTenantRecords(tenantId: number, params: { keyword?: string; pageNo: number; pageSize: number; folderId?:number }) {
  return request<{ tenant: UsableTenant; list: KnowledgeRecord[]; total: number }>({
    url: `/knowledge/tenant/${tenantId}/records`,
    method: 'get',
    params
  })
}

export function getKnowledgeRecord(recordId: number) {
  return request<KnowledgeRecord>({ url: `/knowledge/record/${recordId}`, method: 'get' })
}

export function createKnowledgeRecord(tenantId: number, data: { title: string; content: string; folderId?:number }) {
  return request({ url: `/knowledge/tenant/${tenantId}/records/insert`, method: 'post', data, timeout: 180000 })
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
    timeout: 180000
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
    timeout: 180000
  })
}

export function uploadKnowledgeFiles(tenantId: number, files: File[], folderId = 0) {
  const formData = new FormData()
  files.forEach(file => formData.append('files', file))
  return request<{ inserted: number; files?: number; warnings?: string[] }>({
    url: `/knowledge/tenant/${tenantId}/upload`,
    method: 'post',
    params: { folderId },
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000
  })
}

export function updateKnowledgeRecord(data: { id: number; expectedVersion: number; title: string; content: string; fileUrl: string; tenantId: number; enabled: 0 | 1 }) {
  return request({ url: '/knowledge/record/update', method: 'post', data, timeout: 180000 })
}

export function deleteKnowledgeRecord(id: number, tenantId: number) {
  return request({ url: '/knowledge/record/delete', method: 'post', data: { id, tenantId } })
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

export function syncTenantRecords(tenantId: number) {
  return request({ url: `/knowledge/tenant/${tenantId}/sync`, method: 'post', timeout: 180000 })
}

function downloadFileName(header: string | null, suggested?: string) {
  const matched = /filename\*=UTF-8''([^;]+)/i.exec(header || '')
  if (matched) return decodeURIComponent(matched[1])
  const name = (suggested || '').replace(/[\\/:*?"<>|\r\n]/g, ' ').trim()
  if (!name) return '知识资料.txt'
  return /\.[A-Za-z0-9]{1,8}$/.test(name) ? name : `${name}.txt`
}

export async function downloadKnowledgeRecord(recordId: number, suggestedName?: string) {
  const headers = new Headers()
  const token = localStorage.getItem('fijo-chat-token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const user = JSON.parse(localStorage.getItem('fijo-chat-userInfo') || '{}')
  if (user.id) headers.set('x-user-id', String(user.id))
  if (user.account) headers.set('x-user-name', user.account)
  if (user.userType) headers.set('x-user-type', user.userType)
  if (user.mcpToken) headers.set('x-mcp-token', user.mcpToken)
  if (user.groupId) headers.set('x-group-id', String(user.groupId))
  if (user.orgId) headers.set('x-org-id', String(user.orgId))
  const response = await fetch(`${(import.meta.env.VITE_APP_BASE_URL || '').replace(/\/$/, '')}/knowledge/record/${recordId}/download`, { headers })
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
