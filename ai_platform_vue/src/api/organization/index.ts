import request from '@/util/request'


export interface Organization {
  id: number
  orgCode: string
  name: string
  remarks?: string | null
  enabled: 0 | 1
  createUserName?: string | null
  createTime?: string | null
  updateUserName?: string | null
  updateTime?: string | null
}

export interface OrganizationQuery {
  keyword?: string
  enabled?: 0 | 1
  pageNo: number
  pageSize: number
}

export interface OrganizationSaveParams {
  id?: number
  orgCode: string
  name: string
  remarks?: string
  enabled: 0 | 1
}

export function queryOrganizations(data: OrganizationQuery) {
  return request<{ list: Organization[]; total: number; pageNo: number; pageSize: number }>({
    url: '/organization/querylist',
    method: 'post',
    data
  })
}

export function getOrganizationOptions() {
  return request<{ list: Organization[] }>({
    url: '/organization/options',
    method: 'get'
  })
}

export function createOrganization(data: OrganizationSaveParams) {
  return request<Organization>({
    url: '/organization/insert',
    method: 'post',
    data
  })
}

export function updateOrganization(data: OrganizationSaveParams & { id: number }) {
  return request<Organization>({
    url: '/organization/update',
    method: 'post',
    data
  })
}

export function deleteOrganization(id: number) {
  return request({
    url: '/organization/delete',
    method: 'post',
    data: { id }
  })
}
