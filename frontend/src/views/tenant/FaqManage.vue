<template>
  <div class="faq-manage">
    <t-card title="常见问题FAQ" :bordered="false">
      <div class="faq-layout">
        <!-- 左侧分类列表 -->
        <div class="category-panel">
          <div class="panel-header">
            <span class="panel-title">分类列表</span>
            <t-button size="small" theme="primary" @click="openCategoryDialog()">
              <t-icon name="add" /> 添加分类
            </t-button>
          </div>
          <div class="category-list" v-loading="loading">
            <div
              v-for="cat in categories"
              :key="cat.id"
              class="category-item"
              :class="{ active: selectedCategoryId === cat.id }"
              @click="selectedCategoryId = cat.id"
            >
              <div class="category-info">
                <div class="category-name">{{ cat.name_zh }}</div>
                <div class="category-name-en" v-if="cat.name_en">{{ cat.name_en }}</div>
                <t-tag size="small" variant="light">{{ (cat.items || []).length }} 条</t-tag>
              </div>
              <div class="category-actions" @click.stop>
                <t-button size="small" variant="text" @click="openCategoryDialog(cat)">
                  <t-icon name="edit" />
                </t-button>
                <t-popconfirm content="确认删除该分类及其下所有问题？" @confirm="deleteCategory(cat.id)">
                  <t-button size="small" variant="text" theme="danger">
                    <t-icon name="delete" />
                  </t-button>
                </t-popconfirm>
              </div>
            </div>
            <div v-if="categories.length === 0 && !loading" class="empty-hint">
              暂无分类，请点击上方按钮添加
            </div>
          </div>
        </div>

        <!-- 右侧问题列表 -->
        <div class="item-panel">
          <div class="panel-header">
            <span class="panel-title">
              问题列表
              <template v-if="selectedCategory">
                — {{ selectedCategory.name_zh }}
              </template>
            </span>
            <t-button
              v-if="selectedCategoryId"
              size="small"
              theme="primary"
              @click="openItemDialog()"
            >
              <t-icon name="add" /> 添加问题
            </t-button>
          </div>

          <!-- 未选分类提示 -->
          <div v-if="!selectedCategoryId" class="empty-state">
            <div class="empty-icon">📋</div>
            <div>请从左侧选择一个分类查看问题</div>
          </div>

          <!-- 问题列表 -->
          <div v-else class="item-list">
            <div
              v-for="(item, index) in currentItems"
              :key="item.id"
              class="item-card"
            >
              <div class="item-header" @click="toggleItemExpand(item.id)">
                <div class="item-question">
                  <span class="item-index">{{ index + 1 }}.</span>
                  <span class="item-question-text">{{ item.question_zh }}</span>
                  <span class="item-question-en" v-if="item.question_en">{{ item.question_en }}</span>
                </div>
                <div class="item-actions" @click.stop>
                  <t-button size="small" variant="text" :disabled="index === 0" @click="moveItemUp(index)">
                    <t-icon name="chevron-up" />
                  </t-button>
                  <t-button size="small" variant="text" :disabled="index === currentItems.length - 1" @click="moveItemDown(index)">
                    <t-icon name="chevron-down" />
                  </t-button>
                  <t-button size="small" variant="text" @click="openItemDialog(item)">
                    <t-icon name="edit" />
                  </t-button>
                  <t-popconfirm content="确认删除此问题？" @confirm="deleteItem(item.id)">
                    <t-button size="small" variant="text" theme="danger">
                      <t-icon name="delete" />
                    </t-button>
                  </t-popconfirm>
                </div>
              </div>
              <div v-if="expandedItemIds.has(item.id)" class="item-detail">
                <div class="answer-section">
                  <div class="answer-label">中文答案：</div>
                  <div class="answer-content">{{ item.answer_zh }}</div>
                </div>
                <div class="answer-section" v-if="item.answer_en">
                  <div class="answer-label">英文答案：</div>
                  <div class="answer-content">{{ item.answer_en }}</div>
                </div>
              </div>
            </div>
            <div v-if="currentItems.length === 0" class="empty-hint">
              暂无问题，请点击上方按钮添加
            </div>
          </div>
        </div>
      </div>
    </t-card>

    <!-- 分类对话框 -->
    <t-dialog
      v-model:visible="showCategoryDialog"
      :header="editingCategory ? '编辑分类' : '添加分类'"
      width="480px"
      :on-confirm="saveCategory"
      :confirm-btn="{ loading: savingCategory }"
    >
      <t-form ref="categoryFormRef" :data="categoryForm" label-width="80px">
        <t-form-item label="中文名称" name="name_zh" :rules="[{ required: true, message: '请输入中文名称' }]">
          <t-input v-model="categoryForm.name_zh" placeholder="请输入中文名称" />
        </t-form-item>
        <t-form-item label="英文名称" name="name_en">
          <t-input v-model="categoryForm.name_en" placeholder="选填" />
        </t-form-item>
        <t-form-item label="排序" name="sort_order">
          <t-input-number v-model="categoryForm.sort_order" :min="0" placeholder="数字越小越靠前" />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- 问题对话框 -->
    <t-dialog
      v-model:visible="showItemDialog"
      :header="editingItem ? '编辑问题' : '添加问题'"
      width="600px"
      :on-confirm="saveItem"
      :confirm-btn="{ loading: savingItem }"
    >
      <t-form ref="itemFormRef" :data="itemForm" label-width="80px">
        <t-form-item label="所属分类" name="category_id" :rules="[{ required: true, message: '请选择分类' }]">
          <t-select v-model="itemForm.category_id" placeholder="请选择分类">
            <t-option v-for="cat in categories" :key="cat.id" :value="cat.id" :label="cat.name_zh" />
          </t-select>
        </t-form-item>
        <t-form-item label="中文问题" name="question_zh" :rules="[{ required: true, message: '请输入中文问题' }]">
          <t-input v-model="itemForm.question_zh" placeholder="请输入中文问题" />
        </t-form-item>
        <t-form-item label="英文问题" name="question_en">
          <t-input v-model="itemForm.question_en" placeholder="选填" />
        </t-form-item>
        <t-form-item label="中文答案" name="answer_zh" :rules="[{ required: true, message: '请输入中文答案' }]">
          <t-textarea v-model="itemForm.answer_zh" placeholder="请输入中文答案" :autosize="{ minRows: 3, maxRows: 8 }" />
        </t-form-item>
        <t-form-item label="英文答案" name="answer_en">
          <t-textarea v-model="itemForm.answer_en" placeholder="选填" :autosize="{ minRows: 3, maxRows: 8 }" />
        </t-form-item>
        <t-form-item label="排序" name="sort_order">
          <t-input-number v-model="itemForm.sort_order" :min="0" placeholder="数字越小越靠前" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { tenantApi } from '@/api'

