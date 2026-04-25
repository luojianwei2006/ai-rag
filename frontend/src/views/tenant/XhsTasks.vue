<template>
  <!-- 任务列表视图 -->
  <div class="page-container" v-if="!dialogVisible">
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
          <div class="table-materials" v-if="row.material_ids?.length">
            <img v-for="mid in row.material_ids.slice(0, 5)" :key="mid"
              :src="getMaterialUrl(mid)" class="table-material-thumb" />
            <span v-if="row.material_ids.length > 5" class="table-material-more">+{{ row.material_ids.length - 5 }}</span>
          </div>
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

  <!-- 新建/编辑任务 — 全屏视图 -->
  <div class="fullscreen-task" v-if="dialogVisible">
    <div class="fullscreen-header">
      <t-button variant="text" @click="goBack">
        <template #icon><t-icon name="chevron-left" /></template>
        返回列表
      </t-button>
      <span class="fullscreen-title">{{ editingId ? '编辑发布任务' : '新建发布任务' }}</span>
      <t-button theme="primary" :loading="saving" @click="saveTask">保存任务</t-button>
    </div>

    <div class="fullscreen-body">
      <div class="form-section">
        <div class="form-section-title">基本信息</div>
        <div class="form-row">
          <div class="form-item">
            <label>文章标题</label>
            <t-input v-model="taskForm.title" placeholder="将作为 AI 生成的主题方向" />
          </div>
          <div class="form-item">
            <label>发布账号</label>
            <t-select v-model="taskForm.account_id" placeholder="选择发布账号">
              <t-option v-for="a in accounts" :key="a.id" :value="a.id"
                :label="`${a.nickname}${a.has_cookies ? '' : ' ⚠️无Cookies'}`" />
            </t-select>
          </div>
        </div>
        <div class="form-row">
          <div class="form-item full">
            <label>角色说明 <span class="optional">（选填）</span></label>
            <t-textarea v-model="taskForm.system_prompt" :rows="2"
              placeholder="大模型角色，留空使用默认小红书创作者人设" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-item full">
            <label>内容提示词</label>
            <t-textarea v-model="taskForm.user_prompt" :rows="4"
              placeholder="描述你想要的内容，如：写一篇关于上海外滩探店的笔记，推荐3家网红餐厅" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-item">
            <label>使用的API Key</label>
            <t-select v-model="taskForm.selected_api_key_id" placeholder="默认轮询">
              <t-option :value="null" label="默认（自动轮询）" />
            </t-select>
            <div class="form-tip">留空则自动轮询商户配置的 API Key</div>
          </div>
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">
          关联素材
          <span class="section-action" @click="openMaterialPicker">选择素材</span>
        </div>
        <div class="selected-materials-area">
          <div class="selected-materials-grid" v-if="selectedMaterials.length">
            <div class="sel-material-card" v-for="sm in selectedMaterials" :key="sm.id">
              <img v-if="sm.url" :src="sm.url" class="sel-material-img" />
              <div v-else class="sel-material-img no-img">🖼️</div>
              <div class="sel-material-remove" @click="removeMaterial(sm.id)">
                <t-icon name="close" size="14px" />
              </div>
              <div class="sel-material-size" v-if="sm.width && sm.height">{{ sm.width }}×{{ sm.height }}</div>
            </div>
          </div>
          <div v-else class="no-materials-hint">
            <t-icon name="image" size="32px" style="color:#ccc" />
            <div>暂未选择素材，点击上方"选择素材"添加</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 素材选择器 — 全屏弹窗 -->
    <t-dialog
      v-model:visible="materialPickerVisible"
      header="选择素材"
      :width="'90vw'"
      :top="'5vh'"
      :confirm-btn="{ content: '确认选择', theme: 'primary' }"
      :cancel-btn="{ content: '取消' }"
      @confirm="confirmMaterialPick"
      @close="materialPickerVisible = false"
      class="material-picker-dialog"
    >
      <div class="material-picker-grid" v-if="allMaterials.length">
        <div
          class="picker-card"
          :class="{ 'picker-card--selected': pickerSelectedIds.includes(m.id) }"
          v-for="m in allMaterials"
          :key="m.id"
          @click="togglePickerSelect(m.id)"
        >
          <div class="picker-card-check" v-if="pickerSelectedIds.includes(m.id)">
            <t-icon name="check-circle-filled" size="24px" style="color:#0052d9" />
          </div>
          <img v-if="m.url" :src="m.url" class="picker-card-img" />
          <div v-else class="picker-card-img no-img">🖼️</div>
        </div>
      </div>
      <t-empty v-else description="暂无图片素材，请先在素材库中上传" />
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { xhsApi } from '@/api/index.js'

const tasks = ref([])
const accounts = ref([])
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

const selectedMaterials = computed(() => {
  return allMaterials.value.filter(m => taskForm.value.material_ids.includes(m.id))
})

