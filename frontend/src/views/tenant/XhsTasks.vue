<template>
  <div class="page-container">
    <div class="page-header">
      <h2>🚀 小红书发布任务</h2>
      <t-button theme="primary" @click="openCreate">+ 新建任务</t-button>
    </div>

    <t-loading :loading="loading">
      <t-table
        :data="tasks"
        :columns="columns"
        row-key="id"
        hover
        stripe
        empty="暂无任务"
      >
        <template #status="{ row }">
          <t-tag :theme="statusTheme(row.status)" size="small">{{ statusLabel(row.status) }}</t-tag>
        </template>

        <template #account="{ row }">{{ row.account_nickname }}</template>

        <template #generated="{ row }">
          <t-button v-if="row.generated_content" size="small" variant="text" @click="previewContent(row)">
            预览内容
          </t-button>
          <span v-else style="color:#ccc">—</span>
        </template>

        <template #actions="{ row }">
          <t-space>
            <!-- 草稿/失败：可生成 -->
            <t-button
              v-if="['draft','generated','failed'].includes(row.status)"
              size="small" theme="primary"
              :loading="row._generating"
              @click="generateArticle(row)"
            >
              {{ row.generated_content ? '重新生成' : '生成文章' }}
            </t-button>

            <!-- 已生成：可发布 -->
            <t-button
              v-if="['generated','failed'].includes(row.status) && row.generated_content"
              size="small" theme="success"
              :loading="row._publishing"
              @click="publishTask(row)"
            >
              发布
            </t-button>

            <!-- 发布中：禁用 -->
            <t-button v-if="row.status === 'publishing'" size="small" disabled>发布中...</t-button>

            <!-- 已发布：查看链接 -->
            <t-button
              v-if="row.status === 'published' && row.published_url"
              size="small" variant="text"
              @click="openUrl(row.published_url)"
            >
              查看笔记
            </t-button>

            <t-button size="small" variant="text" @click="openEdit(row)">编辑</t-button>
            <t-popconfirm content="确认删除该任务？" @confirm="deleteTask(row.id)">
              <t-button size="small" variant="text" theme="danger">删除</t-button>
            </t-popconfirm>
          </t-space>
        </template>
      </t-table>
    </t-loading>

    <!-- 新建/编辑任务 抽屉 -->
    <t-drawer
      v-model:visible="drawerVisible"
      :header="editingId ? '编辑任务' : '新建发布任务'"
      size="680px"
      :confirm-btn="{ content: '保存任务', loading: saving }"
      @confirm="saveTask"
    >
      <t-form :data="taskForm" label-width="110px" style="padding:4px 0">
        <t-form-item label="文章标题" name="title">
          <t-input v-model="taskForm.title" placeholder="将作为 AI 生成的主题方向，最终标题由 AI 生成" />
        </t-form-item>

        <t-form-item label="发布账号">
          <t-select v-model="taskForm.account_id" placeholder="选择发布账号">
            <t-option v-for="a in accounts" :key="a.id" :value="a.id"
              :label="`${a.nickname}${a.has_cookies ? '' : ' ⚠️无Cookies'}`" />
          </t-select>
        </t-form-item>

        <t-form-item label="角色说明">
          <t-textarea v-model="taskForm.system_prompt" :rows="3"
            placeholder="大模型角色，留空使用默认小红书创作者人设" />
          <div class="form-tip">留空将使用默认提示词（专业小红书创作者）</div>
        </t-form-item>

        <t-form-item label="内容提示词">
          <t-textarea v-model="taskForm.user_prompt" :rows="5"
            placeholder="描述你想要的内容，如：写一篇关于上海外滩探店的笔记，推荐3家网红餐厅，风格活泼有趣" />
        </t-form-item>

        <t-form-item label="使用的API Key">
          <div class="api-key-section">
            <t-radio-group v-model="taskForm.apiKeyMode">
              <t-radio value="tenant">使用账户默认 API Key</t-radio>
              <t-radio value="custom">自定义 API Key</t-radio>
            </t-radio-group>
            <div v-if="taskForm.apiKeyMode === 'custom'" class="custom-api" style="margin-top:10px">
              <t-select v-model="taskForm.api_key_config.provider" placeholder="选择厂商" style="width:140px;margin-right:8px">
                <t-option value="openai" label="OpenAI" />
                <t-option value="deepseek" label="DeepSeek" />
                <t-option value="qwen" label="通义千问" />
                <t-option value="glm" label="智谱 GLM" />
                <t-option value="moonshot" label="Moonshot" />
              </t-select>
              <t-input v-model="taskForm.api_key_config.model" placeholder="模型，如 gpt-4o-mini" style="width:160px;margin-right:8px" />
              <t-input v-model="taskForm.api_key_config.api_key" placeholder="API Key" type="password" style="flex:1" />
            </div>
          </div>
        </t-form-item>

        <t-form-item label="关联素材">
          <div class="material-select">
            <div class="material-list" v-if="materials.length">
              <t-checkbox-group v-model="taskForm.material_ids">
                <div v-for="m in materials" :key="m.id" class="material-item">
                  <t-checkbox :value="m.id">
                    <t-tag size="small" :theme="typeTheme(m.material_type)" style="margin-right:4px">{{ typeLabel(m.material_type) }}</t-tag>
                    {{ m.name }}
                  </t-checkbox>
                </div>
              </t-checkbox-group>
            </div>
            <t-empty v-else size="small" description="暂无素材（可在素材库中添加）" />
          </div>
          <div class="form-tip">选中的素材内容会加入 AI 提示词中，用于生成参考</div>
        </t-form-item>
      </t-form>
    </t-drawer>

    <!-- 内容预览弹窗 -->
    <t-dialog
      v-model:visible="previewVisible"
      header="生成内容预览"
      width="640px"
      :footer="false"
    >
      <div class="preview-box" v-if="previewTask">
        <div class="preview-title">
          <strong>标题：</strong>{{ previewTask.generated_title || previewTask.title }}
        </div>
        <div class="preview-content">{{ previewTask.generated_content }}</div>
        <div class="preview-tags" v-if="previewTask.generated_tags">
          <t-tag v-for="t in previewTask.generated_tags.split(',')" :key="t" size="small" theme="primary" style="margin:3px">
            #{{ t.trim() }}
          </t-tag>
        </div>
        <div class="preview-error" v-if="previewTask.error_message">
          <t-alert theme="error" :title="previewTask.error_message" />
        </div>
      </div>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { xhsApi } from '@/api/index.js'

