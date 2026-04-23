from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models.models import Admin, SystemConfig
from utils.security import (
    verify_password, get_password_hash,
    create_access_token, get_current_admin
)
from services.email_service import send_email, get_smtp_config
from typing import Optional

router = APIRouter(prefix="/api/admin", tags=["管理员"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class SmtpConfigRequest(BaseModel):
    smtp_host: str
    smtp_port: str
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_tls: str = "true"


class ApiKeyConfigRequest(BaseModel):
    glm: Optional[str] = None
    openai: Optional[str] = None
    gemini: Optional[str] = None


class ApiKeyItem(BaseModel):
    id: Optional[str] = None          # 前端生成的唯一ID
    provider: str                      # glm / openai / gemini / deepseek / qwen
    model: str                         # 具体模型名
    api_key: str
    enabled: bool = True


class ApiKeyListRequest(BaseModel):
    keys: list[ApiKeyItem]


class TestApiKeyRequest(BaseModel):
    provider: str
    model: str
    api_key: str = ""


class TestEmailRequest(BaseModel):
    to_email: str


@router.post("/login")
async def admin_login(req: LoginRequest, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == req.username).first()
    if not admin or not verify_password(req.password, admin.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_access_token({"sub": admin.username, "type": "admin"})
    return {"access_token": token, "token_type": "bearer", "username": admin.username}


@router.post("/change-password")
async def admin_change_password(
    req: ChangePasswordRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if not verify_password(req.old_password, admin.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    admin.hashed_password = get_password_hash(req.new_password)
    db.commit()
    return {"message": "密码修改成功"}


@router.get("/smtp-config")
async def get_smtp_config_api(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    config = get_smtp_config(db)
    # 隐藏密码
    if config.get("smtp_password"):
        config["smtp_password"] = "******"
    return config


@router.post("/smtp-config")
async def save_smtp_config(
    req: SmtpConfigRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    config_data = req.dict()
    for key, value in config_data.items():
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if config:
            config.value = value
        else:
            db.add(SystemConfig(key=key, value=value))
    db.commit()
    return {"message": "SMTP配置保存成功"}


@router.post("/smtp-test")
async def test_smtp(
    req: TestEmailRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    success, msg = await send_email(
        db, req.to_email,
        "SMTP配置测试邮件",
        "<h2>✅ SMTP配置测试成功！</h2><p>您的邮件服务已正常配置。</p>"
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@router.get("/api-keys")
async def get_api_keys(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取系统API Key列表（新格式：列表）"""
    import json
    config = db.query(SystemConfig).filter(SystemConfig.key == "api_keys_v2").first()
    if config and config.value:
        keys = json.loads(config.value)
        # 脱敏处理
        for k in keys:
            raw = k.get("api_key", "")
            if raw and len(raw) > 8:
                k["api_key_masked"] = raw[:4] + "****" + raw[-4:]
            else:
                k["api_key_masked"] = "****"
            k["api_key"] = ""  # 不返回真实key
        return {"keys": keys}
    # 兼容旧格式
    old_keys = db.query(SystemConfig).filter(
        SystemConfig.key.in_(["api_key_glm", "api_key_openai", "api_key_gemini"])
    ).all()
    keys = []
    for c in old_keys:
        provider = c.key.replace("api_key_", "")
        if c.value:
            model_map = {"glm": "glm-4-flash", "openai": "gpt-3.5-turbo", "gemini": "gemini-pro"}
            keys.append({
                "id": provider,
                "provider": provider,
                "model": model_map.get(provider, provider),
                "api_key": "",
                "api_key_masked": c.value[:4] + "****" + c.value[-4:] if len(c.value) > 8 else "****",
                "enabled": True
            })
    return {"keys": keys}


@router.post("/api-keys")
async def save_api_keys(
    req: ApiKeyListRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """保存系统API Key列表"""
    import json
    # 读取旧数据（保留未修改的key值）
    old_config = db.query(SystemConfig).filter(SystemConfig.key == "api_keys_v2").first()
    old_keys_map = {}
    old_keys_by_provider_model = {}
    if old_config and old_config.value:
        for k in json.loads(old_config.value):
            old_keys_map[k["id"]] = k.get("api_key", "")
            # 同时用 provider+model 作为备用key
            pm_key = f"{k.get('provider', '')}:{k.get('model', '')}"
            old_keys_by_provider_model[pm_key] = k.get("api_key", "")

    save_list = []
    for item in req.keys:
        # 如果前端传来空key，先尝试用id匹配，再用provider+model匹配
        real_key = item.api_key
        if not real_key:
            real_key = old_keys_map.get(item.id, "")
        if not real_key:
            pm_key = f"{item.provider}:{item.model}"
            real_key = old_keys_by_provider_model.get(pm_key, "")
        
        save_list.append({
            "id": item.id or item.provider,
            "provider": item.provider,
            "model": item.model,
            "api_key": real_key,
            "enabled": item.enabled
        })

    config = db.query(SystemConfig).filter(SystemConfig.key == "api_keys_v2").first()
    if config:
        config.value = json.dumps(save_list, ensure_ascii=False)
    else:
        db.add(SystemConfig(key="api_keys_v2", value=json.dumps(save_list, ensure_ascii=False)))
    db.commit()
    return {"message": "API Key保存成功"}


@router.post("/api-keys/test")
async def test_api_key(
    req: TestApiKeyRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """测试API Key连通性"""
    import httpx, json
    provider = req.provider
    model = req.model
    api_key = req.api_key

    # 如果api_key为空，从数据库取对应的key
    if not api_key:
        old_config = db.query(SystemConfig).filter(SystemConfig.key == "api_keys_v2").first()
        if old_config and old_config.value:
            for k in json.loads(old_config.value):
                if k.get("provider") == provider and k.get("model") == model:
                    api_key = k.get("api_key", "")
                    break

    if not api_key:
        raise HTTPException(status_code=400, detail="API Key不能为空，请先在输入框中填写Key后再测试")

    try:
        if provider == "glm":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                else:
                    detail = resp.json().get("error", {}).get("message", resp.text[:100])
                    raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif provider == "openai":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                else:
                    detail = resp.json().get("error", {}).get("message", resp.text[:100])
                    raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif provider == "gemini":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                    json={"contents": [{"parts": [{"text": "hi"}]}]}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                else:
                    detail = resp.json().get("error", {}).get("message", resp.text[:100])
                    raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif provider == "deepseek":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                else:
                    detail = resp.json().get("error", {}).get("message", resp.text[:100])
                    raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif provider == "qwen":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                else:
                    detail = resp.json().get("error", {}).get("message", resp.text[:100])
                    raise HTTPException(status_code=400, detail=f"连接失败: {detail}")

        elif provider == "nvidia_zai":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功 ✅"}
                else:
                    # 返回详细的错误信息给前端
                    raw_text = resp.text[:500]
                    raise HTTPException(status_code=400, detail=f"HTTP {resp.status_code}: {raw_text}")

        else:
            raise HTTPException(status_code=400, detail=f"不支持的厂家: {provider}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接异常: {str(e)}")


@router.get("/tenants")
async def list_tenants(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    from models.models import Tenant
    tenants = db.query(Tenant).all()
    return [{
        "id": t.id,
        "email": t.email,
        "company_name": t.company_name,
        "is_active": t.is_active,
        "chat_token": t.chat_token,
        "created_at": t.created_at.isoformat() if t.created_at else None
    } for t in tenants]


@router.patch("/tenants/{tenant_id}/toggle")
async def toggle_tenant(
    tenant_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    from models.models import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="商户不存在")
    tenant.is_active = not tenant.is_active
    db.commit()
    return {"is_active": tenant.is_active}
