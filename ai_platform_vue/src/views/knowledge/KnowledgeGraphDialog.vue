<template>
  <el-dialog class="knowledge-graph-dialog" :model-value="modelValue" :title="`${name} · 知识图谱`" width="96vw" top="3vh" append-to-body
    @update:model-value="emit('update:modelValue', $event)" @opened="load" @closed="close">
    <el-alert title="图谱包含本文档及全部下级文件的实体与关系，问答也使用同一范围。点击节点可查看原文。" type="info" :closable="false" />
    <div class="graph-tools">
      <el-button @click="emit('manageDocuments')">查看下级文档</el-button>
      <el-button v-if="canBuild" type="primary" plain @click="emit('addDocuments')">添加下级文件</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
      <el-button v-if="canBuild && graph && graph.status !== 'ready' && graph.status !== 'building'" type="primary" :loading="building" @click="build">建立图谱</el-button>
      <span v-if="graph?.status === 'ready'">{{ graph.nodeCount }} 个节点 · {{ graph.edgeCount }} 条关系 · {{ graph.documents.length }} 份文档</span>
      <template v-if="graph?.status === 'ready' && graph.nodes.length">
        <el-button aria-label="放大图谱" @click="zoom(1.25)">放大</el-button>
        <el-button aria-label="缩小图谱" @click="zoom(0.8)">缩小</el-button>
        <el-button @click="resetView">复位视图</el-button>
        <el-button v-if="selected" @click="clearFocus">取消聚焦</el-button>
      </template>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-else-if="graph?.status === 'building'" :title="graph.error?.message || '正在按文件逐份建立图谱，已完成的文件不会重做'" type="info" :closable="false" />
    <el-alert v-else-if="graph?.error?.message" :title="graph.error.message" type="error" :closable="false" />
    <div v-loading="loading">
      <el-empty v-if="graph?.status === 'empty'" description="当前层级及下级还没有可建图的文档" />
      <el-empty v-else-if="graph?.status === 'not_created'" description="尚未建立知识图谱" />
      <div v-else-if="graph?.status === 'ready'" class="graph-workspace">
        <div class="graph-main">
          <p class="graph-hint">拖动空白处平移，滚轮缩放；点击节点聚焦直接关联，点击空白处取消。</p>
          <div ref="canvas" class="graph-canvas" role="img" aria-label="知识库实体关系图谱" @wheel.prevent />
          <aside v-if="selected" class="evidence">
            <h3>{{ selected.source ? `${selected.source} → ${selected.target}` : selected.label || selected.id }}</h3>
            <p>{{ selected.description }}</p>
            <div v-if="relatedNodes.length" class="related-nodes">
              <span>直接关联：</span>
              <el-button v-for="node in relatedNodes" :key="node.id" link type="primary" @click="select(node)">{{ node.label || node.id }}</el-button>
            </div>
            <el-button v-for="id in selected.evidenceIds || []" :key="id" link type="primary" @click="proof(id)">查看原文</el-button>
            <p v-if="evidence">{{ evidence.fileName }}</p>
            <pre v-if="evidence">{{ evidence.text }}</pre>
          </aside>
        </div>
        <section class="graph-qa" aria-label="知识图谱问答">
          <h3>图谱问答</h3>
          <p class="graph-hint">模型结合当前图谱的实体、关系和原文依据回答。</p>
          <el-input v-model="question" type="textarea" :rows="3" maxlength="2000" show-word-limit aria-label="图谱问题"
            placeholder="例如：这些资料中的主体有哪些关联？" @keydown.ctrl.enter.prevent="ask" />
          <el-button type="primary" :loading="asking" :disabled="!question.trim() || asking" @click="ask">提问</el-button>
          <el-alert v-if="qaError" :title="qaError" type="error" :closable="false" />
          <el-skeleton v-if="asking" :rows="4" animated />
          <template v-if="answer">
            <p class="asked-question">{{ answer.question }}</p>
            <div class="answer-content" v-html="answerHtml" />
            <el-collapse>
              <el-collapse-item name="context" :title="`提供给模型的依据：${answer.context.entities.length} 个实体 · ${answer.context.relationships.length} 条关系 · ${answer.context.sources.length} 段原文`">
                <p v-if="answer.context.isTruncated" class="graph-hint">本次上下文经过筛选或截取，未召回的内容不能判定为不存在。</p>
                <div class="qa-context">
                  <h4>实体</h4>
                  <p v-for="node in answer.context.entities" :key="node.id"><strong>{{ node.label || node.id }}</strong>：{{ node.description }}</p>
                  <h4>关系</h4>
                  <p v-for="edge in answer.context.relationships" :key="edge.id"><strong>[{{ edge.refId }}] {{ edge.source }} → {{ edge.target }}</strong>：{{ edge.description }}</p>
                  <h4>原文依据</h4>
                  <el-collapse>
                    <el-collapse-item v-for="source in answer.context.sources" :key="source.id" :name="source.id"
                      :title="`[${source.id}] ${source.fileName}${answer.sourceIds.includes(source.id) ? ' · 模型引用' : ''}`">
                      <p v-if="source.isExcerpt" class="graph-hint">已截取与问题相关的原文片段。</p>
                      <pre>{{ source.text }}</pre>
                    </el-collapse-item>
                  </el-collapse>
                </div>
              </el-collapse-item>
            </el-collapse>
          </template>
        </section>
      </div>
      <section v-if="graph?.documents.length" class="documents">
        <h3>图谱中的文档</h3>
        <ul>
          <li v-for="item in graph.documents" :key="item.docId"><el-button v-if="item.recordId" link type="primary" @click="emit('openDocument',item.recordId)">{{ item.name }}</el-button><span v-else>{{ item.name }}</span></li>
        </ul>
      </section>
    </div>
  </el-dialog>
