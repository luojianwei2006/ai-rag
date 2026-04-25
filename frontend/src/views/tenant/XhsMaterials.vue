<template>
  <div class="page-container">
    <div class="page-header">
      <h2>🖼️ 素材库（图片）</h2>
      <t-button theme="primary" @click="imageDialogVisible = true">+ 上传图片</t-button>
    </div>

    <t-loading :loading="loading">
      <div class="materials-grid" v-if="materials.length">
        <div class="material-card" v-for="m in materials" :key="m.id">
          <div class="image-preview">
            <img v-if="m.has_file" :src="`/api/xhs/materials/${m.id}/file`" alt="素材图片" />
            <div v-else class="no-image">🖼️</div>
          </div>

          <div class="material-body">
            <div class="material-name">{{ m.name }}</div>
            <div class="material-desc" v-if="m.description">{{ m.description }}</div>
            <div class="material-tags" v-if="m.tags">
              <t-tag v-for="tag in m.tags.split(',')" :key="tag" size="small" theme="default" style="margin:2px">{{ tag.trim() }}</t-tag>
            </div>
          </div>

          <div class="material-footer">
            <t-button size="small" variant="text" @click="openEdit(m)">编辑</t-button>
            <t-popconfirm content="确认删除此图片素材？" @confirm="deleteMaterial(m.id)">
              <t-button size="small" variant="text" theme="danger">删除</t-button>
            </t-popconfirm>
          </div>
        </div>
      </div>
      <t-empty v-else description="暂无图片素材，点击右上角上传" />
    </t-loading>

    <!-- 上传图片弹窗 -->
    <t-dialog
      v-model:visible="imageDialogVisible"
      header="上传图片素材"
      width="500px"
      :confirm-btn="{ content: '上传', loading: saving }"
      @confirm="uploadImage"
      @close="resetImageForm"
    >
      <t-form label-width="80px">
        <t-form-item label="素材名称">
          <t-input v-model="imageForm.name" placeholder="图片名称，留空则使用文件名" />
        </t-form-item>
        <t-form-item label="素材描述">
          <t-input v-model="imageForm.description" placeholder="描述图片内容，AI 生成文章时可引用" />
        </t-form-item>
        <t-form-item label="标签">
          <t-input v-model="imageForm.tags" placeholder="逗号分隔，如：美食,探店" />
        </t-form-item>
        <t-form-item label="选择图片">
          <t-upload
            v-model="imageForm.files"
            :multiple="false"
            accept="image/*"
            :auto-upload="false"
            theme="image"
          />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- 编辑素材信息弹窗（不替换图片，只改名称/描述/标签） -->
    <t-dialog
      v-model:visible="editDialogVisible"
      header="编辑素材信息"
      width="480px"
      :confirm-btn="{ content: '保存', loading: saving }"
      @confirm="saveMaterial"
    >
      <t-form :data="editForm" label-width="80px">
        <t-form-item label="素材名称">
          <t-input v-model="editForm.name" placeholder="素材名称" />
        </t-form-item>
        <t-form-item label="素材描述">
          <t-input v-model="editForm.description" placeholder="描述图片内容" />
        </t-form-item>
        <t-form-item label="标签">
          <t-input v-model="editForm.tags" placeholder="逗号分隔" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { xhsApi } from '@/api/index.js'

const materials = ref([])
const loading = ref(false)
const imageDialogVisible = ref(false)
const editDialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)

const imageForm = ref({ name: '', description: '', tags: '', files: [] })
const editForm = ref({ name: '', description: '', tags: '' })

async function loadMaterials() {
  loading.value = true
  try {
    materials.value = await xhsApi.getMaterials('image')
  } finally {
    loading.value = false
  }
}

function resetImageForm() {
  imageForm.value = { name: '', description: '', tags: '', files: [] }
}

function openEdit(m) {
  editingId.value = m.id
  editForm.value = { name: m.name, description: m.description || '', tags: m.tags || '' }
  editDialogVisible.value = true
}

async function saveMaterial() {
  if (!editForm.value.name.trim()) return MessagePlugin.warning('请填写素材名称')
  saving.value = true
  try {
    await xhsApi.updateMaterial(editingId.value, editForm.value)
    MessagePlugin.success('素材已更新')
    editDialogVisible.value = false
    loadMaterials()
  } finally {
    saving.value = false
  }
}

async function uploadImage() {
  if (!imageForm.value.files?.length) return MessagePlugin.warning('请选择图片')
  saving.value = true
  try {
    const fd = new FormData()
    fd.append('file', imageForm.value.files[0].raw || imageForm.value.files[0])
    fd.append('name', imageForm.value.name || imageForm.value.files[0].name)
    if (imageForm.value.description) fd.append('description', imageForm.value.description)
    if (imageForm.value.tags) fd.append('tags', imageForm.value.tags)
    await xhsApi.uploadImage(fd)
    MessagePlugin.success('图片上传成功')
    imageDialogVisible.value = false
    resetImageForm()
    loadMaterials()
  } finally {
    saving.value = false
  }
}

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
  margin-bottom: 20px;
}
.page-header h2 { margin: 0; font-size: 20px; }

.materials-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}

.material-card {
  background: white;
  border-radius: 10px;
  border: 1px solid #e8e8e8;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.2s;
}
.material-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.1); }

.image-preview {
  height: 160px;
  background: #f5f5f5;
  overflow: hidden;
}
.image-preview img { width: 100%; height: 100%; object-fit: cover; }
.no-image {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  color: #ccc;
}

.material-body { padding: 10px 12px; flex: 1; display: flex; flex-direction: column; gap: 4px; }
.material-name { font-weight: bold; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.material-desc { font-size: 12px; color: #999; }

.material-footer {
  padding: 8px 12px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  gap: 8px;
}
</style>
