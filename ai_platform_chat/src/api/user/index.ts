import request from '@/util/request';

const baseUrl = 'user';

// 用户登录
export function login(data: any) {
  return request({
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
  orgId?: number
  groupId?: number
  groupName?: string
  agentId?: number
  agentKey?: string
  mcpToken?: string
}

export interface UserGroup {
  id: number
  groupName: string
  agentId: number
  agentName: string
  agentKey: string
  remarks: string | null
  enabled: 0 | 1
  userCount: number
}

interface UserGroupWriteFields {
  groupName: string
  agentId: number
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
  agentId: number
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

export function getUserGroupOptions() {
  return request<{ list: Array<{ id: number; groupName: string; agentId: number }> }>({
    url: `${baseUrl}/group/options`, method: 'GET'
  })
}

export function getAgentOptions() {
  return request<{ list: Array<{ id: number; agentName: string; agentKey: string }> }>({
    url: `${baseUrl}/group/agent-options`, method: 'GET'
  })
}

export function getMyAgents() {
  return request<{ list: Array<{ id: number; agentName: string; agentKey: string }> }>({
    url: `${baseUrl}/external/agents`, method: 'GET'
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

