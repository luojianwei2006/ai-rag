<template>
  <div class="page-container">
    <div class="page-header">
      <h2>🖼️ 素材库</h2>
      <!-- 多选模式操作栏 -->
      <template v-if="selectMode">
        <t-button variant="outline" @click="cancelSelect">取消选择</t-button>
        <t-button variant="outline" @click="selectAll">全选</t-button>
        <t-button
          variant="outline"
          theme="danger"
          :disabled="!selectedIds.length"
          @click="batchDelete"
        >
          批量删除 ({{ selectedIds.length }})
        </t-button>
      </template>
      <template v-else>
        <t-button variant="outline" @click="enterSelect">多选</t-button>
      </template>
    </div>

    <!-- 拖拽上传区域 -->
    <div
      class="drop-zone"
      :class="{ 'drop-zone--active': isDragOver }"
      @dragover.prevent="isDragOver = true"
      @dragleave.prevent="isDragOver = false"
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <div class="drop-zone-content">
        <t-icon name="upload" size="36px" style="color:#bbb" />
        <p>拖拽图片到此处上传，或 <span class="drop-link">点击选择文件</span></p>
        <p class="drop-hint">支持 JPG / PNG / GIF / WebP，可同时拖入多张</p>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        multiple
        style="display:none"
        @change="handleFileSelect"
      />
    </div>

    <!-- 上传进度 -->
    <div v-if="uploading" class="upload-progress">
      <t-loading size="small" />
      <span>上传中... ({{ uploadCount }}/{{ uploadTotal }})</span>
    </div>

    <!-- 图片网格 -->
    <t-loading :loading="loading">
      <div class="materials-grid" v-if="materials.length">
        <div
          class="material-card"
          :class="{
            'material-card--selected': selectMode && selectedIds.includes(m.id),
            'material-card--selectable': selectMode,
          }"
          v-for="m in materials"
          :key="m.id"
        >
          <!-- 多选复选框 -->
          <div v-if="selectMode" class="select-checkbox" @click.stop="toggleSelect(m.id)">
            <t-checkbox :checked="selectedIds.includes(m.id)" />
          </div>

          <!-- 图片预览 -->
          <div
            class="image-preview"
            @click="selectMode ? toggleSelect(m.id) : openEdit(m)"
            :title="selectMode ? '点击选择' : ('点击编辑：' + m.name)"
          >
            <img v-if="m.url" :src="m.url" :alt="m.alt || m.name" />
            <div v-else class="no-image">🖼️</div>
          </div>

          <!-- 图片名称 + 尺寸 -->
          <div class="material-info">
            <div class="material-name" :title="m.name">{{ m.name }}</div>
            <div class="material-size" v-if="m.width && m.height">{{ m.width }} × {{ m.height }}</div>
          </div>

          <!-- 操作栏 -->
          <div class="material-footer">
            <div class="url-copy" v-if="m.url && !selectMode" :title="'点击复制链接'">
              <input
                class="url-input"
                :value="getFullUrl(m.url)"
                readonly
                @focus="($event.target).select()"
              />
              <t-button
                size="small"
                variant="text"
                theme="primary"
                @click.stop="copyUrl(m.url)"
              >
                <template #icon><t-icon name="file-copy" /></template>
              </t-button>
            </div>
            <div class="action-btns" v-if="!selectMode">
              <t-button size="small" variant="text" theme="primary" @click="openEdit(m)">编辑</t-button>
              <t-popconfirm content="确认删除此图片？" @confirm="deleteMaterial(m.id)">
                <t-button size="small" variant="text" theme="danger">删除</t-button>
              </t-popconfirm>
            </div>
          </div>
        </div>
      </div>
      <t-empty v-else-if="!loading" description="暂无图片素材" />
    </t-loading>

    <!-- 编辑弹窗 -->
    <t-dialog
      v-model:visible="editVisible"
      header="编辑图片"
      width="720px"
      :confirm-btn="{ content: '保存', loading: saving }"
      :cancel-btn="{ content: '取消' }"
      @confirm="saveEdit"
      @close="editVisible = false"
    >
      <div class="edit-layout" v-if="editItem">
        <!-- 左侧：图片预览 + 操作 -->
        <div class="edit-preview">
          <div class="edit-preview-wrapper">
            <img
              v-if="editItem.url"
              :src="editItem.url"
              :alt="editItem.alt || editItem.name"
              :style="getEditImgStyle()"
              @load="onEditImgLoad"
            />
          </div>
          <!-- 尺寸调整 -->
          <div class="edit-size-info">
            <span>尺寸：{{ imgNaturalW }} × {{ imgNaturalH }}px</span>
            <span class="edit-size-current" v-if="resizeW && resizeH">
              → {{ resizeW }} × {{ resizeH }}px
            </span>
          </div>
          <!-- 尺寸编辑 -->
          <div class="edit-size-controls">
            <div class="size-row">
              <label>宽：</label>
              <t-input-number
                v-model="resizeW"
                :min="1"
                :max="4000"
                theme="normal"
                size="small"
                style="width:100px"
                @change="onSizeChange('w')"
              />
              <label style="margin-left:8px">高：</label>
              <t-input-number
                v-model="resizeH"
                :min="1"
                :max="4000"
                theme="normal"
                size="small"
                style="width:100px"
                @change="onSizeChange('h')"
              />
              <t-checkbox
                v-model="lockRatio"
                style="margin-left:8px"
              >锁定比例</t-checkbox>
            </div>
          </div>
          <!-- 变换操作工具栏 -->
          <div class="edit-toolbar">
            <t-button size="small" variant="outline" @click="rotateLeft" title="向左旋转90°">
              <template #icon><t-icon name="refresh" /></template> 左旋
            </t-button>
            <t-button size="small" variant="outline" @click="rotateRight" title="向右旋转90°">
              <template #icon><t-icon name="refresh" /></template> 右旋
            </t-button>
            <t-button size="small" variant="outline" @click="zoomIn" title="放大">
              <template #icon><t-icon name="zoom-in" /></template>
            </t-button>
            <t-button size="small" variant="outline" @click="zoomOut" title="缩小">
              <template #icon><t-icon name="zoom-out" /></template>
            </t-button>
            <t-button size="small" variant="outline" @click="resetTransform" title="重置">
              <template #icon><t-icon name="restart" /></template> 重置
            </t-button>
          </div>
        </div>

        <!-- 右侧：信息编辑 -->
        <div class="edit-form">
          <t-form label-width="70px">
            <t-form-item label="素材名称">
              <t-input v-model="editForm.name" placeholder="图片名称" />
            </t-form-item>
            <t-form-item label="描述">
              <t-textarea v-model="editForm.description" :rows="3" placeholder="描述图片内容，AI 生成时可引用" />
            </t-form-item>
            <t-form-item label="Alt 文本">
              <t-textarea v-model="editForm.alt" :rows="2" placeholder="图片的替代文本，用于无障碍访问和 SEO" />
            </t-form-item>
            <t-form-item label="标签">
              <t-input v-model="editForm.tags" placeholder="逗号分隔，如：美食,探店" />
            </t-form-item>
            <t-form-item label="图片链接">
              <div class="link-row">
                <t-input :value="getFullUrl(editItem.url || '')" readonly />
                <t-button theme="primary" variant="outline" size="small" @click="copyUrl(editItem.url)">
                  <template #icon><t-icon name="file-copy" /></template> 复制
                </t-button>
              </div>
            </t-form-item>
          </t-form>
        </div>
      </div>
    </t-dialog>

    <!-- 批量删除确认弹窗 -->
    <t-dialog
      v-model:visible="batchDeleteVisible"
      header="批量删除"
      :confirm-btn="{ content: '确认删除', theme: 'danger', loading: deleting }"
      @confirm="doBatchDelete"
    >
      <p>确定要删除选中的 <strong>{{ selectedIds.length }}</strong> 张图片吗？此操作不可恢复。</p>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { xhsApi } from '@/api/index.js'

