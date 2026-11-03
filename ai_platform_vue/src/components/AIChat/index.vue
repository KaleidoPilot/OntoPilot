<template>
  <div class="ai-chat-container" ref="chatContainer">
    <!-- Floating Tab Button -->
    <div class="chat-trigger-btn" @click.stop="isOpen = !isOpen" :class="{ 'is-open': isOpen }">
      <div class="btn-content">
        <el-icon class="main-icon">
          <ChatLineRound v-if="!isOpen" />
          <Close v-else />
        </el-icon>
        <span class="btn-text">{{ isOpen ? '关闭助手' : '智能助手' }}</span>
      </div>
    </div>

    <!-- Chat Drawer -->
    <el-drawer
      v-model="isOpen"
      direction="rtl"
      size="800px"
      :with-header="true"
      :show-close="false"
      class="ai-chat-drawer"
      :modal="false"
      :lock-scroll="false"
      append-to-body
      @mousedown.stop
    >
      <template #header>
        <div class="drawer-header">
          <span class="title">智能助手</span>
          <el-button link class="clear-btn" @click="clearChat">
            <el-icon><Delete /></el-icon>
            清空对话
          </el-button>
        </div>
      </template>
      <div class="chat-wrapper">
        <div class="chat-messages" ref="messageContainer">
          <div v-for="(msg, index) in messages" :key="index" :class="['message-item', msg.role]">
            <div class="avatar">
              <el-icon v-if="msg.role === 'assistant'"><Avatar /></el-icon>
              <el-icon v-else><User /></el-icon>
            </div>
            <div class="message-content">
              <div v-if="msg.role === 'assistant'" class="assistant-content-wrapper">
                <div v-if="msg.content">
                  <div v-html="renderMarkdown(msg.content)" class="markdown-body"></div>
                  <div class="msg-actions" v-if="!loading || index !== messages.length - 1">
                    <el-button link size="small" @click="exportToWord(msg.content)">
                      <el-icon><Download /></el-icon> 导出为 Word
                    </el-button>
                  </div>
                </div>
                <div v-else class="typing-loader">
                  <span></span><span></span><span></span>
                </div>
              </div>
              <div v-else class="user-text">
                <div v-if="msg.imageUrl" class="msg-image">
                  <el-image :src="msg.imageUrl" :preview-src-list="[msg.imageUrl]" fit="contain" />
                </div>
                <div v-if="msg.fileName" class="msg-file">
                  <el-icon><Document /></el-icon>
                  <span>{{ msg.fileName }}</span>
                </div>
                {{ msg.content }}
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <!-- Image Preview -->
          <div class="image-preview" v-if="uploadedImageUrl">
            <el-image 
              :src="uploadedImageUrl" 
              fit="cover" 
              class="preview-img"
              :preview-src-list="[uploadedImageUrl]"
            />
            <el-button class="remove-img" circle size="small" @click="removeImage">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>

          <!-- File Preview -->
          <div class="file-preview" v-if="uploadedFileUrl">
            <div class="file-info">
              <el-icon class="file-icon"><Document /></el-icon>
              <span class="file-name" :title="uploadedFileName">{{ uploadedFileName }}</span>
            </div>
            <el-button class="remove-file" circle size="small" @click="removeFile">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>

          <div class="feature-toolbar">
            <el-tooltip content="发送附件" placement="top">
              <el-button 
                link 
                class="tool-btn" 
                @click="handleAttachment" 
                :loading="fileUploading"
                :disabled="!!uploadedImageUrl || !!uploadedFileUrl"
              >
                <el-icon><Paperclip /></el-icon>
              </el-button>
            </el-tooltip>
            <input 
              type="file" 
              ref="fileInput" 
              style="display: none" 
              @change="onFileSelect"
            />
            <el-tooltip content="图片识别" placement="top">
              <el-button 
                link 
                class="tool-btn" 
                @click="handleOCR" 
                :loading="imageUploading"
                :disabled="!!uploadedImageUrl || !!uploadedFileUrl"
              >
                <el-icon><Picture /></el-icon>
              </el-button>
            </el-tooltip>
            <input 
              type="file" 
              ref="imageInput" 
              style="display: none" 
              accept="image/*"
              @change="onImageSelect"
            />
          </div>
          <el-input
            v-model="inputMsg"
            type="textarea"
            :rows="3"
            placeholder="请输入您的问题... (Ctrl + Enter 发送)"
            @keydown.enter.ctrl.prevent="sendMessage()"
            resize="none"
          />
          <div class="input-actions">
            <span class="hint">按 Ctrl + Enter 发送</span>
            <el-button type="primary" :loading="loading" @click="sendMessage()">发送</el-button>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { ChatLineRound, Close, Avatar, User, Paperclip, Picture, Delete, Document, Download } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { ElMessage } from 'element-plus'
