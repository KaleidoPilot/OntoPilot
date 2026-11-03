<template>
  <div class="chat-workspace">
    <aside class="rail" aria-label="工作台导航">
      <div class="brand" title="KaleidoPilot"><el-icon><Lightning /></el-icon></div>
      <nav>
        <el-button class="rail-link" :class="{ active: isChatPage }" aria-label="实时对话" :aria-current="isChatPage ? 'page' : undefined" @click="navigate('/chat')"><el-icon><ChatDotRound /></el-icon><span>对话</span></el-button>
        <el-button class="rail-link" :class="{ active: route.path === '/agent' }" :aria-current="route.path === '/agent' ? 'page' : undefined" aria-label="技能管理" @click="navigate('/agent')"><el-icon><MagicStick /></el-icon><span>技能管理</span></el-button>
        <el-button class="rail-link" :class="{ active: route.path === '/templates' }" :aria-current="route.path === '/templates' ? 'page' : undefined" aria-label="模板管理" @click="navigate('/templates')"><el-icon><Upload /></el-icon><span>模板管理</span></el-button>
        <el-button class="rail-link" :class="{ active: route.path === '/knowledge' }" :aria-current="route.path === '/knowledge' ? 'page' : undefined" aria-label="知识库" @click="navigate('/knowledge')"><el-icon><Files /></el-icon><span>知识库</span></el-button>
        <slot name="navigation-extra" />
      </nav>
      <div class="rail-bottom">
        <el-dropdown trigger="click" placement="right-end" @command="handleAccountCommand">
          <el-button class="account-trigger" circle aria-label="账号设置" :title="user.realName || user.account || '当前用户'"><el-avatar :size="40">{{ userInitial }}</el-avatar></el-button>
          <template #dropdown><el-dropdown-menu><el-dropdown-item command="password">修改密码</el-dropdown-item></el-dropdown-menu></template>
        </el-dropdown>
        <el-button class="rail-link" aria-label="退出登录" @click="logout"><el-icon><SwitchButton /></el-icon><span>退出</span></el-button>
      </div>
    </aside>

    <main v-show="isChatPage" class="workspace-main">
      <header class="workspace-header">
        <div class="heading"><el-icon><ChatDotRound /></el-icon><h1>实时对话</h1><el-tag round effect="light" :type="hasSkillGroups ? 'primary' : 'info'">{{ busy ? '正在处理' : isKnowledge ? '知识库查询' : hasSkillGroups ? (isAuto ? 'Auto 模式' : '已选择技能组') : '等待配置' }}</el-tag></div>
        <div class="header-actions">
          <el-button :icon="Clock" @click="historyOpen = true">对话记录</el-button>
          <el-button type="primary" :icon="Plus" :disabled="busy || !messages.length" @click="newConversation">新对话</el-button>
        </div>
      </header>

      <section class="conversation" aria-label="技能组对话">
        <div class="agent-bar">
          <div class="agent-info"><span class="status-dot" :class="{ ready: hasSkillGroups }"></span>
            <strong>KaleidoPilot</strong>
            <span class="agent-description">{{ isKnowledge ? '知识库查询' : isAuto ? 'Auto模式' : (activeGroup?.groupName || '未知技能组') }}</span>
          </div>
          <span class="privacy-note">欢迎使用KaleidoPilot</span>
        </div>

        <el-alert v-if="agentError" class="configuration-alert" :title="agentError" type="warning" :closable="false" show-icon />
        <el-alert v-if="storageError" class="configuration-alert" :title="storageError" type="warning" :closable="false" show-icon />
        <div ref="messageContainer" class="message-scroll" role="log" aria-label="对话消息" :aria-busy="busy" @scroll="trackScroll">
          <div v-if="!messages.length" class="welcome">
            <div class="welcome-mark"><el-icon><Lightning /></el-icon></div>
            <span class="eyebrow">KaleidoPilot · 你的工作助手</span>
            <h2>{{ greeting }}，{{ user.realName || '很高兴见到你' }}</h2>
            <p>把问题交给我，一起找到答案。</p>
            <div class="suggestions">
              <el-button v-for="item in suggestions" :key="item.title" class="suggestion" :disabled="!hasSkillGroups || busy" @click="useSuggestion(item.prompt)">
                <el-icon><component :is="item.icon" /></el-icon><span><strong>{{ item.title }}</strong><small>{{ item.description }}</small></span><el-icon class="suggestion-arrow"><Right /></el-icon>
              </el-button>
            </div>
            <span class="welcome-note">基于技能组绑定的 MCP 与知识库提供帮助</span>
          </div>

          <article v-for="(message, index) in messages" :key="message.id" class="message" :class="message.role" :id="`message-${message.id}`">
            <el-avatar :size="40">{{ message.role === 'user' ? userInitial : 'AI' }}</el-avatar>
            <div class="message-column">
              <div class="message-meta"><time>{{ message.time }}</time></div>
              <div class="bubble">
                <!-- 用户消息只走这一个分支：正文 + 本地文件片段，避免再落到助手分支把问题重复渲染 -->
                <template v-if="message.role === 'user'">
                  <div class="user-content">{{ message.content }}</div>
                  <div v-if="message.localSources?.length" class="local-message-sources"><span v-for="source in message.localSources" :key="`${source.path}:${source.startLine}`">{{ source.path }} · {{ source.startLine }}—{{ source.endLine }} 行</span></div>
                </template>
                <template v-else>
                  <div v-if="message.intent" class="execution-status"><el-icon><CircleCheckFilled /></el-icon>{{ intentLabel(message.intent) }}</div>
                  <div v-if="message.toolStatus" class="execution-status" role="status">{{ message.toolStatus }}</div>
                  <el-collapse v-if="executionParts(message.content).log" class="execution-details"><el-collapse-item title="查看执行过程" :name="message.id"><div class="markdown-body" v-html="renderMarkdown(executionParts(message.content).log, !!message.localSources?.length)" /></el-collapse-item></el-collapse>
                  <div v-if="executionParts(message.content).answer" class="markdown-body" v-html="renderMarkdown(executionParts(message.content).answer, !!message.localSources?.length)" />
                  <el-collapse v-if="message.sources?.length" class="execution-details"><el-collapse-item title="引用资料（检索来源，可查看原文）" :name="`sources-${message.id}`"><div v-for="(source, sourceIndex) in message.sources" :key="source.id"><el-button link type="primary" @click="openSource(source)">[资料{{ sourceIndex + 1 }}] {{ source.title || '未命名资料' }} · 版本 {{ source.version }}</el-button><small> {{ source.tenantName }} · {{ source.fileUrl || '手动录入' }}</small></div></el-collapse-item></el-collapse>
                  <el-collapse v-if="message.graphReferences?.length" class="execution-details"><el-collapse-item title="知识图谱参考（关联梳理，事实请以上方引用资料原文为准）" :name="`graph-references-${message.id}`"><div v-for="(graph, graphIndex) in message.graphReferences" :key="`${graph.tenantId}-${graphIndex}`" class="graph-reference"><div class="graph-reference-head"><strong>{{ graph.tenantName || `知识库 ${graph.tenantId}` }}</strong><small v-if="graph.files.length">图谱原文出处：{{ graph.files.join('、') }}</small></div><div class="markdown-body" v-html="renderMarkdown(graph.answer, false)" /></div></el-collapse-item></el-collapse>
                  <el-collapse v-if="message.localSources?.length" class="execution-details"><el-collapse-item title="本地文件（本次发送的片段）" :name="`local-sources-${message.id}`"><div v-for="source in message.localSources" :key="`${source.path}:${source.startLine}`">{{ source.path }} · 第 {{ source.startLine }}—{{ source.endLine }} 行{{ source.truncated ? '（部分内容）' : '' }}</div></el-collapse-item></el-collapse>
                  <div v-if="message.state === 'streaming'" class="thinking" role="status"><el-icon class="is-loading"><Loading /></el-icon>{{ message.content ? '正在生成回答…' : '正在理解你的问题…' }}</div>
                  <el-alert v-if="message.error" :title="message.error" type="error" :closable="false" show-icon />
                  <div v-if="message.confirmation" class="tool-confirmation">
                    <el-alert :title="`服务 ${message.confirmation.serverName || '个人 MCP'} 的工具 ${message.confirmation.toolName} 需要执行确认（5 分钟内有效）`" type="warning" :closable="false" />
                    <pre>{{ JSON.stringify(message.confirmation.arguments, null, 2) }}</pre>
                    <el-button type="primary" :disabled="busy" @click="confirmOperation(message)">确认执行</el-button><el-button :disabled="busy" @click="rejectOperation(message)">取消操作</el-button>
                  </div>
                  <p v-if="message.state === 'stopped'" class="stopped-note">已停止接收。后台执行可能仍在继续，请勿重复提交同一任务。</p>
                </template>
              </div>
              <div v-if="message.role === 'assistant' && message.state !== 'streaming'" class="message-actions">
                <el-button v-if="message.content" link :icon="CopyDocument" @click="copyAnswer(answerWithSources(message))">复制</el-button>
                <el-dropdown v-if="message.content" trigger="click" @command="(format: ExportFormat) => exportAnswer(message, format)">
                  <el-button link :icon="Download">导出</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="md">Markdown（.md）</el-dropdown-item>
                      <el-dropdown-item command="word">Word（.doc）</el-dropdown-item>
                      <el-dropdown-item command="pdf">PDF（打印后另存）</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button v-if="message.templateTaskId" link type="primary" @click="openTemplateTask(message.templateTaskId)">查看模板进度</el-button>
                <template v-else-if="canAssessTemplate(message)">
                  <el-button v-if="templateAssessments[message.id]?.result?.suitable" link type="primary" @click="openAnswerTemplate(message)">保存为模板</el-button>
                  <el-button v-else link :loading="templateAssessments[message.id]?.loading" :disabled="!!templateAssessments[message.id]?.result" @click="assessAnswerTemplate(message)">{{ templateAssessments[message.id]?.result ? '暂不适合作为模板' : '判断是否适合作为模板' }}</el-button>
                  <el-tooltip v-if="templateAssessments[message.id]?.result" :content="templateAssessments[message.id].result!.reason"><el-icon tabindex="0" aria-label="查看模板判断理由"><InfoFilled /></el-icon></el-tooltip>
                  <span v-if="templateAssessments[message.id]?.error" class="template-assessment-error" role="status">{{ templateAssessments[message.id].error }}</span>
                </template>
                <span v-if="message.state === 'done' && executionParts(message.content).answer.trim().length > 12000" class="template-assessment-error">回答超过模板提炼的12000字限制，请先整理精简。</span>
                <el-button v-if="message.state === 'error'" link :disabled="busy" @click="restoreQuestion(index)">{{ message.localSources?.length ? '编辑问题并重新添加文件' : '编辑问题后重试' }}</el-button>
              </div>
            </div>
          </article>
        </div>

        <footer class="composer-area">
          <el-button v-if="!followBottom && messages.length" class="latest-button" size="small" @click="scrollToBottom(true)">回到最新消息 ↓</el-button>
          <div class="composer" :class="{ 'is-busy': busy }">
            <el-input ref="inputRef" v-model="draft" type="textarea" :autosize="{ minRows: 1, maxRows: 5 }" resize="none" :maxlength="6000" aria-label="输入对话消息" placeholder="输入你的问题，开始与技能组对话…" :disabled="loadingAgents || preparingMessage" @keydown="handleKeydown" />
            <slot name="composer-extra" :conversation-id="currentConversation.id" :busy="busy" />
            <div class="composer-toolbar">
              <el-dropdown trigger="click" :teleported="false" :disabled="busy || loadingAgents" @command="selectGroup">
                <el-button class="agent-picker" :disabled="busy || loadingAgents" aria-label="选择技能组">
                  <el-icon><MagicStick /></el-icon>
                  <span class="agent-picker-label">{{ pickerLabel }}</span>
                  <el-icon class="agent-picker-arrow"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :command="AUTO_AGENT_ID" :class="{ 'is-selected': isAuto }">
                      <div class="agent-option"><span class="agent-option-head"><el-icon><MagicStick /></el-icon><strong>Auto 智能匹配</strong><el-icon v-if="isAuto" class="agent-option-check"><Check /></el-icon></span><small>根据问题自动选择最合适的技能组</small></div>
                    </el-dropdown-item>
                    <!-- 知识库查询对所有账号固定存在：不走技能组匹配与技能编排，一律按用户被授权的知识库做向量召回 -->
                    <el-dropdown-item :command="KNOWLEDGE_AGENT_ID" :class="{ 'is-selected': isKnowledge }">
                      <div class="agent-option"><span class="agent-option-head"><el-icon><Files /></el-icon><strong>知识库查询</strong><el-icon v-if="isKnowledge" class="agent-option-check"><Check /></el-icon></span><small>始终在你被授权的知识库中做向量检索回答</small></div>
                    </el-dropdown-item>
                    <el-dropdown-item v-for="group in skillGroups" :key="group.id" :command="group.id" :class="{ 'is-selected': group.id === selectedGroupId }">
                      <div class="agent-option"><span class="agent-option-head"><el-icon><ChatDotRound /></el-icon><strong>{{ group.groupName }}</strong><el-icon v-if="group.id === selectedGroupId" class="agent-option-check"><Check /></el-icon></span><small>{{ group.description || '指定技能组' }}</small></div>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-tooltip :content="busy ? '停止接收（后台执行可能仍会继续）' : '发送消息'">
                <el-button class="send-button" type="primary" circle :icon="busy ? VideoPause : Top" :disabled="!busy && (!draft.trim() || !hasSkillGroups || loadingAgents)" :aria-label="busy ? '停止接收' : '发送消息'" @click="busy ? stopReceiving() : sendMessage()" />
              </el-tooltip>
            </div>
          </div>
          <div class="composer-hint"><span>Enter 发送 · Shift + Enter 换行</span><span>{{ isKnowledge ? '知识库查询：仅检索你被授权的知识库' : isAuto ? 'Auto 模式：每次提问自动匹配技能组' : `已指定：${activeGroup?.groupName || ''}` }}</span></div>
        </footer>
      </section>
    </main>
    <main v-if="!isChatPage" class="workspace-main skill-content"><router-view /></main>

    <el-dialog v-model="answerTemplateOpen" title="保存为模板" width="min(540px,94vw)" :close-on-click-modal="!answerTemplateSaving" :close-on-press-escape="!answerTemplateSaving" :show-close="!answerTemplateSaving">
      <p>将这条回答的文档结构、写作方法和图表用途提炼成模板 Skill，供后续使用新资料生成文档。</p>
      <el-form label-position="top" @submit.prevent="saveAnswerTemplate"><el-form-item label="模板名称" required><el-input v-model="answerTemplateName" maxlength="100" show-word-limit :disabled="answerTemplateSaving" aria-label="保存的模板名称" @input="answerTemplateKey = ''" /></el-form-item></el-form>
      <el-alert v-if="answerTemplateError" :title="answerTemplateError" type="error" :closable="false" />
      <template #footer><el-button :disabled="answerTemplateSaving" @click="answerTemplateOpen = false">取消</el-button><el-button type="primary" :loading="answerTemplateSaving" :disabled="!answerTemplateName.trim()" @click="saveAnswerTemplate">保存并提炼</el-button></template>
    </el-dialog>
    <el-dialog v-model="sourceOpen" title="引用原文" width="min(760px,94vw)" @closed="sourceText = ''">
      <div v-loading="sourceLoading">
        <el-alert v-if="sourceError" :title="sourceError" type="error" show-icon :closable="false" />
        <el-alert v-if="sourceChanged" title="资料版本已经变化，以下是当前原文，可能与这条历史回答使用的版本不同。" type="warning" show-icon :closable="false" />
        <pre class="source-text">{{ sourceText }}</pre>
      </div>
    </el-dialog>
    <el-drawer v-model="historyOpen" title="历史对话" size="min(380px, 100vw)">
      <el-alert :title="storageError || '历史记录保存在当前浏览器，按账号隔离，包含本次对话。'" :type="storageError ? 'warning' : 'info'" :closable="false" />
      <el-empty v-if="!historyConversations.length" description="还没有对话，发送第一个问题吧" />
      <el-button v-for="conversation in historyConversations" :key="conversation.id" class="history-item" :type="conversation.id === history.activeId ? 'primary' : 'default'" :plain="conversation.id === history.activeId" :disabled="busy && conversation.id !== history.activeId" @click="openConversation(conversation.id)">
        <strong>{{ conversation.messages.find(message => message.role === 'user')?.content || '新对话' }}</strong>
        <small>{{ conversation.id === history.activeId ? '当前对话 · ' : '' }}{{ new Date(conversation.updatedAt).toLocaleString('zh-CN') }}</small>
      </el-button>
    </el-drawer>
    <el-dialog v-model="passwordDialog" title="修改密码" width="min(440px,94vw)" :close-on-click-modal="!passwordSaving" :close-on-press-escape="!passwordSaving" :show-close="!passwordSaving" @closed="clearPasswordForm">
      <el-form label-width="90px" :disabled="passwordSaving" @submit.prevent="savePassword">
        <el-form-item label="原密码" required><el-input v-model="passwordForm.oldPassword" type="password" show-password autocomplete="current-password" maxlength="72" aria-label="原密码" /></el-form-item>
        <el-form-item label="新密码" required><el-input v-model="passwordForm.newPassword" type="password" show-password autocomplete="new-password" maxlength="72" aria-label="新密码" /></el-form-item>
      </el-form>
      <el-alert v-if="passwordError" :title="passwordError" type="error" show-icon :closable="false" />
      <template #footer><el-button :disabled="passwordSaving" @click="passwordDialog = false">取消</el-button><el-button type="primary" :loading="passwordSaving" @click="savePassword">保存密码</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type InputInstance } from 'element-plus'
