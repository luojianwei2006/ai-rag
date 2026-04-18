<template>
  <div class="api-keys-page">
    <!-- 页头 -->
    <div class="page-header">
      <div class="page-header-left">
        <h2 class="page-title">大模型 API Key 配置</h2>
        <p class="page-desc">配置系统默认的大模型 API Key，未设置自有 Key 的商户将使用此处配置。</p>
      </div>
      <div class="page-header-right">
        <t-button theme="primary" @click="openAddDialog">
          <template #icon><t-icon name="add" /></template>
          添加 API Key
        </t-button>
        <t-button theme="primary" variant="outline" :loading="saving" @click="handleSaveAll" style="margin-left:8px">
          <template #icon><t-icon name="save" /></template>
          保存全部
        </t-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-num">{{ keyList.length }}</div>
        <div class="stat-label">已配置</div>
      </div>
      <div class="stat-card enabled">
        <div class="stat-num">{{ keyList.filter(k => k.enabled).length }}</div>
        <div class="stat-label">已启用</div>
      </div>
      <div class="stat-card providers">
        <div class="stat-num">{{ new Set(keyList.map(k => k.provider)).size }}</div>
        <div class="stat-label">厂家数</div>
      </div>
    </div>

    <!-- Key 列表 -->
    <t-card :bordered="false" class="key-list-card">
      <div v-if="keyList.length === 0" class="empty-state">
        <t-icon name="cloud-upload" style="font-size:48px; color:#ccc;" />
        <p>暂无配置，点击「添加 API Key」开始</p>
      </div>

      <div v-for="(item, index) in keyList" :key="item.id" class="key-item" :class="{ disabled: !item.enabled }">
        <!-- 厂家标识 -->
        <div class="key-provider">
          <span class="provider-icon">{{ PROVIDERS[item.provider]?.icon || '🤖' }}</span>
          <div class="provider-info">
            <div class="provider-name">{{ PROVIDERS[item.provider]?.name || item.provider }}</div>
            <div class="provider-model">{{ getModelLabel(item.provider, item.model) }}</div>
          </div>
        </div>

        <!-- Key 显示 -->
        <div class="key-value">
          <span class="key-masked">{{ item.api_key_masked || (item.api_key ? maskKey(item.api_key) : '未填写') }}</span>
          <t-tag v-if="!item.api_key && !item.api_key_masked" theme="warning" variant="light" size="small">待填写</t-tag>
        </div>

        <!-- 测试状态 -->
        <div class="key-test-status">
          <t-tag v-if="item._testStatus === 'ok'" theme="success" variant="light" size="small">
            <t-icon name="check-circle" /> 连接正常
          </t-tag>
          <t-tag v-else-if="item._testStatus === 'fail'" theme="danger" variant="light" size="small">
            <t-icon name="close-circle" /> 连接失败
          </t-tag>
          <t-tag v-else-if="item._testStatus === 'testing'" theme="primary" variant="light" size="small">
            <t-loading size="small" /> 测试中...
          </t-tag>
          <span v-else class="test-placeholder">-</span>
        </div>

        <!-- 操作区 -->
        <div class="key-actions">
          <!-- 启用开关 -->
          <t-switch v-model="item.enabled" size="small" />
          <span class="switch-label">{{ item.enabled ? '已启用' : '已禁用' }}</span>

          <!-- 测试连接按钮 -->
          <t-button
            theme="default"
            variant="outline"
            size="small"
            :loading="item._testStatus === 'testing'"
            :disabled="!item.enabled"
            @click="handleTest(item)"
          >测试连接</t-button>

          <!-- 编辑 -->
          <t-button theme="primary" variant="text" size="small" @click="openEditDialog(item, index)">
            <t-icon name="edit" />
          </t-button>

          <!-- 删除 -->
          <t-popconfirm content="确认删除此 API Key？" @confirm="handleDelete(index)">
            <t-button theme="danger" variant="text" size="small">
              <t-icon name="delete" />
            </t-button>
          </t-popconfirm>
        </div>
      </div>
    </t-card>

    <!-- 添加/编辑弹窗 -->
    <t-dialog
      v-model:visible="dialogVisible"
      :header="editIndex >= 0 ? '编辑 API Key' : '添加 API Key'"
      width="520px"
      :confirm-btn="{ content: '保存', loading: saving }"
      @confirm="handleDialogSave"
    >
      <t-form :data="dialogForm" label-width="120px" ref="dialogFormRef">
        <!-- 厂家选择 -->
        <t-form-item label="选择厂家" name="provider" :rules="[{required: true, message: '请选择厂家'}]">
          <t-select v-model="dialogForm.provider" placeholder="请选择大模型厂家" @change="onProviderChange" style="width:100%">
            <t-option v-for="(p, key) in PROVIDERS" :key="key" :value="key" :label="p.icon + ' ' + p.name" />
          </t-select>
        </t-form-item>

        <!-- 模型选择 -->
        <t-form-item label="选择模型" name="model" :rules="[{required: true, message: '请选择模型'}]">
          <t-select v-model="dialogForm.model" placeholder="请先选择厂家" :disabled="!dialogForm.provider" style="width:100%">
            <t-option
              v-for="m in (PROVIDERS[dialogForm.provider]?.models || [])"
              :key="m.value"
              :value="m.value"
              :label="m.label"
            />
          </t-select>
          <div v-if="selectedModelDesc" class="model-desc">{{ selectedModelDesc }}</div>
        </t-form-item>

        <!-- API Key 输入 -->
        <t-form-item label="API Key" name="api_key" :rules="editIndex < 0 ? [{required: true, message: '请输入API Key'}] : []">
          <t-input
            v-model="dialogForm.api_key"
            type="password"
            :placeholder="editIndex >= 0 ? '留空保持原有Key不变' : `请输入 ${PROVIDERS[dialogForm.provider]?.name || ''} API Key`"
            autocomplete="new-password"
          />
          <div v-if="dialogForm.provider" class="key-hint">
            {{ PROVIDERS[dialogForm.provider]?.keyHint || '' }}
          </div>
        </t-form-item>

        <!-- 启用开关 -->
        <t-form-item label="启用状态">
          <t-switch v-model="dialogForm.enabled" />
          <span style="margin-left:10px; color:#666; font-size:13px;">
            {{ dialogForm.enabled ? '启用后商户可使用此Key' : '禁用后商户无法使用此Key' }}
          </span>
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { adminApi } from '@/api'

