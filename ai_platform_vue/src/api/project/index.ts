import request from '@/util/request'

export interface ProjectGroup {
  id: number
  sandboxConfigId: number | null
  parentId: number | null
  groupName: string
  level: number
  sortOrder: number
  libraryName: string | null
  enabled: 0 | 1
  createTime: string | null
  updateTime: string | null
}

export interface ProjectGroupCreateParams {
  sandboxConfigId?: number | null
  groupName: string
  parentId: number | null
  sortOrder: number
  enabled: 0 | 1
}

export interface ProjectGroupUpdateParams {
  sandboxConfigId?: number | null
  id: number
  groupName: string
  sortOrder: number
  enabled: 0 | 1
}

export interface PaginationParams {
  pageNo: number
  pageSize: number
}

export interface PaginatedResult<T> extends PaginationParams {
  list: T[]
  total: number
}

export interface DatabaseOption {
  libraryName: string
  tableCount: number
}

export interface PhysicalTableColumn {
  columnName: string
  columnType: string
  columnComment: string
  remark: string
}

export interface TableColumnRemarkItem {
  columnName: string
  remark: string
}

export interface TableColumnRemarksSaveParams {
  projectGroupId: number
  tableManagementId: number
  columns: TableColumnRemarkItem[]
}

export interface TableColumnRemarksSaveResult {
  tableManagementId: number
  columns: PhysicalTableColumn[]
}

export interface TableColumnsDeleteResult extends TableColumnRemarksSaveResult {
  deletedCount: number
}

export interface ProjectGroupTableOption {
  tableName: string
  tableSchema: string
  physicalTableName: string
  databaseComment: string
  associated: boolean
  tableManagementId: number | null
  tableCnName: string
  tableComment: string
  columns: PhysicalTableColumn[]
}

export interface ProjectGroupTableOptions {
  projectGroup: ProjectGroup
  rootProjectGroupId: number
  libraryOwnerProjectGroupId: number | null
  libraryName: string | null
  tables: ProjectGroupTableOption[]
}

export interface TableAssociationSaveItem {
  tableName: string
  tableCnName: string
  tableComment: string
}

export interface TableRelationCreateParams {
  projectGroupId: number
  sourceTableId: number
  targetTableId: number
  sourceColumn: string
  targetColumn: string
  relationContent: string
}

export interface TableRelationUpdateParams extends TableRelationCreateParams {
  id: number
}

export interface TableRelationCandidate {
  sourceTableId: number
  targetTableId: number
  sourceColumn: string
  targetColumn: string
  relationContent: string
}

export interface TableRelationSuggestion extends TableRelationCandidate {
  suggestionId: string
  sourceTableName: string
  sourceTableCnName: string
  targetTableName: string
  targetTableCnName: string
}

export interface ProjectGroupTableRelation extends TableRelationUpdateParams {
  sourceTableName: string
  sourceTableCnName: string
  targetTableName: string
  targetTableCnName: string
  remarks: string | null
  createTime: string | null
  updateTime: string | null
  valid: boolean
  invalidReason: string
}

export interface TableSchemaChange {
  tableManagementId: number
  tableName: string
  tableCnName: string
  physicalExists: boolean
  addedColumns: string[]
  removedColumns: string[]
  changedColumns: string[]
}

export interface TableSchemaSyncResult {
  syncedTableCount: number
  changedTableCount: number
  unchangedTableCount: number
  missingTableCount: number
  tableChanges: TableSchemaChange[]
  invalidRelations: ProjectGroupTableRelation[]
  tables: ProjectGroupTableOption[]
}

export interface SingleTableSchemaSyncResult {
  table: ProjectGroupTableOption
  physicalExists: boolean
  structureChanged: boolean
  addedColumns: string[]
  removedColumns: string[]
  changedColumns: string[]
}

export interface ProjectGroupSkill {
  templateId?:string|null
  id: number
  rootProjectGroupId: number
  skillGroupId: number
  skillGroupName: string
  skillName: string
  skillDescription: string | null
  skillType: 2
  skillLevelType: 1 | 2
  ruleContent: string
  tableIds: number[]
  subSkillIds: number[]
  enabled: 0 | 1
  createUserId: number | null
  createUserName: string | null
  createTime: string | null
  updateUserId: number | null
  updateUserName: string | null
  updateTime: string | null
}

export interface ProjectGroupSkillSaveParams {
  templateId?:string|null
  mcpBindings?: import('@/api/mcp').McpBinding[]
  rootProjectGroupId: number
  skillGroupId: number
  skillName: string
  skillDescription: string
  skillLevelType: 1 | 2
  ruleContent: string
  tableIds: number[]
  subSkillIds: number[]
  enabled: 0 | 1
}

export interface ProjectGroupSkillUpdateParams extends ProjectGroupSkillSaveParams {
  id: number
}

export interface ProjectGroupSubSkillOption {
  id: number
  skillName: string
  skillDescription: string | null
  enabled: 0 | 1
}

export function getProjectGroupList() {
  return request<{ list: ProjectGroup[]; total: number }>({
    url: '/project/group/list',
    method: 'get'
  })
}

export function createProjectGroup(data: ProjectGroupCreateParams) {
  return request<ProjectGroup>({
    url: '/project/group/insert',
    method: 'post',
    data
  })
}

export function updateProjectGroup(data: ProjectGroupUpdateParams) {
  return request<ProjectGroup>({
    url: '/project/group/update',
    method: 'post',
    data
  })
}

export function deleteProjectGroup(data: { id: number }) {
  return request({
    url: '/project/group/delete',
    method: 'post',
    data
  })
}

export function getProjectGroupTableOptions(projectGroupId: number) {
  return request<ProjectGroupTableOptions>({
    url: `/project/group/${projectGroupId}/table-options`,
    method: 'get'
  })
}