const tasks = ref([])
const accounts = ref([])
const materials = ref([])
const loading = ref(false)
const drawerVisible = ref(false)
const previewVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const previewTask = ref(null)

const DEFAULT_SYSTEM_PROMPT = '你是一位专业的小红书内容创作者，擅长写出高质量、有吸引力的笔记。你的文章风格轻松活泼，善用 emoji，语言亲切自然，容易引发读者共鸣。每篇文章包含：吸引人的开头、干货内容、实用建议，结尾引导互动（点赞/收藏/评论）。标题要简短有力，控制在 20 字以内。文末提供 3-5 个适合的话题标签（#标签 格式）。'

const taskForm = ref(emptyForm())

function emptyForm() {
  return {
    title: '',
    account_id: null,
    system_prompt: '',
    user_prompt: '',
    material_ids: [],
    apiKeyMode: 'tenant',
    api_key_config: { provider: 'openai', model: 'gpt-4o-mini', api_key: '' },
  }
}

const typeTheme = (t) => ({ text: 'primary', image: 'success', reference: 'warning' }[t] || 'default')
const typeLabel = (t) => ({ text: '文字', image: '图片', reference: '参考' }[t] || t)

const statusTheme = (s) => ({
  draft: 'default', generating: 'warning', generated: 'primary',
  publishing: 'warning', published: 'success', failed: 'danger'
}[s] || 'default')

const statusLabel = (s) => ({
  draft: '草稿', generating: '生成中', generated: '待发布',
  publishing: '发布中', published: '已发布', failed: '失败'
}[s] || s)

