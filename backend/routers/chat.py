import json
import secrets
import asyncio
from datetime import datetime
from typing import Dict, Set
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models.models import Tenant, KnowledgeBase, ChatSession, ChatMessage
from utils.security import get_current_tenant, decode_token
from services.rag_service import query_knowledge_base
from services.llm_service import call_llm, get_tenant_llm_config
from services.points_service import PointsService

router = APIRouter(tags=["聊天"])

# 人工介入关键词
HUMAN_KEYWORDS = [
    "人工", "人工客服", "转人工", "真人", "真人客服",
    "找人工", "要人工", "接人工", "帮我找人", "人工服务"
]

# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        # 客户连接: session_id -> WebSocket
        self.customer_connections: Dict[str, WebSocket] = {}
        # 商户监控连接: tenant_id -> Set[WebSocket]
        self.tenant_monitor_connections: Dict[int, Set[WebSocket]] = {}

    async def connect_customer(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.customer_connections[session_id] = ws

    def disconnect_customer(self, session_id: str):
        self.customer_connections.pop(session_id, None)

    async def connect_tenant_monitor(self, tenant_id: int, ws: WebSocket):
        await ws.accept()
        if tenant_id not in self.tenant_monitor_connections:
            self.tenant_monitor_connections[tenant_id] = set()
        self.tenant_monitor_connections[tenant_id].add(ws)

    def disconnect_tenant_monitor(self, tenant_id: int, ws: WebSocket):
        if tenant_id in self.tenant_monitor_connections:
            self.tenant_monitor_connections[tenant_id].discard(ws)

    async def send_to_customer(self, session_id: str, message: dict):
        ws = self.customer_connections.get(session_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect_customer(session_id)

    async def broadcast_to_tenant(self, tenant_id: int, message: dict):
        """向商户的所有监控连接广播消息"""
        connections = self.tenant_monitor_connections.get(tenant_id, set())
        disconnected = set()
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            connections.discard(ws)


manager = ConnectionManager()


# ─────── REST 接口 ───────

class SendMessageRequest(BaseModel):
    content: str


class HumanReplyRequest(BaseModel):
    session_id: str
    content: str


@router.get("/api/chat/sessions")
async def get_chat_sessions(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """获取商户的所有会话"""
    sessions = db.query(ChatSession).filter(
        ChatSession.tenant_id == tenant.id
    ).order_by(ChatSession.created_at.desc()).limit(100).all()

    result = []
    for s in sessions:
        last_msg = db.query(ChatMessage).filter(
            ChatMessage.session_id == s.session_id
        ).order_by(ChatMessage.created_at.desc()).first()

        result.append({
            "session_id": s.session_id,
            "customer_name": s.customer_name,
            "status": s.status,
            "is_human_service": s.is_human_service,
            "last_message": last_msg.content[:50] if last_msg else "",
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "online": s.session_id in manager.customer_connections
        })
    return result


@router.get("/api/chat/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """获取会话消息历史"""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.tenant_id == tenant.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    return [{
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "created_at": m.created_at.isoformat() if m.created_at else None
    } for m in messages]


@router.post("/api/chat/human-reply")
async def human_reply(
    req: HumanReplyRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """商户发送人工回复"""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == req.session_id,
        ChatSession.tenant_id == tenant.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 人工回复扣费检查
    config = PointsService.get_config(db)
    cost = config.get("human_reply_cost", 1)
    
    if tenant.points_balance < cost:
        raise HTTPException(
            status_code=400, 
            detail=f"积分不足，人工回复需要 {cost} 点，当前余额: {tenant.points_balance} 点"
        )

    # 保存消息
    msg = ChatMessage(
        session_id=req.session_id,
        role="human_agent",
        content=req.content
    )
    db.add(msg)
    db.commit()

    # 扣除积分
    success, message, new_balance = PointsService.deduct_points(
        db, tenant.id, cost, "human_reply",
        description="人工客服回复",
        related_id=req.session_id
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)

    # 判断客户类型
    if session.customer_ip == "feishu" or session.session_id.startswith("feishu_"):
        # 飞书用户：通过飞书 API 发送消息
        from services.feishu_service import FeishuService
        
        # 从 customer_name 中提取 open_id (格式: feishu:{open_id})
        open_id = session.customer_name.replace("feishu:", "") if session.customer_name else None
        
        if open_id and tenant.feishu_app_id and tenant.feishu_app_secret:
            try:
                feishu = FeishuService(tenant.feishu_app_id, tenant.feishu_app_secret)
                success = await feishu.send_text_message(open_id, req.content)
                if not success:
                    raise HTTPException(status_code=500, detail="飞书消息发送失败")
            except Exception as e:
                print(f"[HumanReply] 发送飞书消息失败: {e}")
                raise HTTPException(status_code=500, detail=f"飞书消息发送失败: {str(e)}")
        else:
            print(f"[HumanReply] 无法发送飞书消息: open_id={open_id}, feishu_configured={bool(tenant.feishu_app_id)}")
    
    elif session.customer_ip == "wecom" or session.session_id.startswith("wecom_"):
        # 企业微信用户：通过企业微信 API 发送消息
        from services.wecom_service import WeComService
        
        # 从 customer_name 中提取 user_id (格式: wecom:{user_id})
        user_id = session.customer_name.replace("wecom:", "") if session.customer_name else None
        
        if user_id and tenant.wecom_corp_id and tenant.wecom_agent_id and tenant.wecom_secret:
            try:
                wecom = WeComService(
                    corp_id=tenant.wecom_corp_id,
                    agent_id=tenant.wecom_agent_id,
                    secret=tenant.wecom_secret
                )
                success = await wecom.send_text_message(user_id, req.content)
                if not success:
                    raise HTTPException(status_code=500, detail="企业微信消息发送失败")
            except Exception as e:
                print(f"[HumanReply] 发送企业微信消息失败: {e}")
                raise HTTPException(status_code=500, detail=f"企业微信消息发送失败: {str(e)}")
        else:
            print(f"[HumanReply] 无法发送企业微信消息: user_id={user_id}, wecom_configured={bool(tenant.wecom_corp_id)}")
    
    else:
        # 网页用户：通过 WebSocket 推送
        await manager.send_to_customer(req.session_id, {
            "type": "message",
            "role": "human_agent",
            "content": req.content,
            "timestamp": datetime.now().isoformat()
        })

    return {
        "message": "发送成功",
        "points_deducted": cost,
        "points_balance": new_balance
    }


# ─────── 客户端公开接口 ───────

@router.get("/api/public/chat/{chat_token}/info")
async def get_chat_info(chat_token: str, db: Session = Depends(get_db)):
    """获取客服信息（客户端使用）"""
    tenant = db.query(Tenant).filter(Tenant.chat_token == chat_token).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="客服服务不可用")
    return {
        "company_name": tenant.company_name or "在线客服",
        "chat_token": chat_token
    }


# ─────── WebSocket ───────

@router.websocket("/ws/chat/{chat_token}")
async def customer_chat_ws(
    websocket: WebSocket,
    chat_token: str
):
    """客户聊天 WebSocket"""
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.chat_token == chat_token).first()
        if not tenant or not tenant.is_active:
            await websocket.close(code=4004)
            return

        # 创建会话
        session_id = secrets.token_urlsafe(16)
        session = ChatSession(
            tenant_id=tenant.id,
            session_id=session_id,
            customer_ip=websocket.client.host if websocket.client else "unknown",
            status="active"
        )
        db.add(session)
        db.commit()

        await manager.connect_customer(session_id, websocket)

        # 通知商户
        await manager.broadcast_to_tenant(tenant.id, {
            "type": "new_session",
            "session_id": session_id,
            "customer_name": "访客",
            "timestamp": datetime.now().isoformat()
        })

        # 发送欢迎消息
        welcome = "您好！我是AI客服助手，请问有什么可以帮助您的？"
        welcome_msg = ChatMessage(session_id=session_id, role="ai", content=welcome)
        db.add(welcome_msg)
        db.commit()

        await websocket.send_json({
            "type": "message",
            "role": "ai",
            "content": welcome,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })

        # 消息循环
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_message = payload.get("content", "").strip()

            if not user_message:
                continue

            # 保存用户消息
            user_msg = ChatMessage(session_id=session_id, role="customer", content=user_message)
            db.add(user_msg)
            db.commit()

            # 广播给商户
            await manager.broadcast_to_tenant(tenant.id, {
                "type": "message",
                "session_id": session_id,
                "role": "customer",
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            })

            # 检查是否请求人工
            is_human_request = any(kw in user_message for kw in HUMAN_KEYWORDS)

            if is_human_request or session.is_human_service:
                # 转人工
                if not session.is_human_service:
                    session.is_human_service = True
                    session.status = "human"
                    db.commit()

                    transfer_msg = "已为您转接人工客服，请稍候..."
                    ai_msg = ChatMessage(session_id=session_id, role="ai", content=transfer_msg)
                    db.add(ai_msg)
                    db.commit()

                    await websocket.send_json({
                        "type": "message",
                        "role": "system",
                        "content": transfer_msg,
                        "timestamp": datetime.now().isoformat()
                    })

                    # 通知商户
                    await manager.broadcast_to_tenant(tenant.id, {
                        "type": "human_requested",
                        "session_id": session_id,
                        "content": user_message,
                        "timestamp": datetime.now().isoformat()
                    })
                continue

            # AI回复
            try:
                # AI 回复扣费检查
                config = PointsService.get_config(db)
                cost = config.get("ai_reply_cost", 5)
                
                if tenant.points_balance < cost:
                    reply = f"抱歉，您的积分不足（当前余额: {tenant.points_balance} 点），无法使用AI客服服务。请联系管理员充值。"
                else:
                    # 获取知识库
                    kbs = db.query(KnowledgeBase).filter(
                        KnowledgeBase.tenant_id == tenant.id,
                        KnowledgeBase.status == "ready"
                    ).all()

                    context = ""
                    if kbs:
                        all_docs = []
                        for kb in kbs:
                            docs = query_knowledge_base(tenant.id, kb.id, user_message, n_results=3)
                            all_docs.extend(docs)
                        context = "\n".join(all_docs[:10])

                    # 获取历史消息（最近10条）
                    recent_msgs = db.query(ChatMessage).filter(
                        ChatMessage.session_id == session_id
                    ).order_by(ChatMessage.created_at.desc()).limit(10).all()
                    recent_msgs.reverse()

                    history = []
                    for m in recent_msgs:
                        if m.role == "customer":
                            history.append({"role": "user", "content": m.content})
                        elif m.role == "ai":
                            history.append({"role": "assistant", "content": m.content})

                    model, api_keys = get_tenant_llm_config(tenant, db)
                    if not api_keys:
                        reply = "抱歉，AI服务暂时不可用，请联系客服。"
                    else:
                        reply = await call_llm(model, api_keys, history, context)
                        
                        # 扣除积分
                        PointsService.deduct_points(
                            db, tenant.id, cost, "ai_reply",
                            description="AI客服回答（网页）",
                            related_id=session_id
                        )

            except Exception as e:
                reply = "抱歉，处理您的问题时出现了错误，请稍后重试。"

            # 保存AI回复
            ai_msg = ChatMessage(session_id=session_id, role="ai", content=reply)
            db.add(ai_msg)
            db.commit()

            # 发送给客户
            await websocket.send_json({
                "type": "message",
                "role": "ai",
                "content": reply,
                "timestamp": datetime.now().isoformat()
            })

            # 广播给商户
            await manager.broadcast_to_tenant(tenant.id, {
                "type": "message",
                "session_id": session_id,
                "role": "ai",
                "content": reply,
                "timestamp": datetime.now().isoformat()
            })

    except WebSocketDisconnect:
        manager.disconnect_customer(session_id)
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if session:
            session.status = "closed"
            db.commit()
        await manager.broadcast_to_tenant(tenant.id, {
            "type": "session_closed",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        manager.disconnect_customer(session_id if 'session_id' in locals() else "")
    finally:
        db.close()


@router.websocket("/ws/monitor/{token}")
async def tenant_monitor_ws(websocket: WebSocket, token: str):
    """商户监控 WebSocket"""
    db = SessionLocal()
    try:
        payload = decode_token(token)
        if not payload or payload.get("type") != "tenant":
            await websocket.close(code=4001)
            return

        tenant = db.query(Tenant).filter(Tenant.id == payload.get("sub")).first()
        if not tenant:
            await websocket.close(code=4004)
            return

        await manager.connect_tenant_monitor(tenant.id, websocket)

        await websocket.send_json({
            "type": "connected",
            "message": "监控连接已建立"
        })

        # 保持连接
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # 处理心跳
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("ping")

    except WebSocketDisconnect:
        manager.disconnect_tenant_monitor(tenant.id if 'tenant' in locals() else 0, websocket)
    finally:
        db.close()
