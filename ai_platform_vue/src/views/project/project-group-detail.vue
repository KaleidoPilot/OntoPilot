<template>
  <div class="project-group-detail-page">
    <el-card class="detail-card" shadow="never">
      <template #header>
        <div class="page-header">
          <div class="title-area">
            <el-breadcrumb separator="/">
              <el-breadcrumb-item :to="{ path: '/project/group' }">项目组管理</el-breadcrumb-item>
              <el-breadcrumb-item>{{ projectGroup?.groupName || '项目组详情' }}</el-breadcrumb-item>
            </el-breadcrumb>
            <h1>{{ projectGroup?.groupName || '项目组详情' }}</h1>
            <p v-if="isRootProjectGroup">从绑定沙箱可访问的数据库中选择物理表，导入后供技能选择使用。</p>
            <p v-else>查看当前技能组中的具体技能。</p>
          </div>
          <div class="header-actions">
            <el-button :icon="ArrowLeft" :disabled="!projectGroup" @click="returnToParentProjectGroup">
              返回上级菜单
            </el-button>
            <el-button :icon="Edit" :disabled="!projectGroup" @click="openEditDialog">
              编辑当前项目组
            </el-button>
            <el-button type="danger" plain :icon="Delete" :disabled="!projectGroup" @click="confirmDeleteCurrentGroup">
              删除
            </el-button>
          </div>
        </div>
      </template>

      <el-alert v-if="errorMessage" class="content-alert" :title="errorMessage" type="error" show-icon :closable="false">
        <template #default><el-button link type="primary" @click="fetchDetail">重新加载</el-button></template>
      </el-alert>
      <el-alert
        v-else-if="projectGroup && projectGroup.enabled !== 1"
        class="content-alert"
        title="当前项目组已停用"
        description="可以编辑并重新启用；停用状态下不能修改数据表或技能。"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-alert v-if="isRootProjectGroup && !projectGroup?.sandboxConfigId" class="content-alert" title="当前项目组尚未选择沙箱，请编辑项目组补选。" type="warning" show-icon :closable="false" />
      <el-tag v-else-if="isRootProjectGroup" class="content-alert">绑定沙箱：{{ sandboxLabel(projectGroup?.sandboxConfigId) }}</el-tag>
      <el-tabs v-model="activeManagementTab" type="card" class="management-tabs">
        <el-tab-pane v-if="isRootProjectGroup" label="数据表" name="tables">
          <section class="association-section" aria-label="数据表管理">
            <el-alert
              v-if="tablePageError"
              class="table-page-alert"
              :title="tablePageError"
              type="error"
              show-icon
              :closable="false"
            >
              <template #default>
                <el-button link type="primary" @click="loadProjectGroupTablePage">重新加载</el-button>
              </template>
            </el-alert>
            <div class="section-header">
              <el-input
                v-model="tableSearchKeyword"
                class="table-search"
                :prefix-icon="Search"
                clearable
                aria-label="搜索已导入数据表"
                placeholder="搜索英文表名或中文表名"
              />
              <div class="save-area">
                <el-button
                  type="danger"
                  plain
                  :icon="Delete"
                  :loading="batchDeletingImportedTables"
                  :disabled="!canEditAssociations || !selectedImportedTableNames.length || Boolean(deletingTableName)"
                  @click="confirmBatchRemoveImportedTables"
                >
                  批量删除<span v-if="selectedImportedTableNames.length">（{{ selectedImportedTableNames.length }}）</span>
                </el-button>
                <el-tag :type="libraryName ? 'primary' : 'info'">
                  归属库：<span class="notranslate" translate="no">{{ loading ? '加载中' : (libraryName || '尚未选择') }}</span>
                </el-tag>
                <el-button
                  :icon="Connection"
                  :disabled="loading || !projectGroup"
                  @click="openTableRelationDialog"
                >
                  关联表关系
                </el-button>
                <el-tooltip :disabled="canSyncTableSchemas" content="请先导入数据表" placement="top">
                  <span>
                    <el-button
                      :icon="Refresh"
                      :loading="schemaSyncing"
                      :disabled="loading || !canSyncTableSchemas"
                      @click="syncTableSchemas"
                    >
                      同步表结构
                    </el-button>
                  </span>
                </el-tooltip>
                <el-tooltip :disabled="canImportTables" content="停用状态下不能导入数据表" placement="top">
                  <span>
                    <el-button type="primary" :icon="Upload" :disabled="loading || !canImportTables" @click="openImportDialog">
                      导入数据表
                    </el-button>
                  </span>
                </el-tooltip>
              </div>
            </div>

            <div class="tab-table-area">
              <el-table
                :key="tableStructureVersion"
                v-loading="loading || tablePageLoading || batchDeletingImportedTables"
                :data="tablePageList"
                height="100%"
                row-key="tableName"
                size="small"
                class="association-table"
                @selection-change="handleImportedTableSelectionChange"
              >
              <el-table-column type="selection" width="48" :selectable="canSelectImportedTable" />
              <el-table-column label="物理表" min-width="285">
                <template #default="scope">
                  <div class="physical-table-cell">
                    <div class="physical-table-name notranslate" translate="no">{{ scope.row.physicalTableName }}</div>
                    <div class="schema-name notranslate" translate="no">{{ scope.row.tableSchema || libraryName || '—' }}</div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="tableCnName" label="中文表名" min-width="200" />
              <el-table-column prop="tableComment" label="用途说明" min-width="280" show-overflow-tooltip>
                <template #default="scope">{{ scope.row.tableComment || '—' }}</template>
              </el-table-column>
              <el-table-column label="字段" width="110">
                <template #default="scope">
                  <el-button link type="primary" @click="showColumns(scope.row)">{{ scope.row.columns.length }} 个字段</el-button>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100" fixed="right">
                <template #default="scope">
                  <el-button
                    link
                    type="danger"
                    :icon="Delete"
                    :loading="deletingTableName === scope.row.tableName"
                    :disabled="!canEditAssociations || Boolean(deletingTableName) || batchDeletingImportedTables"
                    @click="confirmRemoveImportedTable(scope.row)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
              <template #empty>
                <el-empty
                  v-if="!loading && !tablePageLoading"
                  :description="tableSearchKeyword.trim() ? '没有符合条件的数据表' : '当前项目组尚未导入数据表'"
                >
                  <el-button
                    v-if="canImportTables && !tableSearchKeyword.trim()"
                    type="primary"
                    :icon="Upload"
                    @click="openImportDialog"
                  >
                    导入数据表
                  </el-button>
                </el-empty>
              </template>
              </el-table>
            </div>
            <div v-if="tableTotal > 0" class="list-pagination">
              <el-pagination
                background
                :current-page="tablePageNo"
                :page-size="tablePageSize"
                layout="total, prev, pager, next, jumper"
                :total="tableTotal"
                @current-change="handleTablePageChange"
              />
            </div>
          </section>
        </el-tab-pane>
        <el-tab-pane v-if="showProjectSkillGroups" :label="isRootProjectGroup ? '技能组管理' : '技能'" name="skills">
          <section v-if="isRootProjectGroup" class="skill-section" aria-label="技能组管理">
            <div class="skill-header">
              <el-input
                v-model="skillGroupKeyword"
                class="skill-search"
                :prefix-icon="Search"
                clearable
                aria-label="搜索技能组"
                placeholder="搜索技能组名称"
              />
              <el-button
                type="primary"
                :icon="Plus"
                :disabled="!canCreateSkillGroup"
                @click="openCreateSkillGroupDialog"
              >
                新增技能组
              </el-button>
            </div>

            <el-alert
              v-if="skillGroupListError"
              class="skill-alert"
              :title="skillGroupListError"
              type="error"
              show-icon
              :closable="false"
            >
              <template #default>
                <el-button link type="primary" @click="loadSkillGroups">重新加载</el-button>
              </template>
            </el-alert>

            <div class="tab-table-area">
              <el-table
                v-loading="skillGroupListLoading"
                :data="skillGroupList"
                height="100%"
                row-key="id"
                size="small"
                class="skill-table"
              >
                <el-table-column prop="groupName" label="技能组名称" min-width="280">
                  <template #default="scope">
                    <el-button link type="primary" @click="openSkillGroup(scope.row)">
                      {{ scope.row.groupName }}
                    </el-button>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="120">
                  <template #default="scope">
                    <el-tag :type="scope.row.enabled === 1 ? 'success' : 'info'">
                      {{ scope.row.enabled === 1 ? '已启用' : '已停用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="创建时间" min-width="180">
                  <template #default="scope">{{ scope.row.createTime || '—' }}</template>
                </el-table-column>
                <el-table-column label="操作" width="220" fixed="right">
                  <template #default="scope">
                    <el-button link type="primary" @click="openSkillGroup(scope.row)">进入</el-button>
                    <el-button
                      link
                      type="primary"
                      :icon="Edit"
                      :disabled="!canEditAssociations || deletingSkillGroupId !== null"
                      @click="openEditSkillGroupDialog(scope.row)"
                    >
                      编辑
                    </el-button>
                    <el-button
                      link
                      type="danger"
                      :icon="Delete"
                      :loading="deletingSkillGroupId === scope.row.id"
                      :disabled="!canEditAssociations || deletingSkillGroupId !== null"
                      @click="confirmDeleteSkillGroup(scope.row)"
                    >
                      删除
                    </el-button>
                  </template>
                </el-table-column>
                <template #empty>
                  <el-empty
                    v-if="!skillGroupListLoading"
                    :description="skillGroupKeyword.trim() ? '没有符合条件的技能组' : '当前项目组还没有技能组'"
                  >
                    <el-button
                      v-if="canCreateSkillGroup && !skillGroupKeyword.trim()"
                      type="primary"
                      :icon="Plus"
                      @click="openCreateSkillGroupDialog"
                    >
                      新增技能组
                    </el-button>
                  </el-empty>
                </template>
              </el-table>
            </div>
            <div v-if="skillGroupTotal > 0" class="list-pagination">
              <el-pagination
                background
                :current-page="skillGroupPageNo"
                :page-size="skillGroupPageSize"
                layout="total, prev, pager, next, jumper"
                :total="skillGroupTotal"
                @current-change="handleSkillGroupPageChange"
              />
            </div>
          </section>

          <section v-else class="skill-section" aria-label="技能组中的具体技能">
            <div class="skill-header">
              <el-input
                v-model="skillKeyword"
                class="skill-search"
                :prefix-icon="Search"
                clearable
                aria-label="搜索项目组技能"
                placeholder="搜索技能名称或描述"
              />
              <div class="skill-toolbar">
                <el-button
                  type="danger"
                  plain
                  :icon="Delete"
                  :loading="batchDeletingSkills"
                  :disabled="!canEditAssociations || !selectedSkillIds.length || deletingSkillId !== null"
                  @click="confirmBatchDeleteSkills"
                >
                  批量删除<span v-if="selectedSkillIds.length">（{{ selectedSkillIds.length }}）</span>
                </el-button>
                <el-select
                  v-model="skillLevelTypeFilter"
                  class="skill-status-filter"
                  aria-label="筛选技能类型"
                  placeholder="全部类型"
                >
                  <el-option label="全部类型" value="" />
                  <el-option label="主技能" :value="1" />
                  <el-option label="子技能" :value="2" />
                </el-select>
                <el-select
                  v-model="skillEnabledFilter"
                  class="skill-status-filter"
                  aria-label="筛选技能状态"
                  placeholder="全部状态"
                >
                  <el-option label="全部状态" value="" />
                  <el-option label="已启用" :value="1" />
                  <el-option label="已停用" :value="0" />
                </el-select>
                <el-tooltip
                  :disabled="canCreateConcreteSkill"
                  content="当前技能组已停用，不能新增技能"
                  placement="top"
                >
                  <span>
                    <el-button
                      type="primary"
                      :icon="Plus"
                      :disabled="!canCreateConcreteSkill"
                      @click="openCreateSkillDialog"
                    >
                      新增技能
                    </el-button>
                  </span>
                </el-tooltip>
              </div>
            </div>

            <el-alert
              v-if="skillListError"
              class="skill-alert"
              :title="skillListError"
              type="error"
              show-icon
              :closable="false"
            >
              <template #default>
                <el-button link type="primary" @click="loadProjectSkills">重新加载</el-button>
              </template>
            </el-alert>

            <div class="tab-table-area">
              <el-table
                v-loading="skillListLoading || batchDeletingSkills"
                :data="skillList"
                height="100%"
                row-key="id"
                size="small"
                class="skill-table"
                @selection-change="handleSkillSelectionChange"
              >
              <el-table-column type="selection" width="48" :selectable="canSelectSkill" />
              <el-table-column prop="skillName" label="技能名称" min-width="190" />
              <el-table-column label="技能类型" width="110" align="center">
                <template #default="scope">
                  <el-tag :type="scope.row.skillLevelType === 1 ? 'primary' : 'success'">
                    {{ scope.row.skillLevelType === 1 ? '主技能' : '子技能' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="技能描述" min-width="220" show-overflow-tooltip>
                <template #default="scope">{{ scope.row.skillDescription || '—' }}</template>
              </el-table-column>
              <el-table-column prop="ruleContent" label="规则内容" min-width="300" show-overflow-tooltip />
              <el-table-column label="关联数据表" width="120">
                <template #default="scope">{{ scope.row.tableIds.length }} 张</template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="scope">
                  <el-tag :type="scope.row.enabled === 1 ? 'success' : 'info'">
                    {{ scope.row.enabled === 1 ? '已启用' : '已停用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="scope">
                  <el-button
                    link
                    type="primary"
                    :icon="Edit"
                    :disabled="!canEditAssociations || batchDeletingSkills"
                    @click="openEditSkillDialog(scope.row)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    link
                    type="danger"
                    :icon="Delete"
                    :loading="deletingSkillId === scope.row.id"
                    :disabled="!canEditAssociations || deletingSkillId !== null || batchDeletingSkills"
                    @click="confirmDeleteSkill(scope.row)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
              <template #empty>
                <el-empty
                  v-if="!skillListLoading"
                  :description="skillKeyword.trim() || skillEnabledFilter !== '' || skillLevelTypeFilter !== '' ? '没有符合条件的技能' : '当前技能组还没有具体技能'"
                >
                  <el-button
                    v-if="canCreateConcreteSkill && !skillKeyword.trim() && skillEnabledFilter === '' && skillLevelTypeFilter === ''"
                    type="primary"
                    :icon="Plus"
                    @click="openCreateSkillDialog"
                  >
                    新增技能
                  </el-button>
                </el-empty>
              </template>
              </el-table>
            </div>
            <div v-if="skillTotal > 0" class="list-pagination">
              <el-pagination
                background
                :current-page="skillPageNo"
                :page-size="skillPageSize"
                layout="total, prev, pager, next, jumper"
                :total="skillTotal"
                @current-change="handleSkillPageChange"
              />
            </div>
          </section>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="importDialogVisible" title="导入数据表" width="min(1120px, calc(100% - 32px))" destroy-on-close @closed="resetImportDialog">
      <div class="database-selector">
        <label for="database-select">数据库</label>
        <el-select
          id="database-select"
          v-model="importLibraryName"
          class="database-select notranslate"
          translate="no"
          popper-class="database-select-popper notranslate"
          filterable
          clearable
          :loading="databaseLoading"
          :disabled="databaseSelectionLocked"
          placeholder="请选择当前连接中的数据库"
          @change="handleLibraryChange"
        >
          <el-option
            v-for="database in databaseOptions"
            :key="database.libraryName"
            :label="`${database.libraryName}（${database.tableCount} 张表）`"
            :value="database.libraryName"
            class="notranslate"
            translate="no"
          >
            <span class="notranslate" translate="no">
              {{ database.libraryName }}（{{ database.tableCount }} 张表）
            </span>
          </el-option>
        </el-select>
        <span v-if="libraryName" class="selector-tip">
          当前一级项目组归属库已确定，只能继续导入该数据库中的表
        </span>
        <span v-else class="selector-tip">当前一级项目组尚未关联数据库，可以自行选择</span>
      </div>

      <div v-if="importLibraryName" class="import-table-filter">
        <el-input
          v-model="importTableKeyword"
          class="import-table-search"
          :prefix-icon="Search"
          clearable
          aria-label="搜索可导入数据表"
          placeholder="搜索真实物理表名"
        />
        <span v-if="importTableKeyword.trim()" class="import-table-match-count">
          找到 {{ filteredImportTableOptions.length }} 张
        </span>
      </div>

      <el-table
        v-loading="importTablesLoading"
        :data="filteredImportTableOptions"
        row-key="tableName"
        max-height="480"
        @selection-change="handleImportSelectionChange"
      >
        <el-table-column type="selection" width="54" reserve-selection :selectable="canSelectImportTable" />
        <el-table-column label="物理表" min-width="245">
          <template #default="scope">
            <div class="physical-table-cell">
              <div class="physical-table-name notranslate" translate="no">{{ scope.row.physicalTableName }}</div>
              <div class="schema-name notranslate" translate="no">{{ scope.row.tableSchema }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="中文表名" min-width="190">
          <template #default="scope">
            <el-input
              v-model="scope.row.tableCnName"
              maxlength="255"
              placeholder="暂无中文表名，勾选后可补充"
              :disabled="!isImportTableSelected(scope.row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="用途说明" min-width="320">
          <template #default="scope">
            <el-input
              v-model="scope.row.tableComment"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
              maxlength="255"
              show-word-limit
              resize="none"
              placeholder="请输入表的用途和业务含义"
              :disabled="!isImportTableSelected(scope.row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="数据库注释" min-width="220" show-overflow-tooltip>
          <template #default="scope">{{ scope.row.databaseComment || '—' }}</template>
        </el-table-column>
        <el-table-column label="字段" width="100" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="showColumns(scope.row)">{{ scope.row.columns.length }} 个字段</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty
            :description="importLoadError || (importTablesLoading || databaseLoading ? '正在读取沙箱数据…' : (importTableKeyword.trim() ? '未找到匹配的物理表' : (importLibraryName ? '该数据库中的数据表均已导入' : '请先选择数据库')))"
          >
            <el-button v-if="importLoadError" type="primary" :loading="databaseLoading || importTablesLoading" @click="retryImportData">重新加载</el-button>
          </el-empty>
        </template>
      </el-table>

      <template #footer>
        <div class="dialog-footer">
          <el-tag type="info">已选择 {{ importSelectedCount }} / {{ importTableOptions.length }}</el-tag>
          <div>
            <el-button @click="importDialogVisible = false">取消</el-button>
            <el-button type="primary" :icon="Upload" :loading="saving" :disabled="!importLibraryName || importTablesLoading || !importSelectedCount" @click="saveAssociations">
              确认导入
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="schemaSyncDialogVisible"
      title="表结构同步结果"
      width="min(980px, calc(100% - 32px))"
    >
      <template v-if="schemaSyncResult">
        <el-descriptions :column="4" border class="sync-summary">
          <el-descriptions-item label="已检查">{{ schemaSyncResult.syncedTableCount }} 张</el-descriptions-item>
          <el-descriptions-item label="发生变化">{{ schemaSyncResult.changedTableCount }} 张</el-descriptions-item>
          <el-descriptions-item label="没有变化">{{ schemaSyncResult.unchangedTableCount }} 张</el-descriptions-item>
          <el-descriptions-item label="物理表缺失">{{ schemaSyncResult.missingTableCount }} 张</el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="schemaSyncResult.missingTableCount"
          class="sync-alert"
          title="检测到真实物理表已不存在"
          description="系统保留数据表管理记录，但已将对应字段快照同步为空；请确认真实数据库是否发生了删除或重命名。"
          type="warning"
          show-icon
          :closable="false"
        />

        <el-table v-if="schemaSyncResult.tableChanges.length" :data="schemaSyncResult.tableChanges" max-height="360">
          <el-table-column label="数据表" min-width="230">
            <template #default="scope">
              <div class="relation-table-name">{{ scope.row.tableCnName }}</div>
              <div class="schema-name notranslate" translate="no">{{ scope.row.tableName }}</div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="scope">
              <el-tag :type="scope.row.physicalExists ? 'success' : 'danger'" effect="plain">
                {{ scope.row.physicalExists ? '结构已更新' : '物理表缺失' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="新增字段" min-width="170" show-overflow-tooltip>
            <template #default="scope">{{ formatColumnNames(scope.row.addedColumns) }}</template>
          </el-table-column>
          <el-table-column label="删除字段" min-width="170" show-overflow-tooltip>
            <template #default="scope">{{ formatColumnNames(scope.row.removedColumns) }}</template>
          </el-table-column>
          <el-table-column label="类型/注释变化" min-width="180" show-overflow-tooltip>
            <template #default="scope">{{ formatColumnNames(scope.row.changedColumns) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="已与真实物理表保持一致，没有结构变化" />

        <div v-if="schemaSyncResult.invalidRelations.length" class="invalid-relation-section">
          <h3>需要修改的失效关系</h3>
          <el-alert
            class="sync-alert"
            title="以下关系引用的物理表或字段已经不存在，关系记录没有被自动删除。"
            type="error"
            show-icon
            :closable="false"
          />
          <el-table :data="schemaSyncResult.invalidRelations" max-height="260">
            <el-table-column label="源表字段" min-width="220">
              <template #default="scope">{{ scope.row.sourceTableCnName }} · {{ scope.row.sourceColumn }}</template>
            </el-table-column>
            <el-table-column label="目标表字段" min-width="220">
              <template #default="scope">{{ scope.row.targetTableCnName }} · {{ scope.row.targetColumn }}</template>
            </el-table-column>
            <el-table-column prop="relationContent" label="关系内容" min-width="220" show-overflow-tooltip />
            <el-table-column prop="invalidReason" label="失效原因" min-width="180" />
          </el-table>
        </div>
      </template>
      <template #footer>
        <el-button type="primary" @click="schemaSyncDialogVisible = false">我知道了</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="relationDialogVisible"
      title="表关系管理"
      width="min(1120px, calc(100% - 32px))"
      destroy-on-close
      @closed="resetRelationManager"
    >
      <div class="relation-manager-header">
        <div>
          <h3>历史关联关系</h3>
          <p>展示当前项目组已保存的字段关系，可以继续创建或修改。</p>
        </div>
        <div class="relation-manager-actions">
          <el-button
            type="danger"
            plain
            :icon="Delete"
            :loading="batchDeletingRelations"
            :disabled="!canEditAssociations || selectedRelationIds.length === 0 || deletingRelationId !== null"
            @click="confirmBatchDeleteTableRelations"
          >
            批量删除<span v-if="selectedRelationIds.length">（{{ selectedRelationIds.length }}）</span>
          </el-button>
          <el-tooltip :disabled="canCreateTableRelation" content="请先导入至少两张数据表" placement="top">
            <span>
              <el-button
                type="primary"
                :icon="Plus"
                :disabled="!canCreateTableRelation || batchDeletingRelations"
                @click="openCreateTableRelationDialog"
              >
                创建关联关系
              </el-button>
            </span>
          </el-tooltip>
        </div>
      </div>

      <el-alert
        v-if="relationListError"
        class="relation-alert"
        :title="relationListError"
        type="error"
        show-icon
        :closable="false"
      >
        <template #default>
          <el-button link type="primary" @click="loadTableRelations">重新加载</el-button>
        </template>
      </el-alert>

      <el-table
        v-loading="relationListLoading || batchDeletingRelations"
        :data="relationList"
        row-key="id"
        max-height="480"
        @selection-change="handleRelationSelectionChange"
      >
        <el-table-column type="selection" width="48" :selectable="canSelectTableRelation" />
        <el-table-column label="源表" min-width="210">
          <template #default="scope">
            <div class="relation-table-name">{{ scope.row.sourceTableCnName }}</div>
            <div class="schema-name notranslate" translate="no">{{ scope.row.sourceTableName }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="sourceColumn" label="源字段" min-width="135" />
        <el-table-column label="目标表" min-width="210">
          <template #default="scope">
            <div class="relation-table-name">{{ scope.row.targetTableCnName }}</div>
            <div class="schema-name notranslate" translate="no">{{ scope.row.targetTableName }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="targetColumn" label="目标字段" min-width="135" />
        <el-table-column prop="relationContent" label="关系内容" min-width="240" show-overflow-tooltip />
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tooltip :disabled="scope.row.valid" :content="scope.row.invalidReason" placement="top">
              <el-tag :type="scope.row.valid ? 'success' : 'danger'" effect="plain">
                {{ scope.row.valid ? '有效' : '字段已失效' }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="170">
          <template #default="scope">{{ scope.row.updateTime || scope.row.createTime || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="scope">
            <el-button
              link
              type="primary"
              :icon="Edit"
              :disabled="!canEditAssociations || batchDeletingRelations"
              @click="openEditTableRelationDialog(scope.row)"
            >
              修改
            </el-button>
            <el-button
              link
              type="danger"
              :icon="Delete"
              :loading="deletingRelationId === scope.row.id"
              :disabled="!canEditAssociations || deletingRelationId !== null || batchDeletingRelations"
              @click="confirmDeleteTableRelation(scope.row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty v-if="!relationListLoading && !relationListError" description="当前项目组尚未创建关联关系" />
        </template>
      </el-table>
    </el-dialog>

    <el-dialog
      v-model="relationFormDialogVisible"
      :title="relationDialogMode === 'create' ? '创建关联关系' : '修改关联关系'"
      :width="relationDialogMode === 'create' && relationCreateMode === 'auto' ? 'min(1180px, calc(100% - 32px))' : 'min(760px, calc(100% - 32px))'"
      append-to-body
      destroy-on-close
      @closed="resetRelationForm"
    >
      <div v-if="relationDialogMode === 'create'" class="relation-mode-switch">
        <el-radio-group v-model="relationCreateMode">
          <el-radio-button label="manual">手动模式</el-radio-button>
          <el-radio-button label="auto">自动模式</el-radio-button>
        </el-radio-group>
      </div>

      <template v-if="relationDialogMode === 'edit' || relationCreateMode === 'manual'">
        <el-alert
          class="relation-alert"
          title="选择两张已导入数据表及其字段，并填写需要保存的关系内容。相同表和字段只能关联一次。"
          type="info"
          show-icon
          :closable="false"
        />
        <el-form
          ref="relationFormRef"
          :model="relationForm"
          :rules="relationRules"
          label-width="100px"
          status-icon
        >
          <el-row :gutter="20">
            <el-col :xs="24" :sm="12">
              <el-form-item label="源表" prop="sourceTableId">
                <el-select
                  v-model="relationForm.sourceTableId"
                  class="relation-select"
                  filterable
                  placeholder="请选择源表"
                  @change="handleSourceTableChange"
                >
                  <el-option
                    v-for="table in relationTableOptions"
                    :key="table.tableManagementId || table.tableName"
                    :label="`${table.tableCnName}（${table.physicalTableName}）`"
                    :value="table.tableManagementId"
                    :disabled="table.tableManagementId === relationForm.targetTableId"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="12">
              <el-form-item label="源字段" prop="sourceColumn">
                <el-select
                  v-model="relationForm.sourceColumn"
                  class="relation-select"
                  filterable
                  :disabled="relationForm.sourceTableId === null"
                  placeholder="请选择源字段"
                >
                  <el-option
                    v-for="column in sourceColumnOptions"
                    :key="column.columnName"
                    :label="column.columnComment ? `${column.columnName}（${column.columnComment}）` : column.columnName"
                    :value="column.columnName"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="12">
              <el-form-item label="目标表" prop="targetTableId">
                <el-select
                  v-model="relationForm.targetTableId"
                  class="relation-select"
                  filterable
                  placeholder="请选择目标表"
                  @change="handleTargetTableChange"
                >
                  <el-option
                    v-for="table in relationTableOptions"
                    :key="table.tableManagementId || table.tableName"
                    :label="`${table.tableCnName}（${table.physicalTableName}）`"
                    :value="table.tableManagementId"
                    :disabled="table.tableManagementId === relationForm.sourceTableId"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="12">
              <el-form-item label="目标字段" prop="targetColumn">
                <el-select
                  v-model="relationForm.targetColumn"
                  class="relation-select"
                  filterable
                  :disabled="relationForm.targetTableId === null"
                  placeholder="请选择目标字段"
                >
                  <el-option
                    v-for="column in targetColumnOptions"
                    :key="column.columnName"
                    :label="column.columnComment ? `${column.columnName}（${column.columnComment}）` : column.columnName"
                    :value="column.columnName"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="关系内容" prop="relationContent">
            <el-input
              v-model="relationForm.relationContent"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 6 }"
              maxlength="200"
              show-word-limit
              resize="none"
              placeholder="请描述这两个字段之间的业务关系"
            />
          </el-form-item>
        </el-form>
      </template>

      <template v-else>
        <el-alert
          class="relation-alert"
          title="AI会根据已导入表的真实结构和备注生成最多6条建议。建议不会自动保存，请检查、修改并勾选需要创建的关系。"
          type="info"
          show-icon
          :closable="false"
        />
        <div class="auto-relation-toolbar">
          <el-button type="primary" :loading="autoRelationGenerating" @click="generateAutoRelationSuggestions">
            AI 生成关系推荐
          </el-button>
          <span>已选择 {{ selectedAutoRelations.length }} / {{ autoRelationSuggestions.length }} 条</span>
        </div>
        <el-table
          ref="autoRelationTableRef"
          v-loading="autoRelationGenerating"
          :data="autoRelationSuggestions"
          row-key="suggestionId"
          max-height="480"
          @selection-change="handleAutoRelationSelectionChange"
        >
          <el-table-column type="selection" width="48" />
          <el-table-column label="源表" min-width="190">
            <template #default="scope">
              <el-select v-model="scope.row.sourceTableId" filterable @change="handleAutoSourceTableChange(scope.row)">
                <el-option
                  v-for="table in relationTableOptions"
                  :key="table.tableManagementId || table.tableName"
                  :label="`${table.tableCnName}（${table.physicalTableName}）`"
                  :value="table.tableManagementId"
                  :disabled="table.tableManagementId === scope.row.targetTableId"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="源字段" min-width="150">
            <template #default="scope">
              <el-select v-model="scope.row.sourceColumn" filterable placeholder="选择源字段">
                <el-option
                  v-for="column in relationColumns(scope.row.sourceTableId)"
                  :key="column.columnName"
                  :label="column.columnComment ? `${column.columnName}（${column.columnComment}）` : column.columnName"
                  :value="column.columnName"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="目标表" min-width="190">
            <template #default="scope">
              <el-select v-model="scope.row.targetTableId" filterable @change="handleAutoTargetTableChange(scope.row)">
                <el-option
                  v-for="table in relationTableOptions"
                  :key="table.tableManagementId || table.tableName"
                  :label="`${table.tableCnName}（${table.physicalTableName}）`"
                  :value="table.tableManagementId"
                  :disabled="table.tableManagementId === scope.row.sourceTableId"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="目标字段" min-width="150">
            <template #default="scope">
              <el-select v-model="scope.row.targetColumn" filterable placeholder="选择目标字段">
                <el-option
                  v-for="column in relationColumns(scope.row.targetTableId)"
                  :key="column.columnName"
                  :label="column.columnComment ? `${column.columnName}（${column.columnComment}）` : column.columnName"
                  :value="column.columnName"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="关系内容" min-width="260">
            <template #default="scope">
              <el-input v-model="scope.row.relationContent" maxlength="200" show-word-limit />
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="点击“AI 生成关系推荐”获取候选关系" :image-size="80" />
          </template>
        </el-table>
      </template>
      <template #footer>
        <el-button @click="relationFormDialogVisible = false">取消</el-button>
        <el-button
          v-if="relationDialogMode === 'edit' || relationCreateMode === 'manual'"
          type="primary"
          :loading="relationSubmitting"
          @click="submitTableRelation"
        >
          {{ relationDialogMode === 'create' ? '确认创建' : '保存修改' }}
        </el-button>
        <el-button
          v-else
          type="primary"
          :loading="autoRelationSubmitting"
          :disabled="selectedAutoRelations.length === 0 || autoRelationGenerating"
          @click="submitAutoTableRelations"
        >
          创建选中关系（{{ selectedAutoRelations.length }}）
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="groupDialogVisible" :title="groupDialogTitle" width="min(560px, 94vw)" :close-on-click-modal="!submittingGroup" :close-on-press-escape="!submittingGroup" :show-close="!submittingGroup" destroy-on-close @closed="resetGroupForm">
      <el-form ref="groupFormRef" :model="groupForm" :rules="groupRules" :disabled="submittingGroup" label-width="100px" status-icon>
        <el-form-item :label="groupDialogMode === 'editCurrent' ? '项目组名称' : '技能组名称'" prop="groupName">
          <el-input
            v-model="groupForm.groupName"
            maxlength="100"
            show-word-limit
            clearable
            :placeholder="groupDialogMode === 'editCurrent' ? '请输入项目组名称' : '请输入技能组名称'"
          />
        </el-form-item>
        <el-form-item label="启用状态" prop="enabled">
          <el-switch v-model="groupForm.enabled" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item v-if="groupDialogMode === 'editCurrent' && isRootProjectGroup" label="沙箱" prop="sandboxConfigId" :rules="[{ required: true, message: '请选择沙箱', trigger: 'change' }]">
          <el-select v-model="groupForm.sandboxConfigId" filterable :filter-method="filterSandboxes" @visible-change="sandboxSearch = ''" :loading="sandboxLoading" placeholder="输入名称或 URL 搜索沙箱" style="width: 100%">
            <el-option v-for="item in filteredSandboxOptions" :key="item.id" :label="item.name || item.url" :value="item.id" />
            <el-option v-if="groupForm.sandboxConfigId && !sandboxOptions.some(item => item.id === groupForm.sandboxConfigId)" label="已绑定沙箱不可用，请重新选择" :value="groupForm.sandboxConfigId" disabled />
          </el-select>
          <el-alert v-if="sandboxError" :title="sandboxError" type="error" :closable="false"><el-button link type="primary" @click="loadSandboxOptions">重新加载</el-button></el-alert>
          <span v-else-if="!sandboxLoading && !sandboxOptions.length">暂无可用沙箱，请先到系统配置新增并启用沙箱。</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="submittingGroup" @click="groupDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingGroup" @click="submitProjectGroup">
          {{ groupDialogMode === 'createSkillGroup' ? '确定新增' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="skillDialogVisible"
      :title="skillDialogMode === 'create' ? '新增项目组技能' : '编辑项目组技能'"
      width="min(840px, calc(100% - 32px))"
      destroy-on-close
      @closed="resetSkillForm"
    >
      <el-form ref="skillFormRef" :model="skillForm" :rules="skillRules" label-width="90px" status-icon>
        <el-form-item label="技能名称" prop="skillName">
          <el-input
            v-model="skillForm.skillName"
            maxlength="100"
            show-word-limit
            clearable
            placeholder="请输入技能名称"
          />
        </el-form-item>
        <el-form-item label="技能类型" prop="skillLevelType">
          <el-radio-group v-model="skillForm.skillLevelType" @change="handleSkillLevelTypeChange">
            <el-radio-button :value="1">主技能</el-radio-button>
            <el-radio-button :value="2">子技能</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="技能描述" prop="skillDescription">
          <el-input
            v-model="skillForm.skillDescription"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            maxlength="255"
            show-word-limit
            resize="none"
            placeholder="请简要说明这个技能的用途"
          />
        </el-form-item>
        <SkillMcpBinding ref="skillMcpRef" :open="skillDialogVisible" :skill-id="editingSkillId || undefined" :skill-type="2" @ready="skillMcpReady = $event" />
        <el-form-item label="规则内容" prop="ruleContent">
          <el-input
            v-model="skillForm.ruleContent"
            type="textarea"
            :autosize="{ minRows: 8, maxRows: 16 }"
            maxlength="16000"
            show-word-limit
            resize="vertical"
            placeholder="请输入该技能需要遵循的完整规则"
          />
        </el-form-item>
        <el-form-item label="关联数据表" prop="tableIds">
          <div class="skill-table-summary">
            <div class="skill-table-summary-header">
              <el-button
                class="select-table-button"
                :icon="Plus"
                :disabled="!skillTableOptions.length"
                @click="openSkillTableSelector"
              >
                选择数据表
              </el-button>
              <span class="selected-table-count">已选择 {{ selectedSkillTables.length }} 张</span>
            </div>
            <div v-if="selectedSkillTables.length" class="selected-skill-tables" aria-label="已选择的数据表">
              <el-tag
                v-for="table in selectedSkillTables"
                :key="table.tableManagementId!"
                closable
                effect="plain"
                @close="removeSelectedSkillTable(table.tableManagementId!)"
              >
                <span class="notranslate" translate="no">{{ table.physicalTableName }}</span>
                <span v-if="table.tableCnName">（{{ table.tableCnName }}）</span>
              </el-tag>
            </div>
            <el-text v-else type="info">
              {{ skillTableOptions.length ? '暂未选择数据表（可选）' : '当前没有可选数据表，可不关联直接创建' }}
            </el-text>
          </div>
        </el-form-item>
        <el-form-item v-if="skillForm.skillLevelType === 1" label="关联子技能" prop="subSkillIds">
          <div class="skill-table-summary">
            <div class="skill-table-summary-header">
              <el-button :icon="Plus" @click="openSubSkillSelector">选择子技能</el-button>
              <span class="selected-table-count">已选择 {{ skillForm.subSkillIds.length }} 个</span>
            </div>
            <div v-if="selectedSubSkills.length" class="selected-skill-tables" aria-label="已选择的子技能">
              <el-tag
                v-for="skill in selectedSubSkills"
                :key="skill.id"
                closable
                effect="plain"
                @close="removeSelectedSubSkill(skill.id)"
              >
                {{ skill.skillName }}
              </el-tag>
            </div>
            <el-text v-else type="info">可选择当前技能组中已启用的子技能</el-text>
          </div>
        </el-form-item>
        <el-form-item label="启用状态" prop="enabled">
          <el-switch
            v-model="skillForm.enabled"
            :active-value="1"
            :inactive-value="0"
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="skillSubmitting" @click="skillDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="skillSubmitting" :disabled="!skillMcpReady" @click="submitProjectSkill">
          {{ skillDialogMode === 'create' ? '确定新增' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="skillTableSelectorVisible"
      title="选择关联数据表"
      width="min(1180px, calc(100% - 32px))"
      append-to-body
      destroy-on-close
      @closed="resetSkillTableSelector"
    >
      <el-input
        v-model="skillTableSearchKeyword"
        class="skill-table-search"
        :prefix-icon="Search"
        clearable
        aria-label="搜索关联数据表"
        placeholder="搜索英文表名或中文表名"
      />
      <div class="skill-table-option-list">
        <el-table :data="filteredSkillTableOptions" row-key="tableManagementId" max-height="420" size="small">
          <el-table-column width="48" align="center">
            <template #header>
              <el-checkbox
                :model-value="allFilteredSkillTablesSelected"
                :indeterminate="someFilteredSkillTablesSelected"
                :disabled="!filteredSkillTableOptions.length"
                aria-label="全选当前搜索结果"
                @change="toggleAllFilteredSkillTables"
              />
            </template>
            <template #default="scope">
              <el-checkbox
                :model-value="skillTableSelectionDraft.includes(scope.row.tableManagementId!)"
                :aria-label="`选择数据表 ${scope.row.physicalTableName}`"
                @change="toggleSkillTableSelection(scope.row.tableManagementId!, $event)"
              />
            </template>
          </el-table-column>
          <el-table-column label="物理表" min-width="260">
            <template #default="scope">
              <div class="physical-table-cell">
                <div class="physical-table-name notranslate" translate="no">{{ scope.row.physicalTableName }}</div>
                <div class="schema-name notranslate" translate="no">{{ scope.row.tableSchema || libraryName || '—' }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="tableCnName" label="中文表名" min-width="180">
            <template #default="scope">{{ scope.row.tableCnName || '—' }}</template>
          </el-table-column>
          <el-table-column prop="tableComment" label="用途说明/备注" min-width="320" show-overflow-tooltip>
            <template #default="scope">{{ scope.row.tableComment || scope.row.databaseComment || '—' }}</template>
          </el-table-column>
          <el-table-column label="字段" width="110" align="center">
            <template #default="scope">
              <el-button link type="primary" @click="openSkillTableColumns(scope.row)">
                {{ scope.row.columns.length }} 个字段
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty
              :description="skillTableSearchKeyword.trim() ? '没有符合条件的数据表' : '所属一级项目组暂无已导入数据表'"
              :image-size="80"
            />
          </template>
        </el-table>
      </div>

      <section class="selector-selected-section" aria-label="本次已选择的数据表">
        <div class="selector-selected-title">已选择的数据表（{{ skillTableSelectionDraft.length }}）</div>
        <div v-if="selectedSkillTableDraftTables.length" class="selected-skill-tables">
          <el-tag
            v-for="table in selectedSkillTableDraftTables"
            :key="table.tableManagementId!"
            closable
            effect="plain"
            @close="toggleSkillTableSelection(table.tableManagementId!, false)"
          >
            <span class="notranslate" translate="no">{{ table.physicalTableName }}</span>
            <span v-if="table.tableCnName">（{{ table.tableCnName }}）</span>
          </el-tag>
        </div>
        <el-text v-else type="info">暂未选择数据表</el-text>
      </section>
      <template #footer>
        <el-button @click="skillTableSelectorVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmSkillTableSelection">
          确定选择（{{ skillTableSelectionDraft.length }}）
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="subSkillSelectorVisible"
      title="选择子技能"
      width="min(820px, calc(100% - 32px))"
      append-to-body
      destroy-on-close
      @closed="resetSubSkillSelector"
    >
      <el-input
        v-model="subSkillSearchKeyword"
        class="skill-table-search"
        :prefix-icon="Search"
        clearable
        aria-label="搜索子技能"
        placeholder="搜索子技能名称或描述"
      />
      <div class="skill-table-option-list">
        <el-table v-loading="subSkillOptionsLoading" :data="filteredSubSkillOptions" row-key="id" max-height="420" size="small">
          <el-table-column width="48" align="center">
            <template #header>
              <el-checkbox
                :model-value="allFilteredSubSkillsSelected"
                :indeterminate="someFilteredSubSkillsSelected"
                :disabled="!filteredSubSkillOptions.length"
                aria-label="全选当前搜索结果"
                @change="toggleAllFilteredSubSkills"
              />
            </template>
            <template #default="scope">
              <el-checkbox
                :model-value="subSkillSelectionDraft.includes(scope.row.id)"
                :aria-label="`选择子技能 ${scope.row.skillName}`"
                @change="toggleSubSkillSelection(scope.row.id, $event)"
              />
            </template>
          </el-table-column>
          <el-table-column prop="skillName" label="子技能名称" min-width="220" />
          <el-table-column label="技能描述" min-width="320" show-overflow-tooltip>
            <template #default="scope">{{ scope.row.skillDescription || '—' }}</template>
          </el-table-column>
          <template #empty>
            <el-empty
              :description="subSkillSearchKeyword.trim() ? '没有符合条件的子技能' : '当前技能组暂无已启用的子技能'"
              :image-size="80"
            />
          </template>
        </el-table>
      </div>
      <section class="selector-selected-section" aria-label="本次已选择的子技能">
        <div class="selector-selected-title">已选择子技能（{{ subSkillSelectionDraft.length }}）</div>
        <div v-if="selectedSubSkillDraftItems.length" class="selected-skill-tables">
          <el-tag
            v-for="skill in selectedSubSkillDraftItems"
            :key="skill.id"
            closable
            effect="plain"
            @close="toggleSubSkillSelection(skill.id, false)"
          >
            {{ skill.skillName }}
          </el-tag>
        </div>
        <el-text v-else type="info">暂未选择子技能</el-text>
      </section>
      <template #footer>
        <el-button @click="subSkillSelectorVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmSubSkillSelection">
          确定选择（{{ subSkillSelectionDraft.length }}）
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="skillTableColumnsVisible"
      :title="`${skillTableColumnSource?.physicalTableName || ''} 字段信息`"
      width="min(940px, calc(100% - 32px))"
      append-to-body
      destroy-on-close
      @closed="skillTableColumnSource = null"
    >
      <el-table :data="skillTableColumnSource?.columns || []" max-height="500" size="small">
        <el-table-column prop="columnName" label="字段名" min-width="180" />
        <el-table-column prop="columnType" label="字段类型" min-width="150" />
        <el-table-column label="字段注释" min-width="230">
          <template #default="scope">{{ scope.row.columnComment || '—' }}</template>
        </el-table-column>
        <el-table-column label="字段备注" min-width="260">
          <template #default="scope">{{ scope.row.remark || '—' }}</template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无字段信息" :image-size="80" />
        </template>
      </el-table>
      <template #footer>
        <el-button type="primary" @click="skillTableColumnsVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="columnsDialogVisible"
      :title="`${activeTable?.physicalTableName || ''} 字段信息`"
      width="min(1080px, calc(100% - 32px))"
      :close-on-click-modal="false"
      @closed="resetColumnRemarkEditor"
    >
      <div class="column-toolbar">
        <el-input
          v-model="columnSearchKeyword"
          class="column-search"
          :prefix-icon="Search"
          clearable
          aria-label="搜索字段"
          placeholder="搜索字段名、类型、注释或备注"
        />
        <div class="column-toolbar-actions">
          <span class="column-match-count">
            <template v-if="columnSearchKeyword.trim()">
              已显示 {{ filteredActiveTableColumns.length }} / {{ activeTable?.columns.length || 0 }} 个字段
            </template>
            <template v-else>共 {{ activeTable?.columns.length || 0 }} 个字段</template>
          </span>
          <el-button
            type="danger"
            plain
            :icon="Delete"
            :loading="batchDeletingColumns"
            :disabled="!canEditAssociations || !selectedColumnNames.length || Boolean(deletingColumnName) || singleTableSchemaSyncing || savingColumnRemarks"
            @click="confirmBatchDeleteColumns"
          >
            批量删除<span v-if="selectedColumnNames.length">（{{ selectedColumnNames.length }}）</span>
          </el-button>
        </div>
      </div>
      <el-table
        ref="columnTableRef"
        v-loading="Boolean(deletingColumnName) || batchDeletingColumns"
        :data="filteredActiveTableColumns"
        row-key="columnName"
        max-height="460"
        @selection-change="handleColumnSelectionChange"
      >
        <el-table-column type="selection" width="48" :selectable="canSelectTableColumn" />
        <el-table-column prop="columnName" label="字段名" min-width="180" />
        <el-table-column prop="columnType" label="字段类型" min-width="150" />
        <el-table-column prop="columnComment" label="字段注释" min-width="220">
          <template #default="scope">{{ scope.row.columnComment || '—' }}</template>
        </el-table-column>
        <el-table-column label="字段备注" min-width="300">
          <template #default="scope">
            <el-input
              v-model="columnRemarkDraft[scope.row.columnName]"
              :aria-label="`${scope.row.columnName} 字段备注`"
              maxlength="500"
              clearable
              placeholder="请输入字段备注"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="scope">
            <el-button
              link
              type="danger"
              :icon="Delete"
              :loading="deletingColumnName === scope.row.columnName"
              :disabled="!canEditAssociations || Boolean(deletingColumnName) || batchDeletingColumns || singleTableSchemaSyncing || savingColumnRemarks"
              @click="confirmDeleteColumn(scope.row.columnName)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty
            :description="columnSearchKeyword.trim() ? '没有符合条件的字段' : '暂无字段信息'"
            :image-size="80"
          />
        </template>
      </el-table>
      <template #footer>
        <el-button
          :icon="Refresh"
          :loading="singleTableSchemaSyncing"
          :disabled="!canEditAssociations || !activeTable?.tableManagementId || savingColumnRemarks || Boolean(deletingColumnName) || batchDeletingColumns"
          @click="syncCurrentTableSchema"
        >
          同步当前表
        </el-button>
        <el-button :disabled="savingColumnRemarks || singleTableSchemaSyncing || Boolean(deletingColumnName) || batchDeletingColumns" @click="columnsDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="savingColumnRemarks"
          :disabled="!activeTable?.tableManagementId || !activeTable.columns.length || singleTableSchemaSyncing || Boolean(deletingColumnName) || batchDeletingColumns"
          @click="saveColumnRemarks"
        >
          保存备注
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import SkillMcpBinding from '@/views/mcp/SkillMcpBinding.vue'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Connection, Delete, Edit, Plus, Refresh, Search, Upload } from '@element-plus/icons-vue'
import { getSandboxOptions, type SandboxOption } from '@/api/system'
import {
  createProjectGroup,
  createProjectGroupSkill,
  createProjectGroupTableRelation,
  createProjectGroupTableRelations,
  deleteProjectGroupTableColumns,
  deleteProjectGroupSkill,
  deleteProjectGroupSkills,
  deleteProjectGroupTableRelation,
  deleteProjectGroupTableRelations,
  getChildProjectGroupPage,
  getProjectDatabaseOptions,
  getProjectGroupList,
  getProjectGroupImportTableOptions,
  getProjectGroupSkills,
  getProjectGroupSubSkillOptions,
  getProjectGroupTablePage,
  getProjectGroupTableRelations,
  getProjectGroupTableOptions,
  generateProjectGroupTableRelationSuggestions,
  deleteProjectGroup,
  saveProjectGroupTableAssociations,
  saveProjectGroupTableColumnRemarks,
  syncProjectGroupTableSchema,
  syncProjectGroupTableSchemas,
  updateProjectGroup,
  updateProjectGroupSkill,
  updateProjectGroupTableRelation,
  type DatabaseOption,
  type PhysicalTableColumn,
  type ProjectGroup,
  type ProjectGroupSkill,
  type ProjectGroupSubSkillOption,
  type ProjectGroupTableRelation,
  type ProjectGroupTableOption,
  type TableRelationSuggestion,
  type TableSchemaSyncResult
} from '@/api/project'

interface ProjectGroupForm {
  sandboxConfigId: number | null
  groupName: string
  sortOrder: number
  enabled: 0 | 1
}

interface TableRelationForm {
  sourceTableId: number | null
  sourceColumn: string
  targetTableId: number | null
  targetColumn: string
  relationContent: string
}

interface EditableTableRelationSuggestion extends Omit<TableRelationSuggestion, 'sourceTableId' | 'targetTableId'> {
  sourceTableId: number | null
  targetTableId: number | null
}

interface ProjectSkillForm {
  skillName: string
  skillDescription: string
  skillLevelType: 1 | 2
  ruleContent: string
  tableIds: number[]
  subSkillIds: number[]
  enabled: 0 | 1
}

const route = useRoute()
const router = useRouter()
const PAGE_SIZE = 5
const groupFormRef = ref<FormInstance>()
const relationFormRef = ref<FormInstance>()
const skillFormRef = ref<FormInstance>()
const loading = ref(false)
const saving = ref(false)
const relationSubmitting = ref(false)
const relationListLoading = ref(false)
const schemaSyncing = ref(false)
const singleTableSchemaSyncing = ref(false)
const savingColumnRemarks = ref(false)
const deletingRelationId = ref<number | null>(null)
const selectedRelationIds = ref<number[]>([])
const batchDeletingRelations = ref(false)
const deletingTableName = ref('')
const selectedImportedTableNames = ref<string[]>([])
const batchDeletingImportedTables = ref(false)
const submittingGroup = ref(false)
const skillSubmitting = ref(false)
const databaseLoading = ref(false)
const importTablesLoading = ref(false)
const importLoadError = ref('')
const errorMessage = ref('')
const projectGroup = ref<ProjectGroup | null>(null)
const sandboxOptions = ref<SandboxOption[]>([])
const sandboxSearch = ref('')
const filterSandboxes = (query: string) => { sandboxSearch.value = query.trim().toLowerCase() }
const filteredSandboxOptions = computed(() => sandboxOptions.value.filter(item => `${item.name || ''} ${item.url}`.toLowerCase().includes(sandboxSearch.value)))
const sandboxLabel = (id?: number | null) => {
  const item = sandboxOptions.value.find(option => option.id === id)
  return item ? item.name || item.url : id ? '已绑定沙箱（不可用）' : '待选择沙箱'
}
const sandboxLoading = ref(false)
const sandboxError = ref('')
const loadSandboxOptions = async () => {
  sandboxLoading.value = true
  sandboxError.value = ''
  try {
    const response = await getSandboxOptions()
    if (!response.success) throw new Error(response.message || '沙箱加载失败')
    sandboxOptions.value = response.data.list
  } catch (error) {
    sandboxOptions.value = []
    sandboxError.value = error instanceof Error ? error.message : '沙箱加载失败'
  } finally { sandboxLoading.value = false }
}
const libraryOwnerProjectGroupId = ref<number | null>(null)
const libraryName = ref<string | null>(null)
const activeManagementTab = ref<'tables' | 'skills'>('tables')
// 项目组页面暂时不展示技能组。页签和层级先隐藏，原有技能组代码与数据保留。
const showProjectSkillGroups = false
const tableOptions = ref<ProjectGroupTableOption[]>([])
const tableSearchKeyword = ref('')
const tablePageList = ref<ProjectGroupTableOption[]>([])
const tablePageLoading = ref(false)
const tablePageError = ref('')
const tablePageNo = ref(1)
const tablePageSize = ref(PAGE_SIZE)
const tableTotal = ref(0)
let tablePageRequestSequence = 0
let detailRequestSequence = 0
const tableStructureVersion = ref(0)
const databaseOptions = ref<DatabaseOption[]>([])
const importTableOptions = ref<ProjectGroupTableOption[]>([])
const importSelectedTableNames = ref<Set<string>>(new Set())
const importLibraryName = ref('')
const importTableKeyword = ref('')
const importDialogVisible = ref(false)
const relationDialogVisible = ref(false)
const relationFormDialogVisible = ref(false)
const relationDialogMode = ref<'create' | 'edit'>('create')
const relationCreateMode = ref<'manual' | 'auto'>('manual')
const editingRelationId = ref<number | null>(null)
const autoRelationSuggestions = ref<EditableTableRelationSuggestion[]>([])
const selectedAutoRelations = ref<EditableTableRelationSuggestion[]>([])
const autoRelationTableRef = ref()
const autoRelationGenerating = ref(false)
const autoRelationSubmitting = ref(false)
const relationList = ref<ProjectGroupTableRelation[]>([])
const relationListError = ref('')
const schemaSyncDialogVisible = ref(false)
const schemaSyncResult = ref<TableSchemaSyncResult | null>(null)
const groupDialogVisible = ref(false)
const groupDialogMode = ref<'editCurrent' | 'createSkillGroup' | 'editSkillGroup'>('editCurrent')
const editingProjectGroupId = ref<number | null>(null)
const columnsDialogVisible = ref(false)
const activeTable = ref<ProjectGroupTableOption | null>(null)
const columnRemarkDraft = ref<Record<string, string>>({})
const columnSearchKeyword = ref('')
const selectedColumnNames = ref<string[]>([])
const deletingColumnName = ref('')
const batchDeletingColumns = ref(false)
const columnTableRef = ref()
const skillList = ref<ProjectGroupSkill[]>([])
const skillListLoading = ref(false)
const skillListError = ref('')
const skillKeyword = ref('')
const skillEnabledFilter = ref<'' | 0 | 1>('')
const skillLevelTypeFilter = ref<'' | 1 | 2>('')
const skillPageNo = ref(1)
const skillPageSize = ref(PAGE_SIZE)
const skillTotal = ref(0)
let skillRequestSequence = 0
const skillDialogVisible = ref(false)
const skillDialogMode = ref<'create' | 'edit'>('create')
const editingSkillId = ref<number | null>(null)
const deletingSkillId = ref<number | null>(null)
const skillTableSelectorVisible = ref(false)
const skillTableSearchKeyword = ref('')
const skillTableSelectionDraft = ref<number[]>([])
const skillTableColumnsVisible = ref(false)
const skillTableColumnSource = ref<ProjectGroupTableOption | null>(null)
const subSkillSelectorVisible = ref(false)
const subSkillSearchKeyword = ref('')
const subSkillSelectionDraft = ref<number[]>([])
const subSkillOptions = ref<ProjectGroupSubSkillOption[]>([])
const subSkillOptionsLoading = ref(false)
const selectedSkillIds = ref<number[]>([])
const batchDeletingSkills = ref(false)
const skillGroupList = ref<ProjectGroup[]>([])
const skillGroupListLoading = ref(false)
const skillGroupListError = ref('')
const skillGroupKeyword = ref('')
const skillGroupPageNo = ref(1)
const skillGroupPageSize = ref(PAGE_SIZE)
const skillGroupTotal = ref(0)
const deletingSkillGroupId = ref<number | null>(null)
let skillGroupRequestSequence = 0

const createDefaultGroupForm = (): ProjectGroupForm => ({ groupName: '', sortOrder: 0, enabled: 1, sandboxConfigId: null })
const groupForm = reactive<ProjectGroupForm>(createDefaultGroupForm())
const groupRules: FormRules<ProjectGroupForm> = {
  groupName: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { min: 1, max: 100, message: '名称不能超过 100 个字符', trigger: 'blur' }
  ]
}
const createDefaultSkillForm = (): ProjectSkillForm => ({
  skillName: '',
  skillDescription: '',
  skillLevelType: 1,
  ruleContent: '',
  tableIds: [],
  subSkillIds: [],
  enabled: 1
})
const skillForm = reactive<ProjectSkillForm>(createDefaultSkillForm())
const skillMcpRef = ref<InstanceType<typeof SkillMcpBinding>>(), skillMcpReady = ref(false)
const skillRules: FormRules<ProjectSkillForm> = {
  skillName: [
    { required: true, message: '请输入技能名称', trigger: 'blur' },
    { max: 100, message: '技能名称不能超过 100 个字符', trigger: 'blur' }
  ],
  skillDescription: [
    { max: 255, message: '技能描述不能超过 255 个字符', trigger: 'blur' }
  ],
  skillLevelType: [
    { required: true, message: '请选择技能类型', trigger: 'change' }
  ],
  ruleContent: [
    { required: true, message: '请输入规则内容', trigger: 'blur' },
    { max: 16000, message: '规则内容不能超过 16000 个字符', trigger: 'blur' }
  ]
}
const createDefaultRelationForm = (): TableRelationForm => ({
  sourceTableId: null,
  sourceColumn: '',
  targetTableId: null,
  targetColumn: '',
  relationContent: ''
})
const relationForm = reactive<TableRelationForm>(createDefaultRelationForm())
const relationRules: FormRules<TableRelationForm> = {
  sourceTableId: [{ required: true, message: '请选择源表', trigger: 'change' }],
  sourceColumn: [{ required: true, message: '请选择源字段', trigger: 'change' }],
  targetTableId: [{ required: true, message: '请选择目标表', trigger: 'change' }],
  targetColumn: [{ required: true, message: '请选择目标字段', trigger: 'change' }],
  relationContent: [
    { required: true, message: '请输入关系内容', trigger: 'blur' },
    { max: 200, message: '关系内容不能超过 200 个字符', trigger: 'blur' }
  ]
}

const currentProjectGroupId = computed(() => Number(route.params.groupId))
const isRootProjectGroup = computed(() => projectGroup.value?.level === 0 && projectGroup.value.parentId === null)
const rootProjectGroupId = computed(() => {
  if (!projectGroup.value) return null
  return isRootProjectGroup.value ? projectGroup.value.id : projectGroup.value.parentId
})
const canEditAssociations = computed(() => projectGroup.value?.enabled === 1)
const groupDialogTitle = computed(() => {
  if (groupDialogMode.value === 'createSkillGroup') return '新增技能组'
  if (groupDialogMode.value === 'editSkillGroup') return '编辑技能组'
  return '编辑当前项目组'
})
const canImportTables = computed(() => canEditAssociations.value && isRootProjectGroup.value)
const skillTableOptions = computed(() => tableOptions.value.filter((table) => table.tableManagementId !== null))
const selectedSkillTables = computed(() => {
  const selectedIds = new Set(skillForm.tableIds)
  return skillTableOptions.value.filter((table) => selectedIds.has(table.tableManagementId!))
})
const selectedSkillTableDraftTables = computed(() => {
  const selectedIds = new Set(skillTableSelectionDraft.value)
  return skillTableOptions.value.filter((table) => selectedIds.has(table.tableManagementId!))
})
const selectedSubSkills = computed<ProjectGroupSubSkillOption[]>(() =>
  skillForm.subSkillIds.map((skillId) => (
    subSkillOptions.value.find((skill) => skill.id === skillId)
    || { id: skillId, skillName: `子技能 #${skillId}`, skillDescription: null, enabled: 1 }
  ))
)
const filteredSubSkillOptions = computed(() => {
  const keyword = subSkillSearchKeyword.value.trim().toLowerCase()
  if (!keyword) return subSkillOptions.value
  return subSkillOptions.value.filter((skill) => [
    skill.skillName,
    skill.skillDescription
  ].some((value) => String(value || '').toLowerCase().includes(keyword)))
})
const selectedSubSkillDraftItems = computed(() => {
  const selectedIds = new Set(subSkillSelectionDraft.value)
  return subSkillOptions.value.filter((skill) => selectedIds.has(skill.id))
})
const allFilteredSubSkillsSelected = computed(() => (
  filteredSubSkillOptions.value.length > 0
  && filteredSubSkillOptions.value.every((skill) => subSkillSelectionDraft.value.includes(skill.id))
))
const someFilteredSubSkillsSelected = computed(() => {
  const selectedCount = filteredSubSkillOptions.value.filter(
    (skill) => subSkillSelectionDraft.value.includes(skill.id)
  ).length
  return selectedCount > 0 && selectedCount < filteredSubSkillOptions.value.length
})
const filteredSkillTableOptions = computed(() => {
  const keyword = skillTableSearchKeyword.value.trim().toLowerCase()
  if (!keyword) return skillTableOptions.value
  return skillTableOptions.value.filter((table) => [
    table.physicalTableName,
    table.tableName,
    table.tableCnName,
    table.tableComment
  ].some((value) => String(value || '').toLowerCase().includes(keyword)))
})
const allFilteredSkillTablesSelected = computed(() => (
  filteredSkillTableOptions.value.length > 0
  && filteredSkillTableOptions.value.every((table) => skillTableSelectionDraft.value.includes(table.tableManagementId!))
))
const someFilteredSkillTablesSelected = computed(() => {
  const selectedCount = filteredSkillTableOptions.value.filter(
    (table) => skillTableSelectionDraft.value.includes(table.tableManagementId!)
  ).length
  return selectedCount > 0 && selectedCount < filteredSkillTableOptions.value.length
})
const canCreateSkillGroup = computed(() => canEditAssociations.value && isRootProjectGroup.value)
const canCreateConcreteSkill = computed(() => canEditAssociations.value && !isRootProjectGroup.value)
const relationTableOptions = computed(() =>
  tableOptions.value.filter((table) => table.tableManagementId !== null)
)
const canCreateTableRelation = computed(() =>
  canEditAssociations.value && relationTableOptions.value.length >= 2
)
const canSyncTableSchemas = computed(() =>
  canEditAssociations.value && Boolean(libraryName.value) && relationTableOptions.value.length > 0
)
const sourceColumnOptions = computed(() =>
  relationTableOptions.value.find((table) => table.tableManagementId === relationForm.sourceTableId)?.columns || []
)
const targetColumnOptions = computed(() =>
  relationTableOptions.value.find((table) => table.tableManagementId === relationForm.targetTableId)?.columns || []
)
const databaseSelectionLocked = computed(() => Boolean(libraryName.value))
const importSelectedCount = computed(() => importSelectedTableNames.value.size)
const filteredImportTableOptions = computed(() => {
  const keyword = importTableKeyword.value.trim().toLowerCase()
  if (!keyword) return importTableOptions.value
  return importTableOptions.value.filter((table) => table.physicalTableName.toLowerCase().includes(keyword))
})
const filteredActiveTableColumns = computed(() => {
  const columns = activeTable.value?.columns || []
  const keyword = columnSearchKeyword.value.trim().toLowerCase()
  if (!keyword) return columns
  return columns.filter((column) => [
    column.columnName,
    column.columnType,
    column.columnComment,
    columnRemarkDraft.value[column.columnName] || column.remark
  ].some((value) => String(value || '').toLowerCase().includes(keyword)))
})

const getErrorMessage = (error: unknown, fallback: string) =>
  error instanceof Error && error.message ? error.message : fallback

const formatColumnNames = (columns: string[]) => columns.length ? columns.join('、') : '—'

const suggestTableCnName = (table: ProjectGroupTableOption) => {
  const suggested = table.databaseComment.split(/[：:]/, 1)[0]?.trim()
  return suggested || table.physicalTableName
}

const toAssociationSaveItem = (table: ProjectGroupTableOption) => ({
  tableName: table.tableName,
  tableCnName: table.tableCnName.trim(),
  tableComment: table.tableComment.trim()
})

const loadProjectGroupTablePage = async () => {
  const requestedProjectGroupId = currentProjectGroupId.value
  if (!isRootProjectGroup.value || !Number.isInteger(requestedProjectGroupId) || requestedProjectGroupId <= 0) return

  selectedImportedTableNames.value = []
  const requestSequence = ++tablePageRequestSequence
  const requestedPageNo = tablePageNo.value
  const requestedPageSize = tablePageSize.value
  tablePageLoading.value = true
  tablePageError.value = ''
  try {
    const response = await getProjectGroupTablePage(requestedProjectGroupId, {
      keyword: tableSearchKeyword.value.trim() || undefined,
      pageNo: requestedPageNo,
      pageSize: requestedPageSize
    })
    if (requestSequence !== tablePageRequestSequence || requestedProjectGroupId !== currentProjectGroupId.value) return
    if (!response.success) {
      tablePageError.value = response.message || '数据表加载失败'
      return
    }

    const lastPage = Math.max(1, Math.ceil(response.data.total / requestedPageSize))
    if (requestedPageNo > lastPage) {
      tablePageNo.value = lastPage
      await loadProjectGroupTablePage()
      return
    }
    tablePageList.value = response.data.list.map((table) => ({ ...table }))
    tableTotal.value = response.data.total
  } catch (error: unknown) {
    if (requestSequence === tablePageRequestSequence && requestedProjectGroupId === currentProjectGroupId.value) {
      tablePageError.value = getErrorMessage(error, '数据表加载失败，请检查后端服务')
    }
  } finally {
    if (requestSequence === tablePageRequestSequence) tablePageLoading.value = false
  }
}

const handleTablePageChange = (pageNo: number) => {
  selectedImportedTableNames.value = []
  tablePageNo.value = pageNo
  loadProjectGroupTablePage()
}

const canSelectImportedTable = () => (
  canEditAssociations.value
  && !deletingTableName.value
  && !batchDeletingImportedTables.value
)

const handleImportedTableSelectionChange = (selection: ProjectGroupTableOption[]) => {
  selectedImportedTableNames.value = selection.map((table) => table.tableName)
}

const fetchDetail = async () => {
  const requestId = ++detailRequestSequence
  const stale = () => requestId !== detailRequestSequence
  if (!Number.isInteger(currentProjectGroupId.value) || currentProjectGroupId.value <= 0) {
    projectGroup.value = null
    libraryOwnerProjectGroupId.value = null
    libraryName.value = null
    tableOptions.value = []
    tablePageList.value = []
    tableTotal.value = 0
    errorMessage.value = '项目组编号无效'
    return
  }

  loading.value = true
  errorMessage.value = ''
  try {
    const groupResponse = await getProjectGroupList()
    if (stale()) return
    if (!groupResponse.success) {
      errorMessage.value = groupResponse.message || '项目组加载失败'
      return
    }
    const currentGroup = groupResponse.data.list.find((group) => group.id === currentProjectGroupId.value)
    if (!currentGroup || ![0, 1].includes(currentGroup.level)) {
      errorMessage.value = '项目组不存在或不属于当前两级结构'
      projectGroup.value = null
      return
    }
    if (!showProjectSkillGroups && currentGroup.level === 1) {
      await router.replace(currentGroup.parentId ? `/project/group/${currentGroup.parentId}` : '/project/group')
      return
    }
    if (stale()) return
    projectGroup.value = currentGroup
    if (currentGroup.level === 0) void loadSandboxOptions()
    const managementTabChanged = showProjectSkillGroups && currentGroup.level === 1 && activeManagementTab.value !== 'skills'
    if (managementTabChanged) activeManagementTab.value = 'skills'

    const requestedRootProjectGroupId = currentGroup.level === 0 ? currentGroup.id : currentGroup.parentId
    if (!requestedRootProjectGroupId) {
      errorMessage.value = '当前技能组缺少所属一级项目组'
      return
    }

    tableOptions.value = []
    libraryOwnerProjectGroupId.value = null
    libraryName.value = null
    if (currentGroup.enabled === 1) {
      const tableResponse = await getProjectGroupTableOptions(requestedRootProjectGroupId)
      if (stale()) return
      if (!tableResponse.success) {
        errorMessage.value = tableResponse.message || '项目组数据表加载失败'
        return
      }
      libraryOwnerProjectGroupId.value = tableResponse.data.libraryOwnerProjectGroupId
      libraryName.value = tableResponse.data.libraryName
      tableOptions.value = tableResponse.data.tables.map((table) => ({ ...table }))
    }
    tableStructureVersion.value += 1
    if (activeManagementTab.value === 'tables') await loadProjectGroupTablePage()
    else if (isRootProjectGroup.value) await loadSkillGroups()
    else if (!managementTabChanged) await loadProjectSkills()
    if (stale()) return
  } catch (error: unknown) {
    if (!stale()) errorMessage.value = getErrorMessage(error, '项目组加载失败，请检查后端服务')
  } finally {
    if (!stale()) loading.value = false
  }
}

const resetImportDialog = () => {
  importLoadError.value = ''
  importLibraryName.value = ''
  importTableKeyword.value = ''
  importTableOptions.value = []
  importSelectedTableNames.value = new Set()
  databaseOptions.value = []
}

const loadDatabaseOptions = async () => {
  databaseLoading.value = true
  try {
    const response = await getProjectDatabaseOptions(currentProjectGroupId.value)
    if (!response.success) {
      importLoadError.value = response.message || '数据库列表加载失败'
      return false
    }
    databaseOptions.value = response.data.list
    return true
  } catch (error: unknown) {
    importLoadError.value = getErrorMessage(error, '数据库列表加载失败')
    return false
  } finally {
    databaseLoading.value = false
  }
}

const loadImportTableOptions = async () => {
  importLoadError.value = ''
  importTableOptions.value = []
  importSelectedTableNames.value = new Set()
  if (!importLibraryName.value) return

  importTablesLoading.value = true
  try {
    const response = await getProjectGroupImportTableOptions(currentProjectGroupId.value, importLibraryName.value)
    if (!response.success) {
      importLoadError.value = response.message || '数据表列表加载失败'
      return
    }
    importTableOptions.value = response.data.tables
      .filter((table) => !table.associated)
      .map((table) => ({
        ...table,
        tableCnName: table.tableCnName.trim() || suggestTableCnName(table),
        tableComment: table.tableComment.trim() || table.databaseComment || ''
      }))
  } catch (error: unknown) {
    importLoadError.value = getErrorMessage(error, '数据表列表加载失败')
  } finally {
    importTablesLoading.value = false
  }
}

const openImportDialog = async () => {
  if (!canImportTables.value) return
  resetImportDialog()
  importLibraryName.value = libraryName.value || ''
  importDialogVisible.value = true
  await retryImportData()
}

const retryImportData = async () => {
  importLoadError.value = ''
  if (!await loadDatabaseOptions()) return
  if (!importLibraryName.value && databaseOptions.value.length === 1) importLibraryName.value = databaseOptions.value[0].libraryName
  if (importLibraryName.value) await loadImportTableOptions()
}

const handleLibraryChange = async () => {
  importTableKeyword.value = ''
  await loadImportTableOptions()
}
const canSelectImportTable = () => canEditAssociations.value
const isImportTableSelected = (table: ProjectGroupTableOption) => importSelectedTableNames.value.has(table.tableName)

const handleImportSelectionChange = (selection: ProjectGroupTableOption[]) => {
  selection.forEach((table) => {
    if (!table.tableCnName.trim()) table.tableCnName = suggestTableCnName(table)
    if (!table.tableComment.trim()) table.tableComment = table.databaseComment || ''
  })
  const visibleTableNames = new Set(filteredImportTableOptions.value.map((table) => table.tableName))
  const selectedTableNames = new Set(importSelectedTableNames.value)
  visibleTableNames.forEach((tableName) => selectedTableNames.delete(tableName))
  selection.forEach((table) => selectedTableNames.add(table.tableName))
  importSelectedTableNames.value = selectedTableNames
}

const saveAssociations = async () => {
  if (!importLibraryName.value) {
    ElMessage.warning('请先选择数据库')
    return
  }
  const selectedTables = importTableOptions.value.filter(isImportTableSelected)
  if (selectedTables.some((table) => !table.tableCnName.trim())) {
    ElMessage.warning('请填写所有已勾选数据表的中文表名')
    return
  }
  if (!selectedTables.length) {
    ElMessage.warning('请至少选择一张要导入的数据表')
    return
  }

  const tablesToSave = [
    ...tableOptions.value.map(toAssociationSaveItem),
    ...selectedTables.map(toAssociationSaveItem)
  ]

  saving.value = true
  try {
    const response = await saveProjectGroupTableAssociations({
      projectGroupId: currentProjectGroupId.value,
      libraryName: importLibraryName.value,
      tables: tablesToSave
    })
    if (!response.success) {
      ElMessage.error(response.message || '数据表导入失败')
      return
    }
    ElMessage.success('数据表导入成功')
    libraryName.value = response.data.libraryName
    libraryOwnerProjectGroupId.value = response.data.libraryOwnerProjectGroupId
    importDialogVisible.value = false
    window.dispatchEvent(new Event('project-groups-changed'))
    await fetchDetail()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '数据表导入失败'))
  } finally {
    saving.value = false
  }
}

const syncTableSchemas = async () => {
  if (!canSyncTableSchemas.value || schemaSyncing.value) return

  schemaSyncing.value = true
  try {
    const response = await syncProjectGroupTableSchemas(currentProjectGroupId.value)
    if (!response.success) {
      ElMessage.warning(response.message || '表结构同步失败')
      return
    }
    schemaSyncResult.value = response.data
    tableOptions.value = response.data.tables.map((table) => ({ ...table }))
    tableStructureVersion.value += 1
    if (activeTable.value) {
      activeTable.value = tableOptions.value.find(
        (table) => table.tableName === activeTable.value?.tableName
      ) || null
      if (!activeTable.value) columnsDialogVisible.value = false
    }
    await fetchDetail()
    schemaSyncDialogVisible.value = true
    if (relationDialogVisible.value) await loadTableRelations()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '表结构同步失败，请检查后端服务'))
  } finally {
    schemaSyncing.value = false
  }
}

const resetRelationForm = () => {
  Object.assign(relationForm, createDefaultRelationForm())
  editingRelationId.value = null
  relationCreateMode.value = 'manual'
  autoRelationSuggestions.value = []
  selectedAutoRelations.value = []
  autoRelationGenerating.value = false
  relationFormRef.value?.clearValidate()
}

const resetRelationManager = () => {
  relationList.value = []
  relationListError.value = ''
  selectedRelationIds.value = []
  relationFormDialogVisible.value = false
  resetRelationForm()
}

const loadTableRelations = async () => {
  relationListLoading.value = true
  relationListError.value = ''
  selectedRelationIds.value = []
  try {
    const response = await getProjectGroupTableRelations(currentProjectGroupId.value)
    if (!response.success) {
      relationListError.value = response.message || '表关系列表加载失败'
      return
    }
    relationList.value = response.data.list
    selectedRelationIds.value = []
  } catch (error: unknown) {
    relationListError.value = getErrorMessage(error, '表关系列表加载失败，请检查后端服务')
  } finally {
    relationListLoading.value = false
  }
}

const openTableRelationDialog = async () => {
  if (!projectGroup.value) return
  relationDialogVisible.value = true
  await loadTableRelations()
}

const openCreateTableRelationDialog = () => {
  if (!canCreateTableRelation.value) {
    ElMessage.warning('请先导入至少两张数据表')
    return
  }
  resetRelationForm()
  relationDialogMode.value = 'create'
  relationFormDialogVisible.value = true
}

const canSelectTableRelation = (_relation: ProjectGroupTableRelation) =>
  canEditAssociations.value
  && deletingRelationId.value === null
  && !batchDeletingRelations.value

const handleRelationSelectionChange = (relations: ProjectGroupTableRelation[]) => {
  selectedRelationIds.value = relations.map((relation) => relation.id)
}

const openEditTableRelationDialog = (relation: ProjectGroupTableRelation) => {
  resetRelationForm()
  relationDialogMode.value = 'edit'
  relationCreateMode.value = 'manual'
  editingRelationId.value = relation.id
  Object.assign(relationForm, {
    sourceTableId: relation.sourceTableId,
    sourceColumn: relation.sourceColumn,
    targetTableId: relation.targetTableId,
    targetColumn: relation.targetColumn,
    relationContent: relation.relationContent
  })
  relationFormDialogVisible.value = true
}

const handleSourceTableChange = () => {
  relationForm.sourceColumn = ''
  if (relationForm.sourceTableId === relationForm.targetTableId) {
    relationForm.targetTableId = null
    relationForm.targetColumn = ''
  }
}

const handleTargetTableChange = () => {
  relationForm.targetColumn = ''
  if (relationForm.targetTableId === relationForm.sourceTableId) {
    relationForm.sourceTableId = null
    relationForm.sourceColumn = ''
  }
}

const relationColumns = (tableId: number | null) =>
  relationTableOptions.value.find((table) => table.tableManagementId === tableId)?.columns || []

const handleAutoSourceTableChange = (relation: EditableTableRelationSuggestion) => {
  relation.sourceColumn = ''
  if (relation.sourceTableId === relation.targetTableId) {
    relation.targetTableId = null
    relation.targetColumn = ''
  }
}

const handleAutoTargetTableChange = (relation: EditableTableRelationSuggestion) => {
  relation.targetColumn = ''
  if (relation.targetTableId === relation.sourceTableId) {
    relation.sourceTableId = null
    relation.sourceColumn = ''
  }
}

const generateAutoRelationSuggestions = async () => {
  autoRelationGenerating.value = true
  selectedAutoRelations.value = []
  try {
    const response = await generateProjectGroupTableRelationSuggestions(currentProjectGroupId.value)
    if (!response.success) {
      ElMessage.warning(response.message || 'AI关系推荐生成失败')
      return
    }
    autoRelationSuggestions.value = response.data.list.map((relation) => ({ ...relation }))
    await nextTick()
    autoRelationTableRef.value?.clearSelection()
    if (!autoRelationSuggestions.value.length) ElMessage.info('没有发现新的可推荐关系')
  } catch {
    autoRelationSuggestions.value = []
    selectedAutoRelations.value = []
  } finally {
    autoRelationGenerating.value = false
  }
}

const handleAutoRelationSelectionChange = (relations: EditableTableRelationSuggestion[]) => {
  selectedAutoRelations.value = relations
}

const validateAutoRelation = (relation: EditableTableRelationSuggestion, index: number) => {
  if (relation.sourceTableId === null || relation.targetTableId === null) return `第${index}条关系请选择源表和目标表`
  if (relation.sourceTableId === relation.targetTableId) return `第${index}条关系的源表和目标表不能相同`
  if (!relation.sourceColumn || !relationColumns(relation.sourceTableId).some((column) => column.columnName === relation.sourceColumn)) return `第${index}条关系请选择有效源字段`
  if (!relation.targetColumn || !relationColumns(relation.targetTableId).some((column) => column.columnName === relation.targetColumn)) return `第${index}条关系请选择有效目标字段`
  if (!relation.relationContent.trim()) return `第${index}条关系请填写关系内容`
  return ''
}

const submitAutoTableRelations = async () => {
  if (!selectedAutoRelations.value.length) {
    ElMessage.warning('请至少选择一条关系建议')
    return
  }
  for (const [index, relation] of selectedAutoRelations.value.entries()) {
    const error = validateAutoRelation(relation, index + 1)
    if (error) {
      ElMessage.warning(error)
      return
    }
  }
  const relationKeys = new Set<string>()
  for (const relation of selectedAutoRelations.value) {
    const endpoints = [
      `${relation.sourceTableId}:${relation.sourceColumn}`,
      `${relation.targetTableId}:${relation.targetColumn}`
    ].sort()
    const key = endpoints.join('|')
    if (relationKeys.has(key)) {
      ElMessage.warning('选中的关系中存在重复项，请修改或取消重复关系')
      return
    }
    relationKeys.add(key)
  }
  autoRelationSubmitting.value = true
  try {
    const response = await createProjectGroupTableRelations({
      projectGroupId: currentProjectGroupId.value,
      relations: selectedAutoRelations.value.map((relation) => ({
        sourceTableId: relation.sourceTableId!,
        sourceColumn: relation.sourceColumn,
        targetTableId: relation.targetTableId!,
        targetColumn: relation.targetColumn,
        relationContent: relation.relationContent.trim()
      }))
    })
    if (!response.success) {
      ElMessage.warning(response.message || '选中关系创建失败')
      return
    }
    ElMessage.success(`已创建 ${response.data.createdCount} 条表关系`)
    relationFormDialogVisible.value = false
    await loadTableRelations()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '选中关系创建失败，请检查后端服务'))
  } finally {
    autoRelationSubmitting.value = false
  }
}

const submitTableRelation = async () => {
  if (!relationFormRef.value) return
  const valid = await relationFormRef.value.validate().catch(() => false)
  if (!valid) return
  if (relationForm.sourceTableId === null || relationForm.targetTableId === null) return

  const duplicateRelation = relationList.value.some((relation) => {
    if (relation.id === editingRelationId.value) return false
    const sameDirection = relation.sourceTableId === relationForm.sourceTableId
      && relation.targetTableId === relationForm.targetTableId
      && relation.sourceColumn === relationForm.sourceColumn
      && relation.targetColumn === relationForm.targetColumn
    const reverseDirection = relation.sourceTableId === relationForm.targetTableId
      && relation.targetTableId === relationForm.sourceTableId
      && relation.sourceColumn === relationForm.targetColumn
      && relation.targetColumn === relationForm.sourceColumn
    return sameDirection || reverseDirection
  })
  if (duplicateRelation) {
    ElMessage.warning('这两张表的相同字段关系已存在，请勿重复关联')
    return
  }

  relationSubmitting.value = true
  try {
    const relationData = {
      projectGroupId: currentProjectGroupId.value,
      sourceTableId: relationForm.sourceTableId,
      targetTableId: relationForm.targetTableId,
      sourceColumn: relationForm.sourceColumn,
      targetColumn: relationForm.targetColumn,
      relationContent: relationForm.relationContent.trim()
    }
    const response = relationDialogMode.value === 'create'
      ? await createProjectGroupTableRelation(relationData)
      : await updateProjectGroupTableRelation({ id: editingRelationId.value!, ...relationData })
    if (!response.success) {
      ElMessage.warning(response.message || (relationDialogMode.value === 'create' ? '表关系创建失败' : '表关系修改失败'))
      return
    }
    ElMessage.success(relationDialogMode.value === 'create' ? '表关系创建成功' : '表关系修改成功')
    relationFormDialogVisible.value = false
    await loadTableRelations()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, relationDialogMode.value === 'create' ? '表关系创建失败' : '表关系修改失败'))
  } finally {
    relationSubmitting.value = false
  }
}

const confirmDeleteTableRelation = async (relation: ProjectGroupTableRelation) => {
  if (!canEditAssociations.value || deletingRelationId.value !== null || batchDeletingRelations.value) return

  try {
    await ElMessageBox.confirm(
      '确定删除这条表关系吗？',
      '删除表关系',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '删除确认失败'))
    return
  }

  deletingRelationId.value = relation.id
  try {
    const response = await deleteProjectGroupTableRelation({
      id: relation.id,
      projectGroupId: currentProjectGroupId.value
    })
    if (!response.success) {
      ElMessage.warning(response.message || '表关系删除失败')
      return
    }
    ElMessage.success('表关系已从数据库中删除')
    await loadTableRelations()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '表关系删除失败'))
  } finally {
    deletingRelationId.value = null
  }
}

const confirmBatchDeleteTableRelations = async () => {
  if (
    !canEditAssociations.value
    || selectedRelationIds.value.length === 0
    || deletingRelationId.value !== null
    || batchDeletingRelations.value
  ) return

  const relationIds = [...selectedRelationIds.value]
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${relationIds.length} 条表关系吗？`,
      '批量删除表关系',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '删除确认失败'))
    return
  }

  batchDeletingRelations.value = true
  try {
    const response = await deleteProjectGroupTableRelations({
      projectGroupId: currentProjectGroupId.value,
      ids: relationIds
    })
    if (!response.success) {
      ElMessage.warning(response.message || '表关系批量删除失败')
      await loadTableRelations()
      return
    }
    ElMessage.success(response.message || `已删除 ${response.data.deletedCount} 条表关系`)
    await loadTableRelations()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '表关系批量删除失败'))
  } finally {
    batchDeletingRelations.value = false
  }
}

const confirmRemoveImportedTable = async (table: ProjectGroupTableOption) => {
  if (
    !canEditAssociations.value
    || !libraryName.value
    || deletingTableName.value
    || batchDeletingImportedTables.value
  ) return

  try {
    await ElMessageBox.confirm(
      '确定删除吗？',
      '删除已导入数据表',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '删除确认失败'))
    return
  }

  deletingTableName.value = table.tableName
  try {
    const response = await saveProjectGroupTableAssociations({
      projectGroupId: currentProjectGroupId.value,
      libraryName: libraryName.value,
      tables: tableOptions.value
        .filter((item) => item.tableName !== table.tableName)
        .map(toAssociationSaveItem)
    })
    if (!response.success) {
      ElMessage.error(response.message || '数据表删除失败')
      return
    }
    ElMessage.success('已永久删除该导入记录，来源物理表未受影响')
    await fetchDetail()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '数据表删除失败'))
  } finally {
    deletingTableName.value = ''
  }
}

const confirmBatchRemoveImportedTables = async () => {
  if (
    !canEditAssociations.value
    || !libraryName.value
    || !selectedImportedTableNames.value.length
    || deletingTableName.value
    || batchDeletingImportedTables.value
  ) return

  const tableNames = new Set(selectedImportedTableNames.value)
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${tableNames.size} 张已导入数据表吗？来源数据库中的真实物理表不会被删除。`,
      '批量删除已导入数据表',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '删除确认失败'))
    return
  }

  batchDeletingImportedTables.value = true
  try {
    const response = await saveProjectGroupTableAssociations({
      projectGroupId: currentProjectGroupId.value,
      libraryName: libraryName.value,
      tables: tableOptions.value
        .filter((table) => !tableNames.has(table.tableName))
        .map(toAssociationSaveItem)
    })
    if (!response.success) {
      ElMessage.error(response.message || '数据表批量删除失败')
      return
    }
    selectedImportedTableNames.value = []
    ElMessage.success(`已删除 ${tableNames.size} 条导入记录，来源物理表未受影响`)
    await fetchDetail()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '数据表批量删除失败'))
  } finally {
    batchDeletingImportedTables.value = false
  }
}