</template>
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import { init, use, type ECharts } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { askKnowledgeGraph, buildKnowledgeGraph, getKnowledgeGraph, getKnowledgeGraphEvidence, type KnowledgeGraphAnswer, type KnowledgeGraphNode, type KnowledgeGraphView } from '@/api/knowledge'
use([GraphChart, TooltipComponent, CanvasRenderer])

const props = defineProps<{ modelValue: boolean; tenantId: number; name: string; canBuild?: boolean; folderId?:number }>()
const emit = defineEmits<{ 'update:modelValue': [boolean]; openDocument:[number]; addDocuments:[]; manageDocuments:[] }>()
const graph = ref<KnowledgeGraphView>()
const loading = ref(false)
const building = ref(false)
const error = ref('')
const selected = ref<KnowledgeGraphNode>()
const evidence = ref<{ text: string; fileName: string }>()
const question = ref('')
const asking = ref(false)
const qaError = ref('')
const answer = ref<KnowledgeGraphAnswer>()
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: false }).disable('image')
const answerHtml = computed(() => markdown.render(answer.value?.answer || ''))
let questionVersion = 0
const canvas = ref<HTMLElement>()
let chart: ECharts | undefined
let timer = 0
let version = 0
let disposed = false
let resizeObserver: ResizeObserver | undefined
let resizeFrame = 0
let evidenceVersion = 0
let displayedGraph: KnowledgeGraphView | undefined
const seriesId = 'knowledge-graph'
const relatedNodes = computed(() => {
  const row = selected.value
  if (!row || !graph.value) return []
  const ids = new Set<string>()
  for (const edge of graph.value.edges) {
    if (row.source ? edge.id === row.id : edge.source === row.id || edge.target === row.id) {
      if (edge.source) ids.add(edge.source)
      if (edge.target) ids.add(edge.target)
    }
  }
  ids.delete(row.id)
  return graph.value.nodes.filter(node => ids.has(node.id))
})

// 一次性布局，节点拖动只更新连线，不反复启动受力迭代。
function positionedNodes(view: KnowledgeGraphView) {
  const neighbours = new Map(view.nodes.map(node => [node.id, new Set<string>()]))
  for (const edge of view.edges) {
    if (edge.source && edge.target) {
      neighbours.get(edge.source)?.add(edge.target)
      neighbours.get(edge.target)?.add(edge.source)
    }
  }
  const ordered: string[] = []
  const visited = new Set<string>()
  const seeds = [...view.nodes].sort((a, b) => (neighbours.get(b.id)?.size || 0) - (neighbours.get(a.id)?.size || 0))
  for (const seed of seeds) {
    if (visited.has(seed.id)) continue
    const queue = [seed.id]
    visited.add(seed.id)
    for (let cursor = 0; cursor < queue.length; cursor++) {
      const id = queue[cursor]!
      ordered.push(id)
      for (const neighbour of neighbours.get(id) || []) {
        if (!visited.has(neighbour)) { visited.add(neighbour); queue.push(neighbour) }
      }
    }
  }
  const order = new Map(ordered.map((id, index) => [id, index]))
  return view.nodes.map(row => {
    const index = order.get(row.id) || 0
    const radius = 36 * Math.sqrt(index)
    const angle = index * 2.399963229728653
    return { id: row.id, name: row.label || row.id, x: radius * Math.cos(angle), y: radius * Math.sin(angle), record: row }
  })
}

