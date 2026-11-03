<template>
  <!-- 左右分栏布局登录页：左侧品牌展示区 + 右侧登录表单区 -->
  <div class="login-container">
    <!-- 左侧品牌区：渐变背景 + 系统名称 + 装饰标语 -->
    <div class="brand-section">
      <div class="brand-content">
        <!-- 系统图标 -->
        <el-icon class="brand-icon"><DataAnalysis /></el-icon>
        <!-- 系统名称 -->
        <h1 class="brand-title">KaleidoPilot</h1>
        <!-- 系统标语 -->
        <p class="brand-subtitle">数智人平台</p>
      </div>
    </div>

    <!-- 右侧表单区：登录表单 -->
    <div class="form-section">
      <el-form ref="loginForm" :model="loginData" :rules="loginRules" class="login-form" autocomplete="on" label-position="left">
        <!-- 表单标题 -->
        <div class="title-container">
          <h3 class="title">欢迎登录</h3>
          <p class="subtitle">请输入您的账号和密码</p>
        </div>

        <!-- 用户名输入框 -->
        <el-form-item prop="username">
          <el-input
            ref="username"
            v-model="loginData.username"
            placeholder="用户名"
            name="username"
            type="text"
            tabindex="1"
            autocomplete="on"
            prefix-icon="User"
          />
        </el-form-item>

        <!-- 密码输入框 -->
        <el-form-item prop="password">
          <el-input
            ref="password"
            v-model="loginData.password"
            type="password"
            placeholder="密码"
            name="password"
            tabindex="2"
            autocomplete="on"
            prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <!-- 登录按钮 -->
        <el-button :loading="loading" type="primary" style="width:100%;margin-bottom:30px;" @click.prevent="handleLogin">登录</el-button>

        <!-- 底部提示信息 -->
        <!-- <div class="tips">
          <span>请使用系统管理员分配的账号登录</span>
        </div> -->
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, getHomeRoute } from '@/api/user'

// 路由实例
const router = useRouter()

// 登录按钮加载状态
const loading = ref(false)

// 表单引用（用于调用 validate 方法）
const loginForm = ref()

// 登录表单数据：用户名 + 密码
const loginData = reactive({
  username: '',
  password: '',
})

// 表单验证规则：用户名和密码必填
const loginRules = {
  username: [{ required: true, trigger: 'blur', message: '请输入用户名' }],
  password: [{ required: true, trigger: 'blur', message: '请输入密码' }],
}

// 登录处理函数：验证表单 → 对接后端真实登录 → 跳转首页
const handleLogin = () => {
  loginForm.value.validate(async (valid: boolean) => {
    if (valid) {
      loading.value = true
      try {
        const res = await login({
          username: loginData.username,
          password: loginData.password
        })
        
        if (res.success) {
          if (res.data.userInfo.userType === 'external') {
            ElMessage.info('外部用户请在用户聊天平台登录，使用或创建智能体')
            return
          }
          // 保存后端返回的真实 token
          localStorage.setItem('token', res.data.token)
          // 可以将用户信息也存起来，供页面显示使用
          localStorage.setItem('userInfo', JSON.stringify(res.data.userInfo))
          localStorage.removeItem('currentOrganization')
          const userInfo = res.data.userInfo
          if (userInfo.userType === 'internal' && userInfo.deptLevel === 1) {
            localStorage.setItem('currentOrganization', JSON.stringify({
              id: userInfo.orgId, orgCode: userInfo.orgCode, name: userInfo.orgName
            }))
          }
          
          const targetRoute = getHomeRoute()
          await router.replace(targetRoute)
          ElMessage.success('登录成功')
        } else {
          // 处理后端返回的失败逻辑
          ElMessage.error(res.message || '登录失败')
        }
      } catch (error: any) {
        console.error('Login error:', error)
        // 捕获请求层面的错误（如果是 axios 拦截器抛出的错误，也可以在这里捕获）
        ElMessage.error(error.message || '网络请求失败，请稍后重试')
      } finally {
        loading.value = false
      }
    } else {
      return false
    }
  })
}
</script>

<style scoped lang="scss">
.login-container {
  min-height: 100vh;
  width: 100%;
  display: flex;
  background-color: #f5f7fa;

  // 左侧品牌区：渐变背景 + 白色文字
  .brand-section {
    width: 50%;
    background: linear-gradient(135deg, #5668ed 0%, #05203b 100%);
    display: flex;
    justify-content: center;
    align-items: center;
    position: relative;
    overflow: hidden;

    .brand-content {
      text-align: center;
      padding: 40px;

      // 品牌图标样式
      .brand-icon {
        font-size: 64px;
        color: #ffffff;
        margin-bottom: 20px;
        opacity: 0.9;
      }

      // 系统名称样式
      .brand-title {
        font-size: 48px;
        color: #ffffff;
        margin: 0 0 16px 0;
        font-weight: bold;
        letter-spacing: 4px;
      }

      // 品牌标语样式
      .brand-subtitle {
        font-size: 16px;
        color: rgba(255, 255, 255, 0.8);
        margin: 0;
        letter-spacing: 2px;
      }
    }
  }

  // 右侧表单区：白色背景 + 居中表单
  .form-section {
    width: 50%;
    display: flex;
    justify-content: center;
    align-items: center;
    background: #fff;

    .login-form {
      width: 360px;
      padding: 40px 30px;
    }

    // 表单标题样式
    .title-container {
      margin-bottom: 30px;
      .title {
        font-size: 28px;
        color: #303133;
        margin: 0 0 8px 0;
        font-weight: bold;
      }
      .subtitle {
        font-size: 14px;
        color: #909399;
        margin: 0;
      }
    }

    // 底部提示样式
    .tips {
      font-size: 14px;
      color: #909399;
      text-align: center;
      span {
        margin: 0 10px;
      }
    }

    // 输入框高度统一
    :deep(.el-input__wrapper) {
      height: 44px;
    }

    // 登录按钮样式
    .el-button--primary {
      height: 44px;
      font-size: 16px;
      background-color: var(--primary-color);
      border-color: var(--primary-color);
      border-radius: 6px;
      &:hover {
        opacity: 0.9;
      }
    }
  }

  // 响应式：小屏幕（<768px）隐藏左侧品牌区，表单居中
  @media (max-width: 768px) {
    .brand-section {
      display: none;
    }
    .form-section {
      width: 100%;
      background: #f5f7fa;
    }
  }
}
</style>