const resetGroupForm = () => {
  Object.assign(groupForm, createDefaultGroupForm())
  editingProjectGroupId.value = null
  groupFormRef.value?.clearValidate()
}

const loadSkillGroups = async () => {
  if (!isRootProjectGroup.value) return
  const requestedProjectGroupId = currentProjectGroupId.value
  const requestSequence = ++skillGroupRequestSequence
  const requestedPageNo = skillGroupPageNo.value
  const requestedPageSize = skillGroupPageSize.value
  skillGroupListLoading.value = true
  skillGroupListError.value = ''
  try {
    const response = await getChildProjectGroupPage(requestedProjectGroupId, {
      keyword: skillGroupKeyword.value.trim() || undefined,
      pageNo: requestedPageNo,
      pageSize: requestedPageSize
    })
    if (requestSequence !== skillGroupRequestSequence || requestedProjectGroupId !== currentProjectGroupId.value) return
    if (!response.success) {
      skillGroupListError.value = response.message || '技能组加载失败'
      return
    }

    const lastPage = Math.max(1, Math.ceil(response.data.total / requestedPageSize))
    if (requestedPageNo > lastPage) {
      skillGroupPageNo.value = lastPage
      await loadSkillGroups()
      return
    }
    skillGroupList.value = response.data.list
    skillGroupTotal.value = response.data.total
  } catch (error: unknown) {
    if (requestSequence === skillGroupRequestSequence && requestedProjectGroupId === currentProjectGroupId.value) {
      skillGroupListError.value = getErrorMessage(error, '技能组加载失败，请检查后端服务')
    }
  } finally {
    if (requestSequence === skillGroupRequestSequence) skillGroupListLoading.value = false
  }
}