function selection(nodes: number[], edges: number[]) {
  if (!chart || !graph.value) return
  // 使用状态动作更新亮度，不重新 setOption/布局，保留拖动位置和平移缩放。
  chart.dispatchAction({ type: 'unselect', batch: [
    { seriesId, dataType: 'node', dataIndex: graph.value.nodes.map((_, i) => i) },
    { seriesId, dataType: 'edge', dataIndex: graph.value.edges.map((_, i) => i) }
  ] })
  chart.dispatchAction({ type: 'select', batch: [
    { seriesId, dataType: 'node', dataIndex: nodes },
    { seriesId, dataType: 'edge', dataIndex: edges }
  ] })
}
function clearFocus() {
  evidenceVersion += 1
  selected.value = undefined
  evidence.value = undefined
  if (graph.value) selection(graph.value.nodes.map((_, i) => i), graph.value.edges.map((_, i) => i))
}
function focus(row: KnowledgeGraphNode) {
  const view = graph.value
  if (!view) return
  const ids = new Set<string>(row.source && row.target ? [row.source, row.target] : [row.id])
  const edges: number[] = []
  view.edges.forEach((edge, index) => {
    if (row.source ? edge.id === row.id : edge.source === row.id || edge.target === row.id) {
      if (edge.source) ids.add(edge.source)
      if (edge.target) ids.add(edge.target)
      edges.push(index)
    }
  })
  selection(view.nodes.flatMap((node, index) => ids.has(node.id) ? [index] : []), edges)
}
function zoom(factor: number) {
  if (chart) chart.dispatchAction({ type: 'graphRoam', seriesId, zoom: factor, originX: chart.getWidth() / 2, originY: chart.getHeight() / 2 })
}
function resetView() {
  chart?.setOption({ series: [{ id: seriesId, zoom: 1, center: ['50%', '50%'] }] })
}
function clearAnswer() {
  questionVersion += 1
  asking.value = false
  qaError.value = ''
  answer.value = undefined
}
async function ask() {
  if (asking.value || graph.value?.status !== 'ready') return
  const text = question.value.trim()
  if (!text) { qaError.value = '请输入要验证的问题'; return }
  clearAnswer()
  asking.value = true
  const requested = questionVersion
  const tenant = props.tenantId
  try {
    const res = await askKnowledgeGraph(tenant, text, props.folderId || 0)
    if (requested !== questionVersion || disposed || !props.modelValue || tenant !== props.tenantId) return
    if (!res.success) throw new Error(res.message || '图谱问答失败')
    answer.value = res.data
  } catch (cause) {
    if (requested === questionVersion && !disposed && props.modelValue) qaError.value = cause instanceof Error ? cause.message : '图谱问答失败'
  } finally {
    if (requested === questionVersion && !disposed) asking.value = false
  }
}
function disposeChart() {
  resizeObserver?.disconnect()
  resizeObserver = undefined
  cancelAnimationFrame(resizeFrame)
  chart?.dispose()
  chart = undefined
  displayedGraph = undefined
}

