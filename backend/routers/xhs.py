"""
小红书矩阵发布模块路由
- /api/xhs/accounts  — 账号矩阵管理
- /api/xhs/materials — 素材库管理
- /api/xhs/tasks     — 发布任务管理
"""
import asyncio
import json
import logging
import os
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.models import Tenant, XhsAccount, XhsMaterial, XhsTask
from utils.security import get_current_tenant
from services.llm_service import call_llm, get_tenant_llm_config, LLMError
from services.xhs_publisher import publish_to_xhs
from config import settings

logger = logging.getLogger("xhs")
router = APIRouter(prefix="/api/xhs", tags=["小红书发布"])

# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = (
    "你是一位专业的小红书内容创作者，擅长写出高质量、有吸引力的笔记。"
    "你的文章风格轻松活泼，善用 emoji，语言亲切自然，容易引发读者共鸣。"
    "每篇文章包含：吸引人的开头、干货内容、实用建议，结尾引导互动（点赞/收藏/评论）。"
    "标题要简短有力，控制在 20 字以内。"
    "文末提供 3-5 个适合的话题标签（#标签 格式）。"
)


# ===================== Pydantic Schema =====================

class AccountCreate(BaseModel):
    nickname: str
    xhs_username: Optional[str] = None
    persona: Optional[str] = None
    niche: Optional[str] = None
    tags: Optional[str] = None

class AccountUpdate(BaseModel):
    nickname: Optional[str] = None
    xhs_username: Optional[str] = None
    persona: Optional[str] = None
    niche: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = None
    cookies: Optional[str] = None  # 直接粘贴 cookies JSON

class MaterialCreate(BaseModel):
    name: str
    material_type: str = "image"   # 仅支持 image
    content: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None

class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    alt: Optional[str] = None
    tags: Optional[str] = None

class TaskCreate(BaseModel):
    account_id: int
    title: str
    system_prompt: Optional[str] = None
    user_prompt: str
    api_key_config: Optional[dict] = None   # {"provider":"openai","api_key":"sk-...","model":"gpt-4o"}
    material_ids: Optional[List[int]] = []
    scheduled_at: Optional[str] = None      # ISO8601 字符串

class TaskGenerate(BaseModel):
    task_id: int

class TaskPublish(BaseModel):
    task_id: int


# ===================== 账号矩阵 =====================