const handleSkillGroupPageChange = (pageNo: number) => {
  skillGroupPageNo.value = pageNo
  loadSkillGroups()
}

const openSkillGroup = (skillGroup: ProjectGroup) => {
  router.push(`/project/group/${skillGroup.id}`)
}

const openCreateSkillGroupDialog = () => {
  if (!canCreateSkillGroup.value) return
  resetGroupForm()
  groupDialogMode.value = 'createSkillGroup'
  groupDialogVisible.value = true
}

const openEditDialog = () => {
  if (!projectGroup.value) return
  if (isRootProjectGroup.value) void loadSandboxOptions()
  resetGroupForm()
  groupDialogMode.value = 'editCurrent'
  editingProjectGroupId.value = projectGroup.value.id
  Object.assign(groupForm, {
    groupName: projectGroup.value.groupName,
    sandboxConfigId: projectGroup.value.sandboxConfigId,
    sortOrder: projectGroup.value.sortOrder,
    enabled: projectGroup.value.enabled
  })
  groupDialogVisible.value = true
}

const openEditSkillGroupDialog = (skillGroup: ProjectGroup) => {
  if (!canEditAssociations.value) return
  resetGroupForm()
  groupDialogMode.value = 'editSkillGroup'
  editingProjectGroupId.value = skillGroup.id
  Object.assign(groupForm, {
    groupName: skillGroup.groupName,
    sortOrder: skillGroup.sortOrder,
    enabled: skillGroup.enabled
  })
  groupDialogVisible.value = true
}

