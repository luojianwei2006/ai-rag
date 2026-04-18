import os
import json
from typing import List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from config import settings
from utils.doc_parser import parse_document, chunk_text

# 全局ChromaDB客户端
_chroma_client = None


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _chroma_client


def get_collection_name(tenant_id: int, kb_id: int) -> str:
    return f"tenant_{tenant_id}_kb_{kb_id}"


def update_kb_progress(kb_id: int, progress: int, message: str):
    """更新知识库处理进度"""
    from database import SessionLocal
    from models.models import KnowledgeBase
    db = SessionLocal()
    try:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if kb:
            kb.progress = progress
            kb.progress_message = message
            db.commit()
    except Exception:
        pass
    finally:
        db.close()


def build_knowledge_base(
    tenant_id: int,
    kb_id: int,
    file_path: str,
    file_type: str
) -> int:
    """构建知识库向量索引，返回chunk数量"""
    # 步骤1: 解析文档 (10%-40%)
    update_kb_progress(kb_id, 10, "正在解析文档...")
    raw_chunks = parse_document(file_path, file_type)
    update_kb_progress(kb_id, 30, f"文档解析完成，共 {len(raw_chunks)} 个原始块")

    # 步骤2: 进一步切片 (40%-60%)
    update_kb_progress(kb_id, 40, "正在切分文本...")
    all_chunks = []
    for idx, chunk in enumerate(raw_chunks):
        sub_chunks = chunk_text(chunk)
        all_chunks.extend(sub_chunks)
        # 每处理10%更新一次进度
        if idx % max(1, len(raw_chunks) // 10) == 0:
            progress = 40 + int(20 * idx / max(1, len(raw_chunks)))
            update_kb_progress(kb_id, progress, f"文本切分中... ({idx}/{len(raw_chunks)})")

    all_chunks = [c for c in all_chunks if len(c.strip()) > 10]
    update_kb_progress(kb_id, 60, f"文本切分完成，共 {len(all_chunks)} 个片段")

    if not all_chunks:
        raise ValueError("文档内容为空或无法解析")

    # 步骤3: 写入ChromaDB (60%-95%)
    update_kb_progress(kb_id, 65, "正在初始化向量数据库...")
    client = get_chroma_client()
    collection_name = get_collection_name(tenant_id, kb_id)

    # 删除旧collection（如果存在）
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    # 批量添加
    batch_size = 100
    total_batches = (len(all_chunks) + batch_size - 1) // batch_size
    for batch_idx in range(0, len(all_chunks), batch_size):
        batch = all_chunks[batch_idx:batch_idx + batch_size]
        ids = [f"doc_{batch_idx + j}" for j in range(len(batch))]
        collection.add(documents=batch, ids=ids)
        
        # 更新进度
        progress = 65 + int(30 * (batch_idx // batch_size + 1) / max(1, total_batches))
        update_kb_progress(kb_id, min(progress, 95), f"正在生成向量... ({batch_idx + len(batch)}/{len(all_chunks)})")

    # 完成
    update_kb_progress(kb_id, 100, "处理完成")
    return len(all_chunks)


def query_knowledge_base(
    tenant_id: int,
    kb_id: int,
    query: str,
    n_results: int = 5
) -> List[str]:
    """查询知识库，返回相关文本列表"""
    client = get_chroma_client()
    collection_name = get_collection_name(tenant_id, kb_id)

    try:
        collection = client.get_collection(collection_name)
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count())
        )
        if results and results["documents"]:
            return results["documents"][0]
        return []
    except Exception as e:
        return []


def delete_knowledge_base(tenant_id: int, kb_id: int):
    """删除知识库向量索引"""
    client = get_chroma_client()
    collection_name = get_collection_name(tenant_id, kb_id)
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
