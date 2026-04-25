<template>
  <div class="page-container">
    <div class="page-header">
      <h2>🗂️ 素材库</h2>
      <div class="header-actions">
        <t-radio-group v-model="filterType" @change="loadMaterials">
          <t-radio-button value="">全部</t-radio-button>
          <t-radio-button value="text">文字</t-radio-button>
          <t-radio-button value="image">图片</t-radio-button>
          <t-radio-button value="reference">参考文章</t-radio-button>
        </t-radio-group>
        <t-button theme="primary" @click="openAdd('text')">+ 文字素材</t-button>
        <t-button theme="primary" variant="outline" @click="openAdd('reference')">+ 参考文章</t-button>
        <t-button theme="primary" variant="outline" @click="imageDialogVisible = true">+ 图片素材</t-button>
      </div>
    </div>

    <t-loading :loading="loading">
      <div class="materials-grid" v-if="materials.length">
        <div class="material-card" v-for="m in materials" :key="m.id">
          <!-- 图片素材 -->
          <div v-if="m.material_type === 'image'" class="image-preview">
            <img v-if="m.has_file" :src="`/api/xhs/materials/${m.id}/file`" alt="素材图片" />
            <div v-else class="no-image">🖼️</div>
          </div>

          <div class="material-body">
            <div class="material-title">
              <t-tag size="small" :theme="typeTheme(m.material_type)">{{ typeLabel(m.material_type) }}</t-tag>
              <span class="name">{{ m.name }}</span>
            </div>
            <div class="material-desc" v-if="m.description">{{ m.description }}</div>
            <div class="material-content" v-if="m.content">{{ m.content }}</div>
            <div class="material-tags" v-if="m.tags">
              <t-tag v-for="t in m.tags.split(',')" :key="t" size="small" theme="default" style="margin:2px">{{ t.trim() }}</t-tag>
            </div>
          </div>

          <div class="material-footer">
            <t-button size="small" variant="text" @click="openEdit(m)">编辑</t-button>
            <t-popconfirm content="确认删除此素材？" @confirm="deleteMaterial(m.id)">
              <t-button size="small" variant="text" theme="danger">删除</t-button>
            </t-popconfirm>
          </div>
        </div>
      </div>
      <t-empty v-else description="暂无素材，点击右上角添加" />
    </t-loading>

    <!-- 文字/参考文章 弹窗 -->
    <t-dialog
      v-model:visible="dialogVisible"
      :header="editingId ? '编辑素材' : (addType === 'reference' ? '添加参考文章' : '添加文字素材')"
      width="600px"
      :confirm-btn="{ content: '保存', loading: saving }"
      @confirm="saveMaterial"
    >
      <t-form :data="form" label-width="80px">
        <t-form-item label="素材名称">
          <t-input v-model="form.name" placeholder="素材名称" />
        </t-form-item>
        <t-form-item label="素材描述">
          <t-input v-model="form.description" placeholder="可选，简短描述用途" />
        </t-form-item>
        <t-form-item :label="addType === 'reference' ? '参考内容' : '文字内容'">
          <t-textarea v-model="form.content" :rows="8"
            :placeholder="addType === 'reference' ? '粘贴参考文章全文，AI 生成时会参考此内容' : '文字素材内容，AI 生成时会引用'" />
        </t-form-item>
        <t-form-item label="标签">
          <t-input v-model="form.tags" placeholder="逗号分隔，如：美食,探店" />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- 图片上传弹窗 -->
    <t-dialog
      v-model:visible="imageDialogVisible"
      header="上传图片素材"
      width="500px"
      :confirm-btn="{ content: '上传', loading: saving }"
      @confirm="uploadImage"
    >
      <t-form label-width="80px">
        <t-form-item label="素材名称">
          <t-input v-model="imageForm.name" placeholder="图片名称" />
        </t-form-item>
        <t-form-item label="素材描述">
          <t-input v-model="imageForm.description" placeholder="描述图片内容，AI 生成时可引用" />
        </t-form-item>
        <t-form-item label="标签">
          <t-input v-model="imageForm.tags" placeholder="逗号分隔" />
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { xhsApi } from '@/api/index.js'

const materials = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const imageDialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const addType = ref('text')
const filterType = ref('')

const form = ref({ name: '', description: '', content: '', tags: '' })
const imageForm = ref({ name: '', description: '', tags: '', files: [] })

const typeTheme = (t) => ({ text: 'primary', image: 'success', reference: 'warning' }[t] || 'default')
const typeLabel = (t) => ({ text: '文字', image: '图片', reference: '参考' }[t] || t)

async function loadMaterials() {
  loading.value = true
  try { materials.value = await xhsApi.getMaterials(filterType.value) }
  finally { loading.value = false }
}

function openAdd(type) {
  editingId.value = null
  addType.value = type
  form.value = { name: '', description: '', content: '', tags: '' }
  dialogVisible.value = true
}

function openEdit(m) {
  editingId.value = m.id
  addType.value = m.material_type
  form.value = { name: m.name, description: m.description || '', content: m.content || '', tags: m.tags || '' }
  dialogVisible.value = true
}

async function saveMaterial() {
  if (!form.value.name.trim()) return MessagePlugin.warning('请填写素材名称')
  saving.value = true
  try {
    if (editingId.value) {
      await xhsApi.updateMaterial(editingId.value, form.value)
      MessagePlugin.success('素材已更新')
    } else {
      await xhsApi.createMaterial({ ...form.value, material_type: addType.value })
      MessagePlugin.success('素材添加成功')
    }
    dialogVisible.value = false
    loadMaterials()
  } finally { saving.value = false }
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
    imageForm.value = { name: '', description: '', tags: '', files: [] }
    loadMaterials()
  } finally { saving.value = false }
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
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px; }
.page-header h2 { margin: 0; font-size: 20px; }
.header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

.materials-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
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

.image-preview { height: 160px; background: #f5f5f5; overflow: hidden; }
.image-preview img { width: 100%; height: 100%; object-fit: cover; }
.no-image { height: 100%; display: flex; align-items: center; justify-content: center; font-size: 40px; color: #ccc; }

.material-body { padding: 12px; flex: 1; display: flex; flex-direction: column; gap: 6px; }
.material-title { display: flex; align-items: center; gap: 6px; }
.name { font-weight: bold; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.material-desc { font-size: 12px; color: #999; }
.material-content {
  font-size: 13px; color: #555; line-height: 1.5;
  max-height: 80px; overflow: hidden;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical;
}

.material-footer {
  padding: 8px 12px;
  border-top: 1px solid #f0f0f0;
  display: flex; gap: 8px;
}
</style>
