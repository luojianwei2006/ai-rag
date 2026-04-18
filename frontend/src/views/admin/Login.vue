<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <div class="logo">💬</div>
        <h2>客服管理平台</h2>
        <p>管理员登录</p>
      </div>
      <t-form :data="form" @submit="handleLogin" :colon="false">
        <t-form-item name="username" label="">
          <t-input v-model="form.username" placeholder="请输入用户名" size="large" prefix-icon="user" />
        </t-form-item>
        <t-form-item name="password" label="">
          <t-input v-model="form.password" type="password" placeholder="请输入密码" size="large" @keyup.enter="handleLogin" />
        </t-form-item>
        <t-form-item>
          <t-button theme="primary" size="large" block :loading="loading" @click="handleLogin">
            登 录
          </t-button>
        </t-form-item>
      </t-form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { adminApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = ref({ username: 'admin', password: 'admin123' })

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    MessagePlugin.warning('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await adminApi.login(form.value)
    auth.setAuth(res.access_token, 'admin', { username: res.username })
    MessagePlugin.success('登录成功')
    router.push('/admin/dashboard')
  } catch (e) {
    // error handled by interceptor
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-box {
  width: 400px;
  background: white;
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
.login-header {
  text-align: center;
  margin-bottom: 32px;
}
.logo { font-size: 48px; margin-bottom: 8px; }
.login-header h2 { margin: 0 0 8px; color: #333; font-size: 24px; }
.login-header p { margin: 0; color: #888; }
</style>
