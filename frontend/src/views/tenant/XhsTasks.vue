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

        <template #materials="{ row }">
          <t-tag v-if="row.material_ids?.length" size="small" theme="default">
            已选 {{ row.material_ids.length }} 个素材
          </t-tag>
          <span v-else style="color:#ccc">—</span>
        </template>

        <template #generated="{ row }">
          <t-button v-if="row.generated_content" size="small" variant="text" @click="previewContent(row)">
            预览内容
          </t-button>
          <span v-else style="color:#ccc">—</span>
        </template>

        <template #actions="{ row }">
          <t-space>
            <t-button
              v-if="['draft','generated','failed'].includes(row.status)"
              size="small" theme="primary"
              :loading="row._generating"
              @click="generateArticle(row)"
            >
              {{ row.generated_content ? '重新生成' : '生成文章' }}
            </t-button>
            <t-button
              v-if="['generated','failed'].includes(row.status) && row.generated_content"
              size="small" theme="success"
              :loading="row._publishing"
              @click="publishTask(row)"
            >发布</t-button>
            <t-button v-if="row.status === 'publishing'" size="small" disabled>发布中...</t-button>
            <t-button
              v-if="row.status === 'published' && row.published_url"
              size="small" variant="text"
              @click="openUrl(row.published_url)"
            >查看笔记</t-button>
            <t-button size="small" variant="text" @click="openEdit(row)">编辑</t-button>
            <t-popconfirm content="确认删除该任务？" @confirm="deleteTask(row.id)">
              <t-button size="small" variant="text" theme="danger">删除</t-button>
            </t-popconfirm>
          </t-space>
        </template>
      </t-table>
    </t-loading>

    <!-- 新建/编辑任务弹窗 -->
    <t-dialog
      v-model:visible="dialogVisible"
      :header="editingId ? '编辑发布任务' : '新建发布任务'"
      width="700px"
      :confirm-btn="{ content: '保存任务', loading: saving }"
      :cancel-btn="{ content: '取消' }"
      @confirm="saveTask"
      @close="dialogVisible = false"
    >
      <t-form :data="taskForm" label-width="110px" style="padding:8px 0">
        <t-form-item label="文章标题" name="title">
          <t-input v-model="taskForm.title" placeholder="将作为 AI 生成的主题方向" />
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
            placeholder="描述你想要的内容，如：写一篇关于上海外滩探店的笔记，推荐3家网红餐厅" />
        </t-form-item>

        <t-form-item label="使用的API Key">
          <t-select
            v-model="taskForm.selected_api_key_id"
            placeholder="选择 API Key（留空使用默认轮询）"
            clearable
          >
            <t-option
              v-for="k in apiKeys"
              :key="k.id"
              :value="k.id"
              :label="`[${k.source}] ${k.provider} / ${k.model}（${k.api_key_masked}）`"
            />
          </t-select>
          <div class="form-tip">留空则自动轮询商户配置的 API Key</div>
        </t-form-item>

        <t-form-item label="关联素材">
          <div class="material-selector">
            <!-- 已选素材标签列表 -->
            <div class="selected-materials" v-if="selectedMaterials.length">
              <div class="selected-material-item" v-for="sm in selectedMaterials" :key="sm.id">
                <img v-if="sm.url" :src="sm.url" class="selected-material-thumb" />
                <div v-else class="selected-material-thumb no-img">🖼️</div>
                <span class="selected-material-name">{{ sm.name }}</span>
                <t-button size="small" variant="text" theme="danger" @click="removeMaterial(sm.id)">
                  <template #icon><t-icon name="close" size="12px" /></template>
                </t-button>
              </div>
            </div>
            <div v-else class="no-materials">暂未选择素材</div>
            <t-button size="small" variant="outline" @click="openMaterialPicker" style="margin-top:8px">
              <template #icon><t-icon name="add" /></template> 选择素材
            </t-button>
          </div>
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- 素材选择器弹窗 -->
    <t-dialog
      v-model:visible="materialPickerVisible"
      header="选择素材"
      width="680px"
      :confirm-btn="{ content: '确认选择' }"
      :cancel-btn="{ content: '取消' }"
      @confirm="confirmMaterialPick"
      @close="materialPickerVisible = false"
    >
      <div class="material-picker-grid" v-if="allMaterials.length">
        <div
          class="picker-item"
          :class="{ 'picker-item--selected': pickerSelectedIds.includes(m.id) }"
          v-for="m in allMaterials"
          :key="m.id"
          @click="togglePickerSelect(m.id)"
        >
          <div class="picker-check">
            <t-checkbox :checked="pickerSelectedIds.includes(m.id)" />
          </div>
          <img v-if="m.url" :src="m.url" class="picker-thumb" />
          <div v-else class="picker-thumb no-img">🖼️</div>
          <div class="picker-name">{{ m.name }}</div>
        </div>
      </div>
      <t-empty v-else description="暂无图片素材，请先在素材库中上传" />
    </t-dialog>

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
import { ref, computed, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { xhsApi } from '@/api/index.js'

const tasks = ref([])
const accounts = ref([])
const apiKeys = ref([])
const allMaterials = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const previewVisible = ref(false)
const materialPickerVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const previewTask = ref(null)

const DEFAULT_SYSTEM_PROMPT = '你是一位专业的小红书内容创作者，擅长写出高质量、有吸引力的笔记。你的文章风格轻松活泼，善用 emoji，语言亲切自然，容易引发读者共鸣。每篇文章包含：吸引人的开头、干货内容、实用建议，结尾引导互动（点赞/收藏/评论）。标题要简短有力，控制在 20 字以内。文末提供 3-5 个适合的话题标签（#标签 格式）。'

const taskForm = ref(emptyForm())
const pickerSelectedIds = ref([])

// 已选素材（完整对象，用于显示缩略图）
const selectedMaterials = computed(() => {
  return allMaterials.value.filter(m => taskForm.value.material_ids.includes(m.id))
})

function emptyForm() {
  return {
    title: '',
    account_id: null,
    system_prompt: '',
    user_prompt: '',
    material_ids: [],
    selected_api_key_id: null,
  }
}

const statusTheme = (s) => ({
  draft: 'default', generating: 'warning', generated: 'primary',
  publishing: 'warning', published: 'success', failed: 'danger'
}[s] || 'default')

const statusLabel = (s) => ({
  draft: '草稿', generating: '生成中', generated: '待发布',
  publishing: '发布中', published: '已发布', failed: '失败'
}[s] || s)

const columns = [
  { colKey: 'title', title: '文章标题', ellipsis: true, width: 180 },
  { colKey: 'account', title: '发布账号', width: 120 },
  { colKey: 'materials', title: '素材', width: 120 },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'generated', title: '生成内容', width: 100 },
  { colKey: 'created_at', title: '创建时间', width: 160, cell: ({ row }) => row.created_at?.slice(0,16).replace('T',' ') },
  { colKey: 'actions', title: '操作', width: 300 },
]

