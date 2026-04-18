"""
积分服务模块
管理商户积分余额和消费记录
"""
from sqlalchemy.orm import Session
from models.models import Tenant, PointsTransaction, SystemConfig


class PointsService:
    """积分服务"""
    
    # 默认扣费配置
    DEFAULT_CONFIG = {
        "knowledge_add_cost": 100,      # 知识库添加扣费
        "ai_reply_cost": 5,              # AI客服回答扣费
        "human_reply_cost": 1            # 人工客服回答扣费
    }
    
    @staticmethod
    def get_config(db: Session) -> dict:
        """获取扣费配置"""
        config = {}
        for key, default_value in PointsService.DEFAULT_CONFIG.items():
            db_config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if db_config and db_config.value:
                try:
                    config[key] = int(db_config.value)
                except ValueError:
                    config[key] = default_value
            else:
                config[key] = default_value
        return config
    
    @staticmethod
    def update_config(db: Session, config: dict) -> bool:
        """更新扣费配置"""
        try:
            for key in PointsService.DEFAULT_CONFIG.keys():
                if key in config:
                    db_config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
                    if db_config:
                        db_config.value = str(config[key])
                    else:
                        db_config = SystemConfig(
                            key=key,
                            value=str(config[key]),
                            description=PointsService._get_config_description(key)
                        )
                        db.add(db_config)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            print(f"更新扣费配置失败: {e}")
            return False
    
    @staticmethod
    def _get_config_description(key: str) -> str:
        """获取配置项描述"""
        descriptions = {
            "knowledge_add_cost": "知识库添加扣费（点）",
            "ai_reply_cost": "AI客服回答扣费（点）",
            "human_reply_cost": "人工客服回答扣费（点）"
        }
        return descriptions.get(key, "")
    
    @staticmethod
    def deduct_points(db: Session, tenant_id: int, points: int, transaction_type: str, 
                      description: str = None, related_id: str = None) -> tuple:
        """
        扣除商户积分
        返回: (success: bool, message: str, new_balance: int)
        """
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return False, "商户不存在", 0
        
        if tenant.points_balance < points:
            return False, f"积分不足，当前余额: {tenant.points_balance} 点", tenant.points_balance
        
        try:
            # 扣除积分
            tenant.points_balance -= points
            
            # 记录消费
            transaction = PointsTransaction(
                tenant_id=tenant_id,
                transaction_type=transaction_type,
                points=-points,
                description=description or PointsService._get_transaction_description(transaction_type),
                related_id=related_id
            )
            db.add(transaction)
            db.commit()
            
            return True, "扣费成功", tenant.points_balance
        except Exception as e:
            db.rollback()
            print(f"扣费失败: {e}")
            return False, f"扣费失败: {str(e)}", tenant.points_balance
    
    @staticmethod
    def recharge_points(db: Session, tenant_id: int, points: int, description: str = None) -> tuple:
        """
        给商户充值积分
        返回: (success: bool, message: str, new_balance: int)
        """
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return False, "商户不存在", 0
        
        try:
            # 增加积分
            tenant.points_balance += points
            
            # 记录充值
            transaction = PointsTransaction(
                tenant_id=tenant_id,
                transaction_type="recharge",
                points=points,
                description=description or "管理员充值"
            )
            db.add(transaction)
            db.commit()
            
            return True, "充值成功", tenant.points_balance
        except Exception as e:
            db.rollback()
            print(f"充值失败: {e}")
            return False, f"充值失败: {str(e)}", tenant.points_balance
    
    @staticmethod
    def _get_transaction_description(transaction_type: str) -> str:
        """获取交易类型描述"""
        descriptions = {
            "knowledge_add": "添加知识库",
            "ai_reply": "AI客服回答",
            "human_reply": "人工客服回答",
            "recharge": "积分充值"
        }
        return descriptions.get(transaction_type, "其他")
    
    @staticmethod
    def get_transaction_history(db: Session, tenant_id: int, limit: int = 50):
        """获取商户积分消费记录"""
        return db.query(PointsTransaction).filter(
            PointsTransaction.tenant_id == tenant_id
        ).order_by(PointsTransaction.created_at.desc()).limit(limit).all()