function getMaterialUrl(id) {
  const m = allMaterials.value.find(m => m.id === id)
  return m?.url || ''
}

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
  { colKey: 'materials', title: '关联素材', width: 220 },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'generated', title: '生成内容', width: 100 },
  { colKey: 'created_at', title: '创建时间', width: 160, cell: ({ row }) => (row?.created_at || '').slice(0,16).replace('T',' ') },
  { colKey: 'actions', title: '操作', width: 300 },
]

async function loadAll() {
  loading.value = true
  try {
    const [t, a, m] = await Promise.all([
      xhsApi.getTasks(),
      xhsApi.getAccounts(),
      xhsApi.getMaterials('image'),
    ])
    tasks.value = t.map(task => ({ ...task, _generating: false, _publishing: false }))
    accounts.value = a
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
  taskForm.value = {
    title: row.title,
    account_id: row.account_id,
    system_prompt: row.system_prompt || '',
    user_prompt: row.user_prompt || '',
    material_ids: row.material_ids || [],
    selected_api_key_id: null,
  }
  dialogVisible.value = true
}

function goBack() {
  dialogVisible.value = false
}

async function saveTask() {
  if (!taskForm.value.title.trim()) return MessagePlugin.warning('请填写文章标题')
  if (!taskForm.value.account_id) return MessagePlugin.warning('请选择发布账号')
  if (!taskForm.value.user_prompt.trim()) return MessagePlugin.warning('请填写内容提示词')

  // API Key 不再指定具体 key，统一使用默认轮询
  const payload = {
    title: taskForm.value.title,
    account_id: taskForm.value.account_id,
    system_prompt: taskForm.value.system_prompt || DEFAULT_SYSTEM_PROMPT,
    user_prompt: taskForm.value.user_prompt,
    material_ids: taskForm.value.material_ids,
    api_key_config: null,
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
    await nextTick()
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
/* ===== 列表视图 ===== */
.page-container { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 20px; }

/* 表格中的素材缩略图 */
.table-materials {
  display: flex;
  align-items: center;
  gap: 4px;
}
.table-material-thumb {
  width: 28px;
  height: 28px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #eee;
}
.table-material-more {
  font-size: 12px;
  color: #999;
  margin-left: 2px;
}

/* ===== 全屏任务编辑视图 ===== */
.fullscreen-task {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
}
.fullscreen-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: white;
  border-bottom: 1px solid #e8e8e8;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  flex-shrink: 0;
}
.fullscreen-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  flex: 1;
}
.fullscreen-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

/* 表单区块 */
.form-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.form-section-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.section-action {
  font-size: 13px;
  color: #0052d9;
  cursor: pointer;
  font-weight: 400;
}
.section-action:hover { color: #003cab; text-decoration: underline; }

.form-row {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
}
.form-item { flex: 1; }
.form-item.full { flex: unset; width: 100%; }
.form-item label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #666;
  margin-bottom: 6px;
}
.optional { color: #bbb; font-weight: 400; }
.form-tip { color: #999; font-size: 12px; margin-top: 4px; }

/* 已选素材区域 */
.selected-materials-area {
  min-height: 120px;
}
.selected-materials-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.sel-material-card {
  position: relative;
  width: 140px;
  border-radius: 10px;
  overflow: hidden;
  border: 2px solid #e8e8e8;
  transition: border-color 0.15s;
}
.sel-material-card:hover { border-color: #bbb; }
.sel-material-img {
  width: 140px;
  height: 140px;
  object-fit: cover;
  display: block;
}
.sel-material-img.no-img {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  font-size: 32px;
  color: #ccc;
}
.sel-material-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
}
.sel-material-card:hover .sel-material-remove { opacity: 1; }
.sel-material-remove { color: white; }
.sel-material-size {
  position: absolute;
  bottom: 4px;
  right: 4px;
  font-size: 10px;
  color: white;
  background: rgba(0,0,0,0.5);
  padding: 1px 6px;
  border-radius: 3px;
}
.no-materials-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 120px;
  color: #bbb;
  font-size: 13px;
}

/* ===== 素材选择器 — 全屏弹窗内 ===== */
:deep(.material-picker-dialog .t-dialog__ctx) {
  max-height: none;
}
.material-picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  max-height: 70vh;
  overflow-y: auto;
  padding: 4px;
}
.picker-card {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  border: 3px solid #e8e8e8;
  transition: all 0.15s;
  aspect-ratio: 1;
}
.picker-card:hover { border-color: #bbb; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.picker-card--selected {
  border-color: #0052d9;
  box-shadow: 0 0 0 2px rgba(0,82,217,0.2);
}
.picker-card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.picker-card-img.no-img {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  font-size: 48px;
  color: #ccc;
}
.picker-card-check {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
  filter: drop-shadow(0 1px 2px rgba(0,0,0,0.3));
}

/* ===== 内容预览 ===== */
.preview-box { display: flex; flex-direction: column; gap: 12px; }
.preview-title { font-size: 18px; font-weight: bold; color: #333; }
.preview-content { white-space: pre-wrap; line-height: 1.8; color: #555; font-size: 14px; max-height: 400px; overflow-y: auto; }
.preview-tags { display: flex; flex-wrap: wrap; gap: 4px; }
</style>