// 状态
const loading = ref(false)
const categories = ref([])
const selectedCategoryId = ref(null)
const expandedItemIds = ref(new Set())

// 分类对话框
const showCategoryDialog = ref(false)
const savingCategory = ref(false)
const editingCategory = ref(null)
const categoryForm = ref({ name_zh: '', name_en: '', sort_order: 0 })
const categoryFormRef = ref(null)

// 问题对话框
const showItemDialog = ref(false)
const savingItem = ref(false)
const editingItem = ref(null)
const itemForm = ref({
  category_id: null,
  question_zh: '',
  question_en: '',
  answer_zh: '',
  answer_en: '',
  sort_order: 0
})
const itemFormRef = ref(null)

// 计算属性
const selectedCategory = computed(() => {
  return categories.value.find(c => c.id === selectedCategoryId.value) || null
})

const currentItems = computed(() => {
  if (!selectedCategory.value) return []
  return [...(selectedCategory.value.items || [])].sort((a, b) => a.sort_order - b.sort_order)
})

// 加载 FAQ 数据
async function loadFaq() {
  loading.value = true
  try {
    categories.value = await tenantApi.getFaq()
    // 自动选中第一个分类
    if (!selectedCategoryId.value && categories.value.length > 0) {
      selectedCategoryId.value = categories.value[0].id
    }
  } catch (e) {
    // error handled by interceptor
  } finally {
    loading.value = false
  }
}

// 展开/收起问题详情
function toggleItemExpand(itemId) {
  const newSet = new Set(expandedItemIds.value)
  if (newSet.has(itemId)) {
    newSet.delete(itemId)
  } else {
    newSet.add(itemId)
  }
  expandedItemIds.value = newSet
}

// === 分类 CRUD ===
function openCategoryDialog(cat = null) {
  editingCategory.value = cat
  if (cat) {
    categoryForm.value = {
      name_zh: cat.name_zh,
      name_en: cat.name_en || '',
      sort_order: cat.sort_order || 0
    }
  } else {
    categoryForm.value = { name_zh: '', name_en: '', sort_order: 0 }
  }
  showCategoryDialog.value = true
  nextTick(() => categoryFormRef.value?.clearValidate())
}

async function saveCategory() {
  const valid = await categoryFormRef.value?.validate()
  if (valid !== true) return

  savingCategory.value = true
  try {
    const data = {
      name_zh: categoryForm.value.name_zh,
      name_en: categoryForm.value.name_en || undefined,
      sort_order: categoryForm.value.sort_order
    }
    if (editingCategory.value) {
      data.id = editingCategory.value.id
    }
    await tenantApi.saveFaqCategory(data)
    MessagePlugin.success(editingCategory.value ? '分类已更新' : '分类已添加')
    showCategoryDialog.value = false
    await loadFaq()
    // 如果是编辑，保持选中状态
    if (editingCategory.value) {
      selectedCategoryId.value = editingCategory.value.id
    }
  } catch (e) {
    // error handled by interceptor
  } finally {
    savingCategory.value = false
  }
}

