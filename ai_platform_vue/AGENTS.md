# AGENTS.md

## 项目概述

`ai-report-vue` 是一个基于 Vue 3 + TypeScript + Vite 的单页应用（SPA）。项目起源于“AI Report - 检测合同管理”，但在当前代码中，登录页与侧边栏已重新包装为“图图小知 · 智慧中枢 · 黄浦区图书馆”主题；`/csgl` 页面目前展示的是图书（藏书库）管理表格，使用本地 Mock 数据。`src/api/contract/` 中仍保留原检测合同相关的 AI/Excel/OCR/流式对话接口，但当前默认 UI 并未调用。

## 技术栈

- **核心框架**：Vue 3（Composition API + `<script setup>`）、TypeScript 5、Vite 5
- **UI 组件库**：Element Plus 2（完整引入，非自动导入）
- **状态管理**：Pinia 2（已在 `main.ts` 中挂载，但当前项目没有自定义 store）
- **路由**：Vue Router 4，使用 `createWebHashHistory`（hash 模式）
- **图表**：ECharts 6 + `vue-echarts` 8，采用手动 `use([...])` 按需注册
- **HTTP**：axios 1.x（`src/util/request.ts` 封装）
- **样式**：SCSS / Sass，`vite.config.ts` 中设置 `api: 'modern-compiler'`
- **富文本/文档**：@wangeditor/editor、markdown-it、marked、html-docx-js-typescript、file-saver
- **图标**：`@element-plus/icons-vue` 全部全局注册

## 命令

```bash
# 启动开发服务器，端口 3000，自动打开浏览器
npm run dev

# 类型检查 + 生产构建（vue-tsc 类型错误会阻塞构建）
npm run build

# 预览生产构建
npm run preview
```

> 当前项目没有配置 lint、format 或测试命令。

## 目录结构

```
src/
├── api/
│   └── contract/
│       └── index.ts       # 后端 API 封装（合同/AI/Excel/OCR/流式对话）
├── components/
│   └── AIChat/
│       └── index.vue      # 流式 AI 聊天抽屉组件（当前在 App.vue 中被注释掉）
├── layout/
│   ├── index.vue          # 带侧边栏/导航栏/主内容区的外壳布局
│   └── components/        # Sidebar、Navbar、AppMain
├── router/
│   └── index.ts           # 路由定义与全局前置守卫
├── styles/
│   └── index.scss         # 全局样式与 Element Plus 主题覆盖
├── util/
│   └── request.ts         # axios 封装（拦截器、错误提示）
├── views/
│   ├── login/
│   │   └── index.vue      # 登录页（硬编码 admin/admin）
│   └── csgl/
│       └── index.vue      # 藏书库管理表格页（当前为 Mock 数据）
├── App.vue
├── env.d.ts               # Vite 客户端类型与 *.vue 声明
└── main.ts                # 应用入口：注册 Pinia/Router/ElementPlus/ECharts/图标
```

## 路由与导航

- hash 路由模式（`createWebHashHistory`）。
- `base: './'`：生产构建使用相对路径部署。
- 路由条目：
  - `/login`：登录页
  - `/` → 重定向到 `/csgl`
  - `/csgl`、`/whhd`、`/zsk`：三个菜单路由，当前都指向 `views/csgl/index.vue`
- 路由守卫：检查 `localStorage.getItem('token')`；未登录访问非登录页会重定向到 `/login`。

## 认证说明

- 登录页采用前端硬编码校验：`admin` / `admin`。
- 登录成功后在 `localStorage` 写入 `token = 'admin-token'`。
- 退出登录时移除 `token` 并跳转到 `/login`。
- `request.ts` 中虽然保留了 token 请求拦截器的注释代码，但当前未自动把 token 注入请求头。

## 环境变量

环境变量前缀必须为 `VITE_` 才能在客户端代码中通过 `import.meta.env` 访问。

- `VITE_APP_BASE_URL`：axios 默认 baseURL
  - 开发：`.env` 中配置（当前使用本地后端地址）
  - 生产：`.env.production` 中配置（当前使用线上 HTTPS 地址）
- `VITE_APP_UPLOAD_URL`：AIChat 组件中图片/附件上传接口，开发与生产共用

> 具体的 URL 值请查看 `.env` 与 `.env.production` 文件，这里不写入以免泄露。

## API 约定

- 所有普通接口统一通过 `src/util/request.ts` 发起。
- 后端响应约定为 `{ code, msg, data }`：
  - `code === 200` 视为成功，响应拦截器直接返回 `response.data`。
  - 其他 code 通过 `ElMessage.error` 提示 `msg` 并 reject。
- `responseType: 'blob'` 或 `'arraybuffer'` 的接口直接返回原始响应，不做 code 解析。
- 以下 AI 相关接口因大模型调用耗时较长，单独设置 `timeout: 600000`（10 分钟），不要缩短：
  - `generateBasicSummary`
  - `verifyExcel`
  - `generateAutoReport`
  - `generateRawRecord`
  - `fillinOCRData`
- 流式对话 `chatBotStream` 使用原生 `fetch` 实现 SSE，**不要用 axios 替换**，以支持 `ReadableStream` 解析。

## 样式约定

- 全局 CSS 变量定义在 `src/styles/index.scss`，包括主色、背景、圆角、侧边栏色等。
- 大量覆盖 Element Plus 默认样式时使用 `!important`。
- 组件内使用 `lang="scss"` + `<style scoped>`，通过 `:deep()` 修改子组件样式。

## 图表使用

- ECharts 在 `main.ts` 中手动注册：`CanvasRenderer`、`BarChart`、`LineChart`、`PieChart`、`GridComponent`、`TooltipComponent`、`LegendComponent`、`TitleComponent`。
- 全局注册为 `<v-chart>` 组件。
- 若需新图表类型，请在 `main.ts` 的 `use([...])` 中添加对应模块。

## 当前状态与注意事项

- **AIChat 组件未启用**：`App.vue` 中 `<AIChat />` 被注释掉，因此聊天入口不会显示。
- **无自定义 Pinia store**：虽然引入了 Pinia，但 `src/stores/` 目录不存在，也没有 store 被使用。
- **无测试、无 lint、无格式化**：项目没有配置 ESLint、Prettier 或单元测试。
- **csgl/whhd/zsk 复用同一组件**：三个侧边栏菜单目前都渲染 `views/csgl/index.vue`，表格数据为写死的 `bookList` Mock 数据。
- **构建输出**：`npm run build` 生成到 `dist/`，产物使用相对路径，可直接作为静态站点部署。
- **路径别名**：`@/` 映射到 `src/`，在 `vite.config.ts` 和 `tsconfig.json` 中均已配置。

## 安全提示

- 登录校验在前端完成，生产环境应替换为真实后端鉴权。
- `.env` / `.env.production` 包含后端地址，提交到公共仓库前请注意脱敏。
- `request.ts` 中的 token 注入逻辑当前被注释，接入真实登录后应取消注释并设置正确的认证头。
- 流式对话和文件上传接口未做额外的 CSRF / XSS 处理，接入生产环境时请按需加固。
