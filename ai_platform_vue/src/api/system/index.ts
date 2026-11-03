import request from '@/util/request'

export type SystemConfigType = 1 | 2 | 3 | 4

export interface SandboxOption { id: number; url: string; name?: string }

export function getSandboxOptions() {
  return request<{ list: SandboxOption[] }>({ url: '/system/configuration/sandbox-options', method: 'get' })
}

export interface SystemConfig {
  id: number
  orgId: number
  configType: SystemConfigType
  configName: string
  configJson: Record<string, unknown>
  enabled: 0 | 1
  createUserName?: string | null
  createTime?: string | null
  updateUserName?: string | null
  updateTime?: string | null
}

export interface SystemConfigQuery {
  configName?: string
  configType?: SystemConfigType
  enabled?: 0 | 1
  pageNo: number
  pageSize: number
}

export interface SystemConfigSaveParams {
  id?: number
  configType: SystemConfigType
  configName: string
  configJson: Record<string, unknown>
  enabled: 0 | 1
}

export function querySystemConfigs(data: SystemConfigQuery) {
  return request<{ list: SystemConfig[]; total: number; pageNo: number; pageSize: number }>({
    url: '/system/configuration/querylist',
    method: 'post',
    data
  })
}

export function createSystemConfig(data: SystemConfigSaveParams) {
  return request({
    url: '/system/configuration/insert',
    method: 'post',
    data
  })
}

export function updateSystemConfig(data: Partial<SystemConfigSaveParams> & { id: number }) {
  return request({
    url: '/system/configuration/update',
    method: 'post',
    data
  })
}

export type SystemConfigSecretPath = 'mysql.password' | 'llm.api_key' | 'embedding.api_key' | 'rerank.api_key' | 'api_key'

export function revealSystemConfig(id: number, secretPath: SystemConfigSecretPath) {
  return request<{ value: string }>({
    url: '/system/configuration/secret/reveal',
    method: 'post',
    data: { id, secretPath }
  })
}

export function deleteSystemConfig(id: number) {
  return request({
    url: '/system/configuration/delete',
    method: 'post',
    data: { id }
  })
}

export interface ModelConfigItem {
  id: number
  model: string
  baseUrl: string
  type: 1 | 2 | 3 | 4
  enabled: 0 | 1
  hasApiKey: boolean
  createUserName?: string | null
  createTime?: string | null
  updateUserName?: string | null
  updateTime?: string | null
}

export interface ModelConfigQuery {
  model?: string
  type?: 1 | 2 | 3 | 4
  enabled?: 0 | 1
  pageNo: number
  pageSize: number
}

export interface ModelConfigCreateParams {
  model: string
  apiKey: string
  baseUrl: string
  type: 1 | 2 | 3 | 4
  enabled: 0 | 1
}

export interface ModelConfigUpdateParams {
  id: number
  model?: string
  apiKey?: string
  baseUrl?: string
  type?: 1 | 2 | 3 | 4
  enabled?: 0 | 1
}

export function getConfig() {
  return request({
    url: '/system/config',
    method: 'get'
  })
}

export function updateConfig(data: any) {
  return request({
    url: '/system/config',
    method: 'put',
    data
  })
}

export function queryModelConfigs(data: ModelConfigQuery) {
  return request<{list: ModelConfigItem[]; total: number; pageNo: number; pageSize: number}>({
    url: '/system/model-config/querylist',
    method: 'post',
    data
  })
}

export function createModelConfig(data: ModelConfigCreateParams) {
  return request({
    url: '/system/model-config/insert',
    method: 'post',
    data
  })
}

export function updateModelConfig(data: ModelConfigUpdateParams) {
  return request({
    url: '/system/model-config/update',
    method: 'post',
    data
  })
}

export function deleteModelConfig(id: number) {
  return request({
    url: '/system/model-config/delete',
    method: 'post',
    data: { id }
  })
}

export function batchDeleteModelConfigs(ids: number[]) {
  return request<{ deletedCount: number }>({
    url: '/system/model-config/batch-delete',
    method: 'post',
    data: { ids }
  })
}
