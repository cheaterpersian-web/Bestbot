from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import HTMLResponse, FileResponse
from typing import Optional, List
import json
import hmac
import hashlib
import urllib.parse
from datetime import datetime

from core.db import get_db_session
from core.config import settings
from sqlalchemy import and_
from models.user import TelegramUser
from models.service import Service
from models.catalog import Server, Category, Plan
from models.billing import Transaction
from services.vpn_panel_service import VPNPanelService


router = APIRouter(prefix="/api", tags=["webapp"])


def verify_telegram_auth(authorization: str = Header(None)) -> dict:
    """Verify Telegram Web App authentication"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    init_data = authorization[7:]  # Remove "Bearer " prefix
    
    try:
        # Parse init data into ordered list
        kv_pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
        data_check_pairs: list[str] = []
        provided_hash: Optional[str] = None
        for key, value in kv_pairs:
            if key == "hash":
                provided_hash = value
            else:
                data_check_pairs.append(f"{key}={value}")
        data_check_pairs.sort()
        data_check_string = "\n".join(data_check_pairs)

        # Build secret key per Telegram docs
        secret_key = hmac.new(
            "WebAppData".encode(),
            settings.bot_token.encode(),
            hashlib.sha256,
        ).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not provided_hash or calculated_hash != provided_hash:
            raise HTTPException(status_code=401, detail="Invalid hash")

        # Parse user data
        user_data_str = dict(kv_pairs).get("user", "{}")
        user_data = json.loads(user_data_str)
        return user_data
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid init data")


@router.get("/", response_class=HTMLResponse)
async def webapp_index():
    """Serve the main webapp page"""
    return FileResponse("app/webapp/static/index.html")


@router.get("/user/stats")
async def get_user_stats(user_data: dict = Depends(verify_telegram_auth)):
    """Get user statistics"""
    async with get_db_session() as session:
        from sqlalchemy import select, func
        
        # Get user
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_data['id'])
        )).scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get active services count
        active_services = (await session.execute(
            select(func.count(Service.id))
            .where(
                and_(
                    Service.user_id == user.id,
                    Service.is_active == True
                )
            )
        )).scalar() or 0
        
        # Get total purchases
        total_purchases = (await session.execute(
            select(func.count(Service.id))
            .where(Service.user_id == user.id)
        )).scalar() or 0
        
        return {
            "wallet_balance": user.wallet_balance,
            "active_services": active_services,
            "total_purchases": total_purchases,
            "total_spent": user.total_spent
        }


@router.get("/user/services")
async def get_user_services(user_data: dict = Depends(verify_telegram_auth)):
    """Get user's services"""
    async with get_db_session() as session:
        from sqlalchemy import select
        
        # Get user
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_data['id'])
        )).scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get services
        services = (await session.execute(
            select(Service)
            .where(Service.user_id == user.id)
            .order_by(Service.created_at.desc())
        )).scalars().all()
        
        return [
            {
                "id": service.id,
                "remark": service.remark,
                "is_active": service.is_active,
                "purchased_at": service.purchased_at.isoformat(),
                "expires_at": service.expires_at.isoformat(),
                "traffic_gb": service.traffic_gb,
                "used_traffic_gb": service.used_traffic_gb,
                "config_link": service.config_link,
                "qr_code": service.qr_code
            }
            for service in services
        ]


@router.get("/servers")
async def get_servers(user_data: dict = Depends(verify_telegram_auth)):
    """Get available servers"""
    async with get_db_session() as session:
        from sqlalchemy import select
        
        servers = (await session.execute(
            select(Server)
            .where(Server.is_active == True)
            .order_by(Server.sort_order)
        )).scalars().all()
        
        return [
            {
                "id": server.id,
                "name": server.name,
                "location": server.location,
                "status": server.status
            }
            for server in servers
        ]


@router.get("/servers/{server_id}/categories")
async def get_server_categories(server_id: int, user_data: dict = Depends(verify_telegram_auth)):
    """Get categories for a specific server"""
    async with get_db_session() as session:
        from sqlalchemy import select
        
        categories = (await session.execute(
            select(Category)
            .where(
                and_(
                    Category.is_active == True,
                    Category.server_id == server_id
                )
            )
            .order_by(Category.sort_order)
        )).scalars().all()
        
        return [
            {
                "id": category.id,
                "title": category.title,
                "description": category.description
            }
            for category in categories
        ]


@router.get("/categories/{category_id}/plans")
async def get_category_plans(category_id: int, user_data: dict = Depends(verify_telegram_auth)):
    """Get plans for a specific category"""
    async with get_db_session() as session:
        from sqlalchemy import select
        
        plans = (await session.execute(
            select(Plan)
            .where(
                and_(
                    Plan.is_active == True,
                    Plan.category_id == category_id
                )
            )
            .order_by(Plan.price_irr)
        )).scalars().all()
        
        return [
            {
                "id": plan.id,
                "title": plan.title,
                "description": plan.description,
                "price_irr": plan.price_irr,
                "duration_days": plan.duration_days,
                "traffic_gb": plan.traffic_gb,
                "protocol": plan.protocol
            }
            for plan in plans
        ]


