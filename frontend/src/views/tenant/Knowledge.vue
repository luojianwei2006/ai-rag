<template>
  <div>
    <t-card title="知识库管理" :bordered="false">
      <template #actions>
        <t-button variant="outline" @click="$router.push('/tenant/knowledge-import')">🌐 从网页导入</t-button>
        <t-button theme="primary" @click="showUploadDialog = true">📤 上传文档</t-button>
      </template>

      <t-table :data="kbList" :columns="columns" row-key="id" :loading="loading" stripe>
        <template #status="{ row }">
          <div class="status-cell">
            <t-tag :theme="statusTheme(row.status)">
              {{ statusLabel(row.status) }}
            </t-tag>
            <div v-if="row.status === 'processing'" class="progress-area">
              <t-progress :percentage="row.progress || 0" :color="{ from: '#108ee9', to: '#87d068' }" />
              <div class="progress-message">{{ row.progress_message || '处理中...' }}</div>
            </div>
          </div>
        </template>
        <template #actions="{ row }">
          <t-space>
            <t-button size="small" variant="outline" @click="$router.push(`/tenant/qa-test?kb=${row.id}`)" :disabled="row.status !== 'ready'">
              测试问答
            </t-button>
            <t-popconfirm content="确认删除此知识库？" @confirm="deleteKb(row.id)">
              <t-button size="small" theme="danger" variant="outline">删除</t-button>
            </t-popconfirm>
          </t-space>
        </template>
      </t-table>
    </t-card>

    <!-- 上传对话框 -->
    <t-dialog v-model:visible="showUploadDialog" header="上传知识库文档" :footer="false" width="500px">
      <div class="upload-form">
        <t-form :data="uploadForm" label-width="80px">
          <t-form-item label="知识库名称">
            <t-input v-model="uploadForm.name" placeholder="留空则使用文件名" />
          </t-form-item>
          <t-form-item label="说明">
            <textarea v-model="uploadForm.description" placeholder="选填" rows="2" class="kb-textarea"></textarea>
          </t-form-item>
          <t-form-item label="上传文件">
            <div class="upload-area" @click="triggerUpload" @dragover.prevent @drop.prevent="handleDrop">
              <input ref="fileInput" type="file" accept=".txt,.docx,.doc,.xlsx,.xls" style="display:none" @change="handleFileChange" />
              <div v-if="!selectedFile" class="upload-placeholder">
                <div class="upload-icon">📁</div>
                <div>点击或拖拽文件上传</div>
                <div class="upload-hint">支持 TXT、Word(.docx)、Excel(.xlsx)</div>
              </div>
              <div v-else class="selected-file">
                <span>📄 {{ selectedFile.name }}</span>
                <t-button size="small" variant="text" theme="danger" @click.stop="selectedFile = null">移除</t-button>
              </div>
            </div>
          </t-form-item>
        </t-form>
        <div class="dialog-footer">
          <t-button variant="outline" @click="showUploadDialog = false">取消</t-button>
          <t-button theme="primary" :loading="uploading" @click="handleUpload">上传</t-button>
        </div>
      </div>
    </t-dialog>

    <!-- 处理进度弹窗 -->
    <t-dialog v-model:visible="showProgressDialog" header="文档处理中" :footer="false" :close-on-overlay-click="false" width="480px">
      <div class="progress-dialog-content">
        <div class="progress-file-info">
          <div class="file-icon">📄</div>
          <div class="file-details">
            <div class="file-name">{{ processingFile?.name }}</div>
            <div class="file-size">{{ formatFileSize(processingFile?.size) }}</div>
          </div>
        </div>

        <div class="progress-steps">
          <div class="progress-step" :class="{ active: currentProgress >= 0, completed: currentProgress >= 30 }">
            <div class="step-icon">
              <t-icon v-if="currentProgress >= 30" name="check-circle-filled" style="color: #52c41a;" />
              <t-loading v-else-if="currentProgress > 0 && currentProgress < 30" size="small" />
              <div v-else class="step-dot"></div>
            </div>
            <div class="step-content">
              <div class="step-title">解析文档</div>
              <div class="step-desc">读取文件内容</div>
            </div>
          </div>

          <div class="progress-step" :class="{ active: currentProgress >= 30, completed: currentProgress >= 60 }">
            <div class="step-icon">
              <t-icon v-if="currentProgress >= 60" name="check-circle-filled" style="color: #52c41a;" />
              <t-loading v-else-if="currentProgress >= 30 && currentProgress < 60" size="small" />
              <div v-else class="step-dot"></div>
            </div>
            <div class="step-content">
              <div class="step-title">文本切分</div>
              <div class="step-desc">将文档切分为语义片段</div>
            </div>
          </div>

          <div class="progress-step" :class="{ active: currentProgress >= 60, completed: currentProgress >= 95 }">
            <div class="step-icon">
              <t-icon v-if="currentProgress >= 95" name="check-circle-filled" style="color: #52c41a;" />
              <t-loading v-else-if="currentProgress >= 60 && currentProgress < 95" size="small" />
              <div v-else class="step-dot"></div>
            </div>
            <div class="step-content">
              <div class="step-title">生成向量</div>
              <div class="step-desc">将文本转换为向量索引</div>
            </div>
          </div>

          <div class="progress-step" :class="{ active: currentProgress >= 95, completed: currentProgress >= 100 }">
            <div class="step-icon">
              <t-icon v-if="currentProgress >= 100" name="check-circle-filled" style="color: #52c41a;" />
              <t-loading v-else-if="currentProgress >= 95 && currentProgress < 100" size="small" />
              <div v-else class="step-dot"></div>
            </div>
            <div class="step-content">
              <div class="step-title">完成</div>
              <div class="step-desc">知识库就绪</div>
            </div>
          </div>
        </div>

        <div class="progress-bar-area">
          <t-progress :percentage="currentProgress" :color="{ from: '#108ee9', to: '#87d068' }" />
          <div class="progress-text">{{ progressMessage }}</div>
        </div>

        <div class="progress-actions">
          <t-button theme="primary" :disabled="currentProgress < 100" @click="closeProgressDialog">
            {{ currentProgress >= 100 ? '完成' : '处理中...' }}
          </t-button>
        </div>
      </div>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { knowledgeApi } from '@/api'

