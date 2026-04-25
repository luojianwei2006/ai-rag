<template>
  <div class="page-container">
    <div class="page-header">
      <h2>📱 小红书账号矩阵</h2>
      <t-button theme="primary" @click="openAdd">+ 添加账号</t-button>
    </div>

    <t-loading :loading="loading">
      <div class="accounts-grid" v-if="accounts.length">
        <div class="account-card" v-for="acc in accounts" :key="acc.id">
          <div class="card-header">
            <div class="avatar">{{ acc.nickname[0] }}</div>
            <div class="info">
              <div class="nickname">{{ acc.nickname }}</div>
              <div class="username" v-if="acc.xhs_username">@{{ acc.xhs_username }}</div>
            </div>
            <t-tag :theme="statusTheme(acc.status)" size="small">{{ statusLabel(acc.status) }}</t-tag>
          </div>

          <div class="card-body">
            <div class="field" v-if="acc.niche">
              <span class="label">账号定位：</span>{{ acc.niche }}
            </div>
            <div class="field" v-if="acc.persona">
              <span class="label">人设描述：</span>
              <span class="truncate">{{ acc.persona }}</span>
            </div>
            <div class="field" v-if="acc.tags">
              <span class="label">常用标签：</span>
              <span class="tag-list">
                <t-tag v-for="t in acc.tags.split(',')" :key="t" size="small" style="margin:2px">{{ t.trim() }}</t-tag>
              </span>
            </div>
            <div class="field cookies-status">
              <span class="label">Cookies：</span>
              <span :class="acc.has_cookies ? 'ok' : 'missing'">
                {{ acc.has_cookies ? '✅ 已配置' : '⚠️ 未配置' }}
              </span>
            </div>
          </div>

          <div class="card-footer">
            <t-button size="small" @click="openEdit(acc)">编辑</t-button>
            <t-button size="small" theme="default" @click="openCookies(acc)">设置Cookies</t-button>
            <t-popconfirm content="确认删除该账号？" @confirm="deleteAccount(acc.id)">
              <t-button size="small" theme="danger" variant="outline">删除</t-button>
            </t-popconfirm>
          </div>
        </div>
      </div>

      <t-empty v-else description="暂无账号，点击右上角添加" />
    </t-loading>

    <!-- 添加/编辑账号弹窗 -->
    <t-dialog
      v-model:visible="dialogVisible"
      :header="editingId ? '编辑账号' : '添加账号'"
      width="560px"
      :confirm-btn="{ content: '保存', loading: saving }"
      @confirm="saveAccount"
    >
      <t-form :data="form" label-width="90px">
        <t-form-item label="账号昵称" name="nickname">
          <t-input v-model="form.nickname" placeholder="便于识别的名称，如：美食号-小红" />
        </t-form-item>
        <t-form-item label="小红书用户名">
          <t-input v-model="form.xhs_username" placeholder="可选，@用户名（仅展示）" />
        </t-form-item>
        <t-form-item label="账号定位">
          <t-input v-model="form.niche" placeholder="如：美食探店、母婴好物、职场干货" />
        </t-form-item>
        <t-form-item label="人设描述">
          <t-textarea v-model="form.persona" :rows="3"
            placeholder="账号人设，会加入 AI 提示词中。如：25岁都市女白领，喜欢探店和分享生活" />
        </t-form-item>
        <t-form-item label="常用标签">
          <t-input v-model="form.tags" placeholder="逗号分隔，如：美食,探店,上海,好吃" />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- Cookies 设置弹窗 -->
    <t-dialog
      v-model:visible="cookiesDialogVisible"
      header="设置账号 Cookies"
      width="640px"
      :confirm-btn="{ content: '保存', loading: saving }"
      @confirm="saveCookies"
    >
      <div class="cookies-tip">
        <t-alert theme="info" title="如何获取 Cookies？">
          <template #message>
            1. 在浏览器中登录 <a href="https://creator.xiaohongshu.com" target="_blank">小红书创作者中心</a><br>
            2. 按 F12 打开开发者工具 → Network → 找到任意请求 → 复制 Cookie 请求头<br>
            3. 或安装 <b>Cookie-Editor</b> 浏览器插件，点击"Export JSON"复制 JSON 格式 Cookies
          </template>
        </t-alert>
        <t-textarea
          v-model="cookiesForm.cookies"
          :rows="8"
          placeholder='粘贴 Cookie 文本或 JSON 数组。文本格式如：a1=xxx; webId=xxx；JSON 格式如：[{"name":"a1","value":"xxx"},...]'
          style="margin-top:12px;font-family:monospace;font-size:12px"
        />
      </div>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { xhsApi } from '@/api/index.js'