const submitProjectGroup = async () => {
  if (submittingGroup.value) return
  if (groupDialogMode.value === 'editCurrent' && isRootProjectGroup.value && (sandboxLoading.value || sandboxError.value)) return
  if (!groupFormRef.value || !projectGroup.value) return
  const valid = await groupFormRef.value.validate().catch(() => false)
  if (!valid) return

  submittingGroup.value = true
  try {
    const groupName = groupForm.groupName.trim()
    const response = groupDialogMode.value === 'createSkillGroup'
      ? await createProjectGroup({
          groupName,
          parentId: projectGroup.value.id,
          sortOrder: groupForm.sortOrder,
          enabled: groupForm.enabled
        })
      : editingProjectGroupId.value === null
        ? null
        : await updateProjectGroup({
            id: editingProjectGroupId.value,
            ...(groupDialogMode.value === 'editCurrent' && isRootProjectGroup.value ? { sandboxConfigId: groupForm.sandboxConfigId } : {}),
            groupName,
            sortOrder: groupForm.sortOrder,
            enabled: groupForm.enabled
          })
    if (!response) {
      ElMessage.error('未找到需要修改的项目组')
      return
    }
    if (response.success) {
      ElMessage.success(groupDialogMode.value === 'createSkillGroup' ? '技能组新增成功' : '修改成功')
      groupDialogVisible.value = false
      window.dispatchEvent(new Event('project-groups-changed'))
      if (groupDialogMode.value === 'editCurrent') await fetchDetail()
      else await loadSkillGroups()
    } else {
      ElMessage.error(response.message || '项目组保存失败')
    }
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '项目组保存失败'))
  } finally {
    submittingGroup.value = false
  }
}

