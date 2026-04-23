import os
import shutil
import asyncio
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models.models import Tenant, KnowledgeBase
from utils.security import get_current_tenant
from services.rag_service import build_knowledge_base, query_knowledge_base, delete_knowledge_base
from services.llm_service import call_llm, get_tenant_llm_config, LLMError
from services.crawler_service import crawl_single_page, crawl_website
from services.points_service import PointsService
from config import settings
from typing import Optional, List

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])

ALLOWED_EXTENSIONS = {
    "txt": "txt",
    "docx": "word",
    "doc": "word",
    "xlsx": "excel",
    "xls": "excel"
}

# 爬取任务缓存（内存），key=task_id, value={status, results, progress}
_crawl_tasks: dict = {}


class QATestRequest(BaseModel):
    kb_id: int
    question: str


class CrawlRequest(BaseModel):
    url: str
    mode: str = "single"  # single=只爬当前页, site=爬整站
    max_depth: int = 3    # 全站爬取最大深度，最多5层


class ImportItem(BaseModel):
    url: str
    title: str
    content: str


class ImportRequest(BaseModel):
    kb_name: str
    items: List[ImportItem]


def process_document(kb_id: int, file_path: str, file_type: str, tenant_id: int, db_session):
    """后台任务：处理文档并建立向量索引"""
    from database import SessionLocal
    db = SessionLocal()
    try:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            return
        kb.status = "processing"
        db.commit()

        chunk_count = build_knowledge_base(tenant_id, kb_id, file_path, file_type)
        kb.status = "ready"
        kb.chunk_count = chunk_count
        kb.collection_name = f"tenant_{tenant_id}_kb_{kb_id}"
        db.commit()
    except Exception as e:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if kb:
            kb.status = "failed"
            db.commit()
    finally:
        db.close()