const materials = ref([])
const loading = ref(false)
const uploading = ref(false)
const uploadCount = ref(0)
const uploadTotal = ref(0)
const isDragOver = ref(false)
const fileInput = ref(null)

// 多选
const selectMode = ref(false)
const selectedIds = ref([])
const batchDeleteVisible = ref(false)
const deleting = ref(false)

// 编辑
const editVisible = ref(false)
const editItem = ref(null)
const saving = ref(false)
const editForm = reactive({ name: '', description: '', alt: '', tags: '' })
const transform = reactive({ rotate: 0, scale: 1 })

// 图片尺寸
const imgNaturalW = ref(0)
const imgNaturalH = ref(0)
const resizeW = ref(null)
const resizeH = ref(null)
const lockRatio = ref(true)
let aspectRatio = 1

// ===================== 加载 =====================
async function loadMaterials() {
  loading.value = true
  try {
    materials.value = await xhsApi.getMaterials('image')
  } finally {
    loading.value = false
  }
}

// ===================== 上传 =====================
function triggerFileInput() { fileInput.value?.click() }

function handleFileSelect(e) {
  const files = Array.from(e.target.files)
  if (files.length) uploadFiles(files)
  e.target.value = ''
}

function handleDrop(e) {
  isDragOver.value = false
  const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'))
  if (!files.length) return MessagePlugin.warning('请拖入图片文件')
  uploadFiles(files)
}