import { ArrowDown, ChatDotRound, Check, CircleCheckFilled, Clock, CopyDocument, DataAnalysis, Download, Files, InfoFilled, Lightning, Loading, MagicStick, Plus, Right, SwitchButton, Top, Upload, VideoPause } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { fetchGroupSkillGroups, matchGroupSkillGroup, streamAgentChat, type AgentChatData, type KnowledgeSource, type SkillGroupOption } from '@/api/agent'
import { rejectMcpApproval, type McpApproval } from '@/api/mcp'
import { getKnowledgeRecord } from '@/api/knowledge'
import { changeExternalUserPassword, type PlatformUserInfo } from '@/api/user'
import { assessTemplateAnswer, createTemplateFromAnswer, type TemplateAnswerAssessment } from '@/api/skill'
import { answerWithSources, createConversation, historyStorageKey, readChatHistory, serializeChatHistory, type ChatComposerExtension, type PreparedChatMessage, type ChatMessage as Message } from '@/util/chatHistory'
import { exportAnswerDocument, type ExportFormat } from '@/util/exportDocument'

const router = useRouter()
const route = useRoute()
const composerExtension = inject<ChatComposerExtension | null>('fijo-chat-composer', null)
const preparingMessage = ref(false)
const isChatPage = computed(() => route.path === '/chat')
const user: PlatformUserInfo = (() => { try { return JSON.parse(localStorage.getItem('fijo-chat-userInfo') || '{}') } catch { return {} } })()
const userInitial = (user.realName || user.account || '我').slice(0, 1)
const passwordDialog = ref(false), passwordSaving = ref(false), passwordError = ref('')
const passwordForm = ref({oldPassword:'',newPassword:''})
const sourceOpen = ref(false), sourceLoading = ref(false), sourceError = ref(''), sourceText = ref(''), sourceChanged = ref(false)
let sourceRequest = 0
async function openSource(source: KnowledgeSource) {
  const requestId = ++sourceRequest
  sourceOpen.value = true; sourceLoading.value = true; sourceError.value = ''; sourceText.value = ''; sourceChanged.value = false
  try {
    const response = await getKnowledgeRecord(source.id)
    if (requestId !== sourceRequest || !sourceOpen.value) return
    if (!response.success) throw new Error(response.message || '原文不可查看，可能已删除或权限已变更')
    sourceText.value = response.data.content || ''
    sourceChanged.value = response.data.version !== source.version
  } catch (cause) { if (requestId === sourceRequest) sourceError.value = cause instanceof Error ? cause.message : '原文加载失败，请重试' }
  finally { if (requestId === sourceRequest) sourceLoading.value = false }
}
function clearPasswordForm() { passwordForm.value={oldPassword:'',newPassword:''};passwordError.value='' }
function handleAccountCommand(command: string) { if(command==='password'){clearPasswordForm();passwordDialog.value=true} }
async function savePassword() {
  if(passwordSaving.value)return
  passwordError.value=''
  if(!passwordForm.value.oldPassword || passwordForm.value.newPassword.length<8){passwordError.value='请填写原密码，新密码至少8位';return}
  passwordSaving.value=true
  try{
    const response=await changeExternalUserPassword({...passwordForm.value})
    if(!response.success)throw new Error(response.message||'密码修改失败')
    clearPasswordForm();passwordDialog.value=false;ElMessage.success('密码修改成功')
  }catch(cause){passwordError.value=cause instanceof Error?cause.message:'密码修改失败，请重试'}finally{passwordSaving.value=false}
}
const greeting = new Date().getHours() < 12 ? '上午好' : new Date().getHours() < 18 ? '下午好' : '晚上好'
// 技能组已替代智能体作为第一层筛选入口
const skillGroups = ref<SkillGroupOption[]>([])
const AUTO_AGENT_ID = 0
// 知识库查询入口对所有账号固定存在，用负数与真实技能组 id 区分；
// 选中后不匹配技能组、不执行技能编排，只按用户被授权的知识库做向量召回。
const KNOWLEDGE_AGENT_ID = -1
// 默认 Auto：由后端依据用户问题自动匹配技能组；也可手动选择指定技能组
const selectedGroupId = ref<number>(AUTO_AGENT_ID)
const isAuto = computed(() => selectedGroupId.value === AUTO_AGENT_ID)
const isKnowledge = computed(() => selectedGroupId.value === KNOWLEDGE_AGENT_ID)
const activeGroup = computed(() => skillGroups.value.find(group => group.id === selectedGroupId.value))
const hasSkillGroups = computed(() => skillGroups.value.length > 0)
const pickerLabel = computed(() => isKnowledge.value ? '知识库查询' : isAuto.value ? 'Auto 智能匹配' : (activeGroup.value?.groupName || 'Auto 智能匹配'))
function selectGroup(command: number) { selectedGroupId.value = command }
const loadingAgents = ref(false)
const agentError = ref('')
const storageError = ref('')
const storageKey = historyStorageKey(user)
const history = ref((() => {
  try { return readChatHistory(localStorage.getItem(storageKey)) } catch {
    storageError.value = '无法读取本机历史记录，当前对话仍可使用；请导出需要保留的回答。'
    return readChatHistory(null)
  }
})())
const currentConversation = computed(() => history.value.conversations.find(item => item.id === history.value.activeId)!)
const messages = computed(() => currentConversation.value.messages)
const templateAssessments = ref<Record<number, { loading: boolean; result?: TemplateAnswerAssessment; error?: string }>>({})
const assessmentControllers = new Set<AbortController>()
const answerTemplateOpen = ref(false), answerTemplateSaving = ref(false), answerTemplateName = ref(''), answerTemplateError = ref('')
let answerTemplateMessage: Message | undefined, answerTemplateQuestion = '', answerTemplateKey = ''
function canAssessTemplate(message: Message) {
  const length = executionParts(message.content).answer.trim().length
  return message.role === 'assistant' && message.state === 'done' && length >= 40 && length <= 12000
}
function templateQuestion(message: Message) {
  for (const conversation of history.value.conversations) {
    const index = conversation.messages.findIndex(item => item.id === message.id)
    if (index >= 0) return conversation.messages.slice(0, index).reverse().find(item => item.role === 'user')?.content.slice(0, 4000) || ''
  }
  return ''
}
async function assessAnswerTemplate(message: Message) {
  if (!canAssessTemplate(message) || message.templateTaskId || templateAssessments.value[message.id]?.loading || templateAssessments.value[message.id]?.result) return
  templateAssessments.value[message.id] = { loading: true }
  const request = new AbortController(); assessmentControllers.add(request)
  try {
    const res = await assessTemplateAnswer({ answer: executionParts(message.content).answer.trim(), question: templateQuestion(message) }, request.signal)
    if (!res.success) throw new Error(res.message || '模板判断失败')
    if (!disposed) templateAssessments.value[message.id] = { loading: false, result: res.data }
  } catch (cause) {
    if (!disposed) templateAssessments.value[message.id] = { loading: false, error: cause instanceof Error ? cause.message : '判断失败，可点击重试' }
  } finally { assessmentControllers.delete(request) }
}
function assessCompletedAnswer(message: Message) {
  // 明显成稿结构才自动判断；其他完整回答仍可手动判断，不阻塞聊天。
  const answer = executionParts(message.content).answer
  if (/(^|\n)\s*(#{1,6}\s|[一二三四五六七八九十]+[、．.]|\d+[、.．]\s)|律师函|建议书|工作报告/.test(answer)) void assessAnswerTemplate(message)
}
function openAnswerTemplate(message: Message) {
  if (!templateAssessments.value[message.id]?.result?.suitable || answerTemplateSaving.value) return
  answerTemplateMessage = message; answerTemplateQuestion = templateQuestion(message)
  answerTemplateName.value = templateAssessments.value[message.id].result!.suggestedName
  answerTemplateError.value = ''; answerTemplateKey = ''; answerTemplateOpen.value = true
}
function openTemplateTask(taskId: string) { void router.push({ path: '/templates', query: { taskId } }) }
async function saveAnswerTemplate() {
  if (!answerTemplateMessage || !answerTemplateName.value.trim() || answerTemplateSaving.value) return
  answerTemplateSaving.value = true; answerTemplateError.value = ''
  answerTemplateKey ||= 'answer-' + crypto.randomUUID()
  try {
    const res = await createTemplateFromAnswer({ answer: executionParts(answerTemplateMessage.content).answer.trim(), question: answerTemplateQuestion, skillName: answerTemplateName.value.trim() }, answerTemplateKey)
    if (!res.success) throw new Error(res.message || '模板保存失败')
    answerTemplateMessage.templateTaskId = res.data.taskId; saveHistory()
    try {
      const org = JSON.parse(localStorage.getItem('fijo-chat-organization') || 'null')
      if (user.id && (org?.id || user.orgId)) localStorage.setItem(`fijo-chat-template-task:${user.id}:${org?.id || user.orgId}`, res.data.taskId)
    } catch { /* 消息中的任务链接仍可打开进度 */ }
    if (!disposed) { answerTemplateOpen.value = false; ElMessage.success('已提交提炼，可在模板管理查看进度') }
  } catch (cause) { if (!disposed) answerTemplateError.value = cause instanceof Error ? cause.message : '保存失败，请重试' }
  finally { answerTemplateSaving.value = false }
}
const historyConversations = computed(() => history.value.conversations.filter(item => item.messages.length).slice().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)))
const draft = computed({ get: () => currentConversation.value.draft, set: value => { currentConversation.value.draft = value } })
const busy = ref(false)
const historyOpen = ref(false)
const followBottom = ref(true)
const messageContainer = ref<HTMLElement>()
const inputRef = ref<InputInstance>()
let controller: AbortController | undefined
// 本轮请求因条数上限被截掉的历史条数：推进记忆游标时需一并计入
let historyTrimmed = 0
let messageId = history.value.conversations.reduce((max, item) => item.messages.reduce((result, message) => Math.max(result, message.id), max), 0)
let disposed = false
let saveTimer: ReturnType<typeof setTimeout> | undefined
function saveHistory() {
  clearTimeout(saveTimer)
  try { localStorage.setItem(storageKey, serializeChatHistory(history.value)); storageError.value = '' } catch {
    storageError.value = '本机存储不可用或空间不足，记录暂未保存；请导出重要回答。'
  }
}
watch(history, () => { clearTimeout(saveTimer); saveTimer = setTimeout(saveHistory, 250) }, { deep: true })
watch(isChatPage, visible => { if (visible) { void scrollToBottom(); void loadAgents() } saveHistory() })
const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true })
const localFileMarkdown = new MarkdownIt({ html: false, linkify: true, breaks: true }).disable('image')
const renderMarkdown = (content: string, hasLocalFiles = false) => (hasLocalFiles ? localFileMarkdown : markdown).render(content)
// 仅识别后端固定的过程容器；其余 HTML 一律按文本处理，避免模型输出执行脚本。
// 模板对同一条消息会多次调用本函数，这里缓存上一次解析结果，
// 流式刷新时只解析一次，避免重复计算拖慢“打字机”观感。
let partsCacheContent = ''
let partsCache = { log: '', answer: '' }
function executionParts(content: string) {
  if (content === partsCacheContent) return partsCache
  const open = '<details class="execution-log">'
  if (!content.startsWith(open)) partsCache = { log: '', answer: content }
  else {
    const start = content.indexOf('</summary>')
    if (start === -1) partsCache = { log: '', answer: '' }
    else {
      const end = content.indexOf('</details>', start)
      partsCache = { log: content.slice(start + 10, end === -1 ? undefined : end), answer: end === -1 ? '' : content.slice(end + 10) }
    }
  }
  partsCacheContent = content
  return partsCache
}
// 多轮上下文只回传业务正文：执行过程容器里的 SQL/日志不参与记忆总结与对话理解
const historyContent = (content: string) => executionParts(content).answer.trim()
// 执行意图文案：把后端下发的 intent 枚举翻译成用户能看懂的说明
function intentLabel(intent: string) {
  if (intent === 'personal_mcp') return '技能组工具执行'
  if (intent === 'assistant_guide') return 'KaleidoPilot 能力介绍'
  if (intent.startsWith('template_')) return '已识别报告模板'
  if (intent.startsWith('skill_')) return '已识别技能'
  return '知识库检索与智能问答'
}
const suggestions = [
  { title: '业务数据分析', description: '梳理指标，发现数据中的变化', prompt: '我想分析业务数据，请先确认你能够分析的数据范围，以及需要我提供哪些条件。', icon: DataAnalysis },
  { title: '知识问答', description: '从已有知识中寻找问题答案', prompt: '请介绍你能回答哪些业务知识问题，以及可以参考的知识范围。', icon: Files },
  { title: '工作协助', description: '说明需求，获取清晰的处理建议', prompt: '我需要你协助处理一项工作，请先说明你的能力范围和需要我提供的信息。', icon: MagicStick }
]

