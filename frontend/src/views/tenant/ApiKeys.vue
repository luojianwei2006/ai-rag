<template>
  <div class="api-keys-page">
    <!-- 页头 -->
    <div class="page-header">
      <div class="page-header-left">
        <h2 class="page-title">API Key 配置</h2>
        <p class="page-desc">配置您自己的大模型 API Key，配置后可选择使用系统 Key 或自有 Key。</p>
      </div>
      <div class="page-header-right">
        <t-button theme="primary" @click="openAddDialog">
          <template #icon><t-icon name="add" /></template>
          添加 API Key
        </t-button>
        <t-button theme="primary" variant="outline" :loading="saving" @click="handleSaveAll" style="margin-left:8px">
          <template #icon><t-icon name="save" /></template>
          保存配置
        </t-button>
      </div>
    </div>

    <!-- 系统Key策略卡片 -->
    <t-card :bordered="false" class="strategy-card">
      <div class="strategy-row">
        <div class="strategy-info">
          <div class="strategy-title">
            <t-icon name="setting" style="color:#1890ff; margin-right:6px;" />
            使用系统默认 Key
          </div>
          <div class="strategy-desc">
            开启后，当您未配置或禁用自有 Key 时，系统会自动使用管理员配置的默认 Key；关闭后仅使用您自己的 Key。
          </div>
        </div>
        <div class="strategy-switch">
          <t-switch v-model="useSystemKey" size="large" />
          <div class="switch-text">{{ useSystemKey ? '已开启系统Key兜底' : '仅使用自有Key' }}</div>
        </div>
      </div>

      <t-divider style="margin: 12px 0;" />

      <div class="strategy-row">
        <div class="strategy-info">
          <div class="strategy-title">
            <t-icon name="swap" style="color:#722ed1; margin-right:6px;" />
            首选模型
          </div>
          <div class="strategy-desc">当同时配置了多个厂家的 Key 时，优先使用哪个厂家的模型进行问答。</div>
        </div>
        <div>
          <t-select v-model="preferredModel" style="width:200px">
            <t-option v-for="(p, key) in PROVIDERS" :key="key" :value="key" :label="p.icon + ' ' + p.name" />
          </t-select>
        </div>
      </div>
    </t-card>

    <!-- Key 列表 -->
    <t-card :bordered="false" class="key-list-card" title="我的 API Key">
      <div v-if="keyList.length === 0" class="empty-state">
        <t-icon name="cloud-upload" style="font-size:48px; color:#ccc;" />
        <p>暂未添加自有 Key，点击「添加 API Key」开始</p>
        <p style="color:#aaa; font-size:12px;">若已开启系统Key兜底，可暂不配置</p>
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
            测试中...
          </t-tag>
          <span v-else class="test-placeholder">-</span>
        </div>

        <!-- 操作区 -->
        <div class="key-actions">
          <t-switch v-model="item.enabled" size="small" />
          <span class="switch-label">{{ item.enabled ? '已启用' : '已禁用' }}</span>

          <t-button
            theme="default"
            variant="outline"
            size="small"
            :loading="item._testStatus === 'testing'"
            :disabled="!item.enabled"
            @click="handleTest(item)"
          >测试连接</t-button>

          <t-button theme="primary" variant="text" size="small" @click="openEditDialog(item, index)">
            <t-icon name="edit" />
          </t-button>

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
      :confirm-btn="{ content: '确定' }"
      @confirm="handleDialogSave"
    >
      <t-form :data="dialogForm" label-width="120px">
        <!-- 厂家选择 -->
        <t-form-item label="选择厂家" name="provider">
          <t-select v-model="dialogForm.provider" placeholder="请选择大模型厂家" @change="onProviderChange" style="width:100%">
            <t-option v-for="(p, key) in PROVIDERS" :key="key" :value="key">
              <template #default>
                <span style="margin-right:6px;">{{ p.icon }}</span>{{ p.name }}
              </template>
            </t-option>
          </t-select>
        </t-form-item>

        <!-- 模型选择 -->
        <t-form-item label="选择模型" name="model">
          <t-select v-model="dialogForm.model" placeholder="请先选择厂家" :disabled="!dialogForm.provider" style="width:100%">
            <t-option
              v-for="m in (PROVIDERS[dialogForm.provider]?.models || [])"
              :key="m.value"
              :value="m.value"
              :label="m.label"
            />
          </t-select>
          <div v-if="dialogForm.provider" class="model-desc">
            {{ PROVIDERS[dialogForm.provider]?.desc || '' }}
          </div>
        </t-form-item>

        <!-- API Key 输入 -->
        <t-form-item label="API Key" name="api_key">
          <t-input
            v-model="dialogForm.api_key"
            type="password"
            :placeholder="editIndex >= 0 ? '留空保持原有 Key 不变' : `请输入 ${PROVIDERS[dialogForm.provider]?.name || ''} API Key`"
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
            {{ dialogForm.enabled ? '启用后系统将优先使用此Key' : '禁用后此Key暂不参与调用' }}
          </span>
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { tenantApi } from '@/api'