async function uploadFiles(files) {
  uploading.value = true
  uploadCount.value = 0
  uploadTotal.value = files.length
  for (const file of files) {
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('name', file.name.replace(/\.[^.]+$/, ''))
      await xhsApi.uploadImage(fd)
      uploadCount.value++
    } catch (err) {
      MessagePlugin.error(`${file.name} 上传失败`)
    }
  }
  uploading.value = false
  MessagePlugin.success(`成功上传 ${uploadCount.value} 张图片`)
  loadMaterials()
}

// ===================== 多选 =====================
function enterSelect() {
  selectMode.value = true
  selectedIds.value = []
}

function cancelSelect() {
  selectMode.value = false
  selectedIds.value = []
}

function selectAll() {
  if (selectedIds.value.length === materials.value.length) {
    selectedIds.value = []
  } else {
    selectedIds.value = materials.value.map(m => m.id)
  }
}

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

function batchDelete() {
  if (!selectedIds.value.length) return
  batchDeleteVisible.value = true
}

async function doBatchDelete() {
  deleting.value = true
  try {
    await xhsApi.batchDeleteMaterials(selectedIds.value)
    MessagePlugin.success(`已删除 ${selectedIds.value.length} 张图片`)
    batchDeleteVisible.value = false
    selectMode.value = false
    selectedIds.value = []
    loadMaterials()
  } catch { /* error handled by interceptor */ }
  finally { deleting.value = false }
}

// ===================== URL 复制 =====================
function getFullUrl(path) {
  if (!path) return ''
  return window.location.origin + path
}

async function copyUrl(url) {
  try {
    await navigator.clipboard.writeText(getFullUrl(url))
    MessagePlugin.success('链接已复制')
  } catch {
    MessagePlugin.error('复制失败，请手动复制')
  }
}

// ===================== 编辑 =====================
function openEdit(m) {
  editItem.value = m
  editForm.name = m.name
  editForm.description = m.description || ''
  editForm.alt = m.alt || ''
  editForm.tags = m.tags || ''
  transform.rotate = 0
  transform.scale = 1
  // 用后端存储的尺寸初始化（优先），否则等图片 load 后设置
  imgNaturalW.value = 0
  imgNaturalH.value = 0
  if (m.width && m.height) {
    imgNaturalW.value = m.width
    imgNaturalH.value = m.height
    resizeW.value = m.width
    resizeH.value = m.height
    aspectRatio = m.width / m.height
  } else {
    resizeW.value = null
    resizeH.value = null
  }
  editVisible.value = true
}

function onEditImgLoad(e) {
  imgNaturalW.value = e.target.naturalWidth
  imgNaturalH.value = e.target.naturalHeight
  // 仅在未从后端加载到尺寸时才从图片元素设置
  if (!resizeW.value || !resizeH.value) {
    resizeW.value = e.target.naturalWidth
    resizeH.value = e.target.naturalHeight
    aspectRatio = e.target.naturalWidth / e.target.naturalHeight
  }
}

function onSizeChange(dim) {
  if (!lockRatio.value) return
  if (dim === 'w' && resizeW.value) {
    resizeH.value = Math.round(resizeW.value / aspectRatio)
  } else if (dim === 'h' && resizeH.value) {
    resizeW.value = Math.round(resizeH.value * aspectRatio)
  }
}