async function loadAgents() {
  if (busy.value || loadingAgents.value) return
  loadingAgents.value = true
  agentError.value = ''
  try {
    // 用户组绑定哪些技能组，账号就能使用哪些技能组（Auto + 指定选择）
    let list: SkillGroupOption[] = []
    if (user.groupId) {
      const response = await fetchGroupSkillGroups(user.groupId)
      list = response.data?.list || []
    }
    skillGroups.value = list
    // Auto 与知识库查询都不依赖具体技能组，刷新列表时保持用户当前选择
    if (!isAuto.value && !isKnowledge.value && !list.some(group => group.id === selectedGroupId.value)) selectedGroupId.value = AUTO_AGENT_ID
    if (!list.length) agentError.value = '当前账号所属用户组未绑定可用技能组，请联系管理员配置后重新登录。'
  } catch (error) {
    skillGroups.value = []
    selectedGroupId.value = AUTO_AGENT_ID
    agentError.value = error instanceof Error ? error.message : '加载失败，请重新打开对话页面'
  } finally { loadingAgents.value = false }
}
function trackScroll() {
  const el = messageContainer.value
  if (el) followBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 100
}
async function scrollToBottom(force = false) {
  if (force) followBottom.value = true
  await nextTick()
  if (followBottom.value && messageContainer.value) messageContainer.value.scrollTop = messageContainer.value.scrollHeight
}
async function newConversation() {
  if (busy.value || !messages.value.length) return
  const conversation = createConversation()
  history.value.conversations.push(conversation)
  history.value.activeId = conversation.id
  followBottom.value = true
  saveHistory()
  await nextTick()
  inputRef.value?.focus()
}
function useSuggestion(prompt: string) { draft.value = prompt; inputRef.value?.focus() }
function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); void sendMessage() }
}
async function sendMessage() {
  const query = draft.value.trim()
  const groupId = user.groupId ?? 0
  if (busy.value || loadingAgents.value || !query) return
  // 知识库查询仍需一个技能组承载模型配置；没有可用技能组时给出明确提示
  if (isKnowledge.value && !hasSkillGroups.value) { ElMessage.error('当前账号未绑定可用技能组，暂时无法使用知识库查询'); return }
  // Auto 与知识库查询依赖用户组解析授权范围；指定模式必须有已选技能组
  if (isAuto.value || isKnowledge.value ? !groupId : !activeGroup.value) return
  busy.value = true
  preparingMessage.value = true
  const preparation = new AbortController()
  controller = preparation
  let prepared: PreparedChatMessage | null
  try {
    prepared = composerExtension ? await composerExtension.prepareMessage(query, currentConversation.value.id, preparation.signal) : { query }
  } catch (cause) {
    if (!preparation.signal.aborted && !disposed) ElMessage.error(cause instanceof Error ? cause.message : '文件准备失败，请重试')
    return
  } finally {
    preparingMessage.value = false
    if (controller === preparation) { controller = undefined; busy.value = false }
  }
  if (!prepared || preparation.signal.aborted || disposed) return
  busy.value = true
  // 多轮上下文：从记忆游标处开始回传对话，游标之前的内容已由后端压缩进 memory 摘要。
  // 只取业务正文（剔除执行过程容器），避免把过程日志当成对话内容送给模型。
  // 服务端只保留最近 6 条原文；这里再兜底截断到 20 条，防止记忆总结失败时请求体无限增长。
  const conversation = currentConversation.value
  const pendingMessages = conversation.messages.slice(conversation.memoryCount || 0)
  historyTrimmed = Math.max(0, pendingMessages.length - 20)
  const contextHistory = pendingMessages
    .slice(historyTrimmed)
    .filter(item => item.content.trim() && item.state !== 'streaming')
    .map(item => ({ role: item.role, content: historyContent(item.content) }))
    .filter(item => item.content)
  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  messages.value.push({ id: ++messageId, role: 'user', content: query, time, localSources: prepared.localSources })
  const answer = ref<Message>({ id: ++messageId, role: 'assistant', agentName: isKnowledge.value ? 'KaleidoPilot · 知识库查询' : isAuto.value ? 'Auto 智能匹配（匹配中…）' : activeGroup.value!.groupName, content: '', time, state: 'streaming', localSources: prepared.localSources })
  messages.value.push(answer.value)
  draft.value = ''
  prepared.onAccepted?.()
  currentConversation.value.updatedAt = new Date().toISOString()
  saveHistory()
  // 不附带已移除工具栏的手动选择。省略 mcpIds、tenantIds 时后端仍使用技能组已绑定的资源，空列表不会清空这些绑定。
  // Auto 模式先传 0，进入 runAnswer 后再按问题匹配具体技能组并回填。
  // 知识库查询模式固定挑一个技能组承载模型配置，并带上 autoAssistant + knowledgeOnly：
  // 后端据此跳过技能组匹配与技能编排，一律按用户被授权的知识库做向量召回。
  const configGroup = isKnowledge.value ? skillGroups.value[0] : activeGroup.value
  answer.value.mcpRequest = {
    skillGroupId: configGroup?.id || 0,
    userGroupId: groupId,
    query: prepared.query,
    history: contextHistory,
    memory: conversation.memory,
    ...(isKnowledge.value ? { autoAssistant: true, knowledgeOnly: true } : {}),
  }
  await runAnswer(answer.value, answer.value.mcpRequest)
  if (!disposed) assessCompletedAnswer(answer.value)
}
async function runAnswer(answer: Message, data: AgentChatData) {
  busy.value = true; answer.state = 'streaming'; answer.error = undefined
  controller = new AbortController()
  const signal = controller.signal
  await scrollToBottom(true)
  // 打字机渲染：累积流式增量文本，按动画帧批量刷新。
  // 逐 token 直接改写 content 会让整段 Markdown 每一帧重排多次，长回答越到后面越卡；
  // 合并为每帧刷新一次，既跟得上模型输出速度，又避免拖慢观感。
  let pending = ''
  let frame = 0
  const flush = () => {
    frame = 0
    if (!pending) return
    answer.content += pending
    pending = ''
    void scrollToBottom()
  }
  try {
    // Auto 模式：先按「用户问题 + 用户组」匹配唯一最合适的技能组，再进入流式对话
    let requestData = { ...data }
    if (!requestData.skillGroupId) {
      const response = await matchGroupSkillGroup(user.groupId ?? 0, data.query)
      if (!response.success) throw new Error(response.message || '技能组匹配失败，请稍后重试。')
      const matched = response.data
      if (matched?.matched && matched.skillGroup?.id) {
        requestData.skillGroupId = matched.skillGroup.id
        answer.agentName = matched.skillGroup.groupName
      } else {
        // 未匹配到专项技能组：交给 KaleidoPilot 做基础回复与知识库查询，而不是直接报错。
        // 这里仍带上候选列表中的第一个技能组，仅用于复用其绑定的知识库与模型配置，
        // autoAssistant=true 会让后端跳过意图识别与技能编排。
        const fallback = matched?.list?.[0]
        if (!fallback?.id) throw new Error('当前用户组未配置可用技能组，请联系管理员。')
        requestData = { ...requestData, skillGroupId: fallback.id, autoAssistant: true }
        answer.agentName = 'KaleidoPilot'
      }
    }
    if (signal.aborted) throw new DOMException('已停止接收', 'AbortError')
    answer.mcpRequest = requestData
    await streamAgentChat(requestData, signal, event => {
      if (disposed) return
      if (event.type === 'content') {
        pending += event.content || ''
        if (!frame) frame = requestAnimationFrame(flush)
      }
      if (event.type === 'metadata') {
        answer.intent = event.data?.intent
        // 模板链路会额外带上模板名称，用于展示“已命中报告模板”
        if (event.data?.templateName) answer.templateName = event.data.templateName
        // 记忆总结：服务端把超出原文窗口的旧对话压缩成摘要，这里落盘并推进游标，
        // 下一轮只回传游标之后的对话，避免重复总结与上下文无限膨胀。
        // 补充确认操作复用同一份上下文，服务端会再次总结同一段内容，此处不再重复推进游标。
        if (event.data?.memory && !data.mcpApproval) {
          const target = currentConversation.value
          target.memory = event.data.memory
          target.memoryCount = Math.min(
            (target.memoryCount || 0) + historyTrimmed + (event.data.memoryConsumed || 0),
            target.messages.length,
          )
        }
      }
      if (event.type === 'sources') {
        answer.sources = event.data?.sources || []
        answer.graphReferences = event.data?.graphReferences || []
      }
      if (event.type === 'tool_status') answer.toolStatus = `${event.data?.name || '工具'}：${event.data?.status === 'running' ? '正在调用' : '已返回结果'}`
      if (event.type === 'confirmation') { answer.confirmation = event.data as McpApproval; if (event.data?.skillId && answer.mcpRequest) answer.mcpRequest = { ...answer.mcpRequest, skillId: event.data.skillId, mcpIds: [] }; if (event.data?.privateSkillId && answer.mcpRequest) answer.mcpRequest = { ...answer.mcpRequest, privateSkillId: event.data.privateSkillId, mcpIds: [] }; answer.state = 'confirmation' }
    })
    if (frame) { cancelAnimationFrame(frame); frame = 0 }
    flush()
    if (answer.confirmation) { answer.state = 'confirmation'; return }
    if (!answer.content.trim()) throw new Error('技能组未返回回答，请检查技能组配置后重试。')
    answer.state = 'done'
  } catch (error) {
    answer.state = signal.aborted ? 'stopped' : 'error'
    if (!signal.aborted) answer.error = error instanceof Error ? error.message : '发送失败，请稍后重试'
  } finally {
    if (frame) { cancelAnimationFrame(frame); frame = 0 }
    flush()
    busy.value = false; controller = undefined; if (!disposed) { currentConversation.value.updatedAt = new Date().toISOString(); saveHistory(); await scrollToBottom(); if (isChatPage.value) inputRef.value?.focus() }
  }
}
async function confirmOperation(answer: Message) {
  if (busy.value || !answer.confirmation || !answer.mcpRequest) return
  const approval = answer.confirmation
  answer.confirmation = undefined
  await runAnswer(answer, { ...answer.mcpRequest, mcpApproval: { configId: approval.configId, id: approval.id } })
  if (!disposed) assessCompletedAnswer(answer)
}
async function rejectOperation(answer: Message) {
  if (busy.value || !answer.confirmation) return
  busy.value = true
  try {
    const res = await rejectMcpApproval(answer.confirmation)
    if (!res.success) throw new Error(res.message || '取消失败')
    answer.confirmation = undefined; answer.state = 'done'; answer.content += '\n\n已取消工具操作。'; saveHistory()
  } catch (cause) { ElMessage.error(cause instanceof Error ? cause.message : '取消失败，请重试') }
  finally { busy.value = false }
}
function stopReceiving() { controller?.abort() }
function restoreQuestion(index: number) { draft.value = messages.value[index - 1]?.content || ''; inputRef.value?.focus() }
async function copyAnswer(content: string) {
  try { await navigator.clipboard.writeText(content); ElMessage.success('已复制回答') } catch { ElMessage.error('复制失败，请手动选中文字复制') }
}
function exportAnswer(message: Message, format: ExportFormat) {
  try {
    // 导出只保留最终回答：执行过程是给用户现场查看的，不进文档
    const content = answerWithSources({ ...message, content: executionParts(message.content).answer })
    exportAnswerDocument(content, format)
  } catch (cause) {
    ElMessage.error(cause instanceof Error ? cause.message : '导出失败，请稍后重试')
  }
}
async function openConversation(id: string) {
  if (busy.value && id !== history.value.activeId) return
  history.value.activeId = id
  historyOpen.value = false
  saveHistory()
  await router.push('/chat')
  await scrollToBottom(true)
}
function navigate(path: string) { void router.push(path) }
async function logout() {
  try {
    await ElMessageBox.confirm('确认退出登录？历史记录将保留在本机。若任务正在执行，退出不会撤销后台操作。', '退出登录', { type: 'warning', confirmButtonText: '退出登录', cancelButtonText: '取消' })
    saveHistory(); stopReceiving(); localStorage.removeItem('fijo-chat-token'); localStorage.removeItem('fijo-chat-userInfo'); localStorage.removeItem('fijo-chat-organization'); await router.replace('/login')
  } catch { /* 用户取消 */ }
}
onMounted(() => { void loadAgents(); void scrollToBottom(true); window.addEventListener('pagehide', saveHistory) })
onBeforeUnmount(() => { disposed = true; for (const request of assessmentControllers) request.abort(); saveHistory(); stopReceiving(); clearTimeout(saveTimer); window.removeEventListener('pagehide', saveHistory) })
</script>