import { chatBotStream } from '@/api/contract'
import axios from 'axios'
import { asBlob } from 'html-docx-js-typescript'
import { saveAs } from 'file-saver'

// Set marked options for better formatting
marked.setOptions({
  breaks: true,
  gfm: true
})

const isOpen = ref(false)
const inputMsg = ref('')
const loading = ref(false)
const messageContainer = ref<HTMLElement | null>(null)
const chatContainer = ref<HTMLElement | null>(null)
const sessionId = ref('') // Store session_id for multi-turn chat

// Image Upload Logic
const imageInput = ref<HTMLInputElement | null>(null)
const uploadedImageUrl = ref('')
const imageUploading = ref(false)

const handleOCR = () => {
  if (imageUploading.value || fileUploading.value || uploadedImageUrl.value || uploadedFileUrl.value) return
  imageInput.value?.click()
}

const onImageSelect = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }

  const formData = new FormData()
  formData.append('file', file)
  formData.append('modular', 'AIRPROT0001')
  formData.append('tenant', 'AIRPROT')
  formData.append('orgCode', 'AIRPROT')

  imageUploading.value = true
  try {
    const uploadUrl = import.meta.env.VITE_APP_UPLOAD_URL
    const response = await axios.post(uploadUrl, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    
    if (response.data?.code === "1") {
      const url = response.data?.data?.filePath
      if (url) {
        uploadedImageUrl.value = url.trim()
        removeFile() // Only one attachment at a time
        ElMessage.success('图片上传成功，可发送进行识别')
      } else {
        throw new Error('未获取到图片链接')
      }
    } else {
      throw new Error(response.data?.msg || '上传失败')
    }
  } catch (error: any) {
    console.error('Image upload error:', error)
    ElMessage.error(error.message || '图片上传失败')
  } finally {
    imageUploading.value = false
    if (imageInput.value) imageInput.value.value = ''
  }
}