export function getProjectGroupTablePage(
  projectGroupId: number,
  params: PaginationParams & { keyword?: string }
) {
  return request<PaginatedResult<ProjectGroupTableOption>>({
    url: `/project/group/${projectGroupId}/tables`,
    method: 'get',
    params
  })
}

export function getChildProjectGroupPage(
  projectGroupId: number,
  params: PaginationParams & { keyword?: string }
) {
  return request<PaginatedResult<ProjectGroup>>({
    url: `/project/group/${projectGroupId}/children`,
    method: 'get',
    params
  })
}

export function getProjectDatabaseOptions(projectGroupId: number) {
  return request<{ list: DatabaseOption[]; total: number }>({
    url: '/project/group/database-options',
    timeout: 90000,
    method: 'get',
    params: { projectGroupId }
  })
}

export function getProjectGroupImportTableOptions(
  projectGroupId: number,
  libraryName: string
) {
  return request<ProjectGroupTableOptions>({
    url: `/project/group/${projectGroupId}/import-table-options`,
    timeout: 240000,
    method: 'get',
    params: { libraryName }
  })
}

export function saveProjectGroupTableAssociations(data: {
  projectGroupId: number
  libraryName: string
  tables: TableAssociationSaveItem[]
}) {
  return request<{
    libraryName: string
    libraryOwnerProjectGroupId: number
    selectedCount: number
  }>({
    url: '/project/group/table-associations/save',
    timeout: 240000,
    method: 'post',
    data
  })
}

export function syncProjectGroupTableSchemas(projectGroupId: number) {
  return request<TableSchemaSyncResult>({
    url: `/project/group/${projectGroupId}/table-associations/sync-schema`,
    timeout: 240000,
    method: 'post'
  })
}

export function syncProjectGroupTableSchema(projectGroupId: number, tableManagementId: number) {
  return request<SingleTableSchemaSyncResult>({
    url: `/project/group/${projectGroupId}/table-associations/${tableManagementId}/sync-schema`,
    timeout: 240000,
    method: 'post'
  })
}

export function saveProjectGroupTableColumnRemarks(data: TableColumnRemarksSaveParams) {
  return request<TableColumnRemarksSaveResult>({
    url: '/project/group/table-columns/remarks/save',
    method: 'post',
    data
  })
}

export function deleteProjectGroupTableColumns(data: {
  projectGroupId: number
  tableManagementId: number
  columnNames: string[]
}) {
  return request<TableColumnsDeleteResult>({
    url: '/project/group/table-columns/delete',
    method: 'post',
    data
  })
}

export function createProjectGroupTableRelation(data: TableRelationCreateParams) {
  return request<{ id: number }>({
    url: '/project/group/table-relations/insert',
    method: 'post',
    data
  })
}

export function generateProjectGroupTableRelationSuggestions(projectGroupId: number) {
  return request<{ list: TableRelationSuggestion[]; total: number }>({
    url: `/project/group/${projectGroupId}/table-relations/ai-suggestions`,
    method: 'post',
    timeout: 70000
  })
}

export function createProjectGroupTableRelations(data: {
  projectGroupId: number
  relations: TableRelationCandidate[]
}) {
  return request<{ createdCount: number }>({
    url: '/project/group/table-relations/batch-insert',
    method: 'post',
    data
  })
}

export function getProjectGroupTableRelations(projectGroupId: number) {
  return request<{ list: ProjectGroupTableRelation[]; total: number }>({
    url: `/project/group/${projectGroupId}/table-relations`,
    method: 'get'
  })
}

export function updateProjectGroupTableRelation(data: TableRelationUpdateParams) {
  return request<{ id: number }>({
    url: '/project/group/table-relations/update',
    method: 'post',
    data
  })
}

export function deleteProjectGroupTableRelation(data: { id: number; projectGroupId: number }) {
  return request({
    url: '/project/group/table-relations/delete',
    method: 'post',
    data
  })
}

export function deleteProjectGroupTableRelations(data: { projectGroupId: number; ids: number[] }) {
  return request<{ deletedCount: number }>({
    url: '/project/group/table-relations/batch-delete',
    method: 'post',
    data
  })
}

export function getProjectGroupSkills(
  projectGroupId: number,
  params: PaginationParams & { keyword?: string; enabled?: 0 | 1; skillLevelType?: 1 | 2 }
) {
  return request<PaginatedResult<ProjectGroupSkill>>({
    url: `/project/group/${projectGroupId}/skills`,
    method: 'get',
    params
  })
}

export function getProjectGroupSubSkillOptions(skillGroupId: number) {
  return request<{ list: ProjectGroupSubSkillOption[]; total: number }>({
    url: `/project/group/${skillGroupId}/skills/sub-skill-options`,
    method: 'get'
  })
}

export function createProjectGroupSkill(data: ProjectGroupSkillSaveParams) {
  return request<{ id: number; skillGroupId: number }>({
    url: '/project/group/skills/insert',
    method: 'post',
    data
  })
}

export function updateProjectGroupSkill(data: ProjectGroupSkillUpdateParams) {
  return request<{ id: number; skillGroupId: number }>({
    url: '/project/group/skills/update',
    method: 'post',
    data
  })
}

export function deleteProjectGroupSkill(data: { id: number; rootProjectGroupId: number }) {
  return request({
    url: '/project/group/skills/delete',
    method: 'post',
    data
  })
}

export function deleteProjectGroupSkills(data: {
  rootProjectGroupId: number
  skillGroupId: number
  ids: number[]
}) {
  return request<{ deletedCount: number }>({
    url: '/project/group/skills/batch-delete',
    method: 'post',
    data
  })
}