<style scoped lang="scss">
.source-text { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 60vh; overflow-y: auto; line-height: 1.7; }
.template-assessment-error { color: var(--el-color-danger); font-size: 12px; overflow-wrap: anywhere; }
.local-message-sources { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; font-size: 12px; opacity: .85; }
.local-message-sources > span { overflow-wrap: anywhere; }
.tool-confirmation { margin-top: 12px; pre { padding: 12px; background: #f4f6fa; white-space: pre-wrap; overflow-wrap: anywhere; } }
.chat-workspace { --chat-muted: #687993; --chat-soft: #f6f8fc; display: flex; height: 100dvh; min-height: 480px; color: #25334e; background: #edf2f8; padding: 8px; box-sizing: border-box; gap: 16px; }
.rail { width: 80px; flex-shrink: 0; background: #fcfdff; border-radius: 14px 0 0 14px; display: flex; align-items: center; flex-direction: column; padding: 24px 0 12px; }
.brand, .welcome-mark { display: grid; place-items: center; color: var(--primary-color); background: #ebefff; border-radius: 18px; width: 56px; height: 56px; font-size: 34px; }
.rail nav { margin-top: 32px; display: flex; flex-direction: column; gap: 8px; overflow-y: auto; overflow-x: hidden; flex-shrink: 1; min-height: 0; }
.rail .rail-link { display: flex; flex-direction: column; gap: 6px; padding: 10px 4px; margin: 0; width: 60px; height: 60px; border: 0; background: transparent; color: var(--chat-muted); font-size: 11px; border-radius: 16px !important; :deep(>span) { display: flex; flex-direction: column; gap: 6px; } .el-icon { font-size: 23px; } &.active, &:hover { color: var(--primary-color); background: #e9eeff; } }
.rail-bottom { margin-top: auto; display: flex; flex-shrink: 0; flex-direction: column; align-items: center; gap: 10px; .el-avatar { color: #3d5684; background: #dce8ff; font-weight: 600; } }
.account-trigger.el-button { width: 44px; height: 44px; padding: 0; border-color: transparent; background: transparent; }.account-trigger.el-button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
.workspace-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; padding: 14px 8px 14px 0; }
.skill-content { overflow: auto; :deep(.private-page) { box-sizing: border-box; height: auto; min-height: 100%; background: transparent; padding: 0; } :deep(.private-card) { min-height: calc(100dvh - 48px); } }
.workspace-header { background: #fcfdff; min-height: 74px; padding: 0 28px; border-radius: 24px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.heading { display: flex; align-items: center; gap: 12px; >.el-icon { color: var(--primary-color); font-size: 24px; } h1 { margin: 0; font-size: 22px; letter-spacing: -.5px; } }
.header-actions { display: flex; gap: 10px; .el-button { margin: 0; } }
.conversation { flex: 1; min-height: 0; background: #f8fafd; border: 1px solid #fff; border-radius: 28px; display: flex; flex-direction: column; overflow: hidden; position: relative; }
.agent-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 62px; padding: 0 30px; border-bottom: 1px solid #edf0f5; font-size: 12px; }
.agent-info { display: flex; align-items: center; gap: 10px; min-width: 0; strong { white-space: nowrap; font-size: 13px; } .el-select { width: 200px; } }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: #a1a9b6; flex-shrink: 0; &.ready { background: #4aab85; } }
.agent-description { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 340px; color: var(--chat-muted); }
.privacy-note { white-space: nowrap; color: var(--chat-muted); }
.configuration-alert { width: auto; margin: 16px 24px 0; flex-shrink: 0; }
.message-scroll { flex: 1; min-height: 0; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #c2cfe2 transparent; padding: 28px; }
.welcome { max-width: 850px; margin: 4vh auto 20px; display: flex; flex-direction: column; align-items: center; text-align: center; .welcome-mark { width: 64px; height: 64px; font-size: 38px; margin-bottom: 24px; } .eyebrow { font-size: 11px; letter-spacing: 2px; color: var(--chat-muted); } h2 { margin: 16px 0 4px; font-size: clamp(24px, 3vw, 34px); font-weight: 600; } p { color: var(--chat-muted); font-size: 15px; } }
.suggestions { display: grid; grid-template-columns: repeat(3, 1fr); width: 100%; gap: 14px; margin: 32px 0 20px; }
.suggestion.el-button { margin: 0; height: auto; padding: 22px 16px; border: 1px solid #e7edf6; border-radius: 16px !important; text-align: left; background: #fff; white-space: normal; :deep(>span) { width: 100%; display: flex; gap: 12px; } .el-icon { color: var(--primary-color); font-size: 22px; flex-shrink: 0; } strong { display: block; font-size: 14px; color: #344460; margin-bottom: 8px; } small { display: block; font-size: 11px; color: var(--chat-muted); line-height: 1.5; } .suggestion-arrow { margin-left: auto; font-size: 16px; } &:hover { border-color: #b8c6fa; background: #fcfdff; } }
.welcome-note { font-size: 12px; color: var(--chat-muted); }
.message { display: flex; gap: 14px; margin: 0 0 28px; .el-avatar { flex-shrink: 0; background: #e8edf5; color: #445672; font-size: 14px; } }
.message-column { max-width: min(85%, 850px); min-width: 0; }
.message-meta { font-size: 11px; color: var(--chat-muted); display: flex; gap: 12px; margin: 0 0 8px 2px; }
.bubble { background: white; padding: 20px 24px; border-radius: 4px 22px 22px; font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; }
.message.user { flex-direction: row-reverse; .message-meta { justify-content: flex-end; } .el-avatar { background: var(--primary-color); color: white; } .bubble { background: var(--primary-color); color: white; border-radius: 22px 4px 22px 22px; } }
.user-content { white-space: pre-wrap; }
.execution-status { display: flex; align-items: center; gap: 8px; color: #58718a; font-size: 12px; margin-bottom: 12px; .el-icon { color: #40b86c; } }
.execution-details { margin-bottom: 16px; :deep(.el-collapse-item__header) { color: var(--chat-muted); font-size: 12px; } }
.thinking { display: flex; align-items: center; gap: 8px; color: var(--chat-muted); font-size: 13px; }
.stopped-note { color: var(--chat-muted); font-size: 12px; margin-bottom: 0; }
/* 操作区统一用 flex 对齐，导出下拉和普通链接按钮保持同一字号、同一基线 */
.message-actions {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 8px 0 0 10px;
  :deep(.el-button) { height: auto; margin-left: 0; padding: 0; color: var(--chat-muted); font-size: 12px; }
  :deep(.el-dropdown) { display: inline-flex; align-items: center; line-height: 1; font-size: 12px; }
  :deep(.el-dropdown .el-button) { color: var(--chat-muted); font-size: 12px; }
  :deep(.el-dropdown .el-icon) { font-size: 14px; }
}
.composer-area { padding: 12px 28px 20px; position: relative; }
.composer { display: flex; flex-direction: column; gap: 10px; background: white; padding: 14px 16px 14px 24px; border: 1px solid #eef1f8; border-radius: 32px; box-shadow: 0 4px 24px #40528006; &:focus-within { border-color: #b5c3fa; } :deep(.el-textarea__inner) { box-shadow: none; background: transparent; padding: 10px 0; font-size: 15px; line-height: 24px; } }
.composer-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.agent-picker.el-button { display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 12px; margin: 0; border: 1px solid #e7edf6; border-radius: 999px !important; background: #fff; color: #3d5684; font-size: 12px; >span { display: inline-flex; align-items: center; gap: 6px; } .el-icon { font-size: 15px; } &:hover, &:focus-visible { border-color: #b8c6fa; background: #f7f9ff; color: var(--primary-color); } }
.agent-picker-label { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agent-picker-arrow { font-size: 12px; color: var(--chat-muted); }
.agent-option { display: flex; flex-direction: column; gap: 4px; min-width: 200px; padding: 2px 0; }
.agent-option-head { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #25334e; .el-icon { color: var(--primary-color); font-size: 15px; } }
.agent-option small { color: var(--chat-muted); font-size: 11px; line-height: 1.4; }
.agent-option-check { margin-left: auto; color: #40b86c !important; }
:deep(.el-dropdown-menu__item) { padding: 10px 14px; border-radius: 10px; &:not(.is-disabled):hover { background: #f4f7ff; } &.is-selected { background: #eef2ff; } }
.send-button.el-button { width: 46px; height: 46px; flex-shrink: 0; font-size: 23px; border-radius: 50% !important; }
.composer-hint { display: flex; justify-content: space-between; gap: 12px; margin: 10px 12px 0; font-size: 11px; color: var(--chat-muted); }
.latest-button { position: absolute; top: -28px; left: 50%; transform: translateX(-50%); }
.history-item.el-button { display: block; margin: 14px 0 0; width: 100%; padding: 16px; height: auto; white-space: normal; text-align: left; :deep(>span) { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } }
.history-item { strong { display: block; overflow: hidden; text-overflow: ellipsis; font-size: 13px; } small { display: block; margin-top: 8px; font-size: 11px; } }
.markdown-body { :deep(p) { margin: 0 0 12px; &:last-child { margin-bottom: 0; } } :deep(pre) { max-width: 100%; overflow: auto; background: #f4f6fa; padding: 14px; border-radius: 8px; } :deep(code) { font-size: 12px; background: #f4f6fa; } :deep(table) { display: block; overflow: auto; border-collapse: collapse; width: 100%; } :deep(th), :deep(td) { border: 1px solid #dfe6ef; padding: 8px 12px; } :deep(a) { color: var(--primary-color); } :deep(blockquote) { margin: 12px 0; padding-left: 16px; border-left: 3px solid var(--primary-color); color: var(--chat-muted); } :deep(img) { max-width: 100%; } }
@media (max-width: 1050px) { .agent-description { display: none; } .suggestions { gap: 8px; } .suggestion.el-button { padding: 18px 12px; .suggestion-arrow { display: none; } } }
@media (max-width: 700px) {
  .chat-workspace { gap: 6px; padding: 0; min-height: 0; } .rail { width: 56px; padding-top: 16px; border-radius: 0; } .brand { width: 38px; height: 42px; font-size: 26px; border-radius: 12px; } .rail .rail-link { width: 48px; height: 55px; } .rail nav { margin-top: 18px; gap: 4px; } .rail-bottom { gap: 6px; }
  .workspace-main { padding: 8px 6px 8px 0; gap: 8px; } .workspace-header { flex-wrap: wrap; min-height: 64px; padding: 14px; border-radius: 16px; } .heading { gap: 8px; h1 { font-size: 18px; } >.el-icon { display: none; } .el-tag { font-size: 10px; } } .header-actions { width: 100%; justify-content: flex-end; .el-button { padding: 6px 12px; height: 28px; font-size: 12px; } }
  .conversation { border-radius: 18px; } .agent-bar { padding: 10px 14px; min-height: 28px; } .privacy-note { display: none; } .agent-info .el-select { width: 180px; } .message-scroll { padding: 18px 12px; } .welcome { margin-top: 12px; .welcome-mark { width: 46px; height: 46px; margin-bottom: 18px; } h2 { font-size: 22px; } p { font-size: 12px; } } .suggestions { grid-template-columns: 1fr; margin: 20px 0 14px; } .suggestion.el-button { padding: 14px; strong { margin-bottom: 4px; } } .welcome-note { font-size: 10px; }
  .message { gap: 8px; .el-avatar { width: 28px; height: 28px; font-size: 11px; } } .message-column { max-width: calc(100% - 36px); } .bubble { padding: 14px; font-size: 13px; } .message-meta { font-size: 10px; } .composer-area { padding: 8px; } .composer { padding: 8px 10px 8px 16px; gap: 6px; border-radius: 24px; :deep(.el-textarea__inner) { font-size: 13px; } } .agent-picker.el-button { height: 28px; padding: 0 10px; } .agent-picker-label { max-width: 110px; } .send-button.el-button { width: 38px; height: 38px; font-size: 20px; } .composer-hint { font-size: 9px; margin: 8px 4px 0; flex-wrap: wrap; gap: 4px; } .configuration-alert { margin: 8px; }
}
</style>