// Remove file logic
const removeFile = () => {
  uploadedFileUrl.value = ''
  uploadedFileName.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

const removeImage = () => {
  uploadedImageUrl.value = ''
  if (imageInput.value) imageInput.value.value = ''
}
const fileInput = ref<HTMLInputElement | null>(null)
const uploadedFileUrl = ref('')
const uploadedFileName = ref('')
const fileUploading = ref(false)

const handleAttachment = () => {
  if (fileUploading.value || imageUploading.value || uploadedImageUrl.value || uploadedFileUrl.value) return
  fileInput.value?.click()
}

const onFileSelect = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)
  formData.append('modular', 'AIRPROT0001')
  formData.append('tenant', 'AIRPROT')
  formData.append('orgCode', 'AIRPROT')

  fileUploading.value = true
  try {
    const uploadUrl = import.meta.env.VITE_APP_UPLOAD_URL
    const response = await axios.post(uploadUrl, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    
    if (response.data?.code === "1") {
      const url = response.data?.data?.filePath
      if (url) {
        uploadedFileUrl.value = url.trim()
        uploadedFileName.value = file.name
        removeImage() // Only one attachment at a time
        ElMessage.success('附件上传成功，可发送进行对话')
      } else {
        throw new Error('未获取到文件链接')
      }
    } else {
      throw new Error(response.data?.msg || '上传失败')
    }
  } catch (error: any) {
    console.error('File upload error:', error)
    ElMessage.error(error.message || '附件上传失败')
  } finally {
    fileUploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}
// const removeFile = () => {
//   uploadedFileUrl.value = ''
//   uploadedFileName.value = ''
// }

// Click outside logic
const handleClickOutside = (event: MouseEvent) => {
  if (!isOpen.value) return
  
  // Check if click is on the drawer itself (since it's appended to body)
  const drawerEl = document.querySelector('.ai-chat-drawer')
  if (drawerEl && drawerEl.contains(event.target as Node)) {
    return
  }

  // Check if click is on the trigger button
  if (chatContainer.value && chatContainer.value.contains(event.target as Node)) {
    return
  }

  isOpen.value = false
}

onMounted(() => {
  window.addEventListener('mousedown', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('mousedown', handleClickOutside)
})

interface Message {
  role: 'user' | 'assistant'
  content: string
  imageUrl?: string
  fileName?: string
}

const messages = ref<Message[]>([
  { role: 'assistant', content: '您好！我是您的 AI 智能助手。有什么我可以帮您的吗？' }
])

const escapeSingleTilde = (text: string) => {
  return text.replace(/(^|[^~])~([^~]|$)/g, '$1\\~$2')
}

const fixMarkdownTable = (markdown: string) => {
  const lines = markdown.split('\n')
  let inTable = false
  const fixedLines: string[] = []
  let currentMaxCols = 0

  for (let i = 0; i < lines.length; i++) {
    const originalLine = lines[i]
    const currentLine = originalLine.trim()

    if (currentLine.startsWith('|')) {
      const cols = currentLine.split('|').filter((_, index, arr) => index > 0 && index < arr.length - 1)
      const numCols = cols.length

      if (!inTable) {
        inTable = true
        currentMaxCols = numCols
        const headerCols = cols.map(c => c.trim() || ' ')
        
        // 尝试修正列数对齐
        if (headerCols.length < currentMaxCols) {
          const diff = currentMaxCols - headerCols.length
          const insertPos = Math.max(1, headerCols.length - 1)
          for (let k = 0; k < diff; k++) {
            headerCols.splice(insertPos, 0, ' ')
          }
        }
        fixedLines.push('|' + headerCols.join('|') + '|')
        
        const nextLine = lines[i + 1]?.trim()
        const isSeparator = nextLine && nextLine.startsWith('|') && nextLine.endsWith('|') && nextLine.includes('---')
        
        const separator = '|' + new Array(currentMaxCols).fill('---').join('|') + '|'
        fixedLines.push(separator)
        
        if (isSeparator) {
          i++
        }
      } else {
        if (currentLine.includes('---') && fixedLines[fixedLines.length - 1].startsWith('|')) {
          continue
        } else {
          fixedLines.push(originalLine)
        }
      }
    } else {
      inTable = false
      fixedLines.push(originalLine)
    }
  }
  return fixedLines.join('\n')
}

const renderMarkdown = (content: string) => {
  if (!content) return ''
  
  const safeText = escapeSingleTilde(content)
  const fixedText = fixMarkdownTable(safeText)
  
  const html = marked.parse(fixedText, { async: false }) as string
  
  // 利用 DOMParser 处理合并单元格 (rowspan / colspan)
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  
  const tables = doc.querySelectorAll('table')
  tables.forEach(table => {
    // 1. 处理表头的 colspan (合并空的 th)
    const thead = table.querySelector('thead')
    if (thead) {
      const headerRows = Array.from(thead.querySelectorAll('tr'))
      headerRows.forEach(row => {
        const cells = Array.from(row.querySelectorAll('th'))
        for (let i = cells.length - 1; i > 0; i--) {
          const cell = cells[i]
          if (!cell.textContent?.trim()) {
            const prevCell = cells[i - 1]
            if (prevCell) {
              const currentCellColSpan = parseInt(cell.getAttribute('colspan') || '1', 10)
              const prevColSpan = parseInt(prevCell.getAttribute('colspan') || '1', 10)
              prevCell.setAttribute('colspan', (prevColSpan + currentCellColSpan).toString())
              cell.remove()
            }
          }
        }
      })
    }

    // 2. 初始化 colMaster
    const colMaster: { [key: number]: HTMLTableCellElement } = {}
    let maxCols = 0
    if (thead) {
      const lastHeaderRow = thead.querySelectorAll('tr')[thead.querySelectorAll('tr').length - 1]
      if (lastHeaderRow) {
        let logicalCol = 0
        Array.from(lastHeaderRow.children).forEach((cell) => {
          const colspan = parseInt(cell.getAttribute('colspan') || '1', 10)
          for (let k = 0; k < colspan; k++) {
            colMaster[logicalCol++] = cell as HTMLTableCellElement
          }
        })
        maxCols = logicalCol
      }
    }

    // 3. 处理 tbody 的 rowspan
    const tbody = table.querySelector('tbody')
    if (tbody) {
      const rows = Array.from(tbody.querySelectorAll('tr'))
      rows.forEach(row => {
        const cells = Array.from(row.children) as HTMLTableCellElement[]
        
        if (cells.length === 1 && maxCols > 1) {
          cells[0].setAttribute('colspan', maxCols.toString())
          return
        }
        
        let logicalCol = 0
        for (let i = 0; i < cells.length; i++) {
          const cell = cells[i]
          
          // Skip columns that are currently covered by a rowspan from above
          while (colMaster[logicalCol] && colMaster[logicalCol].rowSpan > 1) {
            colMaster[logicalCol].rowSpan--
            logicalCol++
          }
          
          const text = cell.textContent?.trim()
          if (!text) {
            let prevRowLogicalCol = logicalCol
            let foundMaster = false
            // 向上寻找可以合并的非空单元格
            for (let r = rows.indexOf(row) - 1; r >= 0; r--) {
              const prevRow = rows[r]
              const prevRowCells = Array.from(prevRow.children) as HTMLTableCellElement[]
              let currentLogical = 0
              for (const prCell of prevRowCells) {
                if (currentLogical === prevRowLogicalCol) {
                  // 如果找到的上一行单元格也是空的，不要合并它，继续往上找
                  if (!prCell.textContent?.trim() && prCell.rowSpan === 1) {
                    break // 这个单元格也是空的且没有向下合并，无法作为 master
                  }
                  
                  const currentSpan = parseInt(prCell.getAttribute('rowspan') || '1', 10)
                  prCell.setAttribute('rowspan', (currentSpan + 1).toString())
                  colMaster[logicalCol] = prCell
                  cell.remove()
                  foundMaster = true
                  break
                }
                currentLogical += parseInt(prCell.getAttribute('colspan') || '1', 10)
              }
              if (foundMaster) break
            }
          }
          
          // Only increment logicalCol if the cell wasn't removed (or if we want to track its original space)
          // Actually, we must always increment by the cell's colspan to keep logical columns aligned
          logicalCol += parseInt(cell.getAttribute('colspan') || '1', 10)
        }
      })
    }
  })
  
  return doc.body.innerHTML
}

const exportToWord = async (markdownContent: string) => {
  try {
    ElMessage.info('正在生成 Word 文档...')
    
    // 1. Get HTML from markdown (use the same render logic to keep tables intact)
    const htmlContent = renderMarkdown(markdownContent)
    
    // 2. Wrap HTML with standard Word document structure and basic styles
    const fullHtml = `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8">
          <title>AI 助手报告</title>
          <style>
            body { font-family: "Microsoft YaHei", SimSun, sans-serif; font-size: 11pt; line-height: 1.5; }
            table { border-collapse: collapse; width: 100%; margin: 10px 0; }
            th, td { border: 1px solid #000000; padding: 5px; text-align: left; }
            th { background-color: #f2f2f2; font-weight: bold; }
            h1, h2, h3, h4, h5, h6 { font-family: "Microsoft YaHei", SimSun, sans-serif; font-weight: bold; margin-top: 15px; margin-bottom: 10px; }
            h1 { font-size: 16pt; }
            h2 { font-size: 14pt; }
            h3 { font-size: 12pt; }
            p { margin-bottom: 10px; }
          </style>
        </head>
        <body>
          ${htmlContent}
        </body>
      </html>
    `

    // 3. Convert HTML to Word Blob
    const blob = await asBlob(fullHtml, {
      orientation: 'portrait',
      margins: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
    })
    
    // 4. Trigger download
    const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)
    saveAs(blob as Blob, `AI助手对话记录_${timestamp}.docx`)
    
    ElMessage.success('Word 文档导出成功')
  } catch (error) {
    console.error('Export to Word error:', error)
    ElMessage.error('导出 Word 文档失败')
  }
}

const clearChat = () => {
  messages.value = [
    { role: 'assistant', content: '对话已清空。我是您的 AI 智能助手，请问有什么可以帮您的吗？' }
  ]
  sessionId.value = ''
  ElMessage.success('对话已重置')
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight
  }
}

