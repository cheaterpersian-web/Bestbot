from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.catalog import Plan, Server
from models.orders import PurchaseIntent
from models.service import Service
from models.user import TelegramUser
from models.referrals import ReferralEvent
from services.panels.base import CreateServiceRequest
from services.panels.factory import get_panel_client


async def create_service_after_payment(session: AsyncSession, user: TelegramUser, plan: Plan, server: Server, remark: str) -> Service:
    client = get_panel_client(server.panel_type)
    result = await client.create_service(
        CreateServiceRequest(
            remark=remark,
            duration_days=plan.duration_days,
            traffic_gb=plan.traffic_gb,
        )
    )

    expires_at: Optional[datetime] = None
    if plan.duration_days:
        expires_at = datetime.utcnow() + timedelta(days=int(plan.duration_days))

    service = Service(
        user_id=user.id,
        server_id=server.id,
        plan_id=plan.id,
        remark=remark,
        uuid=result.uuid,
        subscription_url=result.subscription_url,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(service)
    # award referral bonus if applicable
    if user.referred_by_user_id:
        try:
            percent = max(0, int(settings.referral_percent))
            fixed = max(0, int(settings.referral_fixed))
        except Exception:
            percent, fixed = 0, 0
        total_price = int(plan.price_irr or 0)
        bonus = (total_price * percent) // 100 + fixed
        if bonus > 0:
            # credit referrer wallet
            ref_user = (await session.execute(select(TelegramUser).where(TelegramUser.id == user.referred_by_user_id))).scalar_one_or_none()
            if ref_user:
                ref_user.wallet_balance = int(ref_user.wallet_balance or 0) + bonus
                session.add(ReferralEvent(referrer_user_id=ref_user.id, buyer_user_id=user.id, bonus_amount=bonus, description=f"bonus {percent}%+{fixed}"))
    return service

