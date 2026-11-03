<template>
  <main class="login-page">
    <section class="login-intro"><div class="logo"><el-icon><Lightning /></el-icon><strong>KaleidoPilot</strong></div><h1>你的工作，<br />从一句对话开始。</h1><p>连接业务知识与智能技能，<br />让每一个问题都有清晰的下一步。</p><span>用户对话工作台</span></section>
    <section class="login-panel"><div class="login-form"><h2>欢迎回来</h2><p>使用管理员分配的用户账号登录</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
        <el-form-item label="账号" prop="username"><el-input v-model="form.username" autocomplete="username" placeholder="请输入账号" size="large" :disabled="busy" /></el-form-item>
        <el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" show-password autocomplete="current-password" placeholder="请输入密码" size="large" :disabled="busy" /></el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <el-button class="login-submit" type="primary" size="large" native-type="submit" :loading="busy">登录工作台 <el-icon><Right /></el-icon></el-button>
      </el-form><small>账号或技能组未配置？请联系你的管理员。</small>
    </div></section>
  </main>
</template>
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { type FormInstance, type FormRules } from 'element-plus'
import { Lightning, Right } from '@element-plus/icons-vue'
import { login } from '@/api/user'
const router = useRouter()
const form = reactive({ username: '', password: '' })
const formRef = ref<FormInstance>()
const rules: FormRules = { username: [{ required: true, whitespace: true, message: '请输入账号', trigger: 'blur' }], password: [{ required: true, message: '请输入密码', trigger: 'blur' }] }
const busy = ref(false)
const error = ref('')
async function submit() {
  if (busy.value || !await formRef.value?.validate().catch(() => false)) return
  busy.value = true; error.value = ''
  try {
    const response = await login({ username: form.username.trim(), password: form.password })
    if (!response.success) throw new Error(response.message || '登录失败，请检查账号密码')
    if (response.data?.userInfo?.userType !== 'external') throw new Error('这里是用户工作台，请使用外部用户账号；管理员请使用原管理平台。')
    if (!response.data.token) throw new Error('登录状态无效，请重试')
    localStorage.setItem('fijo-chat-token', response.data.token)
    localStorage.setItem('fijo-chat-userInfo', JSON.stringify(response.data.userInfo))
    form.password = ''
    await router.replace('/chat')
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '登录失败，请稍后重试' }
  finally { busy.value = false }
}
</script>
<style scoped lang="scss">
.login-page { min-height: 100dvh; display: grid; grid-template-columns: 1fr 1fr; }
.login-intro { padding: 10vh 12%; display: flex; flex-direction: column; background: #edf2ff; .logo { display: flex; gap: 12px; align-items: center; color: var(--primary-color); font-size: 24px; .el-icon { font-size: 32px; } } h1 { margin: auto 0 24px; padding-top: 70px; font-size: clamp(32px,4vw,54px); font-weight: 600; line-height: 1.5; letter-spacing: -1px; } p { color: #687993; line-height: 2; font-size: 16px; } >span { margin-top: auto; padding-top: 70px; font-size: 12px; color: #687993; } }
.login-panel { display: grid; place-items: center; background: #fff; padding: 32px; } .login-form { width: min(100%,360px); h2 { font-size: 28px; margin: 0 0 12px; } >p { color: #687993; font-size: 14px; margin-bottom: 36px; } small { color: #687993; font-size: 12px; } .login-submit { width: 100%; margin: 14px 0 24px; height: 46px; .el-icon { margin-left: 8px; } } }
@media (max-width: 700px) { .login-page { grid-template-columns: 1fr; } .login-intro { padding: 28px; h1 { font-size: 30px; padding-top: 22px; margin-bottom: 4px; } >span, p { display: none; } } .login-panel { padding: 36px 28px; } }
</style>