const confirmDeleteSkillGroup = async (skillGroup: ProjectGroup) => {
  if (!canEditAssociations.value || deletingSkillGroupId.value !== null) return
  try {
    await ElMessageBox.confirm(
      `确定删除技能组“${skillGroup.groupName}”吗？该技能组下的所有具体技能也会被永久删除。`,
      '删除技能组',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '删除确认失败'))
    return
  }

  deletingSkillGroupId.value = skillGroup.id
  try {
    const response = await deleteProjectGroup({ id: skillGroup.id })
    if (!response.success) {
      ElMessage.warning(response.message || '技能组删除失败')
      return
    }
    ElMessage.success('技能组删除成功')
    window.dispatchEvent(new Event('project-groups-changed'))
    await loadSkillGroups()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '技能组删除失败'))
  } finally {
    deletingSkillGroupId.value = null
  }
}

const returnToParentProjectGroup = () => {
  if (!projectGroup.value) return
  const parentId = projectGroup.value.parentId
  router.push(parentId ? `/project/group/${parentId}` : '/project/group')
}

const confirmDeleteCurrentGroup = async () => {
  if (!projectGroup.value) return
  try {
    await ElMessageBox.confirm(`确定删除项目组“${projectGroup.value.groupName}”吗？这会永久删除数据库中的对应记录，且无法恢复。`, '删除项目组', {
      confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning'
    })
    const response = await deleteProjectGroup({ id: projectGroup.value.id })
    if (!response.success) {
      ElMessage.error(response.message || '项目组删除失败')
      return
    }
    const parentId = projectGroup.value.parentId
    ElMessage.success('项目组删除成功')
    window.dispatchEvent(new Event('project-groups-changed'))
    await router.push(parentId ? `/project/group/${parentId}` : '/project/group')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '项目组删除失败'))
  }
}

