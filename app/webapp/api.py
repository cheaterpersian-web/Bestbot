from fastapi import APIRouter, HTTPException, Depends, Header, Body
from fastapi.responses import HTMLResponse, FileResponse
from typing import Optional, List
import json
import hmac
import hashlib
import urllib.parse
from datetime import datetime, timedelta

from core.db import get_db_session
from core.config import settings
from sqlalchemy import and_
from models.user import TelegramUser
from models.service import Service
from models.catalog import Server, Category, Plan
from models.billing import Transaction
from services.purchases import create_service_after_payment
from services.panels.factory import get_panel_client_for_server


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
        # Optional: check auth_date freshness (within 1 day)
        try:
            auth_date_str = dict(kv_pairs).get("auth_date")
            if auth_date_str:
                auth_ts = int(auth_date_str)
                if abs(int(datetime.utcnow().timestamp()) - auth_ts) > 86400:
                    raise HTTPException(status_code=401, detail="Auth data expired")
        except HTTPException:
            raise
        except Exception:
            pass
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
            "wallet_balance": float(user.wallet_balance or 0),
            "active_services": active_services,
            "total_purchases": total_purchases,
            "total_spent": float(user.total_spent or 0)
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
        
        result = []
        for service in services:
            # Fetch live usage from panel when possible
            used_gb = float(service.traffic_used_gb or 0)
            total_gb = float(service.traffic_limit_gb or 0)
            panel_seen = True
            try:
                server = (await session.execute(select(Server).where(Server.id == service.server_id))).scalar_one_or_none()
                if server:
                    client = get_panel_client_for_server(
                        base_url=server.api_base_url,
                        panel_type=server.panel_type,
                        auth_mode=getattr(server, "auth_mode", "apikey"),
                        api_key=server.api_key or "",
                        username=getattr(server, "auth_username", None),
                        password=getattr(server, "auth_password", None),
                    )
                    # Prefer querying by email/remark when present, otherwise by uuid
                    query_key = service.remark or service.uuid
                    usage = await client.get_usage(query_key)
                    if isinstance(usage, dict):
                        # If panel returns empty/zero AND DB has no link, consider panel_missing
                        used_from_panel = usage.get("used_gb")
                        total_from_panel = usage.get("total_gb")
                        if used_from_panel is not None:
                            used_gb = float(used_from_panel)
                        try:
                            if total_from_panel is not None and float(total_from_panel) > 0:
                                total_gb = float(total_from_panel)
                        except Exception:
                            pass
                    else:
                        panel_seen = False
            except Exception:
                panel_seen = False

            # Hide services that do not exist on panel anymore and have no usable link
            if not panel_seen and not service.subscription_url:
                continue

            result.append({
                "id": service.id,
                "remark": service.remark,
                "is_active": service.is_active,
                "purchased_at": service.purchased_at.isoformat() if service.purchased_at else None,
                "expires_at": service.expires_at.isoformat() if service.expires_at else None,
                "traffic_gb": total_gb,
                "used_traffic_gb": used_gb,
                "config_link": service.subscription_url,
                "qr_code": None
            })
        return result


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
                "status": getattr(server, "sync_status", "unknown"),
                "panel_type": getattr(server, "panel_type", "mock"),
            }
            for server in servers
        ]