@router.post("/purchase")
async def purchase_service(
    plan_id: int,
    user_data: dict = Depends(verify_telegram_auth)
):
    """Purchase a new service"""
    async with get_db_session() as session:
        from sqlalchemy import select
        
        # Get user
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_data['id'])
        )).scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get plan
        plan = (await session.execute(
            select(Plan).where(Plan.id == plan_id)
        )).scalar_one_or_none()
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Check if user has enough wallet balance
        if user.wallet_balance < plan.price_irr:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")
        
        # Deduct from wallet
        user.wallet_balance -= plan.price_irr
        
        # Create service
        service = Service(
            user_id=user.id,
            plan_id=plan.id,
            server_id=plan.category.server_id,
            remark=f"Service from plan {plan.title}",
            is_active=True,
            purchased_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=plan.duration_days),
            traffic_gb=plan.traffic_gb
        )
        session.add(service)
        await session.flush()
        
        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            service_id=service.id,
            amount=plan.price_irr,
            payment_method="wallet",
            status="approved"
        )
        session.add(transaction)
        
        # Create VPN service on panel
        try:
            vpn_service = await VPNPanelService.create_service(
                session=session,
                service=service,
                plan=plan
            )
            
            # Update service with config details
            service.config_link = vpn_service.get('config_link')
            service.qr_code = vpn_service.get('qr_code')
            service.uuid = vpn_service.get('uuid')
            
        except Exception as e:
            print(f"Error creating VPN service: {e}")
            # Service created but VPN config failed
        
        return {
            "success": True,
            "service_id": service.id,
            "message": "Service purchased successfully"
        }


@router.post("/wallet/topup")
async def wallet_topup(
    amount: int,
    payment_method: str,
    user_data: dict = Depends(verify_telegram_auth)
):
    """Request wallet top-up"""
    async with get_db_session() as session:
        from sqlalchemy import select
        
        # Get user
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_data['id'])
        )).scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if amount < 10000:
            raise HTTPException(status_code=400, detail="Minimum amount is 10,000 IRR")
        
        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            payment_method=payment_method,
            status="pending",
            description=f"Wallet top-up request"
        )
        session.add(transaction)
        
        return {
            "success": True,
            "transaction_id": transaction.id,
            "message": "Top-up request submitted successfully"
        }


@router.get("/wallet/transactions")
async def get_wallet_transactions(user_data: dict = Depends(verify_telegram_auth)):
    """Get user's wallet transactions"""
    async with get_db_session() as session:
        from sqlalchemy import select
        
        # Get user
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_data['id'])
        )).scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get transactions
        transactions = (await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
            .limit(50)
        )).scalars().all()
        
        return [
            {
                "id": transaction.id,
                "amount": transaction.amount,
                "payment_method": transaction.payment_method,
                "status": transaction.status,
                "description": transaction.description,
                "created_at": transaction.created_at.isoformat()
            }
            for transaction in transactions
        ]


@router.post("/service/{service_id}/renew")
async def renew_service(
    service_id: int,
    user_data: dict = Depends(verify_telegram_auth)
):
    """Renew a service"""
    async with get_db_session() as session:
        from sqlalchemy import select
        
        # Get user
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_data['id'])
        )).scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get service
        service = (await session.execute(
            select(Service).where(
                and_(
                    Service.id == service_id,
                    Service.user_id == user.id
                )
            )
        )).scalar_one_or_none()
        
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Get plan
        plan = (await session.execute(
            select(Plan).where(Plan.id == service.plan_id)
        )).scalar_one_or_none()
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Check wallet balance
        if user.wallet_balance < plan.price_irr:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")
        
        # Deduct from wallet
        user.wallet_balance -= plan.price_irr
        
        # Extend service
        service.expires_at += timedelta(days=plan.duration_days)
        service.traffic_gb += plan.traffic_gb
        
        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            service_id=service.id,
            amount=plan.price_irr,
            payment_method="wallet",
            status="approved",
            description=f"Service renewal"
        )
        session.add(transaction)
        
        return {
            "success": True,
            "message": "Service renewed successfully",
            "new_expiry": service.expires_at.isoformat()
        }


@router.get("/service/{service_id}/config")
async def get_service_config(
    service_id: int,
    user_data: dict = Depends(verify_telegram_auth)
):
    """Get service configuration"""
    async with get_db_session() as session:
        from sqlalchemy import select
        
        # Get user
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_data['id'])
        )).scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get service
        service = (await session.execute(
            select(Service).where(
                and_(
                    Service.id == service_id,
                    Service.user_id == user.id
                )
            )
        )).scalar_one_or_none()
        
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        return {
            "config_link": service.config_link,
            "qr_code": service.qr_code,
            "uuid": service.uuid,
            "remark": service.remark,
            "expires_at": service.expires_at.isoformat(),
            "traffic_gb": service.traffic_gb,
            "used_traffic_gb": service.used_traffic_gb
        }