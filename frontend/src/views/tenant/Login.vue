<template>
  <div class="auth-container">
    <div class="auth-box">
      <div class="auth-header">
        <div class="logo">💬</div>
        <h2>商户登录</h2>
        <p>AI智能客服平台</p>
      </div>
      <t-form :data="form" label-width="0">
        <t-form-item>
          <t-input v-model="form.email" placeholder="请输入邮箱" size="large" />
        </t-form-item>
        <t-form-item>
          <t-input v-model="form.password" type="password" placeholder="请输入密码" size="large" @keyup.enter="handleLogin" />
        </t-form-item>
        <t-form-item>
          <t-button theme="primary" size="large" block :loading="loading" @click="handleLogin">登 录</t-button>
        </t-form-item>
      </t-form>
      <div class="auth-links">
        <router-link to="/register">注册商户账号</router-link>
        <span class="divider">|</span>
        <router-link to="/reset-password">忘记密码</router-link>
        <span class="divider">|</span>
        <router-link to="/admin/login">管理员登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { tenantApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = ref({ email: '', password: '' })

async function handleLogin() {
  if (!form.value.email || !form.value.password) {
    return MessagePlugin.warning('请填写邮箱和密码')
  }
  loading.value = true
  try {
    const res = await tenantApi.login(form.value)
    auth.setAuth(res.access_token, 'tenant', res.tenant)
    MessagePlugin.success('登录成功')
    router.push('/tenant/knowledge')
  } catch (e) {} finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex; align-items: center; justify-content: center;
}
.auth-box {
  width: 420px; background: white; border-radius: 16px; padding: 40px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.auth-header { text-align: center; margin-bottom: 28px; }
.logo { font-size: 48px; margin-bottom: 8px; }
.auth-header h2 { margin: 0 0 6px; color: #333; font-size: 24px; }
.auth-header p { margin: 0; color: #888; }
.auth-links { text-align: center; margin-top: 16px; font-size: 14px; }
.auth-links a { color: #667eea; text-decoration: none; }
.auth-links a:hover { text-decoration: underline; }
.divider { color: #ddd; margin: 0 8px; }
</style>