async function loadAll() {
  loading.value = true
  try {
    const [t, a, k, m] = await Promise.all([
      xhsApi.getTasks(),
      xhsApi.getAccounts(),
      xhsApi.getApiKeys(),
      xhsApi.getMaterials('image'),
    ])
    tasks.value = t.map(task => ({ ...task, _generating: false, _publishing: false }))
    accounts.value = a
    apiKeys.value = k
    allMaterials.value = m
  } finally { loading.value = false }
}

function openCreate() {
  editingId.value = null
  taskForm.value = emptyForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  // 尝试匹配已选 API Key
  let selected_api_key_id = null
  if (row.api_key_config) {
    const cfg = row.api_key_config
    const match = apiKeys.value.find(k =>
      k.provider === cfg.provider && k.model === cfg.model && k.api_key === cfg.api_key
    )
    if (match) selected_api_key_id = match.id
  }
  taskForm.value = {
    title: row.title,
    account_id: row.account_id,
    system_prompt: row.system_prompt || '',
    user_prompt: row.user_prompt || '',
    material_ids: row.material_ids || [],
    selected_api_key_id,
  }
  dialogVisible.value = true
}

async function saveTask() {
  if (!taskForm.value.title.trim()) return MessagePlugin.warning('请填写文章标题')
  if (!taskForm.value.account_id) return MessagePlugin.warning('请选择发布账号')
  if (!taskForm.value.user_prompt.trim()) return MessagePlugin.warning('请填写内容提示词')

  // 根据 selected_api_key_id 查找完整 key 配置
  let api_key_config = null
  if (taskForm.value.selected_api_key_id) {
    const key = apiKeys.value.find(k => k.id === taskForm.value.selected_api_key_id)
    if (key) {
      api_key_config = {
        provider: key.provider,
        model: key.model,
        api_key: key.api_key,
      }
    }
  }

  const payload = {
    title: taskForm.value.title,
    account_id: taskForm.value.account_id,
    system_prompt: taskForm.value.system_prompt || DEFAULT_SYSTEM_PROMPT,
    user_prompt: taskForm.value.user_prompt,
    material_ids: taskForm.value.material_ids,
    api_key_config,
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
    dialogVisible.value = false
    loadAll()
  } finally { saving.value = false }
}