const sendMessage = async () => {
  if (!inputMsg.value.trim() && !uploadedImageUrl.value && !uploadedFileUrl.value) return
  if (loading.value || imageUploading.value || fileUploading.value) return

  loading.value = true 

  // Determine type and content BEFORE clearing
  const isImageMode = !!uploadedImageUrl.value
  const isFileMode = !!uploadedFileUrl.value
  const type = isImageMode ? 'image' : 'chat'
  const fileUrls = isImageMode ? uploadedImageUrl.value : (isFileMode ? uploadedFileUrl.value : "")
  const currentFileName = isFileMode ? uploadedFileName.value : ""
  
  const userContent = inputMsg.value || (isImageMode ? '进行图片识别' : (isFileMode ? `分析附件: ${currentFileName}` : ''))
  
  messages.value.push({ 
    role: 'user', 
    content: userContent,
    imageUrl: isImageMode ? uploadedImageUrl.value : undefined,
    fileName: isFileMode ? currentFileName : undefined
  })
  
  inputMsg.value = ''
  
  // Clear attachments IMMEDIATELY from UI after reading their values
  if (isImageMode) removeImage()
  if (isFileMode) removeFile()
  
  await scrollToBottom()

  // Add an empty assistant message to be filled by the stream
  messages.value.push({ role: 'assistant', content: '' })
  const assistantMsgIndex = messages.value.length - 1

  try {
    const response = await chatBotStream({
      session_id: sessionId.value || null,
      query: userContent,
      file_urls: fileUrls,
      type: type
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('ReadableStream not supported')
    }

    const decoder = new TextDecoder()
    let partialData = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      partialData += chunk

      // Split by 'data: ' prefix for SSE
      const lines = partialData.split('\n')
      // Keep the last line in partialData if it's incomplete
      partialData = lines.pop() || ''

      for (const line of lines) {
        const trimmedLine = line.trim()
        if (!trimmedLine || !trimmedLine.startsWith('data:')) continue

        const dataStr = trimmedLine.replace('data:', '').trim()
        if (dataStr === '[DONE]') continue

        try {
          const jsonData = JSON.parse(dataStr)
          
          if (jsonData.session_id) {
            sessionId.value = jsonData.session_id
          }

          const content = jsonData.choices?.[0]?.delta?.content
          if (content) {
            messages.value[assistantMsgIndex].content += content
            await scrollToBottom()
          }
        } catch (e) {
          console.error('Error parsing stream JSON:', e, dataStr)
        }
      }
    }
  } catch (error) {
    console.error('Chat stream error:', error)
    messages.value[assistantMsgIndex].content = '抱歉，服务出现异常，请稍后再试。'
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}
</script>

<style lang="scss" scoped>
.ai-chat-container {
  position: fixed;
  z-index: 3000;
}

.chat-trigger-btn {
  position: fixed;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  background: #D79B45; /* Golden/Mustard color from Image 1 */
  color: #fff;
  width: 42px;
  padding: 20px 0;
  border-radius: 16px 0 0 16px;
  cursor: pointer;
  box-shadow: -4px 0 15px rgba(0, 0, 0, 0.15);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 3001;

  &:hover {
    background: #c68a35;
    transform: translateY(-50%) translateX(-2px);
  }

  &.is-open {
    right: 800px; /* Match drawer size */
  }

  .btn-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }

  .main-icon {
    font-size: 24px;
    margin-bottom: 4px;
  }

  .btn-text {
    writing-mode: vertical-rl;
    font-size: 15px;
    letter-spacing: 4px;
    font-weight: 600;
    text-transform: uppercase;
  }
}

