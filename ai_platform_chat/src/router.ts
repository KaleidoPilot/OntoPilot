import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', component: () => import('./views/login.vue') },
    { path: '/', component: () => import('./views/agent/chat.vue'), redirect: '/chat', children: [
      // 对话由常驻工作台展示，切换子页面不销毁正在接收的回答。
      { path: 'chat', component: { render: () => null } },
      // 用户端暂时关闭技能、MCP 管理页。页面文件保留，旧地址直接回到对话，不加载管理页。
      { path: 'mcp', redirect: '/chat' },
      { path: 'knowledge', component: () => import('./views/knowledge/index.vue') },
      { path: 'agent', component: () => import('./views/skill/imported-skill.vue') },
      { path: 'skill', redirect: '/agent' },
      { path: 'templates', component: () => import('./views/skill/template-upload.vue') }
    ] },
    { path: '/:pathMatch(.*)*', redirect: '/chat' }
  ]
})
router.beforeEach(to => {
  let authenticated = false
  try { authenticated = !!localStorage.getItem('fijo-chat-token') && JSON.parse(localStorage.getItem('fijo-chat-userInfo') || '{}').userType === 'external' } catch { /* 损坏的登录状态需要重新登录 */ }
  if (!authenticated && to.path !== '/login') return '/login'
  if (authenticated && to.path === '/login') return '/chat'
})
export default router