// -------- 厂家 & 模型配置 --------
const PROVIDERS = {
  glm: {
    name: '智谱 GLM',
    icon: '🤖',
    keyHint: '格式：以 eyJ 或字母数字混合开头，前往 https://open.bigmodel.cn 获取',
    models: [
      { value: 'glm-4-flash', label: 'GLM-4-Flash（推荐，速度快）' },
      { value: 'glm-4', label: 'GLM-4（旗舰版）' },
      { value: 'glm-4-air', label: 'GLM-4-Air（轻量版）' },
      { value: 'glm-4-long', label: 'GLM-4-Long（长文本）' },
      { value: 'glm-3-turbo', label: 'GLM-3-Turbo（经济版）' },
    ]
  },
  openai: {
    name: 'OpenAI',
    icon: '🌟',
    keyHint: '格式：sk-... 前往 https://platform.openai.com 获取',
    models: [
      { value: 'gpt-4o', label: 'GPT-4o（最强多模态）' },
      { value: 'gpt-4o-mini', label: 'GPT-4o mini（经济版）' },
      { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
      { value: 'gpt-4', label: 'GPT-4' },
      { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo（经济版）' },
    ]
  },
  gemini: {
    name: 'Google Gemini',
    icon: '💎',
    keyHint: '前往 https://aistudio.google.com 获取 API Key',
    models: [
      { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash（推荐）' },
      { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro（旗舰）' },
      { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash（速度快）' },
      { value: 'gemini-pro', label: 'Gemini Pro（经典）' },
    ]
  },
  deepseek: {
    name: 'DeepSeek',
    icon: '🔮',
    keyHint: '前往 https://platform.deepseek.com 获取 API Key',
    models: [
      { value: 'deepseek-chat', label: 'DeepSeek-V3（推荐）' },
      { value: 'deepseek-reasoner', label: 'DeepSeek-R1（推理增强）' },
    ]
  },
  qwen: {
    name: '阿里通义千问',
    icon: '🌙',
    keyHint: '前往 https://dashscope.aliyuncs.com 获取 API Key',
    models: [
      { value: 'qwen-turbo', label: 'Qwen-Turbo（速度快）' },
      { value: 'qwen-plus', label: 'Qwen-Plus（均衡）' },
      { value: 'qwen-max', label: 'Qwen-Max（旗舰）' },
      { value: 'qwen-long', label: 'Qwen-Long（长文本）' },
    ]
  },
  nvidia_zai: {
    name: 'NVIDIA Z-AI',
    icon: '⚡',
    keyHint: '前往 NVIDIA Z-AI 平台获取 API Key',
    models: [
      { value: 'z-ai/glm5', label: 'GLM-5' },
      { value: 'z-ai/glm4.7', label: 'GLM-4.7' },
    ]
  }
}

// -------- 状态 --------
const keyList = ref([])
const saving = ref(false)
const dialogVisible = ref(false)
const editIndex = ref(-1)
const dialogFormRef = ref()

const dialogForm = ref({
  provider: '',
  model: '',
  api_key: '',
  enabled: true
})

// -------- 计算属性 --------
const selectedModelDesc = computed(() => {
  if (!dialogForm.value.provider || !dialogForm.value.model) return ''
  const models = PROVIDERS[dialogForm.value.provider]?.models || []
  const m = models.find(x => x.value === dialogForm.value.model)
  return m ? m.label : ''
})

// -------- 方法 --------
function maskKey(key) {
  if (!key || key.length < 8) return '****'
  return key.slice(0, 4) + '****' + key.slice(-4)
}

function getModelLabel(provider, model) {
  const models = PROVIDERS[provider]?.models || []
  const m = models.find(x => x.value === model)
  return m ? m.label : model
}

function onProviderChange() {
  dialogForm.value.model = ''
  // 自动选第一个模型
  const models = PROVIDERS[dialogForm.value.provider]?.models || []
  if (models.length > 0) {
    dialogForm.value.model = models[0].value
  }
}

function openAddDialog() {
  editIndex.value = -1
  dialogForm.value = { provider: '', model: '', api_key: '', enabled: true }
  dialogVisible.value = true
}

function openEditDialog(item, index) {
  editIndex.value = index
  dialogForm.value = {
    provider: item.provider,
    model: item.model,
    api_key: '',   // 编辑时不回显真实Key
    enabled: item.enabled
  }
  dialogVisible.value = true
}

async function handleDialogSave() {
  if (!dialogForm.value.provider) {
    MessagePlugin.warning('请选择厂家')
    return
  }
  if (!dialogForm.value.model) {
    MessagePlugin.warning('请选择模型')
    return
  }
  if (editIndex.value < 0 && !dialogForm.value.api_key) {
    MessagePlugin.warning('请输入 API Key')
    return
  }

  const id = editIndex.value >= 0 ? keyList.value[editIndex.value].id : Date.now().toString()

  if (editIndex.value >= 0) {
    // 编辑
    const old = keyList.value[editIndex.value]
    keyList.value[editIndex.value] = {
      ...old,
      provider: dialogForm.value.provider,
      model: dialogForm.value.model,
      enabled: dialogForm.value.enabled,
      // 如果新key不为空则更新，否则保持
      api_key: dialogForm.value.api_key || old.api_key,
      api_key_masked: dialogForm.value.api_key ? maskKey(dialogForm.value.api_key) : old.api_key_masked,
      _testStatus: null
    }
  } else {
    // 新增
    keyList.value.push({
      id,
      provider: dialogForm.value.provider,
      model: dialogForm.value.model,
      api_key: dialogForm.value.api_key,
      api_key_masked: maskKey(dialogForm.value.api_key),
      enabled: dialogForm.value.enabled,
      _testStatus: null
    })
  }

  dialogVisible.value = false
  MessagePlugin.success(editIndex.value >= 0 ? '已更新，记得点保存全部' : '已添加，记得点保存全部')
}

function handleDelete(index) {
  keyList.value.splice(index, 1)
  MessagePlugin.success('已删除，记得点保存全部')
}

async function handleTest(item) {
  if (!item.enabled) {
    MessagePlugin.warning('请先启用该Key')
    return
  }
  const keyToTest = item.api_key || ''
  item._testStatus = 'testing'
  try {
    await adminApi.testApiKey({
      provider: item.provider,
      model: item.model,
      api_key: keyToTest
    })
    item._testStatus = 'ok'
    MessagePlugin.success('连接测试成功 ✅')
  } catch (e) {
    item._testStatus = 'fail'
    // 错误由拦截器处理
  }
}

async function handleSaveAll() {
  saving.value = true
  try {
    // 调试：打印要保存的数据
    const keysToSave = keyList.value.map(k => ({
      id: k.id,
      provider: k.provider,
      model: k.model,
      api_key: k.api_key || '',
      enabled: k.enabled
    }))
    console.log('Saving keys:', keysToSave)
    
    await adminApi.saveApiKeys({ keys: keysToSave })
    MessagePlugin.success('API Key 配置保存成功 ✅')
    await loadKeys()
  } catch (e) {
    // 错误由拦截器处理
    console.error('Save error:', e)
  } finally {
    saving.value = false
  }
}

async function loadKeys() {
  try {
    const res = await adminApi.getApiKeys()
    keyList.value = (res.keys || []).map(k => ({
      ...k,
      _testStatus: null
    }))
  } catch (e) {}
}

onMounted(loadKeys)
</script>

<style scoped>
.api-keys-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 4px;
}

.page-desc {
  font-size: 13px;
  color: #888;
  margin: 0;
}

/* 统计卡片 */
.stats-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  flex: 1;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px 20px;
  text-align: center;
}

.stat-card.enabled { border-color: #52c41a33; background: #f6ffed; }
.stat-card.providers { border-color: #1890ff33; background: #e6f7ff; }

.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: #333;
  line-height: 1;
}

.stat-label {
  font-size: 12px;
  color: #888;
  margin-top: 4px;
}

/* Key 列表卡片 */
.key-list-card {
  min-height: 200px;
}

.empty-state {
  text-align: center;
  padding: 60px 0;
  color: #999;
}

.key-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  margin-bottom: 10px;
  background: #fff;
  transition: all 0.2s;
}

.key-item:hover {
  border-color: #d0e8ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.08);
}

.key-item.disabled {
  opacity: 0.5;
  background: #fafafa;
}

/* 厂家区域 */
.key-provider {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 160px;
}

.provider-icon {
  font-size: 24px;
  line-height: 1;
}

.provider-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.provider-model {
  font-size: 12px;
  color: #888;
  margin-top: 2px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Key 值 */
.key-value {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.key-masked {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #555;
  background: #f5f5f5;
  padding: 3px 10px;
  border-radius: 4px;
  letter-spacing: 1px;
}

/* 测试状态 */
.key-test-status {
  min-width: 80px;
  text-align: center;
}

.test-placeholder {
  color: #ccc;
  font-size: 16px;
}

/* 操作区 */
.key-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.switch-label {
  font-size: 12px;
  color: #888;
  white-space: nowrap;
}

/* 弹窗内样式 */
.model-desc {
  font-size: 12px;
  color: #888;
  margin-top: 4px;
  padding-left: 2px;
}

.key-hint {
  font-size: 12px;
  color: #aaa;
  margin-top: 4px;
  padding-left: 2px;
  line-height: 1.4;
}
</style>
