import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from database import get_db
from models.models import Tenant
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


class TestApiKeyRequest(BaseModel):
    provider: str
    model: str
    api_key: str


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
            "points_balance": tenant.points_balance
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
        "points_balance": tenant.points_balance
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

        else:
            raise HTTPException(status_code=400, detail=f"不支持的厂家: {req.provider}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接异常: {str(e)}")
