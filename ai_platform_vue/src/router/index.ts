import { createRouter, createWebHashHistory, RouteRecordRaw } from 'vue-router'
import Layout from '@/layout/index.vue'
import { getHomeRoute, readStoredPlatformUser } from '@/api/user'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    component: Layout,
    redirect: getHomeRoute,
    children: [
      {
        path: 'organization',
        name: 'OrganizationManagement',
        component: () => import('@/views/organization/index.vue'),
        meta: { title: '公司管理', userTypes: ['internal'], organizationOptional: true }
      },
      {
        path: 'system/config',
        name: 'SystemConfig',
        component: () => import('@/views/system/config.vue'),
        meta: { title: '系统配置管理', icon: 'Setting' }
      },
      {
        path: 'project/group',
        name: 'ProjectGroup',
        component: () => import('@/views/project/project-group.vue'),
        meta: { title: '项目组管理', icon: 'FolderOpened' }
      },
      {
        path: 'project/group/:groupId',
        name: 'ProjectGroupDetail',
        component: () => import('@/views/project/project-group-detail.vue'),
        meta: { title: '项目组详情', icon: 'Folder' }
      },
      {
        path: 'knowledge',
        name: 'KnowledgeTenantList',
        component: () => import('@/views/knowledge/tenant-list.vue'),
        meta: { title: '知识库管理', icon: 'Files' }
      },
      {
        path: 'knowledge/:tenantId',
        name: 'KnowledgeTenantDetail',
        component: () => import('@/views/knowledge/tenant-detail.vue'),
        meta: { title: 'Tenant 知识数据', icon: 'Document' }
      },
      {
        path: 'agent/list',
        name: 'AgentList',
        component: () => import('@/views/agent/index.vue'),
        meta: { title: '智能体管理', icon: 'Plus' }
      },
      {
        path: 'agent/detail/:id',
        name: 'AgentDetail',
        component: () => import('@/views/agent/detail.vue'),
        meta: { title: '智能体详情', icon: 'Document' }
      },
      {
        path: 'user/enterprise',
        name: 'EnterpriseUserManagement',
        component: () => import('@/views/user/external-user.vue'),
        meta: { title: '企业后台用户管理', userTypes: ['internal'] }
      },
      {
        path: 'user/external',
        name: 'ExternalUserManagement',
        component: () => import('@/views/user/external-user.vue'),
        meta: { title: '用户组管理', userTypes: ['internal'] }
      },
      {
        path: 'skill/private',
        redirect: '/agent/list'
      },
      {
        path: 'skill/library',
        redirect: '/agent/list'
      },
      {
        path: 'mcp',
        name: 'CompanyMcp',
        component: () => import('@/views/mcp/index.vue'),
        meta: { title: 'MCP 管理', userTypes: ['internal'] }
      },
      {
        path: 'skill/groups',
        name: 'SkillGroupManagement',
        component: () => import('@/views/skill/group-manager.vue'),
        meta: { title: '技能管理', userTypes: ['internal'] }
      },
      {
        // 公共技能管理暂时从后台入口隐藏，页面文件保留，旧地址回到技能管理。
        path: 'skill/public',
        redirect: '/skill/groups'
      },
      {
        path:'skill/templates',name:'CompanyTemplates',component:()=>import('@/views/skill/template-manager.vue'),
        meta:{title:'模板管理',userTypes:['internal']}
      }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

function getStoredUserType(): 'internal' | 'external' {
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')
    return userInfo.userType === 'external' ? 'external' : 'internal'
  } catch {
    return 'internal'
  }
}

function hasStoredOrganization(): boolean {
  try {
    const user = readStoredPlatformUser()
    if (user.deptLevel === 1 || user.userType === 'external') {
      return Number.isInteger(Number(user.orgId)) && Number(user.orgId) > 0
    }
    const organization = JSON.parse(localStorage.getItem('currentOrganization') || '{}')
    return Number.isInteger(Number(organization.id)) && Number(organization.id) > 0
  } catch {
    return false
  }
}

// 路由守卫
router.beforeEach((to) => {
  // 旧后台外部用户会话退出；外部用户改用独立聊天平台。
  if (getStoredUserType() === 'external') {
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    localStorage.removeItem('currentOrganization')
    return to.path === '/login' ? true : '/login'
  }
  const token = localStorage.getItem('token')
  if (to.path === '/login') {
    if (token) {
      return '/'
    }
    return true
  } else {
    if (!token) {
      return '/login'
    }
    const userType = getStoredUserType()
    if (
      userType === 'internal'
      && !to.meta.organizationOptional
      && !hasStoredOrganization()
    ) {
      if (readStoredPlatformUser().deptLevel === 1) {
        localStorage.removeItem('token')
        localStorage.removeItem('userInfo')
        localStorage.removeItem('currentOrganization')
        return '/login'
      }
      return '/organization'
    }
    const allowed = to.meta.userTypes as string[] | undefined
    if (allowed && !allowed.includes(userType)) {
      return '/organization'
    }
    return true
  }
})

export default router