// 素材选择器
function openMaterialPicker() {
  pickerSelectedIds.value = [...taskForm.value.material_ids]
  materialPickerVisible.value = true
}

function togglePickerSelect(id) {
  const idx = pickerSelectedIds.value.indexOf(id)
  if (idx >= 0) pickerSelectedIds.value.splice(idx, 1)
  else pickerSelectedIds.value.push(id)
}

function confirmMaterialPick() {
  taskForm.value.material_ids = [...pickerSelectedIds.value]
}

function removeMaterial(id) {
  const idx = taskForm.value.material_ids.indexOf(id)
  if (idx >= 0) taskForm.value.material_ids.splice(idx, 1)
}

async function generateArticle(row) {
  row._generating = true
  try {
    const result = await xhsApi.generateArticle(row.id)
    MessagePlugin.success('文章生成成功！')
    Object.assign(row, {
      status: 'generated',
      generated_title: result.generated_title,
      generated_content: result.generated_content,
      generated_tags: result.generated_tags,
      _generating: false,
    })
  } catch {
    row._generating = false
  }
}

async function publishTask(row) {
  row._publishing = true
  try {
    await xhsApi.publishTask(row.id)
    MessagePlugin.success('发布任务已启动，请稍后刷新查看结果')
    row.status = 'publishing'
  } catch {} finally { row._publishing = false }
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

function openUrl(url) { window.open(url, '_blank') }

onMounted(loadAll)
</script>

<style scoped>
.page-container { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 20px; }
.form-tip { color: #999; font-size: 12px; margin-top: 4px; }

/* 素材选择区域 */
.material-selector { width: 100%; }
.selected-materials {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  min-height: 60px;
}
.no-materials {
  padding: 12px 8px;
  color: #bbb;
  font-size: 13px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  text-align: center;
}
.selected-material-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  background: #f5f5f5;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}
.selected-material-thumb {
  width: 32px;
  height: 32px;
  object-fit: cover;
  border-radius: 4px;
}
.selected-material-thumb.no-img {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eee;
  font-size: 14px;
  color: #ccc;
}
.selected-material-name {
  font-size: 12px;
  max-width: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 素材选择器弹窗 */
.material-picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}
.picker-item {
  position: relative;
  border: 2px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.15s;
}
.picker-item:hover { border-color: #bbb; }
.picker-item--selected {
  border-color: #0052d9;
  background: #f0f5ff;
}
.picker-check {
  position: absolute;
  top: 6px;
  left: 6px;
  z-index: 2;
  background: rgba(255,255,255,0.85);
  border-radius: 4px;
  padding: 2px;
}
.picker-thumb {
  width: 100%;
  height: 100px;
  object-fit: cover;
}
.picker-thumb.no-img {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  font-size: 28px;
  color: #ccc;
}
.picker-name {
  padding: 4px 6px;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 内容预览 */
.preview-box { display: flex; flex-direction: column; gap: 12px; }
.preview-title { font-size: 18px; font-weight: bold; color: #333; }
.preview-content { white-space: pre-wrap; line-height: 1.8; color: #555; font-size: 14px; max-height: 400px; overflow-y: auto; }
.preview-tags { display: flex; flex-wrap: wrap; gap: 4px; }
</style>