const showColumns = (table: ProjectGroupTableOption) => {
  activeTable.value = table
  columnSearchKeyword.value = ''
  selectedColumnNames.value = []
  columnRemarkDraft.value = Object.fromEntries(
    table.columns.map((column) => [column.columnName, column.remark || column.columnComment || ''])
  )
  columnsDialogVisible.value = true
}

const resetColumnRemarkEditor = () => {
  activeTable.value = null
  columnRemarkDraft.value = {}
  columnSearchKeyword.value = ''
  selectedColumnNames.value = []
  deletingColumnName.value = ''
  batchDeletingColumns.value = false
}

const canSelectTableColumn = () => (
  canEditAssociations.value
  && !deletingColumnName.value
  && !batchDeletingColumns.value
  && !singleTableSchemaSyncing.value
  && !savingColumnRemarks.value
)

const handleColumnSelectionChange = (columns: PhysicalTableColumn[]) => {
  selectedColumnNames.value = columns.map((column) => column.columnName)
}

const applyUpdatedTableColumns = (
  tableManagementId: number,
  columns: PhysicalTableColumn[]
) => {
  const updatedColumns = columns.map((column) => ({ ...column }))
  const existingRemarkDraft = { ...columnRemarkDraft.value }
  tableOptions.value = tableOptions.value.map((item) =>
    item.tableManagementId === tableManagementId
      ? { ...item, columns: updatedColumns }
      : item
  )
  tablePageList.value = tablePageList.value.map((item) =>
    item.tableManagementId === tableManagementId
      ? { ...item, columns: updatedColumns }
      : item
  )
  if (activeTable.value?.tableManagementId === tableManagementId) {
    activeTable.value = { ...activeTable.value, columns: updatedColumns }
    columnRemarkDraft.value = Object.fromEntries(
      updatedColumns.map((column) => [
        column.columnName,
        Object.prototype.hasOwnProperty.call(existingRemarkDraft, column.columnName)
          ? existingRemarkDraft[column.columnName]
          : (column.remark || column.columnComment || '')
      ])
    )
  }
  selectedColumnNames.value = []
  columnTableRef.value?.clearSelection()
  tableStructureVersion.value += 1
}

