import secrets
import string
import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from database import get_db
from models.models import Tenant, FaqCategory, FaqItem
from utils.security import (
    verify_password, get_password_hash,
    create_access_token, get_current_tenant
)
from services.email_service import send_password_email, send_reset_password_email
from typing import Optional
import json

router = APIRouter(prefix="/api/tenant", tags=["商户"])


def generate_password(length=10) -> str:
    """生成随机密码"""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_chat_token() -> str:
    """生成客服链接Token"""
    return secrets.token_urlsafe(32)


class RegisterRequest(BaseModel):
    email: str
    company_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    email: str


class UpdateApiKeyRequest(BaseModel):
    use_system_api_key: Optional[bool] = None
    custom_api_keys: Optional[dict] = None
    preferred_model: Optional[str] = None
    # 新格式：列表型Key配置
    api_keys_list: Optional[list] = None


class UpdateSettingsRequest(BaseModel):
    chat_language: Optional[str] = None  # zh, en
    ai_enabled: Optional[bool] = None


class RegenerateEmbedKeyRequest(BaseModel):
    """重新生成嵌入 API Key（空 body 即可）"""
    pass


class TestApiKeyRequest(BaseModel):
    provider: str
    model: str
    api_key: str = ""
    api_base: Optional[str] = None


@router.post("/register")
async def register_tenant(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(Tenant).filter(Tenant.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    password = generate_password()
    tenant = Tenant(
        email=req.email,
        company_name=req.company_name,
        hashed_password=get_password_hash(password),
        chat_token=generate_chat_token(),
        use_system_api_key=True,
        custom_api_keys={},
        preferred_model="glm"
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    # 发送密码邮件
    success, msg = await send_password_email(db, req.email, password, req.company_name or "")
    if not success:
        # 邮件发送失败但仍然注册成功，返回密码
        return {
            "message": f"注册成功（邮件发送失败: {msg}），临时密码: {password}",
            "email": req.email,
            "temp_password": password
        }

    return {"message": "注册成功，密码已发送到您的邮箱", "email": req.email}


@router.post("/login")
async def tenant_login(req: LoginRequest, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.email == req.email).first()
    if not tenant or not verify_password(req.password, tenant.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if not tenant.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用，请联系管理员")

    token = create_access_token({"sub": tenant.id, "type": "tenant"})
    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant": {
            "id": tenant.id,
            "email": tenant.email,
            "company_name": tenant.company_name,
            "chat_token": tenant.chat_token,
            "chat_url": f"/chat/{tenant.chat_token}",
            "points_balance": tenant.points_balance or 0
        }
    }


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.email == req.email).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="该邮箱未注册")

    new_password = generate_password()
    tenant.hashed_password = get_password_hash(new_password)
    db.commit()

    success, msg = await send_reset_password_email(db, req.email, new_password)
    if not success:
        return {"message": f"密码已重置但邮件发送失败: {msg}", "temp_password": new_password}
    return {"message": "新密码已发送到您的邮箱"}


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    if not verify_password(req.old_password, tenant.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    tenant.hashed_password = get_password_hash(req.new_password)
    db.commit()
    return {"message": "密码修改成功"}


@router.get("/profile")
async def get_profile(tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    custom_keys = tenant.custom_api_keys or {}
    # 新格式：api_keys_list
    api_keys_list = custom_keys.get("__v2__", None)
    if api_keys_list:
        # 脱敏
        masked_list = []
        for k in api_keys_list:
            raw = k.get("api_key", "")
            masked_list.append({
                **k,
                "api_key": "",
                "api_key_masked": (raw[:4] + "****" + raw[-4:]) if raw and len(raw) > 8 else ("****" if raw else "")
            })
        return {
            "id": tenant.id,
            "email": tenant.email,
            "company_name": tenant.company_name,
            "chat_token": tenant.chat_token,
            "use_system_api_key": tenant.use_system_api_key,
            "api_keys_list": masked_list,
            "preferred_model": tenant.preferred_model,
            "chat_url": f"/chat/{tenant.chat_token}",
            "points_balance": tenant.points_balance,
            "chat_language": tenant.chat_language or "zh",
            "ai_enabled": tenant.ai_enabled if tenant.ai_enabled is not None else True,
            "avatar_url": tenant.avatar_url,
            "embed_api_key": tenant.embed_api_key or ""
        }

    return {
        "id": tenant.id,
        "email": tenant.email,
        "company_name": tenant.company_name,
        "chat_token": tenant.chat_token,
        "use_system_api_key": tenant.use_system_api_key,
        "custom_api_keys": {k: (v[:4] + "****" if v and len(v) > 8 else v) for k, v in custom_keys.items() if k != "__v2__"},
        "api_keys_list": [],
        "preferred_model": tenant.preferred_model,
        "chat_url": f"/chat/{tenant.chat_token}",
        "points_balance": tenant.points_balance,
        "chat_language": tenant.chat_language or "zh",
        "ai_enabled": tenant.ai_enabled if tenant.ai_enabled is not None else True,
        "avatar_url": tenant.avatar_url,
        "embed_api_key": tenant.embed_api_key or ""
    }


@router.put("/api-keys")
async def update_api_keys(
    req: UpdateApiKeyRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    if req.use_system_api_key is not None:
        tenant.use_system_api_key = req.use_system_api_key
    if req.preferred_model is not None:
        tenant.preferred_model = req.preferred_model

    # 新格式：列表型Key
    if req.api_keys_list is not None:
        current = tenant.custom_api_keys or {}
        # 读取旧数据保留真实key
        old_list = current.get("__v2__", [])
        old_map = {k["id"]: k.get("api_key", "") for k in old_list}
        # 同时用 provider+model 作为备用key
        old_pm_map = {f"{k.get('provider', '')}:{k.get('model', '')}": k.get("api_key", "") for k in old_list}

        save_list = []
        for item in req.api_keys_list:
            real_key = item.get("api_key")
            item_id = item.get("id")
            provider = item["provider"]
            model = item["model"]
            
            # 如果前端传来空key，先尝试用id匹配，再用provider+model匹配
            if not real_key:
                real_key = old_map.get(item_id, "")
            if not real_key:
                pm_key = f"{provider}:{model}"
                real_key = old_pm_map.get(pm_key, "")
                
            save_list.append({
                "id": item_id or provider,
                "provider": provider,
                "model": model,
                "api_key": real_key,
                "api_base": item.get("api_base", ""),
                "enabled": item.get("enabled", True)
            })
        current["__v2__"] = save_list
        tenant.custom_api_keys = current

    elif req.custom_api_keys is not None:
        current_keys = tenant.custom_api_keys or {}
        current_keys.update(req.custom_api_keys)
        tenant.custom_api_keys = {k: v for k, v in current_keys.items() if v}

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(tenant, "custom_api_keys")
    db.commit()
    return {"message": "API Key配置已更新"}


@router.post("/api-keys/test")
async def test_tenant_api_key(
    req: TestApiKeyRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """商户测试自己的API Key"""
    import httpx
    api_key = req.api_key

    # 若key为空，从商户存储中取
    if not api_key:
        keys = tenant.custom_api_keys or {}
        v2_list = keys.get("__v2__", [])
        for k in v2_list:
            if k.get("provider") == req.provider and k.get("model") == req.model:
                api_key = k.get("api_key", "")
                break

    if not api_key:
        raise HTTPException(status_code=400, detail="API Key不能为空，请先填写Key")

    try:
        if req.provider == "glm":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": req.model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                detail = resp.json().get("error", {}).get("message", resp.text[:100])
                raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif req.provider == "openai":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": req.model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                detail = resp.json().get("error", {}).get("message", resp.text[:100])
                raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif req.provider == "gemini":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{req.model}:generateContent?key={api_key}",
                    json={"contents": [{"parts": [{"text": "hi"}]}]}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                detail = resp.json().get("error", {}).get("message", resp.text[:100])
                raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif req.provider == "deepseek":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": req.model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                detail = resp.json().get("error", {}).get("message", resp.text[:100])
                raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif req.provider == "qwen":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": req.model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                detail = resp.json().get("error", {}).get("message", resp.text[:100])
                raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif req.provider == "nvidia_zai":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": req.model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                detail = resp.json().get("error", {}).get("message", resp.text[:100])
                raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif req.provider == "custom_openai":
            base = req.api_base or "https://api.openai.com/v1"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": req.model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": f"Custom OpenAI compatible API 连接成功 ({req.model})"}
                detail = resp.json().get("error", {}).get("message", resp.text[:100])
                raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        else:
            raise HTTPException(status_code=400, detail=f"不支持的厂家: {req.provider}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接异常: {str(e)}")


@router.put("/settings")
async def update_settings(
    req: UpdateSettingsRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """更新商户设置（语言、AI开关等）"""
    if req.chat_language is not None:
        if req.chat_language not in ("zh", "en"):
            raise HTTPException(status_code=400, detail="不支持的语言，请选择 zh 或 en")
        tenant.chat_language = req.chat_language
    if req.ai_enabled is not None:
        tenant.ai_enabled = req.ai_enabled
    db.commit()
    return {"message": "设置已更新", "chat_language": tenant.chat_language, "ai_enabled": tenant.ai_enabled}


@router.get("/embed-key")
async def get_embed_key(tenant: Tenant = Depends(get_current_tenant)):
    """获取当前嵌入监控 API Key"""
    return {"embed_api_key": tenant.embed_api_key or ""}


@router.post("/embed-key/regenerate")
async def regenerate_embed_key(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """重新生成嵌入监控 API Key"""
    import secrets
    # 确保新 key 不重复
    while True:
        new_key = secrets.token_urlsafe(32)
        exists = db.query(Tenant).filter(Tenant.embed_api_key == new_key).first()
        if not exists:
            break
    tenant.embed_api_key = new_key
    db.commit()
    return {"message": "API Key 已重新生成", "embed_api_key": new_key}


# ─────── 头像上传 ───────

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """上传商户头像"""
    # 校验文件类型
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/GIF/WebP 格式")

    # 校验文件大小
    file.file.seek(0, 2)  # 移到文件末尾
    file_size = file.file.tell()
    file.file.seek(0)  # 移回开头
    if file_size > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过 2MB")

    # 确定文件扩展名
    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
    ext = ext_map.get(file.content_type, ".jpg")

    # 保存路径：static/avatars/{tenant_id}.{ext}
    from config import settings
    avatar_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)

    # 删除旧头像文件（如果存在）
    if tenant.avatar_url:
        old_path = os.path.join(settings.UPLOAD_DIR, tenant.avatar_url.replace("/static/", "", 1))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    filename = f"{tenant.id}{ext}"
    file_path = os.path.join(avatar_dir, filename)

    # 保存并压缩图片
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # 用 Pillow 压缩/裁剪为正方形
        with Image.open(file_path) as img:
            # 转换为 RGB（处理 RGBA/P 模式）
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            # 裁剪为正方形（居中裁剪）
            w, h = img.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            img = img.crop((left, top, left + side, top + side))
            # 缩放到 200x200
            img = img.resize((200, 200), Image.LANCZOS)
            img.save(file_path, "JPEG", quality=85)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片处理失败: {str(e)}")

    # 保存 URL 到数据库
    avatar_url = f"/static/avatars/{filename}"
    tenant.avatar_url = avatar_url
    db.commit()

    return {"message": "头像上传成功", "avatar_url": avatar_url}


@router.delete("/avatar")
async def delete_avatar(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """删除商户头像"""
    if tenant.avatar_url:
        from config import settings
        old_path = os.path.join(settings.UPLOAD_DIR, tenant.avatar_url.replace("/static/", "", 1))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass
        tenant.avatar_url = None
        db.commit()

    return {"message": "头像已删除"}


# ==================== FAQ 管理 ====================

class FaqCategoryRequest(BaseModel):
    id: Optional[int] = None
    name_zh: str
    name_en: Optional[str] = ""
    sort_order: int = 0

class FaqItemRequest(BaseModel):
    id: Optional[int] = None
    category_id: int
    question_zh: str
    question_en: Optional[str] = ""
    answer_zh: str
    answer_en: Optional[str] = ""
    sort_order: int = 0

class FaqReorderRequest(BaseModel):
    ids: list  # 新的排序列表 [id1, id2, ...]

@router.get("/faq")
async def get_faq(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """获取FAQ（含分类和问题）"""
    categories = db.query(FaqCategory).filter(
        FaqCategory.tenant_id == tenant.id
    ).order_by(FaqCategory.sort_order).all()

    result = []
    for cat in categories:
        items = db.query(FaqItem).filter(
            FaqItem.category_id == cat.id,
            FaqItem.tenant_id == tenant.id
        ).order_by(FaqItem.sort_order).all()

        result.append({
            "id": cat.id,
            "name_zh": cat.name_zh,
            "name_en": cat.name_en or cat.name_zh,
            "sort_order": cat.sort_order,
            "items": [{
                "id": it.id,
                "category_id": it.category_id,
                "question_zh": it.question_zh,
                "question_en": it.question_en or it.question_zh,
                "answer_zh": it.answer_zh,
                "answer_en": it.answer_en or it.answer_zh,
                "sort_order": it.sort_order,
            } for it in items]
        })
    return result


@router.post("/faq/category")
async def save_faq_category(
    req: FaqCategoryRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """保存分类（id有值则更新，无则新建）"""
    if req.id:
        cat = db.query(FaqCategory).filter(
            FaqCategory.id == req.id, FaqCategory.tenant_id == tenant.id
        ).first()
        if not cat:
            raise HTTPException(status_code=404, detail="分类不存在")
    else:
        cat = FaqCategory(tenant_id=tenant.id)

    cat.name_zh = req.name_zh
    cat.name_en = req.name_en or ""
    cat.sort_order = req.sort_order

    if not req.id:
        db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "message": "保存成功"}


@router.delete("/faq/category/{cat_id}")
async def delete_faq_category(
    cat_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """删除分类（同时删除分类下的所有问题）"""
    cat = db.query(FaqCategory).filter(
        FaqCategory.id == cat_id, FaqCategory.tenant_id == tenant.id
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    db.delete(cat)
    db.commit()
    return {"message": "已删除"}


@router.post("/faq/item")
async def save_faq_item(
    req: FaqItemRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """保存问题（id有值则更新，无则新建）"""
    if req.id:
        item = db.query(FaqItem).filter(
            FaqItem.id == req.id, FaqItem.tenant_id == tenant.id
        ).first()
        if not item:
            raise HTTPException(status_code=404, detail="问题不存在")
    else:
        item = FaqItem(tenant_id=tenant.id)

    item.category_id = req.category_id
    item.question_zh = req.question_zh
    item.question_en = req.question_en or ""
    item.answer_zh = req.answer_zh
    item.answer_en = req.answer_en or ""
    item.sort_order = req.sort_order

    if not req.id:
        db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "message": "保存成功"}


@router.delete("/faq/item/{item_id}")
async def delete_faq_item(
    item_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """删除问题"""
    item = db.query(FaqItem).filter(
        FaqItem.id == item_id, FaqItem.tenant_id == tenant.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="问题不存在")
    db.delete(item)
    db.commit()
    return {"message": "已删除"}


@router.put("/faq/reorder")
async def reorder_faq(
    req: FaqReorderRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """批量重排"""
    for idx, item_id in enumerate(req.ids):
        db.query(FaqItem).filter(
            FaqItem.id == item_id, FaqItem.tenant_id == tenant.id
        ).update({"sort_order": idx})
    db.commit()
    return {"message": "排序已更新"}

