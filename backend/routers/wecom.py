"""
企业微信 Webhook 路由
接收企业微信消息事件并回复
"""
import json
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.models import Tenant
from services.wecom_service import WeComService, verify_wecom_signature, parse_wecom_message, handle_wecom_message
from utils.security import get_current_tenant

router = APIRouter(prefix="/api/wecom", tags=["企业微信"])


@router.get("/webhook/{tenant_id}")
async def wecom_webhook_verify(
    tenant_id: int,
    msg_signature: str = "",
    timestamp: str = "",
    nonce: str = "",
    echostr: str = "",
    db: Session = Depends(get_db)
):
    """
    企业微信服务器验证（URL 验证）
    企业微信配置接收消息时，需要验证服务器地址
    """
    print(f"[WeCom Webhook] 验证请求: tenant_id={tenant_id}")
    
    # 获取商户配置
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="商户不存在或未激活")
    
    if not tenant.wecom_corp_id or not tenant.wecom_token:
        raise HTTPException(status_code=400, detail="商户未配置企业微信")
    
    # 验证签名
    if tenant.wecom_token:
        expected_sig = verify_wecom_signature(tenant.wecom_token, timestamp, nonce, echostr)
        if expected_sig != msg_signature:
            print(f"[WeCom Webhook] 签名验证失败")
            raise HTTPException(status_code=403, detail="签名验证失败")
    
    print(f"[WeCom Webhook] 验证成功，返回 echostr")
    # 返回 echostr 完成验证
    return echostr


@router.post("/webhook/{tenant_id}")
async def wecom_webhook(
    tenant_id: int,
    request: Request,
    msg_signature: str = "",
    timestamp: str = "",
    nonce: str = "",
    db: Session = Depends(get_db)
):
    """
    企业微信消息接收 Webhook
    每个商户有独立的 webhook 地址: /api/wecom/webhook/{tenant_id}
    """
    # 读取原始 body（XML 格式）
    body = await request.body()
    body_str = body.decode("utf-8")
    
    print(f"[WeCom Webhook] 收到消息: tenant_id={tenant_id}")
    print(f"[WeCom Webhook] Body: {body_str[:500]}")
    
    # 获取商户配置
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant or not tenant.is_active:
        print(f"[WeCom Webhook] 商户不存在或未激活: {tenant_id}")
        raise HTTPException(status_code=404, detail="商户不存在或未激活")
    
    if not tenant.wecom_corp_id or not tenant.wecom_agent_id or not tenant.wecom_secret:
        print(f"[WeCom Webhook] 商户未配置企业微信: {tenant_id}")
        raise HTTPException(status_code=400, detail="商户未配置企业微信")
    
    # 解析 XML 消息
    message_data = parse_wecom_message(body_str)
    if not message_data:
        print(f"[WeCom Webhook] 解析消息失败")
        raise HTTPException(status_code=400, detail="无效的消息格式")
    
    print(f"[WeCom Webhook] 解析后的消息: {message_data}")
    
    # 处理消息
    reply_content = await handle_wecom_message(tenant, message_data)
    print(f"[WeCom Webhook] 回复内容: {reply_content[:100] if reply_content else '(empty)'}")
    
    # 如果有回复内容，发送给用户
    if reply_content:
        user_id = message_data.get("FromUserName", "")
        print(f"[WeCom Webhook] 发送回复给用户: {user_id}")
        
        wecom = WeComService(
            corp_id=tenant.wecom_corp_id,
            agent_id=tenant.wecom_agent_id,
            secret=tenant.wecom_secret
        )
        success = await wecom.send_text_message(user_id, reply_content)
        print(f"[WeCom Webhook] 发送结果: {success}")
    
    # 返回成功响应（企业微信要求返回 success）
    return "success"


@router.get("/config")
async def get_wecom_config(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """获取商户企业微信配置（敏感信息脱敏）"""
    return {
        "enabled": tenant.wecom_enabled or False,
        "corp_id": tenant.wecom_corp_id or "",
        "agent_id": tenant.wecom_agent_id or "",
        "secret_masked": mask_secret(tenant.wecom_secret) if tenant.wecom_secret else "",
        "token_masked": mask_secret(tenant.wecom_token) if tenant.wecom_token else "",
        "encoding_aes_key_masked": mask_secret(tenant.wecom_encoding_aes_key) if tenant.wecom_encoding_aes_key else "",
        "webhook_url": f"/api/wecom/webhook/{tenant.id}" if tenant.id else ""
    }


@router.post("/config")
async def update_wecom_config(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """更新商户企业微信配置"""
    data = await request.json()
    
    tenant.wecom_enabled = data.get("enabled", False)
    
    # 更新 corp_id
    if "corp_id" in data:
        tenant.wecom_corp_id = data["corp_id"]
    
    # 更新 agent_id
    if "agent_id" in data:
        tenant.wecom_agent_id = data["agent_id"]
    
    # 更新 secret（如果提供了新值）
    if "secret" in data and data["secret"]:
        tenant.wecom_secret = data["secret"]
    
    # 更新 token（如果提供了新值）
    if "token" in data and data["token"]:
        tenant.wecom_token = data["token"]
    
    # 更新 encoding_aes_key（如果提供了新值）
    if "encoding_aes_key" in data and data["encoding_aes_key"]:
        tenant.wecom_encoding_aes_key = data["encoding_aes_key"]
    
    db.commit()
    
    return {"message": "配置已保存"}


@router.post("/test")
async def test_wecom_connection(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """测试企业微信连接"""
    data = await request.json()
    
    corp_id = data.get("corp_id") or tenant.wecom_corp_id
    agent_id = data.get("agent_id") or tenant.wecom_agent_id
    secret = data.get("secret") or tenant.wecom_secret
    
    if not corp_id or not agent_id or not secret:
        raise HTTPException(status_code=400, detail="请提供 CorpID、AgentID 和 Secret")
    
    try:
        wecom = WeComService(corp_id=corp_id, agent_id=agent_id, secret=secret)
        token = await wecom._get_access_token()
        return {"success": True, "message": "连接成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")


def mask_secret(secret: str) -> str:
    """脱敏显示密钥"""
    if not secret or len(secret) < 8:
        return "****"
    return secret[:4] + "****" + secret[-4:]