const accounts = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const cookiesDialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const cookiesTargetId = ref(null)

const form = ref({ nickname: '', xhs_username: '', niche: '', persona: '', tags: '' })
const cookiesForm = ref({ cookies: '' })

const statusTheme = (s) => ({ active: 'success', inactive: 'default', cookie_expired: 'warning' }[s] || 'default')
const statusLabel = (s) => ({ active: '正常', inactive: '停用', cookie_expired: 'Cookies过期' }[s] || s)

async function loadAccounts() {
  loading.value = true
  try { accounts.value = await xhsApi.getAccounts() }
  finally { loading.value = false }
}

function openAdd() {
  editingId.value = null
  form.value = { nickname: '', xhs_username: '', niche: '', persona: '', tags: '' }
  dialogVisible.value = true
}

function openEdit(acc) {
  editingId.value = acc.id
  form.value = { nickname: acc.nickname, xhs_username: acc.xhs_username || '', niche: acc.niche || '', persona: acc.persona || '', tags: acc.tags || '' }
  dialogVisible.value = true
}

function openCookies(acc) {
  cookiesTargetId.value = acc.id
  cookiesForm.value.cookies = ''
  cookiesDialogVisible.value = true
}

async function saveAccount() {
  if (!form.value.nickname.trim()) return MessagePlugin.warning('请填写账号昵称')
  saving.value = true
  try {
    if (editingId.value) {
      await xhsApi.updateAccount(editingId.value, form.value)
      MessagePlugin.success('账号已更新')
    } else {
      await xhsApi.createAccount(form.value)
      MessagePlugin.success('账号添加成功')
    }
    dialogVisible.value = false
    loadAccounts()
  } finally { saving.value = false }
}

async function saveCookies() {
  if (!cookiesForm.value.cookies.trim()) return MessagePlugin.warning('请粘贴 Cookies')
  const raw = cookiesForm.value.cookies.trim()
  // 兼容两种格式：纯文本（key=value; ...）和 JSON 数组
  try {
    JSON.parse(raw) // JSON 格式，直接通过
  } catch {
    // 非 JSON，检查是否为 key=value 纯文本格式
    if (!/^[^=]+=[^;]*(;\s*[^=]+=[^;]*)*$/.test(raw)) {
      return MessagePlugin.error('Cookies 格式不正确，请粘贴 Cookie 文本或 JSON 数组')
    }
    // 纯文本格式自动转为 JSON 数组
    const cookies = raw.split(';').map(c => {
      const idx = c.indexOf('=')
      return idx > -1 ? { name: c.substring(0, idx).trim(), value: c.substring(idx + 1).trim() } : null
    }).filter(Boolean)
    cookiesForm.value.cookies = JSON.stringify(cookies)
  }
  saving.value = true
  try {
    await xhsApi.updateAccount(cookiesTargetId.value, { cookies: cookiesForm.value.cookies })
    MessagePlugin.success('Cookies 保存成功')
    cookiesDialogVisible.value = false
    loadAccounts()
  } finally { saving.value = false }
}

async function deleteAccount(id) {
  await xhsApi.deleteAccount(id)
  MessagePlugin.success('账号已删除')
  loadAccounts()
}

onMounted(loadAccounts)
</script>

<style scoped>
.page-container { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 20px; }

.accounts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.account-card {
  background: white;
  border-radius: 12px;
  border: 1px solid #e8e8e8;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: box-shadow 0.2s;
}
.account-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.1); }

.card-header { display: flex; align-items: center; gap: 10px; }
.avatar {
  width: 42px; height: 42px; border-radius: 50%;
  background: linear-gradient(135deg, #ff2442, #ff6b8a);
  color: white; font-size: 18px; font-weight: bold;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.info { flex: 1; overflow: hidden; }
.nickname { font-weight: bold; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.username { color: #999; font-size: 12px; }

.card-body { display: flex; flex-direction: column; gap: 6px; }
.field { font-size: 13px; color: #555; display: flex; align-items: flex-start; gap: 4px; }
.label { color: #999; flex-shrink: 0; }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; }
.ok { color: #00a870; }
.missing { color: #e6a23c; }

.card-footer { display: flex; gap: 8px; flex-wrap: wrap; border-top: 1px solid #f0f0f0; padding-top: 12px; }

.cookies-tip a { color: #0052d9; }
</style>