const columns = [
  { colKey: 'title', title: '文章标题', ellipsis: true, width: 200 },
  { colKey: 'account', title: '发布账号', width: 120 },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'generated', title: '生成内容', width: 100 },
  { colKey: 'created_at', title: '创建时间', width: 160, cell: ({ row }) => row.created_at?.slice(0,16).replace('T',' ') },
  { colKey: 'actions', title: '操作', width: 300 },
]

async function loadAll() {
  loading.value = true
  try {
    const [t, a, m] = await Promise.all([xhsApi.getTasks(), xhsApi.getAccounts(), xhsApi.getMaterials()])
    tasks.value = t.map(task => ({ ...task, _generating: false, _publishing: false }))
    accounts.value = a
    materials.value = m
  } finally { loading.value = false }
}

function openCreate() {
  editingId.value = null
  taskForm.value = emptyForm()
  drawerVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  taskForm.value = {
    title: row.title,
    account_id: row.account_id,
    system_prompt: row.system_prompt || '',
    user_prompt: row.user_prompt || '',
    material_ids: row.material_ids || [],
    apiKeyMode: 'tenant',
    api_key_config: { provider: 'openai', model: 'gpt-4o-mini', api_key: '' },
  }
  drawerVisible.value = true
}

async function saveTask() {
  if (!taskForm.value.title.trim()) return MessagePlugin.warning('请填写文章标题')
  if (!taskForm.value.account_id) return MessagePlugin.warning('请选择发布账号')
  if (!taskForm.value.user_prompt.trim()) return MessagePlugin.warning('请填写内容提示词')

  const payload = {
    title: taskForm.value.title,
    account_id: taskForm.value.account_id,
    system_prompt: taskForm.value.system_prompt || DEFAULT_SYSTEM_PROMPT,
    user_prompt: taskForm.value.user_prompt,
    material_ids: taskForm.value.material_ids,
    api_key_config: taskForm.value.apiKeyMode === 'custom' ? taskForm.value.api_key_config : null,
  }

  saving.value = true
  try {
    if (editingId.value) {
      await xhsApi.updateTask(editingId.value, payload)
      MessagePlugin.success('任务已更新')
    } else {
      await xhsApi.createTask(payload)
      MessagePlugin.success('任务创建成功')
    }
    drawerVisible.value = false
    loadAll()
  } finally { saving.value = false }
}

async function generateArticle(row) {
  row._generating = true
  try {
    const result = await xhsApi.generateArticle(row.id)
    MessagePlugin.success('文章生成成功！')
    // 更新本地数据
    Object.assign(row, {
      status: 'generated',
      generated_title: result.generated_title,
      generated_content: result.generated_content,
      generated_tags: result.generated_tags,
      _generating: false,
    })
  } catch {
    row._generating = false
    // 错误已由拦截器弹出
  }
}

async function publishTask(row) {
  row._publishing = true
  try {
    await xhsApi.publishTask(row.id)
    MessagePlugin.success('发布任务已启动，请稍后刷新查看结果')
    row.status = 'publishing'
  } catch {
    // 错误已由拦截器处理
  } finally { row._publishing = false }
}

async function deleteTask(id) {
  await xhsApi.deleteTask(id)
  MessagePlugin.success('任务已删除')
  loadAll()
}

function previewContent(row) {
  previewTask.value = row
  previewVisible.value = true
}

function openUrl(url) {
  window.open(url, '_blank')
}

onMounted(loadAll)
</script>

<style scoped>
.page-container { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 20px; }

.form-tip { color: #999; font-size: 12px; margin-top: 4px; }

.api-key-section { width: 100%; }
.custom-api { display: flex; align-items: center; flex-wrap: wrap; gap: 0; }

.material-list { max-height: 200px; overflow-y: auto; border: 1px solid #e8e8e8; border-radius: 6px; padding: 8px; }
.material-item { padding: 4px 0; }

.preview-box { display: flex; flex-direction: column; gap: 12px; }
.preview-title { font-size: 18px; font-weight: bold; color: #333; }
.preview-content { white-space: pre-wrap; line-height: 1.8; color: #555; font-size: 14px; max-height: 400px; overflow-y: auto; }
.preview-tags { display: flex; flex-wrap: wrap; gap: 4px; }
</style>