async function deleteCategory(catId) {
  try {
    await tenantApi.deleteFaqCategory(catId)
    MessagePlugin.success('分类已删除')
    if (selectedCategoryId.value === catId) {
      selectedCategoryId.value = null
    }
    await loadFaq()
  } catch (e) {
    // error handled by interceptor
  }
}

// === 问题 CRUD ===
function openItemDialog(item = null) {
  editingItem.value = item
  if (item) {
    itemForm.value = {
      category_id: item.category_id,
      question_zh: item.question_zh,
      question_en: item.question_en || '',
      answer_zh: item.answer_zh,
      answer_en: item.answer_en || '',
      sort_order: item.sort_order || 0
    }
  } else {
    itemForm.value = {
      category_id: selectedCategoryId.value,
      question_zh: '',
      question_en: '',
      answer_zh: '',
      answer_en: '',
      sort_order: 0
    }
  }
  showItemDialog.value = true
  nextTick(() => itemFormRef.value?.clearValidate())
}

async function saveItem() {
  const valid = await itemFormRef.value?.validate()
  if (valid !== true) return

  savingItem.value = true
  try {
    const data = {
      category_id: itemForm.value.category_id,
      question_zh: itemForm.value.question_zh,
      question_en: itemForm.value.question_en || undefined,
      answer_zh: itemForm.value.answer_zh,
      answer_en: itemForm.value.answer_en || undefined,
      sort_order: itemForm.value.sort_order
    }
    if (editingItem.value) {
      data.id = editingItem.value.id
    }
    await tenantApi.saveFaqItem(data)
    MessagePlugin.success(editingItem.value ? '问题已更新' : '问题已添加')
    showItemDialog.value = false
    // 选中问题所属分类
    selectedCategoryId.value = data.category_id
    await loadFaq()
  } catch (e) {
    // error handled by interceptor
  } finally {
    savingItem.value = false
  }
}

async function deleteItem(itemId) {
  try {
    await tenantApi.deleteFaqItem(itemId)
    MessagePlugin.success('问题已删除')
    await loadFaq()
  } catch (e) {
    // error handled by interceptor
  }
}

// === 排序 ===
async function moveItemUp(index) {
  if (index <= 0) return
  const items = currentItems.value
  const newItems = [...items]
  ;[newItems[index - 1], newItems[index]] = [newItems[index], newItems[index - 1]]
  // 重新分配 sort_order
  const reordered = newItems.map((item, i) => ({ ...item, sort_order: i }))
  // 更新本地数据
  if (selectedCategory.value) {
    selectedCategory.value.items = reordered
  }
  // 提交排序
  try {
    await tenantApi.reorderFaqItems({ ids: reordered.map(i => i.id) })
  } catch (e) {
    await loadFaq() // 回滚
  }
}

async function moveItemDown(index) {
  const items = currentItems.value
  if (index >= items.length - 1) return
  await moveItemUp(index + 1) // 等同于把下一个元素上移
}

onMounted(() => {
  loadFaq()
})
</script>

<style scoped>
.faq-layout {
  display: flex;
  gap: 16px;
  min-height: 500px;
}

/* 左侧分类面板 */
.category-panel {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid #e7e7e7;
  padding-right: 16px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-title {
  font-weight: 600;
  font-size: 15px;
  color: #333;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.category-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  border: 1px solid transparent;
}

.category-item:hover {
  background: #f3f4f6;
}

.category-item.active {
  background: #e8f3ff;
  border-color: #0052d9;
}

.category-info {
  flex: 1;
  min-width: 0;
}

.category-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-name-en {
  font-size: 12px;
  color: #888;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

.category-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
}

.category-item:hover .category-actions {
  opacity: 1;
}

/* 右侧问题面板 */
.item-panel {
  flex: 1;
  min-width: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  color: #999;
  font-size: 14px;
  gap: 12px;
}

.empty-icon {
  font-size: 48px;
  opacity: 0.5;
}

.empty-hint {
  text-align: center;
  padding: 40px 0;
  color: #999;
  font-size: 14px;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.item-card {
  border: 1px solid #e7e7e7;
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s;
}

.item-card:hover {
  border-color: #0052d9;
}

.item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  gap: 12px;
}

.item-question {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-index {
  color: #999;
  font-size: 13px;
  flex-shrink: 0;
}

.item-question-text {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-question-en {
  font-size: 12px;
  color: #888;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}

.item-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
}

.item-card:hover .item-actions {
  opacity: 1;
}

.item-detail {
  border-top: 1px solid #f0f0f0;
  padding: 16px;
  background: #fafafa;
}

.answer-section {
  margin-bottom: 12px;
}

.answer-section:last-child {
  margin-bottom: 0;
}

.answer-label {
  font-size: 13px;
  font-weight: 600;
  color: #666;
  margin-bottom: 4px;
}

.answer-content {
  font-size: 14px;
  color: #444;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