@router.get("/servers/{server_id}/categories")
async def get_server_categories(server_id: int, user_data: dict = Depends(verify_telegram_auth)):
    """Get categories for a specific server"""
    async with get_db_session() as session:
        from sqlalchemy import select

        # Get distinct category ids that have plans on this server
        cat_ids_subq = (
            select(Category.id)
            .join(Plan, Plan.category_id == Category.id)
            .where(and_(Category.is_active == True, Plan.server_id == server_id))
            .distinct()
        )

        categories = (await session.execute(
            select(Category)
            .where(Category.id.in_(cat_ids_subq))
            .order_by(Category.sort_order)
        )).scalars().all()

        return [
            {
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "icon": getattr(c, "icon", None),
                "color": getattr(c, "color", None),
            }
            for c in categories
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
    payload: dict = Body(...),
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
        
        plan_id = int(payload.get("plan_id")) if payload and payload.get("plan_id") else None
        desired_alias = (payload.get("alias") or payload.get("service_name") or payload.get("name") or "").strip()
        # alias is optional; if empty, a default will be used
        # Get plan
        plan = (await session.execute(
            select(Plan).where(Plan.id == plan_id)
        )).scalar_one_or_none()
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Check if user has enough wallet balance
        if float(user.wallet_balance or 0) < float(plan.price_irr or 0):
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")
        
        # Deduct from wallet
        user.wallet_balance = float(user.wallet_balance or 0) - float(plan.price_irr or 0)

        # Find server for plan
        server = (await session.execute(select(Server).where(Server.id == plan.server_id))).scalar_one_or_none()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        # Create service via panel
        # Build a unique remark/alias: prefer user input, fallback to default; if duplicate, append -NN
        base_alias = desired_alias if desired_alias else f"u{user.id}-{plan.title}"
        remark = base_alias
        try:
            from sqlalchemy import select
            exists = (await session.execute(
                select(Service.id).where(Service.user_id == user.id, Service.remark == remark)
            )).first() is not None
            if exists:
                import random
                tried = set()
                for _ in range(50):
                    n = random.randint(10, 99)
                    if n in tried:
                        continue
                    tried.add(n)
                    candidate = f"{base_alias}-{n}"
                    exists = (await session.execute(
                        select(Service.id).where(Service.user_id == user.id, Service.remark == candidate)
                    )).first() is not None
                    if not exists:
                        remark = candidate
                        break
        except Exception:
            pass

        service = await create_service_after_payment(
            session=session,
            user=user,
            plan=plan,
            server=server,
            remark=remark
        )
        await session.flush()

        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            amount=float(plan.price_irr or 0),
            type="purchase",
            status="approved",
            description=f"Purchase plan {plan.title}",
            payment_gateway="wallet",
        )
        session.add(transaction)

        return {
            "success": True,
            "service_id": service.id,
            "message": "Service purchased successfully"
        }


@router.post("/wallet/topup")
async def wallet_topup(
    payload: dict = Body(...),
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
        
        amount = int(payload.get("amount") or 0)
        payment_method = (payload.get("payment_method") or "").strip() or "card_to_card"
        if amount < 10000:
            raise HTTPException(status_code=400, detail="Minimum amount is 10,000 IRR")
        
        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            type="wallet_topup",
            status="pending",
            description=f"Wallet top-up request",
            payment_gateway=payment_method,
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
        if float(user.wallet_balance or 0) < float(plan.price_irr or 0):
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")
        
        # Deduct from wallet
        user.wallet_balance = float(user.wallet_balance or 0) - float(plan.price_irr or 0)

        # Extend service (DB)
        add_days = int(plan.duration_days or 0)
        add_gb = int(plan.traffic_gb or 0)
        if add_days:
            if service.expires_at:
                service.expires_at += timedelta(days=add_days)
            else:
                service.expires_at = datetime.utcnow() + timedelta(days=add_days)
        if add_gb:
            current = float(service.traffic_limit_gb or 0)
            service.traffic_limit_gb = current + float(add_gb)

        # Propagate to panel
        try:
            server = (await session.execute(select(Server).where(Server.id == service.server_id))).scalar_one_or_none()
            if server:
                client = get_panel_client_for_server(
                    base_url=server.api_base_url,
                    panel_type=server.panel_type,
                    auth_mode=getattr(server, "auth_mode", "apikey"),
                    api_key=server.api_key or "",
                    username=getattr(server, "auth_username", None),
                    password=getattr(server, "auth_password", None),
                )
                # Update expiry
                if add_days:
                    await client.renew_service(service.remark or service.uuid, add_days=add_days)
                # Update traffic
                if add_gb:
                    await client.add_traffic(service.remark or service.uuid, add_gb=add_gb)
        except Exception:
            # Ignore panel errors to not block DB renewal; UI will fetch live usage later
            pass

        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            amount=float(plan.price_irr or 0),
            type="purchase",
            status="approved",
            description=f"Service renewal",
            payment_gateway="wallet",
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
            "config_link": service.subscription_url,
            "qr_code": None,
            "uuid": service.uuid,
            "remark": service.remark,
            "expires_at": service.expires_at.isoformat() if service.expires_at else None,
            "traffic_gb": float(service.traffic_limit_gb or 0),
            "used_traffic_gb": float(service.traffic_used_gb or 0)
        }