const deleteColumnsFromSnapshot = async (columnNames: string[]) => {
  const tableManagementId = activeTable.value?.tableManagementId
  if (!tableManagementId || !columnNames.length) return false

  const response = await deleteProjectGroupTableColumns({
    projectGroupId: currentProjectGroupId.value,
    tableManagementId,
    columnNames
  })
  if (!response.success) {
    ElMessage.error(response.message || '字段删除失败')
    return false
  }

  applyUpdatedTableColumns(response.data.tableManagementId, response.data.columns)
  if (relationDialogVisible.value) await loadTableRelations()
  ElMessage.success(response.message || '字段删除成功')
  return true
}

const confirmDeleteColumn = async (columnName: string) => {
  if (!canSelectTableColumn()) return
  try {
    await ElMessageBox.confirm(
      `确定删除字段“${columnName}”吗？`,
      '删除字段',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '删除确认失败'))
    return
  }

  deletingColumnName.value = columnName
  try {
    await deleteColumnsFromSnapshot([columnName])
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '字段删除失败，请检查后端服务'))
  } finally {
    deletingColumnName.value = ''
  }
}

const confirmBatchDeleteColumns = async () => {
  const columnNames = [...selectedColumnNames.value]
  if (!columnNames.length || !canSelectTableColumn()) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${columnNames.length} 个字段吗？`,
      '批量删除字段',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '删除确认失败'))
    return
  }

  batchDeletingColumns.value = true
  try {
    await deleteColumnsFromSnapshot(columnNames)
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '字段批量删除失败，请检查后端服务'))
  } finally {
    batchDeletingColumns.value = false
  }
}

const syncCurrentTableSchema = async () => {
  const table = activeTable.value
  if (!table?.tableManagementId || !canEditAssociations.value || singleTableSchemaSyncing.value) return

  const tableManagementId = table.tableManagementId
  const existingRemarkDraft = { ...columnRemarkDraft.value }
  singleTableSchemaSyncing.value = true
  try {
    const response = await syncProjectGroupTableSchema(
      currentProjectGroupId.value,
      tableManagementId
    )
    if (!response.success) {
      ElMessage.warning(response.message || '当前表结构同步失败')
      return
    }

    const updatedTable = { ...response.data.table }
    tableOptions.value = tableOptions.value.map((item) =>
      item.tableManagementId === tableManagementId ? updatedTable : item
    )
    tablePageList.value = tablePageList.value.map((item) =>
      item.tableManagementId === tableManagementId ? updatedTable : item
    )
    if (activeTable.value?.tableManagementId === tableManagementId) {
      activeTable.value = updatedTable
      columnRemarkDraft.value = Object.fromEntries(
        updatedTable.columns.map((column) => [
          column.columnName,
          Object.prototype.hasOwnProperty.call(existingRemarkDraft, column.columnName)
            ? existingRemarkDraft[column.columnName]
            : (column.remark || column.columnComment || '')
        ])
      )
    }
    tableStructureVersion.value += 1
    if (response.data.physicalExists) {
      ElMessage.success(response.message || '当前表结构同步完成')
    } else {
      ElMessage.warning(response.message || '真实物理表不存在')
    }
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '当前表结构同步失败，请检查后端服务'))
  } finally {
    singleTableSchemaSyncing.value = false
  }
}

const saveColumnRemarks = async () => {
  const table = activeTable.value
  if (!table?.tableManagementId || savingColumnRemarks.value || singleTableSchemaSyncing.value) return

  savingColumnRemarks.value = true
  try {
    const response = await saveProjectGroupTableColumnRemarks({
      projectGroupId: currentProjectGroupId.value,
      tableManagementId: table.tableManagementId,
      columns: table.columns.map((column) => ({
        columnName: column.columnName,
        remark: columnRemarkDraft.value[column.columnName]?.trim() || ''
      }))
    })
    if (!response.success) {
      ElMessage.error(response.message || '字段备注保存失败')
      return
    }

    const updatedColumns = response.data.columns.map((column) => ({ ...column }))
    tableOptions.value = tableOptions.value.map((item) =>
      item.tableManagementId === response.data.tableManagementId
        ? { ...item, columns: updatedColumns }
        : item
    )
    tablePageList.value = tablePageList.value.map((item) =>
      item.tableManagementId === response.data.tableManagementId
        ? { ...item, columns: updatedColumns }
        : item
    )
    tableStructureVersion.value += 1
    ElMessage.success(response.message || '字段备注保存成功')
    columnsDialogVisible.value = false
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '字段备注保存失败，请检查后端服务'))
  } finally {
    savingColumnRemarks.value = false
  }
}

const resetSkillForm = () => {
  Object.assign(skillForm, createDefaultSkillForm())
  editingSkillId.value = null
  skillTableSelectorVisible.value = false
  subSkillSelectorVisible.value = false
  resetSkillTableSelector()
  resetSubSkillSelector()
  skillFormRef.value?.clearValidate()
}

const resetSkillTableSelector = () => {
  skillTableSearchKeyword.value = ''
  skillTableSelectionDraft.value = []
  skillTableColumnsVisible.value = false
  skillTableColumnSource.value = null
}

const openSkillTableSelector = () => {
  if (!skillTableOptions.value.length) return
  skillTableSearchKeyword.value = ''
  skillTableSelectionDraft.value = [...skillForm.tableIds]
  skillTableSelectorVisible.value = true
}

const confirmSkillTableSelection = () => {
  skillForm.tableIds = [...skillTableSelectionDraft.value]
  skillFormRef.value?.clearValidate('tableIds')
  skillTableSelectorVisible.value = false
}

const toggleSkillTableSelection = (
  tableManagementId: number,
  checked: boolean | string | number
) => {
  const selectedIds = new Set(skillTableSelectionDraft.value)
  if (checked === true) selectedIds.add(tableManagementId)
  else selectedIds.delete(tableManagementId)
  skillTableSelectionDraft.value = [...selectedIds]
}

const toggleAllFilteredSkillTables = (checked: boolean | string | number) => {
  const selectedIds = new Set(skillTableSelectionDraft.value)
  filteredSkillTableOptions.value.forEach((table) => {
    const tableManagementId = table.tableManagementId!
    if (checked === true) selectedIds.add(tableManagementId)
    else selectedIds.delete(tableManagementId)
  })
  skillTableSelectionDraft.value = [...selectedIds]
}

const openSkillTableColumns = (table: ProjectGroupTableOption) => {
  skillTableColumnSource.value = table
  skillTableColumnsVisible.value = true
}

const removeSelectedSkillTable = (tableManagementId: number) => {
  skillForm.tableIds = skillForm.tableIds.filter((tableId) => tableId !== tableManagementId)
}

const resetSubSkillSelector = () => {
  subSkillSearchKeyword.value = ''
  subSkillSelectionDraft.value = []
}

const loadSubSkillOptions = async () => {
  if (isRootProjectGroup.value) return
  subSkillOptionsLoading.value = true
  try {
    const response = await getProjectGroupSubSkillOptions(currentProjectGroupId.value)
    if (!response.success) {
      ElMessage.error(response.message || '子技能选项加载失败')
      subSkillOptions.value = []
      return
    }
    subSkillOptions.value = response.data.list.filter((skill) => skill.id !== editingSkillId.value)
  } catch (error: unknown) {
    subSkillOptions.value = []
    ElMessage.error(getErrorMessage(error, '子技能选项加载失败'))
  } finally {
    subSkillOptionsLoading.value = false
  }
}

const openSubSkillSelector = async () => {
  subSkillSearchKeyword.value = ''
  subSkillSelectionDraft.value = [...skillForm.subSkillIds]
  subSkillSelectorVisible.value = true
  await loadSubSkillOptions()
}

const confirmSubSkillSelection = () => {
  skillForm.subSkillIds = [...subSkillSelectionDraft.value]
  skillFormRef.value?.clearValidate('subSkillIds')
  subSkillSelectorVisible.value = false
}

const toggleSubSkillSelection = (
  skillId: number,
  checked: boolean | string | number
) => {
  const selectedIds = new Set(subSkillSelectionDraft.value)
  if (checked === true) selectedIds.add(skillId)
  else selectedIds.delete(skillId)
  subSkillSelectionDraft.value = [...selectedIds]
}

const toggleAllFilteredSubSkills = (checked: boolean | string | number) => {
  const selectedIds = new Set(subSkillSelectionDraft.value)
  filteredSubSkillOptions.value.forEach((skill) => {
    if (checked === true) selectedIds.add(skill.id)
    else selectedIds.delete(skill.id)
  })
  subSkillSelectionDraft.value = [...selectedIds]
}

const removeSelectedSubSkill = (skillId: number) => {
  skillForm.subSkillIds = skillForm.subSkillIds.filter((id) => id !== skillId)
}

const handleSkillLevelTypeChange = (value: string | number | boolean | undefined) => {
  if (Number(value) === 2) skillForm.subSkillIds = []
}

const loadProjectSkills = async () => {
  if (!projectGroup.value || isRootProjectGroup.value) return

  selectedSkillIds.value = []
  const requestedProjectGroupId = currentProjectGroupId.value
  const requestSequence = ++skillRequestSequence
  const requestedPageNo = skillPageNo.value
  const requestedPageSize = skillPageSize.value
  skillListLoading.value = true
  skillListError.value = ''
  try {
    const response = await getProjectGroupSkills(requestedProjectGroupId, {
      keyword: skillKeyword.value.trim() || undefined,
      enabled: skillEnabledFilter.value === '' ? undefined : skillEnabledFilter.value,
      skillLevelType: skillLevelTypeFilter.value === '' ? undefined : skillLevelTypeFilter.value,
      pageNo: requestedPageNo,
      pageSize: requestedPageSize
    })
    if (requestSequence !== skillRequestSequence || requestedProjectGroupId !== currentProjectGroupId.value) return
    if (!response.success) {
      skillListError.value = response.message || '项目组技能加载失败'
      return
    }

    const lastPage = Math.max(1, Math.ceil(response.data.total / requestedPageSize))
    if (requestedPageNo > lastPage) {
      skillPageNo.value = lastPage
      await loadProjectSkills()
      return
    }
    skillList.value = response.data.list
    skillTotal.value = response.data.total
  } catch (error: unknown) {
    if (requestSequence === skillRequestSequence && requestedProjectGroupId === currentProjectGroupId.value) {
      skillListError.value = getErrorMessage(error, '项目组技能加载失败，请检查后端服务')
    }
  } finally {
    if (requestSequence === skillRequestSequence) skillListLoading.value = false
  }
}

const handleSkillPageChange = (pageNo: number) => {
  selectedSkillIds.value = []
  skillPageNo.value = pageNo
  loadProjectSkills()
}

const canSelectSkill = () => (
  canEditAssociations.value
  && !batchDeletingSkills.value
  && deletingSkillId.value === null
)

const handleSkillSelectionChange = (selection: ProjectGroupSkill[]) => {
  selectedSkillIds.value = selection.map((skill) => skill.id)
}

const openCreateSkillDialog = () => {
  if (!canCreateConcreteSkill.value) {
    ElMessage.warning('当前技能组已停用，不能新增技能')
    return
  }
  resetSkillForm()
  skillDialogMode.value = 'create'
  skillDialogVisible.value = true
}

const openEditSkillDialog = (skill: ProjectGroupSkill) => {
  if (!canEditAssociations.value) return
  resetSkillForm()
  skillDialogMode.value = 'edit'
  editingSkillId.value = skill.id
  Object.assign(skillForm, {
    skillName: skill.skillName,
    skillDescription: skill.skillDescription || '',
    skillLevelType: skill.skillLevelType,
    ruleContent: skill.ruleContent,
    tableIds: [...skill.tableIds],
    subSkillIds: [...skill.subSkillIds],
    enabled: skill.enabled
  })
  if (skill.skillLevelType === 1 && skill.subSkillIds.length) loadSubSkillOptions()
  skillDialogVisible.value = true
}

const submitProjectSkill = async () => {
  if (!skillMcpReady.value) return ElMessage.warning('请等待 MCP 配置加载成功')
  if (!skillFormRef.value || !canEditAssociations.value || isRootProjectGroup.value) return
  const requestedRootProjectGroupId = rootProjectGroupId.value
  if (!requestedRootProjectGroupId) {
    ElMessage.error('未找到所属一级项目组')
    return
  }
  const valid = await skillFormRef.value.validate().catch(() => false)
  if (!valid) return

  skillSubmitting.value = true
  try {
    const skillData = {
      mcpBindings: skillMcpRef.value!.getBindings(),
      rootProjectGroupId: requestedRootProjectGroupId,
      skillGroupId: currentProjectGroupId.value,
      skillName: skillForm.skillName.trim(),
      skillDescription: skillForm.skillDescription.trim(),
      skillLevelType: skillForm.skillLevelType,
      ruleContent: skillForm.ruleContent.trim(),
      tableIds: [...skillForm.tableIds],
      subSkillIds: [...skillForm.subSkillIds],
      enabled: skillForm.enabled
    }
    const response = skillDialogMode.value === 'create'
      ? await createProjectGroupSkill(skillData)
      : await updateProjectGroupSkill({ id: editingSkillId.value!, ...skillData })
    if (!response.success) {
      ElMessage.warning(response.message || (skillDialogMode.value === 'create' ? '技能新增失败' : '技能修改失败'))
      return
    }
    ElMessage.success(response.message || (skillDialogMode.value === 'create' ? '技能新增成功' : '技能修改成功'))
    skillDialogVisible.value = false
    window.dispatchEvent(new Event('project-groups-changed'))
    await fetchDetail()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, skillDialogMode.value === 'create' ? '技能新增失败' : '技能修改失败'))
  } finally {
    skillSubmitting.value = false
  }
}

const confirmDeleteSkill = async (skill: ProjectGroupSkill) => {
  if (!canEditAssociations.value || deletingSkillId.value !== null) return

  try {
    await ElMessageBox.confirm(
      `确定删除技能“${skill.skillName}”吗？这会永久删除数据库中的对应记录。`,
      '删除技能',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '删除确认失败'))
    return
  }

  deletingSkillId.value = skill.id
  try {
    const requestedRootProjectGroupId = rootProjectGroupId.value
    if (!requestedRootProjectGroupId) {
      ElMessage.error('未找到所属一级项目组')
      return
    }
    const response = await deleteProjectGroupSkill({
      id: skill.id,
      rootProjectGroupId: requestedRootProjectGroupId
    })
    if (!response.success) {
      ElMessage.warning(response.message || '技能删除失败')
      return
    }
    ElMessage.success(response.message || '技能已从数据库中删除')
    await loadProjectSkills()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '技能删除失败'))
  } finally {
    deletingSkillId.value = null
  }
}

const confirmBatchDeleteSkills = async () => {
  const skillIds = [...selectedSkillIds.value]
  const requestedRootProjectGroupId = rootProjectGroupId.value
  if (!skillIds.length || !requestedRootProjectGroupId || !canSelectSkill()) return
  try {
    await ElMessageBox.confirm(
      `确定永久删除选中的 ${skillIds.length} 个具体技能吗？`,
      '批量删除技能',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '删除确认失败'))
    return
  }

  batchDeletingSkills.value = true
  try {
    const response = await deleteProjectGroupSkills({
      rootProjectGroupId: requestedRootProjectGroupId,
      skillGroupId: currentProjectGroupId.value,
      ids: skillIds
    })
    if (!response.success) {
      ElMessage.warning(response.message || '技能批量删除失败')
      return
    }
    selectedSkillIds.value = []
    ElMessage.success(response.message || `已删除 ${skillIds.length} 个具体技能`)
    await loadProjectSkills()
  } catch (error: unknown) {
    ElMessage.error(getErrorMessage(error, '技能批量删除失败'))
  } finally {
    batchDeletingSkills.value = false
  }
}

watch(
  () => route.params.groupId,
  () => {
    tablePageRequestSequence += 1
    skillRequestSequence += 1
    skillGroupRequestSequence += 1
    activeManagementTab.value = 'tables'
    tableSearchKeyword.value = ''
    tablePageList.value = []
    tablePageLoading.value = false
    tablePageError.value = ''
    tablePageNo.value = 1
    tableTotal.value = 0
    skillList.value = []
    skillListLoading.value = false
    skillListError.value = ''
    skillKeyword.value = ''
    skillEnabledFilter.value = ''
    skillLevelTypeFilter.value = ''
    skillPageNo.value = 1
    skillTotal.value = 0
    skillDialogVisible.value = false
    subSkillSelectorVisible.value = false
    subSkillOptions.value = []
    selectedSkillIds.value = []
    batchDeletingSkills.value = false
    skillGroupList.value = []
    skillGroupListLoading.value = false
    skillGroupListError.value = ''
    skillGroupKeyword.value = ''
    skillGroupPageNo.value = 1
    skillGroupTotal.value = 0
    deletingSkillGroupId.value = null
    fetchDetail()
  },
  { immediate: true }
)

watch(activeManagementTab, (tab) => {
  if (tab === 'tables') loadProjectGroupTablePage()
  if (tab === 'skills') {
    if (isRootProjectGroup.value) loadSkillGroups()
    else loadProjectSkills()
  }
})

watch(tableSearchKeyword, (_keyword, _previousKeyword, onCleanup) => {
  tablePageRequestSequence += 1
  const timer = window.setTimeout(() => {
    if (activeManagementTab.value !== 'tables') return
    tablePageNo.value = 1
    loadProjectGroupTablePage()
  }, 250)
  onCleanup(() => window.clearTimeout(timer))
})

watch(skillKeyword, (_keyword, _previousKeyword, onCleanup) => {
  skillRequestSequence += 1
  const timer = window.setTimeout(() => {
    if (activeManagementTab.value !== 'skills' || isRootProjectGroup.value) return
    skillPageNo.value = 1
    loadProjectSkills()
  }, 250)
  onCleanup(() => window.clearTimeout(timer))
})

watch(skillEnabledFilter, () => {
  skillRequestSequence += 1
  if (activeManagementTab.value !== 'skills' || isRootProjectGroup.value) return
  skillPageNo.value = 1
  loadProjectSkills()
})

watch(skillLevelTypeFilter, () => {
  skillRequestSequence += 1
  if (activeManagementTab.value !== 'skills' || isRootProjectGroup.value) return
  skillPageNo.value = 1
  loadProjectSkills()
})

watch(skillGroupKeyword, (_keyword, _previousKeyword, onCleanup) => {
  skillGroupRequestSequence += 1
  const timer = window.setTimeout(() => {
    if (activeManagementTab.value !== 'skills' || !isRootProjectGroup.value) return
    skillGroupPageNo.value = 1
    loadSkillGroups()
  }, 250)
  onCleanup(() => window.clearTimeout(timer))
})

</script>

<style scoped lang="scss">
.project-group-detail-page {
  box-sizing: border-box; height: 100%; min-height: 0; overflow: auto; padding: 12px 24px; background: var(--bg-dark);
}
.detail-card {
  display: flex; flex-direction: column; height: 100%; min-height: 480px; border: none;
  :deep(.el-card__header) { flex: 0 0 auto; padding: 12px 24px; }
  :deep(.el-card__body) {
    display: flex; flex: 1; flex-direction: column; min-height: 0; overflow: hidden; padding: 12px 24px;
  }
}
.page-header, .section-header, .header-actions, .save-area, .dialog-footer { display: flex; align-items: center; }
.page-header, .section-header, .dialog-footer { justify-content: space-between; gap: 24px; }
.title-area {
  min-width: 0;
  h1 { margin: 8px 0 0; color: #303133; font-size: 22px; line-height: 1.3; }
  p { margin: 4px 0 0; color: #909399; font-size: 14px; }
}
.header-actions, .save-area {
  flex-wrap: wrap; justify-content: flex-end; gap: 10px;
  :deep(.el-button + .el-button) { margin-left: 0; }
}
.content-alert, .import-alert, .relation-alert, .table-page-alert { flex-shrink: 0; margin-bottom: 12px; }
.management-tabs {
  display: flex; flex: 1; flex-direction: column; min-height: 0;
  :deep(.el-tabs__header) { flex: 0 0 auto; margin-bottom: 12px; }
  :deep(.el-tabs__content) { flex: 1; min-height: 0; overflow: hidden; }
  :deep(.el-tab-pane) { height: 100%; min-height: 0; }
}
.association-section, .skill-section {
  display: flex; flex-direction: column; height: 100%; min-width: 0; min-height: 0;
}
.section-header {
  flex-shrink: 0; margin-bottom: 8px;
}
.table-search { width: 280px; }
.skill-header {
  display: flex; flex-shrink: 0; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 8px;
}
.skill-toolbar { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 10px; }
.skill-search { width: 240px; }
.skill-status-filter { width: 130px; }
.skill-alert { margin-bottom: 20px; }
.skill-table { width: 100%; }
.skill-table-summary { width: 100%; }
.skill-table-summary-header { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.select-table-button {
  color: var(--el-text-color-regular); background: var(--el-bg-color); border-color: var(--el-border-color);
  &:hover, &:focus { color: var(--el-color-primary); background: var(--el-color-primary-light-9); border-color: var(--el-color-primary-light-5); }
}
.selected-table-count { color: #909399; font-size: 13px; }
.selected-skill-tables { display: flex; flex-wrap: wrap; gap: 8px; }
.skill-table-search { width: min(360px, 100%); margin-bottom: 12px; }
.skill-table-option-list {
  overflow: hidden; border: 1px solid var(--el-border-color); border-radius: 6px;
}
.selector-selected-section { margin-top: 16px; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px; }
.selector-selected-title { margin-bottom: 10px; color: var(--el-text-color-primary); font-weight: 600; }
.tab-table-area {
  flex: 1 1 0; min-height: 0; overflow: hidden;
  :deep(.el-table__cell) { padding: 6px 0; }
}
.list-pagination {
  display: flex; flex: 0 0 auto; justify-content: flex-end; align-items: center; min-height: 44px; box-sizing: border-box; padding: 6px 0; margin-top: 8px; overflow-x: auto; border-top: 1px solid var(--el-border-color-lighter);
  :deep(.el-pagination) { flex-shrink: 0; }
}
.association-table { width: 100%; }
.database-selector {
  display: flex; align-items: center; gap: 12px; margin: 20px 0;
  label { color: #606266; font-weight: 500; }
  .el-select { width: min(420px, 100%); }
}
.import-table-filter { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.import-table-search { width: min(360px, 100%); }
.import-table-match-count { color: var(--text-secondary); font-size: 13px; white-space: nowrap; }
.column-toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px;
}
.column-search { width: min(360px, 100%); }
.column-toolbar-actions { display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
.column-match-count { color: var(--text-secondary); font-size: 13px; white-space: nowrap; }
.selector-tip, .schema-name { color: #909399; font-size: 12px; }
.physical-table-cell { min-width: 0; }
.physical-table-name { color: #303133; font-size: 13px; font-weight: 600; white-space: nowrap; }
.schema-name { margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.relation-select { width: 100%; }
.relation-mode-switch { display: flex; justify-content: center; margin-bottom: 20px; }
.auto-relation-toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px;
  span { color: var(--text-secondary); font-size: 13px; }
}
.auto-relation-toolbar + :deep(.el-table) {
  .el-select, .el-input { width: 100%; }
}
.relation-manager-header {
  display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 20px;
  h3 { margin: 0; color: #303133; font-size: 17px; }
  p { margin: 6px 0 0; color: #909399; font-size: 13px; }
}
.relation-manager-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 10px; }
.relation-table-name { color: #303133; font-size: 13px; font-weight: 600; }
.sync-summary { margin-bottom: 20px; }
.sync-alert { margin: 20px 0; }
.invalid-relation-section {
  margin-top: 24px;
  h3 { margin: 0; color: #303133; font-size: 16px; }
}

@media (max-width: 1024px) {
  .page-header, .section-header, .skill-header { align-items: flex-start; flex-direction: column; }
  .header-actions, .save-area { justify-content: flex-start; }
  .skill-toolbar { justify-content: flex-start; width: 100%; }
  .relation-manager-header { align-items: flex-start; }
}
@media (max-width: 768px) {
  .project-group-detail-page { padding: 12px; }
  .header-actions, .save-area, .dialog-footer, .database-selector, .skill-toolbar {
    align-items: stretch; flex-direction: column; width: 100%;
  }
  .import-table-filter, .column-toolbar, .auto-relation-toolbar { align-items: stretch; flex-direction: column; }
  .column-toolbar-actions { justify-content: space-between; }
  .table-search, .skill-search, .skill-status-filter, .import-table-search, .column-search { width: 100%; }
  .relation-manager-header { align-items: stretch; flex-direction: column; }
  .relation-manager-actions { align-items: stretch; flex-direction: column; width: 100%; }
  .relation-manager-actions .el-button { width: 100%; }
  .header-actions, .save-area { .el-button { width: 100%; } }
  .list-pagination { justify-content: flex-start; }
  .skill-table-summary-header { align-items: flex-start; flex-direction: column; }
  :deep(.el-dialog) { width: calc(100% - 24px) !important; }
}
</style>
