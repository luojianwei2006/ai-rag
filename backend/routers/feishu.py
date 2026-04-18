"""
飞书开放平台 Webhook 路由
接收飞书消息事件并回复
"""
import json
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.models import Tenant
from services.feishu_service import FeishuService, verify_feishu_signature, handle_feishu_message
from utils.security import get_current_tenant

router = APIRouter(prefix="/api/feishu", tags=["飞书"])


@router.post("/webhook/{tenant_id}")
async def feishu_webhook(
    tenant_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    飞书事件订阅 Webhook
    每个商户有独立的 webhook 地址: /api/feishu/webhook/{tenant_id}
    """
    # 读取原始 body
    body = await request.body()
    body_str = body.decode("utf-8")
    
    print(f"[Feishu Webhook] Received: {body_str[:500]}")
    
    # 解析事件数据
    try:
        event_data = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的 JSON 数据")
    
    # 处理飞书 URL 验证（挑战请求）
    if event_data.get("type") == "url_verification":
        challenge = event_data.get("challenge", "")
        print(f"[Feishu Webhook] URL verification: {challenge}")
        return {"challenge": challenge}
    
    # 获取商户配置
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant or not tenant.is_active:
        print(f"[Feishu Webhook] Tenant not found or inactive: {tenant_id}")
        raise HTTPException(status_code=404, detail="商户不存在或未激活")
    
    # 检查是否配置了飞书
    if not tenant.feishu_app_id or not tenant.feishu_app_secret:
        print(f"[Feishu Webhook] Feishu not configured for tenant: {tenant_id}")
        raise HTTPException(status_code=400, detail="商户未配置飞书接入")
    
    # 验证签名（如果配置了加密密钥）
    timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
    nonce = request.headers.get("X-Lark-Request-Nonce", "")
    signature = request.headers.get("X-Lark-Signature", "")
    
    if tenant.feishu_encrypt_key:
        if not verify_feishu_signature(timestamp, nonce, tenant.feishu_encrypt_key, body_str, signature):
            raise HTTPException(status_code=401, detail="签名验证失败")
    
    # 处理消息
    reply_content = await handle_feishu_message(tenant, event_data)
    print(f"[Feishu Webhook] Reply content: {reply_content[:100] if reply_content else '(empty)'}")
    
    # 如果有回复内容，发送给用户
    if reply_content:
        event = event_data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})
        
        # 获取用户 open_id - 飞书实际返回的字段可能是 union_id 或 user_id
        sender_id_obj = sender.get("sender_id", {})
        open_id = sender_id_obj.get("open_id") or sender_id_obj.get("union_id") or sender_id_obj.get("user_id", "")
        
        print(f"[Feishu Webhook] === 准备发送回复消息 ===")
        print(f"[Feishu Webhook] Reply content: {reply_content[:200] if reply_content else '(empty)'}")
        print(f"[Feishu Webhook] Sender object: {sender}")
        print(f"[Feishu Webhook] Sender ID object: {sender_id_obj}")
        print(f"[Feishu Webhook] User open_id: {open_id}")
        print(f"[Feishu Webhook] Tenant ID: {tenant.id}")
        print(f"[Feishu Webhook] Tenant feishu_app_id: {tenant.feishu_app_id}")
        print(f"[Feishu Webhook] Tenant feishu_app_secret: {tenant.feishu_app_secret[:4]}****{tenant.feishu_app_secret[-4:] if tenant.feishu_app_secret and len(tenant.feishu_app_secret) > 8 else ''}")
        
        if open_id:
            print(f"[Feishu Webhook] 创建 FeishuService 实例...")
            feishu = FeishuService(tenant.feishu_app_id, tenant.feishu_app_secret)
            print(f"[Feishu Webhook] 调用 send_text_message...")
            success = await feishu.send_text_message(open_id, reply_content)
            print(f"[Feishu Webhook] Send message result: {success}")
        else:
            print(f"[Feishu Webhook] No open_id found in sender: {sender}")
    
    # 返回成功响应
    return {"code": 0, "msg": "success"}


@router.get("/config")
async def get_feishu_config(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """获取商户飞书配置（敏感信息脱敏）"""
    return {
        "enabled": tenant.feishu_enabled or False,
        "app_id": tenant.feishu_app_id or "",
        "app_secret_masked": mask_secret(tenant.feishu_app_secret) if tenant.feishu_app_secret else "",
        "encrypt_key_masked": mask_secret(tenant.feishu_encrypt_key) if tenant.feishu_encrypt_key else "",
        "webhook_url": f"/api/feishu/webhook/{tenant.id}" if tenant.id else ""
    }


@router.post("/config")
async def update_feishu_config(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """更新商户飞书配置"""
    data = await request.json()
    
    tenant.feishu_enabled = data.get("enabled", False)
    
    # 更新 app_id
    if "app_id" in data:
        tenant.feishu_app_id = data["app_id"]
    
    # 更新 app_secret（如果提供了新值）
    if "app_secret" in data and data["app_secret"]:
        tenant.feishu_app_secret = data["app_secret"]
    
    # 更新 encrypt_key（如果提供了新值）
    if "encrypt_key" in data and data["encrypt_key"]:
        tenant.feishu_encrypt_key = data["encrypt_key"]
    
    db.commit()
    
    return {"message": "配置已保存"}


@router.post("/test")
async def test_feishu_connection(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """测试飞书连接"""
    data = await request.json()
    
    app_id = data.get("app_id") or tenant.feishu_app_id
    app_secret = data.get("app_secret") or tenant.feishu_app_secret
    
    if not app_id or not app_secret:
        raise HTTPException(status_code=400, detail="请提供 App ID 和 App Secret")
    
    try:
        feishu = FeishuService(app_id, app_secret)
        token = await feishu._get_access_token()
        return {"success": True, "message": "连接成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")


def mask_secret(secret: str) -> str:
    """脱敏显示密钥"""
    if not secret or len(secret) < 8:
        return "****"
    return secret[:4] + "****" + secret[-4:]



