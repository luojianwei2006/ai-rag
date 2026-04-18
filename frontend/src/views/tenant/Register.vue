<template>
  <div class="auth-container">
    <div class="auth-box">
      <div class="auth-header">
        <div class="logo">🏢</div>
        <h2>注册商户账号</h2>
        <p>密码将发送到您的邮箱</p>
      </div>
      <t-form :data="form" label-width="0">
        <t-form-item>
          <t-input v-model="form.email" placeholder="请输入邮箱地址" size="large" />
        </t-form-item>
        <t-form-item>
          <t-input v-model="form.company_name" placeholder="公司名称（选填）" size="large" />
        </t-form-item>
        <t-form-item>
          <t-button theme="primary" size="large" block :loading="loading" @click="handleRegister">注 册</t-button>
        </t-form-item>
      </t-form>
      <div class="auth-links">
        已有账号？<router-link to="/login">立即登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { tenantApi } from '@/api'

const router = useRouter()
const loading = ref(false)
const form = ref({ email: '', company_name: '' })

async function handleRegister() {
  if (!form.value.email) return MessagePlugin.warning('请输入邮箱')
  loading.value = true
  try {
    const res = await tenantApi.register(form.value)
    MessagePlugin.success(res.message)
    setTimeout(() => router.push('/login'), 1500)
  } catch (e) {} finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container { min-height:100vh; background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); display:flex; align-items:center; justify-content:center; }
.auth-box { width:420px; background:white; border-radius:16px; padding:40px; box-shadow:0 20px 60px rgba(0,0,0,0.2); }
.auth-header { text-align:center; margin-bottom:28px; }
.logo { font-size:48px; margin-bottom:8px; }
.auth-header h2 { margin:0 0 6px; color:#333; font-size:24px; }
.auth-header p { margin:0; color:#888; }
.auth-links { text-align:center; margin-top:16px; font-size:14px; }
.auth-links a { color:#667eea; text-decoration:none; }
</style>
