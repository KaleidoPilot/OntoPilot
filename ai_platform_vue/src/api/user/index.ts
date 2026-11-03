import request from '@/util/request';

const baseUrl = 'user';

// 用户登录
export function login(data: any) {
  return request<{ token: string; userInfo: PlatformUserInfo }>({
    url: `${baseUrl}/login`,
    method: 'POST',
    data
  })
}

// 物理删除用户
export function deleteUser(data: { id: number }) {
  return request({
    url: `${baseUrl}/delete`,
    method: 'POST',
    data
  })
}

// 逻辑删除用户
export function logicDeleteUser(data: { id: number }) {
  return request({
    url: `${baseUrl}/deleteLj`,
    method: 'POST',
    data
  })
}

export interface PlatformUserInfo {
  id: number
  realName: string
  account: string
  userType: 'internal' | 'external'
  groupId?: number
  groupName?: string
  agentId?: number
  agentKey?: string
  mcpToken?: string
  deptLevel?: 0 | 1
  orgId?: number | null
  orgCode?: string
  orgName?: string
}

export function getCurrentPlatformUser() {
  return request<PlatformUserInfo>({url:'/user/me',method:'GET'})
}

export function readStoredPlatformUser(): Partial<PlatformUserInfo> {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || '{}')
  } catch {
    return {}
  }
}

export function getHomeRoute(): string {
  const user = readStoredPlatformUser()
  if (user.userType === 'external') return '/login'
  return user.deptLevel === 1 ? '/user/enterprise' : '/organization'
}

export interface CompanyAdministrator {
  id: number
  orgId: number
  deptLevel: 1
  realName: string
  account: string
  phone: string | null
  deptName: string | null
  remarks: string | null
  enabled: 0 | 1
  createTime?: string | null
}

export interface CompanyAdministratorInput {
  orgId: number
  realName: string
  account: string
  phone: string
  deptName: string
  remarks: string
  enabled: 0 | 1
  password?: string
}

export function queryCompanyAdministrators(data: {orgId:number;keyword?:string;enabled?:0|1;pageNo:number;pageSize:number}) {
  return request<PageResult<CompanyAdministrator>>({ url: '/user/company-admin/querylist', method: 'POST', data })
}

export function createCompanyAdministrator(data: CompanyAdministratorInput & {password:string}) {
  return request<{id:number}>({ url: '/user/company-admin/insert', method: 'POST', data })
}

export function updateCompanyAdministrator(data: CompanyAdministratorInput & {id:number}) {
  return request<{id:number}>({ url: '/user/company-admin/update', method: 'POST', data })
}

export interface UserGroup {
  id: number
  groupName: string
  agentId: string | number
  agentName: string
  agentKey: string
  remarks: string | null
  enabled: 0 | 1
  userCount: number
}

interface UserGroupWriteFields {
  groupName: string
  agentId: string
  remarks: string
  enabled: 0 | 1
}

export interface UserGroupCreateInput extends UserGroupWriteFields {}

export interface UserGroupUpdateInput extends UserGroupWriteFields {
  id: number
}

export interface ExternalUser {
  id: number
  groupId: number
  groupName: string
  agentId: string | number
  agentName: string
  realName: string
  account: string
  phone: string | null
  remarks: string | null
  enabled: 0 | 1
}

interface ExternalUserWriteFields {
  groupId: number
  realName: string
  account: string
  phone: string
  remarks: string
  enabled: 0 | 1
}

export interface ExternalUserCreateInput extends ExternalUserWriteFields {
  password: string
}

export interface ExternalUserUpdateInput extends ExternalUserWriteFields {
  id: number
}

export interface PageResult<T> {
  list: T[]
  total: number
  pageNo: number
  pageSize: number
}

export function getUserGroupPage(data: any) {
  return request<PageResult<UserGroup>>({ url: `${baseUrl}/group/querylist`, method: 'POST', data })
}

export function getUserGroupOptions(includeDisabled = false) {
  return request<{ list: Array<{ id: number; groupName: string; agentId: string | number; enabled: 0 | 1 }> }>({
    url: `${baseUrl}/group/options`, method: 'GET', params: { includeDisabled }
  })
}

export function getAgentOptions() {
  return request<{ list: Array<{ id: number; agentName: string; agentKey: string }> }>({
    url: `${baseUrl}/group/agent-options`, method: 'GET'
  })
}

export function createUserGroup(data: UserGroupCreateInput) {
  return request<{ id: number }>({ url: `${baseUrl}/group/insert`, method: 'POST', data })
}

export function updateUserGroup(data: UserGroupUpdateInput) {
  return request<{ id: number }>({ url: `${baseUrl}/group/update`, method: 'POST', data })
}

export function deleteUserGroup(data: { id: number }) {
  return request({ url: `${baseUrl}/group/delete`, method: 'POST', data })
}

export function getExternalUserPage(data: any) {
  return request<PageResult<ExternalUser>>({ url: `${baseUrl}/external/querylist`, method: 'POST', data })
}

export function createExternalUser(data: ExternalUserCreateInput) {
  return request<{ id: number }>({ url: `${baseUrl}/external/insert`, method: 'POST', data })
}

export function updateExternalUser(data: ExternalUserUpdateInput) {
  return request<{ id: number }>({ url: `${baseUrl}/external/update`, method: 'POST', data })
}

export function resetExternalUserPassword(data: { id: number; newPassword: string }) {
  return request({ url: `${baseUrl}/external/reset-password`, method: 'POST', data })
}

export function changeExternalUserPassword(data: { oldPassword: string; newPassword: string }) {
  return request({ url: `${baseUrl}/external/change-password`, method: 'POST', data })
}

export function deleteExternalUser(data: { id: number }) {
  return request({ url: `${baseUrl}/external/delete`, method: 'POST', data })
}

export function batchDeleteExternalUsers(data: { ids: number[] }) {
  return request<{ deletedUsers: number; deletedSkills: number; deletedShares: number; deletedLibraries: number }>({
    url: `${baseUrl}/external/batch-delete`, method: 'POST', data
  })
}