@router.get("/accounts")
def list_accounts(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """获取账号列表"""
    accounts = db.query(XhsAccount).filter(XhsAccount.tenant_id == tenant.id).all()
    return [
        {
            "id": a.id,
            "nickname": a.nickname,
            "xhs_username": a.xhs_username,
            "persona": a.persona,
            "niche": a.niche,
            "tags": a.tags,
            "status": a.status,
            "has_cookies": bool(a.cookies),
            "last_login_at": a.last_login_at.isoformat() if a.last_login_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in accounts
    ]


@router.post("/accounts")
def create_account(
    req: AccountCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """添加小红书账号"""
    account = XhsAccount(
        tenant_id=tenant.id,
        nickname=req.nickname,
        xhs_username=req.xhs_username,
        persona=req.persona,
        niche=req.niche,
        tags=req.tags,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return {"id": account.id, "message": "账号添加成功"}


@router.put("/accounts/{account_id}")
def update_account(
    account_id: int,
    req: AccountUpdate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """更新账号信息（含 Cookies 粘贴）"""
    account = db.query(XhsAccount).filter(
        XhsAccount.id == account_id,
        XhsAccount.tenant_id == tenant.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    for field, value in req.dict(exclude_none=True).items():
        setattr(account, field, value)

    # 更新 cookies 时同步刷新状态
    if req.cookies:
        account.status = "active"
        from datetime import datetime, timezone
        account.last_login_at = datetime.now(timezone.utc)

    db.commit()
    return {"message": "账号更新成功"}


@router.delete("/accounts/{account_id}")
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """删除账号"""
    account = db.query(XhsAccount).filter(
        XhsAccount.id == account_id,
        XhsAccount.tenant_id == tenant.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    db.delete(account)
    db.commit()
    return {"message": "账号已删除"}


# ===================== 素材库 =====================

@router.get("/materials")
def list_materials(
    material_type: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """获取素材列表"""
    q = db.query(XhsMaterial).filter(XhsMaterial.tenant_id == tenant.id)
    if material_type:
        q = q.filter(XhsMaterial.material_type == material_type)
    materials = q.order_by(XhsMaterial.created_at.desc()).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "material_type": m.material_type,
            "description": m.description,
            "alt": m.content,  # 复用 content 字段存 alt
            "tags": m.tags,
            "file_path": m.file_path,
            "has_file": bool(m.file_path and os.path.exists(m.file_path)),
            "url": f"/api/xhs/materials/{m.id}/file" if (m.file_path and os.path.exists(m.file_path)) else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in materials
    ]


@router.post("/materials")
def create_material(
    req: MaterialCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """添加图片素材记录（无文件，仅元数据）"""
    material = XhsMaterial(
        tenant_id=tenant.id,
        name=req.name,
        material_type="image",
        content=req.content,
        description=req.description,
        tags=req.tags,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return {"id": material.id, "message": "素材添加成功"}


@router.post("/materials/upload-image")
async def upload_material_image(
    name: str,
    description: Optional[str] = None,
    tags: Optional[str] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """上传图片素材"""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/GIF/WebP 图片")

    upload_dir = os.path.join(settings.UPLOAD_DIR, "xhs_materials", str(tenant.id))
    os.makedirs(upload_dir, exist_ok=True)

    import uuid
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(upload_dir, filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    material = XhsMaterial(
        tenant_id=tenant.id,
        name=name or file.filename,
        material_type="image",
        file_path=file_path,
        description=description,
        tags=tags,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return {"id": material.id, "message": "图片上传成功"}


@router.put("/materials/{material_id}")
def update_material(
    material_id: int,
    req: MaterialUpdate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """更新素材"""
    material = db.query(XhsMaterial).filter(
        XhsMaterial.id == material_id,
        XhsMaterial.tenant_id == tenant.id
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")
    for field, value in req.dict(exclude_none=True).items():
        setattr(material, field, value)
    db.commit()
    return {"message": "素材更新成功"}


@router.delete("/materials/{material_id}")
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """删除素材"""
    material = db.query(XhsMaterial).filter(
        XhsMaterial.id == material_id,
        XhsMaterial.tenant_id == tenant.id
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")
    # 删除文件
    if material.file_path and os.path.exists(material.file_path):
        os.remove(material.file_path)
    db.delete(material)
    db.commit()
    return {"message": "素材已删除"}


@router.get("/materials/{material_id}/file")
def get_material_file(
    material_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """访问素材图片文件"""
    material = db.query(XhsMaterial).filter(
        XhsMaterial.id == material_id,
        XhsMaterial.tenant_id == tenant.id,
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")
    if not material.file_path or not os.path.exists(material.file_path):
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(material.file_path)


# ===================== 发布任务 =====================

@router.get("/tasks")
def list_tasks(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """获取任务列表"""
    tasks = (
        db.query(XhsTask)
        .filter(XhsTask.tenant_id == tenant.id)
        .order_by(XhsTask.created_at.desc())
        .all()
    )
    result = []
    for t in tasks:
        account = db.query(XhsAccount).filter(XhsAccount.id == t.account_id).first()
        result.append({
            "id": t.id,
            "title": t.title,
            "account_id": t.account_id,
            "account_nickname": account.nickname if account else "—",
            "status": t.status,
            "generated_title": t.generated_title,
            "generated_content": t.generated_content,
            "generated_tags": t.generated_tags,
            "error_message": t.error_message,
            "published_url": t.published_url,
            "material_ids": t.material_ids or [],
            "system_prompt": t.system_prompt,
            "user_prompt": t.user_prompt,
            "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        })
    return result


@router.post("/tasks")
def create_task(
    req: TaskCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """创建发布任务（草稿）"""
    account = db.query(XhsAccount).filter(
        XhsAccount.id == req.account_id,
        XhsAccount.tenant_id == tenant.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    task = XhsTask(
        tenant_id=tenant.id,
        account_id=req.account_id,
        title=req.title,
        system_prompt=req.system_prompt or DEFAULT_SYSTEM_PROMPT,
        user_prompt=req.user_prompt,
        api_key_config=req.api_key_config,
        material_ids=req.material_ids or [],
        status="draft",
    )
    if req.scheduled_at:
        from datetime import datetime
        try:
            task.scheduled_at = datetime.fromisoformat(req.scheduled_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="scheduled_at 格式错误，请使用 ISO8601 格式")

    db.add(task)
    db.commit()
    db.refresh(task)
    return {"id": task.id, "message": "任务创建成功"}


@router.put("/tasks/{task_id}")
def update_task(
    task_id: int,
    req: TaskCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """更新任务（仅 draft 状态可修改）"""
    task = db.query(XhsTask).filter(
        XhsTask.id == task_id,
        XhsTask.tenant_id == tenant.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in ("draft", "generated", "failed"):
        raise HTTPException(status_code=400, detail=f"任务状态为 {task.status}，不可修改")

    task.account_id = req.account_id
    task.title = req.title
    task.system_prompt = req.system_prompt or DEFAULT_SYSTEM_PROMPT
    task.user_prompt = req.user_prompt
    task.api_key_config = req.api_key_config
    task.material_ids = req.material_ids or []
    task.status = "draft"
    task.generated_title = None
    task.generated_content = None
    task.generated_tags = None
    task.error_message = None
    db.commit()
    return {"message": "任务更新成功"}


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """删除任务"""
    task = db.query(XhsTask).filter(
        XhsTask.id == task_id,
        XhsTask.tenant_id == tenant.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.delete(task)
    db.commit()
    return {"message": "任务已删除"}


# ===================== 生成文章 =====================

@router.post("/tasks/{task_id}/generate")
async def generate_article(
    task_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """调用大模型生成文章内容（同步，前端 loading 等待）"""
    task = db.query(XhsTask).filter(
        XhsTask.id == task_id,
        XhsTask.tenant_id == tenant.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status == "generating":
        raise HTTPException(status_code=400, detail="任务正在生成中，请勿重复点击")

    # 构建提示词：拼入选用素材
    material_context = ""
    if task.material_ids:
        materials = db.query(XhsMaterial).filter(
            XhsMaterial.id.in_(task.material_ids),
            XhsMaterial.tenant_id == tenant.id,
        ).all()
        mat_parts = []
        for m in materials:
            # 仅图片素材，将描述信息拼入提示词
            mat_parts.append(f"【图片素材 - {m.name}】（描述：{m.description or '无'}）")
        if mat_parts:
            material_context = "\n\n参考素材：\n" + "\n\n".join(mat_parts)

    full_user_prompt = task.user_prompt + material_context

    # 确定 API Key
    messages = [{"role": "user", "content": full_user_prompt}]
    system_prompt = task.system_prompt or DEFAULT_SYSTEM_PROMPT

    # 支持任务独立配置 API Key，或 fallback 商户配置
    if task.api_key_config:
        cfg = task.api_key_config
        model = cfg.get("model", "gpt-4o-mini")
        api_keys = {cfg.get("provider", "openai"): [cfg.get("api_key", "")]}
    else:
        model, api_keys = get_tenant_llm_config(tenant, db)

    if not api_keys:
        raise HTTPException(status_code=400, detail="未配置可用的 API Key")

    # 更新状态
    task.status = "generating"
    task.error_message = None
    db.commit()

    try:
        # 在 system_prompt 前加上角色说明
        full_messages = [
            {"role": "system", "content": system_prompt},
        ] + messages

        result = await call_llm(model, api_keys, full_messages, "")
    except LLMError as e:
        task.status = "failed"
        task.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=502, detail=f"AI 生成失败: {e}")

    # 解析生成内容（尝试提取标题 + 正文 + 标签）
    generated_title, generated_content, generated_tags = _parse_generated(result, task.title)

    task.status = "generated"
    task.generated_title = generated_title
    task.generated_content = generated_content
    task.generated_tags = generated_tags
    db.commit()

    return {
        "message": "文章生成成功",
        "generated_title": generated_title,
        "generated_content": generated_content,
        "generated_tags": generated_tags,
    }


def _parse_generated(text: str, fallback_title: str):
    """
    尝试从 LLM 输出中解析 标题/正文/标签。
    格式宽松，支持：
      标题：xxx
      正文：xxx
      标签：#xxx #xxx
    如果无法解析则整段作为正文。
    """
    import re

    title = fallback_title
    content = text
    tags = ""

    # 提取标题
    title_match = re.search(r"(?:标题[：:]\s*)(.+)", text)
    if title_match:
        title = title_match.group(1).strip()[:20]

    # 提取标签（末尾 #标签 形式）
    tag_matches = re.findall(r"#([\u4e00-\u9fa5a-zA-Z0-9_]{1,20})", text)
    if tag_matches:
        tags = ",".join(tag_matches[:8])
        # 从正文中去掉标签行
        text = re.sub(r"(\s*#[\u4e00-\u9fa5a-zA-Z0-9_]+)+\s*$", "", text).strip()

    # 提取正文（去掉标题行）
    content = re.sub(r"^(?:标题[：:]\s*.+\n?)", "", text, flags=re.MULTILINE).strip()
    # 去掉 "正文：" 前缀
    content = re.sub(r"^正文[：:]\s*", "", content, flags=re.MULTILINE).strip()

    return title, content, tags


# ===================== 发布到小红书 =====================

@router.post("/tasks/{task_id}/publish")
async def publish_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """触发发布任务（后台异步执行）"""
    task = db.query(XhsTask).filter(
        XhsTask.id == task_id,
        XhsTask.tenant_id == tenant.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in ("generated", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"任务状态为 {task.status}，只有 generated/failed 状态可以发布"
        )
    if not task.generated_content:
        raise HTTPException(status_code=400, detail="请先生成文章内容再发布")

    account = db.query(XhsAccount).filter(XhsAccount.id == task.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    if not account.cookies:
        raise HTTPException(status_code=400, detail="账号未配置 Cookies，请先设置登录 Cookies")

    # 标记为发布中（立即返回，后台执行）
    task.status = "publishing"
    task.error_message = None
    db.commit()

    background_tasks.add_task(_do_publish, task_id, tenant.id)

    return {"message": "发布任务已启动，请稍后刷新查看结果"}


async def _do_publish(task_id: int, tenant_id: int):
    """后台执行发布逻辑"""
    from database import SessionLocal
    db = SessionLocal()
    try:
        task = db.query(XhsTask).filter(XhsTask.id == task_id).first()
        if not task:
            return

        account = db.query(XhsAccount).filter(XhsAccount.id == task.account_id).first()
        if not account:
            task.status = "failed"
            task.error_message = "关联账号不存在"
            db.commit()
            return

        # 收集图片素材路径
        image_paths = []
        if task.material_ids:
            materials = db.query(XhsMaterial).filter(
                XhsMaterial.id.in_(task.material_ids),
                XhsMaterial.material_type == "image",
            ).all()
            image_paths = [m.file_path for m in materials if m.file_path and os.path.exists(m.file_path)]

        result = await publish_to_xhs(
            cookies_json=account.cookies,
            title=task.generated_title or task.title,
            content=task.generated_content,
            tags=task.generated_tags,
            image_paths=image_paths or None,
        )

        if result["success"]:
            task.status = "published"
            task.published_url = result.get("url")
            logger.info(f"任务 {task_id} 发布成功: {task.published_url}")
        else:
            task.status = "failed"
            task.error_message = result.get("error", "未知错误")
            logger.error(f"任务 {task_id} 发布失败: {task.error_message}")

            # 若是 Cookies 失效，更新账号状态
            if "Cookies" in (task.error_message or "") and "失效" in (task.error_message or ""):
                account.status = "cookie_expired"

        db.commit()
    except Exception as e:
        logger.exception(f"发布任务 {task_id} 异常: {e}")
        try:
            task = db.query(XhsTask).filter(XhsTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