:deep(.el-overlay) {
  pointer-events: none; // Allow clicks to pass through to the background
  background: transparent !important; // Hide any mask
}

:deep(.ai-chat-drawer) {
  pointer-events: auto; // Re-enable pointer events for the drawer itself
  box-shadow: -10px 0 30px rgba(0,0,0,0.1);

  .el-drawer__header {
    margin-bottom: 0;
    padding: 0; // Reset padding to use custom drawer-header
    border-bottom: 1px solid var(--border-color, #e4e7ed);
    background: #fff;
    .el-drawer__title {
      display: none; // Hide default title
    }
  }
  .el-drawer__body {
    padding: 0;
  }
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  width: 100%;
  
  .title {
    font-weight: 600;
    font-size: 18px;
    color: var(--text-primary, #303133);
  }

  .clear-btn {
    font-size: 13px;
    color: var(--text-secondary, #909399);
    display: flex;
    align-items: center;
    gap: 4px;
    
    &:hover {
      color: #f56c6c;
    }
    
    .el-icon {
      font-size: 14px;
    }
  }
}

.chat-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #f8f9fb;
  scroll-behavior: smooth;

  .message-item {
    display: flex;
    margin-bottom: 28px;
    gap: 14px;

    .avatar {
      width: 40px;
      height: 40px;
      border-radius: 12px;
      background: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 10px rgba(0,0,0,0.05);
      flex-shrink: 0;
      
      .el-icon {
        font-size: 22px;
      }
    }

    .message-content {
      max-width: 80%;
      padding: 14px 20px;
      border-radius: 18px;
      font-size: 14.5px;
      line-height: 1.6;
      position: relative;
    }

    .assistant-content-wrapper {
    width: 100%;

    .msg-actions {
      display: flex;
      justify-content: flex-end;
      margin-top: 8px;
      border-top: 1px dashed rgba(0,0,0,0.05);
      padding-top: 8px;

      .el-button {
        color: var(--text-secondary);
        font-size: 13px;

        &:hover {
          color: var(--primary-color);
        }
      }
    }
  }

  &.assistant {
      .avatar {
        background: linear-gradient(135deg, #D79B45, #e6a23c);
        .el-icon { color: #fff; }
      }
      .message-content {
        background: #fff;
        color: var(--text-primary, #303133);
        border-top-left-radius: 4px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04);
        border: 1px solid #f0f0f0;
      }
    }

    &.user {
      flex-direction: row-reverse;
      .avatar {
        background: linear-gradient(135deg, var(--accent-color, #409eff), #66b1ff);
        .el-icon { color: #fff; }
      }
      .message-content {
        background: var(--accent-color, #409eff);
        color: #fff;
        border-top-right-radius: 4px;
        box-shadow: 0 4px 20px rgba(64, 158, 255, 0.15);
      }
    }
  }
}

.chat-input-area {
  padding: 16px 24px 24px;
  border-top: 1px solid var(--border-color, #e4e7ed);
  background: #fff;

  .image-preview {
    display: inline-block;
    position: relative;
    margin-bottom: 12px;
    
    .preview-img {
      width: 80px;
      height: 80px;
      border-radius: 8px;
      border: 1px solid var(--border-color);
      box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    .remove-img {
      position: absolute;
      top: -8px;
      right: -8px;
      background: #f56c6c;
      color: #fff;
      border: none;
      padding: 4px;
      
      &:hover {
        background: #f78989;
      }
    }
  }

  .file-preview {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: #f4f4f5;
    border-radius: 8px;
    margin-bottom: 12px;
    border: 1px solid var(--border-color);
    max-width: 300px;

    .file-info {
      display: flex;
      align-items: center;
      gap: 8px;
      overflow: hidden;

      .file-icon {
        font-size: 18px;
        color: var(--primary-color);
      }

      .file-name {
        font-size: 13px;
        color: var(--text-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }

    .remove-file {
      background: #f56c6c;
      color: #fff;
      border: none;
      padding: 4px;
      flex-shrink: 0;
      
      &:hover {
        background: #f78989;
      }
    }
  }

  .feature-toolbar {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
    
    .tool-btn {
      padding: 6px;
      font-size: 20px;
      color: var(--text-secondary, #909399);
      transition: all 0.2s;
      
      &:hover {
        color: var(--primary-color, #e6a23c);
        background: #fff8f0;
        border-radius: 6px;
      }
    }
  }

  .el-textarea {
    :deep(.el-textarea__inner) {
      border: none;
      padding: 0;
      box-shadow: none;
      font-size: 14px;
      &:focus {
        box-shadow: none;
      }
    }
  }

  .input-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 15px;

    .hint {
      font-size: 12px;
      color: var(--text-secondary, #909399);
    }

    .el-button {
      padding: 8px 24px;
      border-radius: 8px;
      font-weight: 500;
    }
  }
}

.typing-loader {
  display: flex;
  gap: 5px;
  padding: 8px 0;
  span {
    width: 8px;
    height: 8px;
    background: var(--primary-color, #e6a23c);
    border-radius: 50%;
    opacity: 0.4;
    animation: typing 1s infinite ease-in-out;
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
}

@keyframes typing {
  0%, 100% { transform: translateY(0); opacity: 0.4; }
  50% { transform: translateY(-6px); opacity: 1; }
}

:deep(.markdown-body) {
  p { margin: 0 0 12px 0; }
  p:last-child { margin-bottom: 0; }
  ul, ol { padding-left: 20px; margin-bottom: 12px; }
  li { margin-bottom: 4px; }
  
  h1, h2, h3, h4, h5, h6 {
    margin: 16px 0 8px 0;
    font-weight: 600;
    line-height: 1.25;
  }
  
  h3 { font-size: 1.25em; }

  code {
    background: #f3f4f6;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Fira Code', monospace;
    font-size: 0.9em;
    color: #d63384;
  }
  
  pre {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 16px;
    border-radius: 10px;
    overflow-x: auto;
    margin: 12px 0;
    box-shadow: inset 0 2px 10px rgba(0,0,0,0.2);
    
    code {
      background: transparent;
      padding: 0;
      color: inherit;
      font-size: 13px;
    }
  }

  a {
    color: var(--accent-color, #409eff);
    text-decoration: none;
    &:hover {
      text-decoration: underline;
    }
  }

  blockquote {
    margin: 12px 0;
    padding: 0 1em;
    color: #6a737d;
    border-left: 0.25em solid #dfe2e5;
  }

  /* Table styling for markdown */
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    overflow-x: auto;
    display: block;
    
    th, td {
      border: 1px solid var(--border-color, #e4e7ed);
      padding: 8px 12px;
      text-align: left;
    }
    
    th {
      background-color: #f5f7fa;
      font-weight: 600;
    }
    
    td {
      background-color: #ffffff;
    }
  }
}

.user-text {
  white-space: pre-wrap;
  word-break: break-word;

  .msg-image {
    margin-bottom: 8px;
    max-width: 200px;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.2);
  }

  .msg-file {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: rgba(255,255,255,0.15);
    border-radius: 6px;
    margin-bottom: 8px;
    font-size: 13px;
    border: 1px solid rgba(255,255,255,0.2);

    .el-icon {
      font-size: 16px;
    }
  }
}
</style>
