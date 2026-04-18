"""
积分管理路由
管理员设置扣费规则、查看消费记录、给商户充值
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.models import Admin
from services.points_service import PointsService
from utils.security import get_current_admin

router = APIRouter(prefix="/api/admin/points", tags=["积分管理"])


@router.get("/config")
async def get_points_config(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取扣费配置"""
    config = PointsService.get_config(db)
    return config


@router.post("/config")
async def update_points_config(
    data: dict,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """更新扣费配置"""
    success = PointsService.update_config(db, data)
    if success:
        return {"message": "配置已更新"}
    raise HTTPException(status_code=500, detail="配置更新失败")


@router.get("/tenants/{tenant_id}")
async def get_tenant_points(
    tenant_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取商户积分信息"""
    from models.models import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="商户不存在")
    
    # 获取消费记录
    transactions = PointsService.get_transaction_history(db, tenant_id, limit=20)
    
    return {
        "tenant_id": tenant.id,
        "company_name": tenant.company_name,
        "email": tenant.email,
        "points_balance": tenant.points_balance,
        "transactions": [
            {
                "id": t.id,
                "type": t.transaction_type,
                "points": t.points,
                "description": t.description,
                "related_id": t.related_id,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in transactions
        ]
    }


@router.post("/tenants/{tenant_id}/recharge")
async def recharge_tenant_points(
    tenant_id: int,
    data: dict,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """给商户充值积分"""
    points = data.get("points", 0)
    description = data.get("description", f"管理员 {admin.username} 充值")
    
    if points <= 0:
        raise HTTPException(status_code=400, detail="充值点数必须大于0")
    
    success, message, new_balance = PointsService.recharge_points(
        db, tenant_id, points, description
    )
    
    if success:
        return {
            "message": message,
            "points_added": points,
            "new_balance": new_balance
        }
    raise HTTPException(status_code=500, detail=message)


@router.get("/tenants")
async def get_all_tenants_points(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取所有商户的积分信息"""
    from models.models import Tenant
    
    tenants = db.query(Tenant).all()
    
    return {
        "tenants": [
            {
                "id": t.id,
                "company_name": t.company_name,
                "email": t.email,
                "points_balance": t.points_balance or 0
            }
            for t in tenants
        ]
    }


@router.get("/transactions")
async def get_all_transactions(
    limit: int = 100,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取所有商户的积分消费记录"""
    from models.models import PointsTransaction, Tenant
    
    transactions = db.query(PointsTransaction, Tenant).join(
        Tenant, PointsTransaction.tenant_id == Tenant.id
    ).order_by(
        PointsTransaction.created_at.desc()
    ).limit(limit).all()
    
    return {
        "transactions": [
            {
                "id": t.PointsTransaction.id,
                "tenant_id": t.Tenant.id,
                "company_name": t.Tenant.company_name,
                "type": t.PointsTransaction.transaction_type,
                "points": t.PointsTransaction.points,
                "description": t.PointsTransaction.description,
                "created_at": t.PointsTransaction.created_at.isoformat() if t.PointsTransaction.created_at else None
            }
            for t in transactions
        ]
    }
