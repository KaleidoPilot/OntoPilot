import MarkdownIt from 'markdown-it'

export type ExportFormat = 'md' | 'word' | 'pdf'

const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true })

// 导出用的版式：A4、中文优先字体、表格斑马纹，并尽量避免标题和表格被分页切断
const DOCUMENT_STYLES = `
  @page { size: A4; margin: 18mm 16mm; }
  body { margin: 0 auto; max-width: 820px; padding: 28px 32px 40px; color: #1f2d3d;
    font-family: "Microsoft YaHei", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    font-size: 14px; line-height: 1.75; background: #fff; }
  h1 { font-size: 24px; margin: 0 0 8px; padding-bottom: 12px; border-bottom: 2px solid #e5e9f2; }
  h2 { font-size: 19px; margin: 26px 0 12px; padding-left: 10px; border-left: 4px solid #4a6cf7; }
  h3 { font-size: 16px; margin: 20px 0 10px; }
  h4 { font-size: 14px; margin: 16px 0 8px; }
  p { margin: 0 0 12px; }
  ul, ol { margin: 0 0 12px; padding-left: 22px; }
  li { margin: 4px 0; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0 18px; font-size: 13px; }
  thead th { background: #eef2ff; color: #22315a; font-weight: 600; }
  th, td { border: 1px solid #d6dce8; padding: 8px 10px; text-align: left; vertical-align: top; }
  tbody tr:nth-child(even) { background: #fafbfe; }
  blockquote { margin: 12px 0; padding: 8px 14px; border-left: 3px solid #4a6cf7; background: #f7f9ff; color: #4e5d78; }
  code { font-family: Consolas, "Courier New", monospace; font-size: 12px; background: #f4f6fa; padding: 1px 5px; border-radius: 4px; }
  pre { background: #f4f6fa; border-radius: 8px; padding: 12px 14px; overflow-x: auto; }
  pre code { background: transparent; padding: 0; }
  a { color: #2b5cff; word-break: break-all; }
  img { max-width: 100%; }
  hr { border: none; border-top: 1px solid #e5e9f2; margin: 22px 0; }
  h2, h3, h4 { page-break-after: avoid; }
  tr, img, blockquote, pre { page-break-inside: avoid; }
  @media print { body { max-width: none; padding: 0; } }
`

/**
 * 导出回答内容。
 * - md：保留原始 Markdown
 * - word：把 Markdown 转成带样式的 HTML，按 .doc 保存，Word 能直接打开并保留表格样式
 * - pdf：打开带打印样式的预览窗口，走浏览器“另存为 PDF”，文字保持矢量清晰
 */
export function exportAnswerDocument(content: string, format: ExportFormat) {
  // 历史消息里可能残留“正在生成”这类过程提示，导出前先剔除
  const body = stripStatusLines(content)
  // 文件名统一用当前时间戳，避免标题里的特殊字符影响下载
  const fileBase = timestamp()
  if (format === 'md') {
    triggerDownload(new Blob([body], { type: 'text/markdown;charset=utf-8' }), `${fileBase}.md`)
    return
  }

  const html = buildHtml(fileBase, markdown.render(body), format === 'word')

  if (format === 'word') {
    // 加 BOM，避免部分 Word 版本把中文识别成乱码
    triggerDownload(new Blob(['\ufeff', html], { type: 'application/msword;charset=utf-8' }), `${fileBase}.doc`)
    return
  }
  printPdf(html, fileBase)
}

function buildHtml(title: string, body: string, forWord: boolean) {
  // 这段 Word 命名空间声明能避免 Word 走“兼容模式”，排版更稳定
  const wordHeader = forWord
    ? '<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom></w:WordDocument></xml><![endif]-->'
    : ''
  return '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
    + `<title>${escapeHtml(title)}</title>${wordHeader}`
    + `<style>${DOCUMENT_STYLES}</style></head><body>`
    + `${body}</body></html>`
}

function printPdf(html: string, title: string) {
  const win = window.open('', '_blank', 'width=900,height=720')
  if (!win) throw new Error('浏览器拦截了导出窗口，请允许弹出窗口后重试')
  win.document.open()
  win.document.write(html)
  win.document.close()
  win.document.title = title
  const start = () => setTimeout(() => { win.focus(); win.print() }, 300)
  // 等图片等资源加载完再唤起打印，避免 PDF 里出现空白图
  if (win.document.readyState === 'complete') start()
  else win.addEventListener('load', start, { once: true })
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// 去掉“⏳ 正在生成…”这类过程提示，只保留最终报告内容
function stripStatusLines(content: string) {
  return content
    .split('\n')
    .filter(line => !/^[⏳🔄]/.test(line.trim()))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function timestamp() {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`
}

function escapeHtml(text: string) {
  return text.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char] || char)
}
