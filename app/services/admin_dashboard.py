from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import TelegramUser
from models.service import Service
from models.billing import Transaction
from models.catalog import Server, Category, Plan
from models.referrals import ReferralEvent
from models.support import Ticket
from models.analytics import DailyStats


class AdminDashboardService:
    """Service for generating admin dashboard statistics and reports"""
    
    @staticmethod
    async def get_dashboard_stats(session: AsyncSession) -> Dict:
        """Get comprehensive dashboard statistics"""
        now = datetime.utcnow()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # User statistics
        total_users = (await session.execute(
            select(func.count(TelegramUser.id))
        )).scalar() or 0
        
        new_users_today = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(func.date(TelegramUser.created_at) == today)
        )).scalar() or 0
        
        new_users_week = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.created_at >= week_ago)
        )).scalar() or 0
        
        new_users_month = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.created_at >= month_ago)
        )).scalar() or 0
        
        active_users_today = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.last_seen_at >= now - timedelta(days=1))
        )).scalar() or 0
        
        blocked_users = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.is_blocked == True)
        )).scalar() or 0
        
        # Service statistics
        total_services = (await session.execute(
            select(func.count(Service.id))
        )).scalar() or 0
        
        active_services = (await session.execute(
            select(func.count(Service.id))
            .where(Service.is_active == True)
        )).scalar() or 0
        
        new_services_today = (await session.execute(
            select(func.count(Service.id))
            .where(func.date(Service.purchased_at) == today)
        )).scalar() or 0
        
        # Revenue statistics
        total_revenue = (await session.execute(
            select(func.sum(Transaction.amount))
            .where(and_(
                Transaction.status == "approved",
                Transaction.type.in_(["purchase", "wallet_topup"])
            ))
        )).scalar() or 0
        
        revenue_today = (await session.execute(
            select(func.sum(Transaction.amount))
            .where(and_(
                Transaction.status == "approved",
                Transaction.type.in_(["purchase", "wallet_topup"]),
                func.date(Transaction.approved_at) == today
            ))
        )).scalar() or 0
        
        revenue_week = (await session.execute(
            select(func.sum(Transaction.amount))
            .where(and_(
                Transaction.status == "approved",
                Transaction.type.in_(["purchase", "wallet_topup"]),
                Transaction.approved_at >= week_ago
            ))
        )).scalar() or 0
        
        revenue_month = (await session.execute(
            select(func.sum(Transaction.amount))
            .where(and_(
                Transaction.status == "approved",
                Transaction.type.in_(["purchase", "wallet_topup"]),
                Transaction.approved_at >= month_ago
            ))
        )).scalar() or 0
        
        # Transaction statistics
        pending_transactions = (await session.execute(
            select(func.count(Transaction.id))
            .where(Transaction.status == "pending")
        )).scalar() or 0
        
        total_transactions = (await session.execute(
            select(func.count(Transaction.id))
        )).scalar() or 0
        
        # Referral statistics
        total_referrals = (await session.execute(
            select(func.count(ReferralEvent.id))
        )).scalar() or 0
        
        referral_bonus_paid = (await session.execute(
            select(func.sum(ReferralEvent.bonus_amount))
        )).scalar() or 0
        
        # Support statistics
        open_tickets = (await session.execute(
            select(func.count(Ticket.id))
            .where(Ticket.status == "open")
        )).scalar() or 0
        
        total_tickets = (await session.execute(
            select(func.count(Ticket.id))
        )).scalar() or 0
        
        # Server statistics
        total_servers = (await session.execute(
            select(func.count(Server.id))
        )).scalar() or 0
        
        active_servers = (await session.execute(
            select(func.count(Server.id))
            .where(Server.is_active == True)
        )).scalar() or 0
        
        # Category and Plan statistics
        total_categories = (await session.execute(
            select(func.count(Category.id))
        )).scalar() or 0
        
        active_categories = (await session.execute(
            select(func.count(Category.id))
            .where(Category.is_active == True)
        )).scalar() or 0
        
        total_plans = (await session.execute(
            select(func.count(Plan.id))
        )).scalar() or 0
        
        active_plans = (await session.execute(
            select(func.count(Plan.id))
            .where(Plan.is_active == True)
        )).scalar() or 0
        
        return {
            "users": {
                "total": total_users,
                "new_today": new_users_today,
                "new_week": new_users_week,
                "new_month": new_users_month,
                "active_today": active_users_today,
                "blocked": blocked_users
            },
            "services": {
                "total": total_services,
                "active": active_services,
                "new_today": new_services_today
            },
            "revenue": {
                "total": total_revenue,
                "today": revenue_today,
                "week": revenue_week,
                "month": revenue_month
            },
            "transactions": {
                "total": total_transactions,
                "pending": pending_transactions
            },
            "referrals": {
                "total": total_referrals,
                "bonus_paid": referral_bonus_paid
            },
            "support": {
                "open_tickets": open_tickets,
                "total_tickets": total_tickets
            },
            "infrastructure": {
                "servers": {"total": total_servers, "active": active_servers},
                "categories": {"total": total_categories, "active": active_categories},
                "plans": {"total": total_plans, "active": active_plans}
            }
        }
    
    @staticmethod
    async def get_recent_activities(session: AsyncSession, limit: int = 10) -> List[Dict]:
        """Get recent activities for dashboard"""
        activities = []
        
        # Recent users
        recent_users = (await session.execute(
            select(TelegramUser)
            .order_by(TelegramUser.created_at.desc())
            .limit(5)
        )).scalars().all()
        
        for user in recent_users:
            activities.append({
                "type": "new_user",
                "timestamp": user.created_at,
                "data": {
                    "user_id": user.telegram_user_id,
                    "username": user.username,
                    "first_name": user.first_name
                }
            })
        
        # Recent transactions
        recent_transactions = (await session.execute(
            select(Transaction)
            .order_by(Transaction.created_at.desc())
            .limit(5)
        )).scalars().all()
        
        for tx in recent_transactions:
            activities.append({
                "type": "transaction",
                "timestamp": tx.created_at,
                "data": {
                    "id": tx.id,
                    "amount": tx.amount,
                    "type": tx.type,
                    "status": tx.status
                }
            })
        
        # Recent services
        recent_services = (await session.execute(
            select(Service)
            .order_by(Service.purchased_at.desc())
            .limit(5)
        )).scalars().all()
        
        for service in recent_services:
            activities.append({
                "type": "new_service",
                "timestamp": service.purchased_at,
                "data": {
                    "id": service.id,
                    "uuid": service.uuid,
                    "remark": service.remark
                }
            })
        
        # Sort by timestamp and return limited results
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        return activities[:limit]
    
    @staticmethod
    async def get_user_stats(session: AsyncSession, user_id: int) -> Dict:
        """Get detailed statistics for a specific user"""
        user = await session.get(TelegramUser, user_id)
        if not user:
            return {}
        
        # User services
        user_services = (await session.execute(
            select(Service)
            .where(Service.user_id == user_id)
        )).scalars().all()
        
        active_services = len([s for s in user_services if s.is_active])
        total_spent = sum(s.plan.price_irr for s in user_services if hasattr(s, 'plan'))
        
        # User transactions
        user_transactions = (await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
        )).scalars().all()
        
        total_transactions = len(user_transactions)
        total_deposited = sum(tx.amount for tx in user_transactions if tx.type == "wallet_topup" and tx.status == "approved")
        
        # Referral stats
        referrals_made = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.referred_by_user_id == user_id)
        )).scalar() or 0
        
        referral_earnings = (await session.execute(
            select(func.sum(ReferralEvent.bonus_amount))
            .where(ReferralEvent.referrer_user_id == user_id)
        )).scalar() or 0
        
        return {
            "user": {
                "id": user.telegram_user_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "wallet_balance": user.wallet_balance,
                "is_blocked": user.is_blocked,
                "created_at": user.created_at,
                "last_seen_at": user.last_seen_at
            },
            "services": {
                "total": len(user_services),
                "active": active_services,
                "total_spent": total_spent
            },
            "transactions": {
                "total": total_transactions,
                "total_deposited": total_deposited
            },
            "referrals": {
                "made": referrals_made,
                "earnings": referral_earnings
            }
        }