const loading = ref(false)
const kbList = ref([])
const showUploadDialog = ref(false)
const uploading = ref(false)
const selectedFile = ref(null)
const fileInput = ref(null)
const uploadForm = ref({ name: '', description: '' })
let refreshTimer = null

// 进度弹窗相关
const showProgressDialog = ref(false)
const currentProgress = ref(0)
const progressMessage = ref('准备处理...')
const processingFile = ref(null)
const processingKbId = ref(null)

const columns = [
  { colKey: 'name', title: '知识库名称' },
  { colKey: 'file_name', title: '文件名', width: 180 },
  { colKey: 'file_type', title: '类型', width: 80 },
  { colKey: 'status', title: '状态', cell: 'status', width: 200 },
  { colKey: 'chunk_count', title: '片段数', width: 80 },
  { colKey: 'created_at', title: '上传时间', width: 160 },
  { colKey: 'actions', title: '操作', cell: 'actions', width: 160 }
]

function statusTheme(s) {
  return { processing: 'warning', ready: 'success', failed: 'danger' }[s] || 'default'
}
function statusLabel(s) {
  return { processing: '处理中', ready: '就绪', failed: '失败' }[s] || s
}

function formatFileSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

async function loadList() {
  loading.value = true
  try {
    kbList.value = await knowledgeApi.list()
    // 如果有正在处理的任务，更新进度弹窗
    if (processingKbId.value && showProgressDialog.value) {
      const processingKb = kbList.value.find(k => k.id === processingKbId.value)
      if (processingKb) {
        currentProgress.value = processingKb.progress || 0
        progressMessage.value = processingKb.progress_message || '处理中...'
        // 处理完成自动关闭
        if (processingKb.status === 'ready' || processingKb.status === 'failed') {
          currentProgress.value = processingKb.status === 'ready' ? 100 : currentProgress.value
          setTimeout(() => {
            showProgressDialog.value = false
            processingKbId.value = null
            MessagePlugin.success(processingKb.status === 'ready' ? '文档处理完成' : '文档处理失败')
          }, 800)
        }
      }
    }
  } finally {
    loading.value = false
  }
}

