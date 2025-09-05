import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc, extract
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import Transaction
from models.user import TelegramUser
from models.service import Service
from models.catalog import Plan, Category, Server
from models.advanced_reseller import AdvancedReseller, ResellerCommission


class FinancialReportService:
    """Service for generating advanced financial reports"""
    
    @staticmethod
    async def generate_daily_report(
        session: AsyncSession,
        date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate daily financial report"""
        
        if not date:
            date = datetime.utcnow().date()
        
        start_date = datetime.combine(date, datetime.min.time())
        end_date = start_date + timedelta(days=1)
        
        # Daily transactions
        daily_transactions = (await session.execute(
            select(Transaction)
            .where(
                and_(
                    Transaction.created_at >= start_date,
                    Transaction.created_at < end_date
                )
            )
        )).scalars().all()
        
        # Calculate metrics
        total_revenue = sum(t.amount for t in daily_transactions if t.status == "approved")
        total_transactions = len(daily_transactions)
        approved_transactions = len([t for t in daily_transactions if t.status == "approved"])
        pending_transactions = len([t for t in daily_transactions if t.status == "pending"])
        rejected_transactions = len([t for t in daily_transactions if t.status == "rejected"])
        
        # Payment methods breakdown
        payment_methods = {}
        for transaction in daily_transactions:
            method = transaction.payment_method or "unknown"
            if method not in payment_methods:
                payment_methods[method] = {"count": 0, "amount": 0}
            payment_methods[method]["count"] += 1
            if transaction.status == "approved":
                payment_methods[method]["amount"] += transaction.amount
        
        # New users
        new_users = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(
                and_(
                    TelegramUser.created_at >= start_date,
                    TelegramUser.created_at < end_date
                )
            )
        )).scalar()
        
        # New services
        new_services = (await session.execute(
            select(func.count(Service.id))
            .where(
                and_(
                    Service.purchased_at >= start_date,
                    Service.purchased_at < end_date
                )
            )
        )).scalar()
        
        return {
            "date": date.isoformat(),
            "revenue": {
                "total": total_revenue,
                "transactions": {
                    "total": total_transactions,
                    "approved": approved_transactions,
                    "pending": pending_transactions,
                    "rejected": rejected_transactions
                },
                "approval_rate": (approved_transactions / total_transactions * 100) if total_transactions > 0 else 0
            },
            "payment_methods": payment_methods,
            "growth": {
                "new_users": new_users,
                "new_services": new_services
            }
        }
    
    @staticmethod
    async def generate_weekly_report(
        session: AsyncSession,
        week_start: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate weekly financial report"""
        
        if not week_start:
            # Get start of current week (Monday)
            today = datetime.utcnow().date()
            week_start = today - timedelta(days=today.weekday())
        
        week_start = datetime.combine(week_start, datetime.min.time())
        week_end = week_start + timedelta(days=7)
        
        # Weekly transactions
        weekly_transactions = (await session.execute(
            select(Transaction)
            .where(
                and_(
                    Transaction.created_at >= week_start,
                    Transaction.created_at < week_end
                )
            )
        )).scalars().all()
        
        # Daily breakdown
        daily_breakdown = {}
        for i in range(7):
            day_start = week_start + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            day_transactions = [t for t in weekly_transactions if day_start <= t.created_at < day_end]
            day_revenue = sum(t.amount for t in day_transactions if t.status == "approved")
            
            daily_breakdown[day_start.strftime('%Y-%m-%d')] = {
                "revenue": day_revenue,
                "transactions": len(day_transactions)
            }
        
        # Top performing plans
        plan_performance = (await session.execute(
            select(Plan.id, Plan.title, func.count(Service.id), func.sum(Transaction.amount))
            .join(Service, Plan.id == Service.plan_id)
            .join(Transaction, Service.id == Transaction.service_id)
            .where(
                and_(
                    Transaction.created_at >= week_start,
                    Transaction.created_at < week_end,
                    Transaction.status == "approved"
                )
            )
            .group_by(Plan.id, Plan.title)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(10)
        )).all()
        
        # Top performing servers
        server_performance = (await session.execute(
            select(Server.id, Server.name, func.count(Service.id), func.sum(Transaction.amount))
            .join(Service, Server.id == Service.server_id)
            .join(Transaction, Service.id == Transaction.service_id)
            .where(
                and_(
                    Transaction.created_at >= week_start,
                    Transaction.created_at < week_end,
                    Transaction.status == "approved"
                )
            )
            .group_by(Server.id, Server.name)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(10)
        )).all()
        
        return {
            "week_start": week_start.date().isoformat(),
            "week_end": (week_end - timedelta(days=1)).date().isoformat(),
            "daily_breakdown": daily_breakdown,
            "plan_performance": [
                {
                    "plan_id": plan_id,
                    "title": title,
                    "sales_count": sales_count,
                    "revenue": revenue
                }
                for plan_id, title, sales_count, revenue in plan_performance
            ],
            "server_performance": [
                {
                    "server_id": server_id,
                    "name": name,
                    "sales_count": sales_count,
                    "revenue": revenue
                }
                for server_id, name, sales_count, revenue in server_performance
            ]
        }
    
    @staticmethod
    async def generate_monthly_report(
        session: AsyncSession,
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """Generate monthly financial report"""
        
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Monthly transactions
        monthly_transactions = (await session.execute(
            select(Transaction)
            .where(
                and_(
                    Transaction.created_at >= start_date,
                    Transaction.created_at < end_date
                )
            )
        )).scalars().all()
        
        # Revenue by category
        category_revenue = (await session.execute(
            select(Category.id, Category.title, func.sum(Transaction.amount))
            .join(Plan, Category.id == Plan.category_id)
            .join(Service, Plan.id == Service.plan_id)
            .join(Transaction, Service.id == Transaction.service_id)
            .where(
                and_(
                    Transaction.created_at >= start_date,
                    Transaction.created_at < end_date,
                    Transaction.status == "approved"
                )
            )
            .group_by(Category.id, Category.title)
            .order_by(func.sum(Transaction.amount).desc())
        )).all()
        
        # Customer analysis
        customer_analysis = (await session.execute(
            select(
                func.count(func.distinct(Transaction.user_id)),
                func.avg(Transaction.amount),
                func.max(Transaction.amount),
                func.min(Transaction.amount)
            )
            .where(
                and_(
                    Transaction.created_at >= start_date,
                    Transaction.created_at < end_date,
                    Transaction.status == "approved"
                )
            )
        )).first()
        
        # Reseller performance
        reseller_performance = (await session.execute(
            select(
                AdvancedReseller.id,
                TelegramUser.username,
                func.count(ResellerCommission.id),
                func.sum(ResellerCommission.commission_amount)
            )
            .join(TelegramUser, AdvancedReseller.user_id == TelegramUser.id)
            .join(ResellerCommission, AdvancedReseller.id == ResellerCommission.reseller_id)
            .where(
                and_(
                    ResellerCommission.created_at >= start_date,
                    ResellerCommission.created_at < end_date
                )
            )
            .group_by(AdvancedReseller.id, TelegramUser.username)
            .order_by(func.sum(ResellerCommission.commission_amount).desc())
            .limit(10)
        )).all()
        
        # Growth metrics
        previous_month_start = start_date - timedelta(days=start_date.day)
        previous_month_end = start_date
        
        current_month_revenue = sum(t.amount for t in monthly_transactions if t.status == "approved")
        previous_month_revenue = (await session.execute(
            select(func.sum(Transaction.amount))
            .where(
                and_(
                    Transaction.created_at >= previous_month_start,
                    Transaction.created_at < previous_month_end,
                    Transaction.status == "approved"
                )
            )
        )).scalar() or 0
        
        revenue_growth = 0
        if previous_month_revenue > 0:
            revenue_growth = ((current_month_revenue - previous_month_revenue) / previous_month_revenue) * 100
        
        return {
            "year": year,
            "month": month,
            "revenue": {
                "total": current_month_revenue,
                "growth_percent": revenue_growth,
                "previous_month": previous_month_revenue
            },
            "category_revenue": [
                {
                    "category_id": cat_id,
                    "title": title,
                    "revenue": revenue
                }
                for cat_id, title, revenue in category_revenue
            ],
            "customer_analysis": {
                "total_customers": customer_analysis[0] or 0,
                "avg_transaction": customer_analysis[1] or 0,
                "max_transaction": customer_analysis[2] or 0,
                "min_transaction": customer_analysis[3] or 0
            },
            "reseller_performance": [
                {
                    "reseller_id": reseller_id,
                    "username": username,
                    "commission_count": commission_count,
                    "total_commission": total_commission
                }
                for reseller_id, username, commission_count, total_commission in reseller_performance
            ]
        }
    
    @staticmethod
    async def generate_custom_report(
        session: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate custom financial report with filters"""
        
        if not filters:
            filters = {}
        
        # Build base query
        query = select(Transaction).where(
            and_(
                Transaction.created_at >= start_date,
                Transaction.created_at <= end_date
            )
        )
        
        # Apply filters
        if filters.get("status"):
            query = query.where(Transaction.status.in_(filters["status"]))
        
        if filters.get("payment_method"):
            query = query.where(Transaction.payment_method.in_(filters["payment_method"]))
        
        if filters.get("min_amount"):
            query = query.where(Transaction.amount >= filters["min_amount"])
        
        if filters.get("max_amount"):
            query = query.where(Transaction.amount <= filters["max_amount"])
        
        # Execute query
        transactions = (await session.execute(query)).scalars().all()
        
        # Calculate metrics
        total_revenue = sum(t.amount for t in transactions if t.status == "approved")
        total_transactions = len(transactions)
        
        # Revenue by day
        daily_revenue = {}
        for transaction in transactions:
            if transaction.status == "approved":
                date_str = transaction.created_at.date().isoformat()
                if date_str not in daily_revenue:
                    daily_revenue[date_str] = 0
                daily_revenue[date_str] += transaction.amount
        
        # Top customers
        customer_revenue = {}
        for transaction in transactions:
            if transaction.status == "approved":
                if transaction.user_id not in customer_revenue:
                    customer_revenue[transaction.user_id] = 0
                customer_revenue[transaction.user_id] += transaction.amount
        
        top_customers = sorted(customer_revenue.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Get customer details
        top_customer_details = []
        for user_id, revenue in top_customers:
            user = (await session.execute(
                select(TelegramUser).where(TelegramUser.id == user_id)
            )).scalar_one_or_none()
            
            if user:
                top_customer_details.append({
                    "user_id": user_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "revenue": revenue
                })
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "filters": filters,
            "summary": {
                "total_revenue": total_revenue,
                "total_transactions": total_transactions,
                "avg_transaction": total_revenue / total_transactions if total_transactions > 0 else 0
            },
            "daily_revenue": daily_revenue,
            "top_customers": top_customer_details
        }
    
    @staticmethod
    async def generate_profit_loss_report(
        session: AsyncSession,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate profit and loss report"""
        
        # Revenue
        total_revenue = (await session.execute(
            select(func.sum(Transaction.amount))
            .where(
                and_(
                    Transaction.created_at >= start_date,
                    Transaction.created_at <= end_date,
                    Transaction.status == "approved"
                )
            )
        )).scalar() or 0
        
        # Reseller commissions (expense)
        total_commissions = (await session.execute(
            select(func.sum(ResellerCommission.commission_amount))
            .where(
                and_(
                    ResellerCommission.created_at >= start_date,
                    ResellerCommission.created_at <= end_date
                )
            )
        )).scalar() or 0
        
        # Refunds (expense)
        total_refunds = (await session.execute(
            select(func.sum(Transaction.amount))
            .where(
                and_(
                    Transaction.created_at >= start_date,
                    Transaction.created_at <= end_date,
                    Transaction.status == "refunded"
                )
            )
        )).scalar() or 0
        
        # Calculate profit
        gross_profit = total_revenue - total_commissions - total_refunds
        profit_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "revenue": {
                "total": total_revenue,
                "transactions": total_revenue
            },
            "expenses": {
                "commissions": total_commissions,
                "refunds": total_refunds,
                "total": total_commissions + total_refunds
            },
            "profit": {
                "gross_profit": gross_profit,
                "profit_margin": profit_margin
            }
        }
    
    @staticmethod
    async def generate_trend_analysis(
        session: AsyncSession,
        days: int = 30
    ) -> Dict[str, Any]:
        """Generate trend analysis for specified days"""
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Daily revenue trend
        daily_revenue = (await session.execute(
            select(
                func.date(Transaction.created_at).label('date'),
                func.sum(Transaction.amount).label('revenue'),
                func.count(Transaction.id).label('transactions')
            )
            .where(
                and_(
                    Transaction.created_at >= start_date,
                    Transaction.created_at <= end_date,
                    Transaction.status == "approved"
                )
            )
            .group_by(func.date(Transaction.created_at))
            .order_by(func.date(Transaction.created_at))
        )).all()
        
        # Calculate growth rates
        revenue_trend = []
        for i, (date, revenue, transactions) in enumerate(daily_revenue):
            growth_rate = 0
            if i > 0:
                prev_revenue = daily_revenue[i-1][1] or 0
                if prev_revenue > 0:
                    growth_rate = ((revenue - prev_revenue) / prev_revenue) * 100
            
            revenue_trend.append({
                "date": date.isoformat(),
                "revenue": revenue or 0,
                "transactions": transactions or 0,
                "growth_rate": growth_rate
            })
        
        # Weekly averages
        weekly_avg_revenue = sum(r["revenue"] for r in revenue_trend) / len(revenue_trend) if revenue_trend else 0
        weekly_avg_transactions = sum(r["transactions"] for r in revenue_trend) / len(revenue_trend) if revenue_trend else 0
        
        return {
            "period_days": days,
            "daily_trend": revenue_trend,
            "averages": {
                "daily_revenue": weekly_avg_revenue,
                "daily_transactions": weekly_avg_transactions
            }
        }