function schedule() {
  window.clearTimeout(timer)
  if (props.modelValue && graph.value?.status === 'building') timer = window.setTimeout(() => void load(), 2500)
}
async function draw() {
  await nextTick()
  if (!canvas.value || graph.value?.status !== 'ready' || !props.modelValue) return
  if (displayedGraph === graph.value && chart) return
  if (!chart) {
    chart = init(canvas.value, undefined, { renderer: 'canvas', devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2) })
    resizeObserver = new ResizeObserver(() => {
      cancelAnimationFrame(resizeFrame)
      resizeFrame = requestAnimationFrame(() => chart?.resize())
    })
    resizeObserver.observe(canvas.value)
    chart.getZr().on('click', event => { if (!event.target) clearFocus() })
  }
  chart.setOption({
    animation: false,
    stateAnimation: { duration: 0 },
    tooltip: { renderMode: 'richText' },
    series: [{
      id: seriesId, type: 'graph', layout: 'none', roam: true, roamTrigger: 'global', draggable: true,
      symbolSize: Math.max(10, 26 - Math.sqrt(graph.value.nodes.length) * 0.7),
      selectedMode: 'multiple', scaleLimit: { min: 0.15, max: 6 }, zoom: 1,
      label: { show: true, position: 'right', color: '#303133', fontSize: 12, width: 140, overflow: 'truncate', textBorderColor: '#fff', textBorderWidth: 2, opacity: 0.12 },
      itemStyle: { color: '#5470c6', opacity: 0.12 },
      edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 7,
      lineStyle: { color: '#9caec9', curveness: 0.12, opacity: 0.08 },
      emphasis: { disabled: true },
      select: { itemStyle: { opacity: 1, borderWidth: 0 }, label: { opacity: 1 }, lineStyle: { opacity: 0.85, width: 1.5 } },
      data: positionedNodes(graph.value),
      links: graph.value.edges.map(row => ({ id: row.id, name: `edge:${row.id}`, source: row.source, target: row.target, record: row }))
    }]
  }, true)
  displayedGraph = graph.value
  clearFocus()
  chart.off('click')
  chart.on('click', event => { const data = event.data as { record?: KnowledgeGraphNode } | undefined; if (data?.record) select(data.record) })
  chart.resize()
}
function select(row: KnowledgeGraphNode) {
  selected.value = row
  evidence.value = undefined
  focus(row)
  const id = row.evidenceIds?.[0]
  if (id) void proof(id)
}
async function proof(id: string) {
  error.value = ''
  const requested = ++evidenceVersion
  const requestedTenant = props.tenantId
  try {
    const res = await getKnowledgeGraphEvidence(requestedTenant, id, props.folderId || 0)
    if (requested !== evidenceVersion || disposed || !props.modelValue || requestedTenant !== props.tenantId) return
    if (!res.success) throw new Error(res.message || '原文加载失败')
    evidence.value = res.data
  } catch (cause) {
    if (requested === evidenceVersion && !disposed && props.modelValue) error.value = cause instanceof Error ? cause.message : '原文加载失败'
  }
}
async function load() {
  if (!props.modelValue || !props.tenantId || disposed || building.value) return
  const requested = ++version
  loading.value = true
  error.value = ''
  try {
    const res = await getKnowledgeGraph(props.tenantId, props.folderId || 0)
    if (!res.success) throw new Error(res.message || '图谱加载失败')
    if (requested !== version || disposed) return
    if (!displayedGraph || JSON.stringify(res.data) !== JSON.stringify(displayedGraph)) {
      clearAnswer()
      graph.value = res.data
      if (res.data.status === 'ready') await draw()
      else { clearFocus(); disposeChart() }
    }
    schedule()
  } catch (cause) {
    if (requested === version && !disposed) error.value = cause instanceof Error ? cause.message : '图谱加载失败'
  } finally {
    if (requested === version && !disposed) loading.value = false
  }
}
async function build() {
  if (!props.canBuild || building.value) return
  building.value = true
  clearAnswer()
  loading.value = false
  window.clearTimeout(timer)
  const requested = ++version
  error.value = ''
  try {
    const res = await buildKnowledgeGraph(props.tenantId, props.folderId || 0)
    if (requested !== version || disposed || !props.modelValue) return
    if (!res.success) throw new Error(res.message || '建图失败')
    graph.value = res.data
    if (res.data.status === 'ready') await draw()
    else { clearFocus(); disposeChart() }
    schedule()
  } catch (cause) {
    if (requested === version && !disposed && props.modelValue) error.value = cause instanceof Error ? cause.message : '建图失败'
  } finally {
    if (requested === version && !disposed) building.value = false
  }
}
function close() {
  version += 1
  evidenceVersion += 1
  clearAnswer()
  question.value = ''
  disposeChart()
  window.clearTimeout(timer)
  loading.value = false
  building.value = false
  graph.value = undefined
  selected.value = undefined
  evidence.value = undefined
  error.value = ''
}
watch(()=>[props.tenantId,props.folderId],()=>{close();if(props.modelValue)void load()})
onBeforeUnmount(() => { disposed = true; close() })
</script>
<style scoped>
:global(.knowledge-graph-dialog) { max-width: 1800px; max-height: 94vh; display: flex; flex-direction: column; }
:global(.knowledge-graph-dialog .el-dialog__body) { min-height: 0; overflow-y: auto; }
.graph-workspace { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 20px; align-items: start; }
.graph-main, .graph-qa { min-width: 0; }
.graph-qa { padding: 16px; border: 1px solid var(--el-border-color-light); border-radius: 8px; }
.graph-qa h3 { margin: 0 0 8px; }
.graph-qa > .el-button { margin: 12px 0; }
.asked-question { font-weight: 600; overflow-wrap: anywhere; }
.answer-content { line-height: 1.7; overflow-wrap: anywhere; }
.answer-content :deep(table) { width: 100%; border-collapse: collapse; }
.answer-content :deep(td), .answer-content :deep(th) { border: 1px solid var(--el-border-color); padding: 6px; }
.qa-context { max-height: 420px; overflow: auto; overflow-wrap: anywhere; }
.qa-context p { margin: 6px 0; }
@media (max-width: 1100px) { .graph-workspace { grid-template-columns: minmax(0, 1fr); } }
.graph-tools { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 12px 0; }
.graph-canvas { width: 100%; height: clamp(460px, 66vh, 900px); touch-action: none; overscroll-behavior: contain; }
.graph-hint { color: var(--el-text-color-secondary); font-size: 12px; margin: 0 0 8px; }
.related-nodes { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 8px; }
.evidence { margin-top: 12px; padding: 12px; background: var(--el-fill-color-light); overflow-wrap: anywhere; }
.evidence h3, .documents h3 { margin: 0 0 8px; font-size: 14px; }
.documents ul { margin: 8px 0 0; padding-left: 18px; }
pre { white-space: pre-wrap; max-height: 220px; overflow: auto; }
.el-alert { margin-bottom: 12px; }
</style>