function triggerUpload() { fileInput.value?.click() }
function handleFileChange(e) { selectedFile.value = e.target.files[0] || null }
function handleDrop(e) { selectedFile.value = e.dataTransfer.files[0] || null }

async function handleUpload() {
  if (!selectedFile.value) return MessagePlugin.warning('请选择文件')
  
  // 前端预检文件大小（50MB）
  const maxSize = 50 * 1024 * 1024
  if (selectedFile.value.size > maxSize) {
    return MessagePlugin.warning(`文件过大（${(selectedFile.value.size / 1024 / 1024).toFixed(1)}MB），最大允许 50MB`)
  }

  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    fd.append('name', uploadForm.value.name)
    fd.append('description', uploadForm.value.description)
    const res = await knowledgeApi.upload(fd)
    
    // 打开进度弹窗
    processingFile.value = selectedFile.value
    processingKbId.value = res.id
    currentProgress.value = 0
    progressMessage.value = '等待处理...'
    showProgressDialog.value = true
    
    MessagePlugin.success('上传成功，开始处理')
    showUploadDialog.value = false
    selectedFile.value = null
    uploadForm.value = { name: '', description: '' }
    loadList()
  } finally {
    uploading.value = false
  }
}

function closeProgressDialog() {
  showProgressDialog.value = false
  processingKbId.value = null
}

async function deleteKb(id) {
  try {
    await knowledgeApi.delete(id)
    MessagePlugin.success('删除成功')
    loadList()
  } catch (e) {}
}

onMounted(() => {
  loadList()
  refreshTimer = setInterval(loadList, 2000) // 加快轮询到2秒
})
onUnmounted(() => clearInterval(refreshTimer))
</script>

<style scoped>
.status-cell { display: flex; flex-direction: column; gap: 6px; }
.progress-area { width: 100%; }
.progress-message { font-size: 12px; color: #888; margin-top: 4px; }

.upload-area {
  border: 2px dashed #d1d5db; border-radius: 10px; padding: 24px;
  cursor: pointer; transition: border-color 0.2s; text-align: center;
}
.upload-area:hover { border-color: #667eea; }
.upload-placeholder .upload-icon { font-size: 36px; margin-bottom: 8px; }
.upload-placeholder { color: #666; }
.upload-hint { font-size: 12px; color: #aaa; margin-top: 4px; }
.selected-file { display: flex; align-items: center; justify-content: space-between; padding: 8px; }
.dialog-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

/* 进度弹窗样式 */
.progress-dialog-content { padding: 8px; }
.progress-file-info {
  display: flex; align-items: center; gap: 12px;
  padding: 16px; background: #f5f7fa; border-radius: 8px;
  margin-bottom: 20px;
}
.file-icon { font-size: 32px; }
.file-name { font-weight: 600; color: #333; }
.file-size { font-size: 13px; color: #888; margin-top: 2px; }

.progress-steps { margin-bottom: 24px; }
.progress-step {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 12px 0; opacity: 0.5;
}
.progress-step.active { opacity: 1; }
.progress-step.completed { opacity: 1; }
.step-icon { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.step-dot { width: 10px; height: 10px; border-radius: 50%; background: #d9d9d9; }
.progress-step.active .step-dot { background: #1890ff; }
.step-content { flex: 1; }
.step-title { font-size: 14px; font-weight: 600; color: #333; }
.step-desc { font-size: 12px; color: #888; margin-top: 2px; }

.progress-bar-area { margin-bottom: 20px; }
.progress-text { text-align: center; font-size: 13px; color: #666; margin-top: 8px; }
.progress-actions { text-align: center; }
.kb-textarea {
  width: 100%;
  min-height: 60px;
  padding: 10px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  font-family: inherit;
}
.kb-textarea:focus {
  border-color: #667eea;
}
</style>