function rotateLeft() { transform.rotate -= 90 }
function rotateRight() { transform.rotate += 90 }
function zoomIn() { transform.scale = Math.min(transform.scale + 0.25, 3) }
function zoomOut() { transform.scale = Math.max(transform.scale - 0.25, 0.25) }
function resetTransform() { transform.rotate = 0; transform.scale = 1 }

function getEditImgStyle() {
  return {
    maxWidth: '100%',
    maxHeight: '100%',
    objectFit: 'contain',
    transform: `rotate(${transform.rotate}deg) scale(${transform.scale})`,
    transition: 'transform 0.2s ease',
  }
}

async function saveEdit() {
  if (!editForm.name.trim()) return MessagePlugin.warning('请填写素材名称')
  saving.value = true
  try {
    await xhsApi.updateMaterial(editItem.value.id, {
      name: editForm.name,
      description: editForm.description,
      content: editForm.alt,
      tags: editForm.tags,
      width: resizeW.value,
      height: resizeH.value,
    })
    MessagePlugin.success('素材已更新')
    editVisible.value = false
    loadMaterials()
  } finally {
    saving.value = false
  }
}

// ===================== 单个删除 =====================
async function deleteMaterial(id) {
  await xhsApi.deleteMaterial(id)
  MessagePlugin.success('素材已删除')
  loadMaterials()
}

onMounted(loadMaterials)
</script>

<style scoped>
.page-container { padding: 0; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}
.page-header h2 { margin: 0; font-size: 20px; }

/* 拖拽上传区 */
.drop-zone {
  border: 2px dashed #d9d9d9;
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #fafafa;
  margin-bottom: 20px;
}
.drop-zone:hover,
.drop-zone--active {
  border-color: #0052d9;
  background: #f0f5ff;
}
.drop-zone-content { pointer-events: none; }
.drop-zone p { margin: 8px 0 0; color: #999; font-size: 14px; }
.drop-link { color: #0052d9; text-decoration: underline; }
.drop-hint { font-size: 12px !important; color: #bbb !important; }

.upload-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0;
  color: #666;
  font-size: 14px;
}

/* 图片网格 */
.materials-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}

.material-card {
  background: white;
  border-radius: 10px;
  border: 2px solid transparent;
  overflow: hidden;
  transition: all 0.2s;
  position: relative;
}
.material-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
.material-card--selectable { border-color: #e8e8e8; cursor: pointer; }
.material-card--selected {
  border-color: #0052d9;
  background: #f0f5ff;
}

/* 多选复选框 */
.select-checkbox {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
  background: rgba(255,255,255,0.85);
  border-radius: 4px;
  padding: 2px;
}

.image-preview {
  height: 180px;
  background: #f5f5f5;
  overflow: hidden;
}
.material-card:not(.material-card--selectable) .image-preview { cursor: pointer; }
.image-preview img { width: 100%; height: 100%; object-fit: cover; }
.no-image {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  color: #ccc;
}

.material-info {
  padding: 8px 10px 0;
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.material-name {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #333;
  flex: 1;
  min-width: 0;
}
.material-size {
  font-size: 11px;
  color: #bbb;
  white-space: nowrap;
  flex-shrink: 0;
}

.material-footer {
  padding: 4px 8px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.url-copy {
  display: flex;
  align-items: center;
  gap: 0;
}
.url-input {
  flex: 1;
  font-size: 11px;
  color: #999;
  border: none;
  background: transparent;
  padding: 2px 6px;
  outline: none;
  min-width: 0;
}

.action-btns {
  display: flex;
  gap: 0;
  justify-content: flex-end;
}

/* 编辑弹窗 */
.edit-layout {
  display: flex;
  gap: 20px;
  min-height: 400px;
}
.edit-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.edit-preview-wrapper {
  width: 100%;
  height: 280px;
  overflow: hidden;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
}
.edit-size-info {
  font-size: 12px;
  color: #999;
  text-align: center;
}
.edit-size-current { color: #0052d9; font-weight: 500; }
.edit-size-controls { padding: 0 4px; }
.size-row {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}
.edit-toolbar {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.edit-form {
  width: 240px;
  flex-shrink: 0;
}

.link-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.link-row .t-input { flex: 1; }
</style>