@router.post("/upload")
async def upload_knowledge(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = "",
    description: str = "",
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    # 检查文件类型
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型，支持：{', '.join(ALLOWED_EXTENSIONS.keys())}")

    # 扣费检查
    config = PointsService.get_config(db)
    cost = config.get("knowledge_add_cost", 100)
    
    if tenant.points_balance < cost:
        raise HTTPException(
            status_code=400, 
            detail=f"积分不足，添加知识库需要 {cost} 点，当前余额: {tenant.points_balance} 点"
        )

    # 保存文件
    tenant_dir = os.path.join(settings.UPLOAD_DIR, str(tenant.id))
    os.makedirs(tenant_dir, exist_ok=True)

    # 创建知识库记录
    kb = KnowledgeBase(
        tenant_id=tenant.id,
        name=name or file.filename,
        description=description,
        file_name=file.filename,
        file_type=ALLOWED_EXTENSIONS[ext],
        status="processing"
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)

    file_path = os.path.join(tenant_dir, f"{kb.id}_{file.filename}")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    kb.file_path = file_path
    db.commit()

    # 扣除积分
    success, message, new_balance = PointsService.deduct_points(
        db, tenant.id, cost, "knowledge_add", 
        description=f"添加知识库: {kb.name}",
        related_id=str(kb.id)
    )
    
    if not success:
        # 扣费失败，删除已创建的记录
        db.delete(kb)
        db.commit()
        raise HTTPException(status_code=400, detail=message)

    # 后台处理
    background_tasks.add_task(process_document, kb.id, file_path, ALLOWED_EXTENSIONS[ext], tenant.id, None)

    return {
        "id": kb.id,
        "name": kb.name,
        "status": "processing",
        "progress": 0,
        "progress_message": "等待处理",
        "message": f"文件上传成功，已扣除 {cost} 点积分，正在处理中...",
        "points_deducted": cost,
        "points_balance": new_balance
    }


@router.get("/list")
async def list_knowledge(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    kbs = db.query(KnowledgeBase).filter(KnowledgeBase.tenant_id == tenant.id).order_by(KnowledgeBase.created_at.desc()).all()
    return [{
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "file_name": kb.file_name,
        "file_type": kb.file_type,
        "status": kb.status,
        "progress": kb.progress or 0,
        "progress_message": kb.progress_message or "",
        "chunk_count": kb.chunk_count,
        "created_at": kb.created_at.isoformat() if kb.created_at else None
    } for kb in kbs]


@router.delete("/{kb_id}")
async def delete_knowledge(
    kb_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.tenant_id == tenant.id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 删除向量索引
    delete_knowledge_base(tenant.id, kb_id)

    # 删除文件
    if kb.file_path and os.path.exists(kb.file_path):
        os.remove(kb.file_path)

    db.delete(kb)
    db.commit()
    return {"message": "知识库已删除"}


@router.post("/qa-test")
async def test_qa(
    req: QATestRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """测试知识库问答"""
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == req.kb_id,
        KnowledgeBase.tenant_id == tenant.id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if kb.status != "ready":
        raise HTTPException(status_code=400, detail="知识库尚未就绪")

    # 检索相关内容
    relevant_docs = query_knowledge_base(tenant.id, req.kb_id, req.question)
    context = "\n".join(relevant_docs) if relevant_docs else ""

    # 获取LLM配置（返回模型和API Key列表用于轮询）
    model, api_keys = get_tenant_llm_config(tenant, db)
    if not api_keys:
        raise HTTPException(status_code=400, detail="未配置API Key，请先在设置中配置")

    # 调用LLM（支持轮询）
    messages = [{"role": "user", "content": req.question}]
    try:
        answer = await call_llm(model, api_keys, messages, context)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=f"AI服务调用失败: {e}")

    return {
        "question": req.question,
        "answer": answer,
        "model": model,
        "relevant_chunks": len(relevant_docs)
    }


@router.post("/crawl")
async def start_crawl(
    req: CrawlRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_current_tenant),
):
    """启动爬取任务，返回 task_id"""
    if req.max_depth > 5:
        req.max_depth = 5

    task_id = str(uuid.uuid4())
    _crawl_tasks[task_id] = {
        "status": "running",
        "progress": 0,
        "total": 0,
        "results": [],
        "error": None
    }

    async def do_crawl():
        try:
            async def on_progress(crawled, total):
                _crawl_tasks[task_id]["progress"] = crawled
                _crawl_tasks[task_id]["total"] = total

            if req.mode == "single":
                result = await crawl_single_page(req.url)
                results = [result] if result else []
            else:
                results = await crawl_website(
                    req.url,
                    max_depth=req.max_depth,
                    max_pages=100,
                    progress_callback=on_progress
                )

            _crawl_tasks[task_id]["results"] = [
                {
                    "url": r.url,
                    "title": r.title,
                    "content": r.content,
                    "content_preview": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                    "content_length": len(r.content),
                    "depth": r.depth
                }
                for r in results
            ]
            _crawl_tasks[task_id]["status"] = "done"
            _crawl_tasks[task_id]["progress"] = len(results)
            _crawl_tasks[task_id]["total"] = len(results)
        except Exception as e:
            _crawl_tasks[task_id]["status"] = "error"
            _crawl_tasks[task_id]["error"] = str(e)

    background_tasks.add_task(do_crawl)
    return {"task_id": task_id, "message": "爬取任务已启动"}


@router.get("/crawl/{task_id}")
async def get_crawl_status(
    task_id: str,
    tenant: Tenant = Depends(get_current_tenant),
):
    """获取爬取任务状态和结果"""
    task = _crawl_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/crawl-import")
async def import_from_crawl(
    req: ImportRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """将爬取结果批量导入知识库"""
    if not req.items:
        raise HTTPException(status_code=400, detail="没有可导入的内容")

    # 扣费检查
    config = PointsService.get_config(db)
    cost = config.get("knowledge_add_cost", 100)
    
    if tenant.points_balance < cost:
        raise HTTPException(
            status_code=400, 
            detail=f"积分不足，添加知识库需要 {cost} 点，当前余额: {tenant.points_balance} 点"
        )

    # 将所有内容合并为一个文本文件
    tenant_dir = os.path.join(settings.UPLOAD_DIR, str(tenant.id))
    os.makedirs(tenant_dir, exist_ok=True)

    combined_content = ""
    for item in req.items:
        combined_content += f"# {item.title}\n来源：{item.url}\n\n{item.content}\n\n{'='*60}\n\n"

    # 保存为 txt 文件
    file_name = f"网页导入_{req.kb_name}.txt"
    file_path = os.path.join(tenant_dir, f"crawl_{uuid.uuid4().hex}_{file_name}")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(combined_content)

    # 创建知识库记录
    kb = KnowledgeBase(
        tenant_id=tenant.id,
        name=req.kb_name,
        description=f"从网页导入，共 {len(req.items)} 个页面",
        file_name=file_name,
        file_path=file_path,
        file_type="txt",
        status="processing",
        progress=0,
        progress_message="等待处理"
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)

    # 扣除积分
    success, message, new_balance = PointsService.deduct_points(
        db, tenant.id, cost, "knowledge_add", 
        description=f"网页导入知识库: {kb.name}",
        related_id=str(kb.id)
    )
    
    if not success:
        # 扣费失败，删除已创建的记录和文件
        db.delete(kb)
        db.commit()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=message)

    # 后台向量化处理
    background_tasks.add_task(process_document, kb.id, file_path, "txt", tenant.id, None)

    return {
        "id": kb.id,
        "name": kb.name,
        "status": "processing",
        "progress": 0,
        "message": f"已创建知识库，已扣除 {cost} 点积分，正在处理 {len(req.items)} 个页面...",
        "points_deducted": cost,
        "points_balance": new_balance
    }