// -------- 厂家 & 模型配置 --------
const PROVIDERS = {
  glm: {
    name: '智谱 GLM',
    icon: '🤖',
    desc: '国内领先大模型，中文效果优秀，性价比高',
    keyHint: '格式：以 eyJ 或字母数字混合开头，前往 open.bigmodel.cn 获取',
    models: [
      { value: 'glm-4-flash', label: 'GLM-4-Flash（推荐 · 速度快）' },
      { value: 'glm-4', label: 'GLM-4（旗舰版）' },
      { value: 'glm-4-air', label: 'GLM-4-Air（轻量版）' },
      { value: 'glm-4-long', label: 'GLM-4-Long（128K长文本）' },
      { value: 'glm-3-turbo', label: 'GLM-3-Turbo（经济版）' },
    ]
  },
  openai: {
    name: 'OpenAI',
    icon: '🌟',
    desc: 'ChatGPT 系列模型，全球最广泛使用',
    keyHint: '格式：sk-...，前往 platform.openai.com 获取',
    models: [
      { value: 'gpt-4o', label: 'GPT-4o（最强多模态）' },
      { value: 'gpt-4o-mini', label: 'GPT-4o mini（推荐 · 性价比高）' },
      { value: 'gpt-4-turbo', label: 'GPT-4 Turbo（128K）' },
      { value: 'gpt-4', label: 'GPT-4' },
      { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo（经济版）' },
    ]
  },
  gemini: {
    name: 'Google Gemini',
    icon: '💎',
    desc: 'Google 最新多模态大模型系列',
    keyHint: '前往 aistudio.google.com 申请 API Key',
    models: [
      { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash（推荐 · 最新）' },
      { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro（旗舰）' },
      { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash（快速）' },
      { value: 'gemini-pro', label: 'Gemini Pro（经典）' },
    ]
  },
  deepseek: {
    name: 'DeepSeek',
    icon: '🔮',
    desc: '国产顶级推理模型，性能强劲',
    keyHint: '前往 platform.deepseek.com 获取 API Key',
    models: [
      { value: 'deepseek-chat', label: 'DeepSeek-V3（推荐 · 综合能力强）' },
      { value: 'deepseek-reasoner', label: 'DeepSeek-R1（逻辑推理增强）' },
    ]
  },
  qwen: {
    name: '阿里通义千问',
    icon: '🌙',
    desc: '阿里云大模型，中文能力出色',
    keyHint: '前往 dashscope.aliyuncs.com 获取 API Key',
    models: [
      { value: 'qwen-turbo', label: 'Qwen-Turbo（速度快 · 低延迟）' },
      { value: 'qwen-plus', label: 'Qwen-Plus（推荐 · 均衡）' },
      { value: 'qwen-max', label: 'Qwen-Max（旗舰版）' },
      { value: 'qwen-long', label: 'Qwen-Long（超长文本）' },
    ]
  },
  nvidia_zai: {
    name: 'NVIDIA Z-AI',
    icon: '⚡',
    desc: 'NVIDIA Z-AI 平台模型',
    keyHint: '前往 NVIDIA Z-AI 平台获取 API Key',
    models: [
      { value: 'z-ai/glm5', label: 'GLM-5' },
      { value: 'z-ai/glm4.7', label: 'GLM-4.7' },
    ]
  }
}

// -------- 状态 --------
const keyList = ref([])
const useSystemKey = ref(true)
const preferredModel = ref('glm')
const saving = ref(false)

const dialogVisible = ref(false)
const editIndex = ref(-1)
const dialogForm = ref({
  provider: '',
  model: '',
  api_key: '',
  enabled: true
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
    api_key: '',
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

  if (editIndex.value >= 0) {
    const old = keyList.value[editIndex.value]
    keyList.value[editIndex.value] = {
      ...old,
      provider: dialogForm.value.provider,
      model: dialogForm.value.model,
      enabled: dialogForm.value.enabled,
      api_key: dialogForm.value.api_key || old.api_key,
      api_key_masked: dialogForm.value.api_key ? maskKey(dialogForm.value.api_key) : old.api_key_masked,
      _testStatus: null
    }
    MessagePlugin.success('已更新，请点保存配置')
  } else {
    keyList.value.push({
      id: Date.now().toString(),
      provider: dialogForm.value.provider,
      model: dialogForm.value.model,
      api_key: dialogForm.value.api_key,
      api_key_masked: maskKey(dialogForm.value.api_key),
      enabled: dialogForm.value.enabled,
      _testStatus: null
    })
    MessagePlugin.success('已添加，请点保存配置')
  }

  dialogVisible.value = false
}

function handleDelete(index) {
  keyList.value.splice(index, 1)
  MessagePlugin.success('已删除，请点保存配置')
}

async function handleTest(item) {
  if (!item.enabled) {
    MessagePlugin.warning('请先启用该Key')
    return
  }
  if (!item.api_key) {
    MessagePlugin.warning('该Key未显示，请先点击编辑按钮重新输入API Key后再测试')
    return
  }
  item._testStatus = 'testing'
  try {
    await tenantApi.testApiKey({
      provider: item.provider,
      model: item.model,
      api_key: item.api_key
    })
    item._testStatus = 'ok'
    MessagePlugin.success('连接测试成功 ✅')
  } catch (e) {
    item._testStatus = 'fail'
  }
}

async function handleSaveAll() {
  saving.value = true
  try {
    await tenantApi.updateApiKeys({
      use_system_api_key: useSystemKey.value,
      preferred_model: preferredModel.value,
      api_keys_list: keyList.value.map(k => ({
        id: k.id,
        provider: k.provider,
        model: k.model,
        api_key: k.api_key || '',
        enabled: k.enabled
      }))
    })
    MessagePlugin.success('配置保存成功 ✅')
    await loadData()
  } catch (e) {
    // 错误由拦截器处理
  } finally {
    saving.value = false
  }
}

async function loadData() {
  try {
    const profile = await tenantApi.getProfile()
    useSystemKey.value = profile.use_system_api_key ?? true
    preferredModel.value = profile.preferred_model || 'glm'
    keyList.value = (profile.api_keys_list || []).map(k => ({
      ...k,
      _testStatus: null
    }))
  } catch (e) {}
}

onMounted(loadData)
</script>

<style scoped>
.api-keys-page { padding: 0; }

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

/* 策略卡片 */
.strategy-card {
  margin-bottom: 16px;
}

.strategy-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.strategy-info { flex: 1; }

.strategy-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
}

.strategy-desc {
  font-size: 13px;
  color: #888;
  line-height: 1.5;
}

.strategy-switch {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.switch-text {
  font-size: 12px;
  color: #888;
  white-space: nowrap;
}

/* Key 列表 */
.key-list-card { margin-bottom: 20px; }

.empty-state {
  text-align: center;
  padding: 50px 0;
  color: #999;
}

.key-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  margin-bottom: 10px;
  background: #fff;
  transition: all 0.2s;
}

.key-item:hover {
  border-color: #b3d4ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.08);
}

.key-item.disabled {
  opacity: 0.5;
  background: #fafafa;
}

.key-provider {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 160px;
}

.provider-icon { font-size: 24px; }

.provider-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.provider-model {
  font-size: 12px;
  color: #888;
  margin-top: 2px;
  max-width: 130px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

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

.key-test-status {
  min-width: 90px;
  text-align: center;
}

.test-placeholder { color: #ccc; }

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
  min-width: 40px;
}

.model-desc {
  font-size: 12px;
  color: #1890ff;
  margin-top: 4px;
  padding-left: 2px;
}

.key-hint {
  font-size: 12px;
  color: #aaa;
  margin-top: 4px;
  line-height: 1.5;
}
</style>
