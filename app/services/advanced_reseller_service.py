import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.advanced_reseller import (
    AdvancedReseller, SubReseller, ResellerCommission, ResellerTarget,
    ResellerActivity, ResellerPayment, ResellerLevelRule,
    ResellerLevel, ResellerStatus, CommissionType
)
from models.user import TelegramUser
from models.billing import Transaction
from models.service import Service


class AdvancedResellerService:
    """Service for managing advanced reseller system"""
    
    @staticmethod
    async def create_reseller(
        session: AsyncSession,
        user_id: int,
        business_name: Optional[str] = None,
        business_type: str = "individual",
        parent_reseller_id: Optional[int] = None
    ) -> AdvancedReseller:
        """Create a new reseller"""
        
        # Check if user is already a reseller
        existing = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.user_id == user_id)
        )).scalar_one_or_none()
        
        if existing:
            raise ValueError("User is already a reseller")
        
        # Get parent reseller if specified
        parent_reseller = None
        if parent_reseller_id:
            parent_reseller = (await session.execute(
                select(AdvancedReseller).where(AdvancedReseller.id == parent_reseller_id)
            )).scalar_one_or_none()
            
            if not parent_reseller:
                raise ValueError("Parent reseller not found")
            
            if parent_reseller.status != ResellerStatus.ACTIVE:
                raise ValueError("Parent reseller is not active")
            
            # Check if parent can create sub-resellers
            if not parent_reseller.can_create_sub_resellers:
                raise ValueError("Parent reseller cannot create sub-resellers")
            
            if parent_reseller.total_sub_resellers >= parent_reseller.max_sub_resellers:
                raise ValueError("Parent reseller has reached sub-reseller limit")
        
        # Create reseller
        reseller = AdvancedReseller(
            user_id=user_id,
            business_name=business_name,
            business_type=business_type,
            parent_reseller_id=parent_reseller_id,
            level=ResellerLevel.BRONZE,
            status=ResellerStatus.PENDING
        )
        
        # Set initial commission based on level rules
        level_rule = await AdvancedResellerService._get_level_rule(session, ResellerLevel.BRONZE)
        if level_rule:
            reseller.commission_rate = level_rule.commission_rate
            reseller.max_sub_resellers = level_rule.max_sub_resellers
            reseller.can_set_commission = level_rule.can_set_commission
            reseller.can_manage_customers = level_rule.can_manage_customers
        
        session.add(reseller)
        await session.flush()
        
        # Create sub-reseller relationship if parent exists
        if parent_reseller:
            sub_reseller = SubReseller(
                parent_reseller_id=parent_reseller_id,
                sub_reseller_id=reseller.id
            )
            session.add(sub_reseller)
            
            # Update parent's sub-reseller count
            parent_reseller.total_sub_resellers += 1
        
        # Log activity
        await AdvancedResellerService._log_activity(
            session, reseller.id, "reseller_created", "Reseller account created"
        )
        
        return reseller
    
    @staticmethod
    async def approve_reseller(
        session: AsyncSession,
        reseller_id: int,
        approved_by: int,
        admin_notes: Optional[str] = None
    ) -> AdvancedReseller:
        """Approve a reseller"""
        
        reseller = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.id == reseller_id)
        )).scalar_one_or_none()
        
        if not reseller:
            raise ValueError("Reseller not found")
        
        if reseller.status != ResellerStatus.PENDING:
            raise ValueError("Reseller is not pending approval")
        
        reseller.status = ResellerStatus.ACTIVE
        reseller.approved_at = datetime.utcnow()
        reseller.admin_notes = admin_notes
        
        # Log activity
        await AdvancedResellerService._log_activity(
            session, reseller.id, "reseller_approved", "Reseller approved by admin"
        )
        
        return reseller
    
    @staticmethod
    async def calculate_commission(
        session: AsyncSession,
        transaction: Transaction,
        service: Optional[Service] = None
    ) -> List[ResellerCommission]:
        """Calculate commissions for reseller hierarchy"""
        
        # Find the reseller who referred this customer
        customer = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == transaction.user_id)
        )).scalar_one()
        
        if not customer.referred_by_user_id:
            return []  # No referral, no commission
        
        # Find the referring reseller
        referring_reseller = (await session.execute(
            select(AdvancedReseller)
            .where(AdvancedReseller.user_id == customer.referred_by_user_id)
        )).scalar_one_or_none()
        
        if not referring_reseller or referring_reseller.status != ResellerStatus.ACTIVE:
            return []  # Not an active reseller
        
        commissions = []
        current_reseller = referring_reseller
        level = 1
        
        # Calculate commissions up the hierarchy (max 3 levels)
        while current_reseller and level <= 3:
            commission_amount = await AdvancedResellerService._calculate_commission_amount(
                session, current_reseller, transaction.amount, level
            )
            
            if commission_amount > 0:
                commission = ResellerCommission(
                    reseller_id=current_reseller.id,
                    transaction_id=transaction.id,
                    commission_type=current_reseller.commission_type,
                    commission_rate=current_reseller.commission_rate,
                    base_amount=transaction.amount,
                    commission_amount=commission_amount,
                    level=level,
                    parent_reseller_id=current_reseller.parent_reseller_id,
                    customer_id=transaction.user_id,
                    service_id=service.id if service else None
                )
                session.add(commission)
                commissions.append(commission)
                
                # Update reseller stats
                current_reseller.total_sales += transaction.amount
                current_reseller.total_commission_earned += commission_amount
                current_reseller.pending_commission += commission_amount
                current_reseller.monthly_sales += transaction.amount
                current_reseller.monthly_commission += commission_amount
                current_reseller.last_activity_at = datetime.utcnow()
                
                # Log activity
                await AdvancedResellerService._log_activity(
                    session, current_reseller.id, "commission_earned",
                    f"Commission earned: {commission_amount:,.0f} IRR",
                    amount=commission_amount,
                    transaction_id=transaction.id
                )
            
            # Move to parent reseller
            if current_reseller.parent_reseller_id:
                current_reseller = (await session.execute(
                    select(AdvancedReseller).where(
                        AdvancedReseller.id == current_reseller.parent_reseller_id
                    )
                )).scalar_one_or_none()
            else:
                current_reseller = None
            
            level += 1
        
        return commissions
    
    @staticmethod
    async def _calculate_commission_amount(
        session: AsyncSession,
        reseller: AdvancedReseller,
        transaction_amount: float,
        level: int
    ) -> float:
        """Calculate commission amount for a reseller"""
        
        if reseller.commission_type == CommissionType.PERCENTAGE:
            # Apply level-based commission reduction
            level_multiplier = 1.0 if level == 1 else (0.5 if level == 2 else 0.25)
            return transaction_amount * (reseller.commission_rate / 100) * level_multiplier
        
        elif reseller.commission_type == CommissionType.FIXED:
            return reseller.fixed_commission
        
        elif reseller.commission_type == CommissionType.TIERED:
            # Calculate based on tiered rates
            if reseller.tiered_rates:
                try:
                    rates = json.loads(reseller.tiered_rates)
                    for tier in rates:
                        if transaction_amount >= tier['min_amount']:
                            return transaction_amount * (tier['rate'] / 100)
                except (json.JSONDecodeError, KeyError):
                    pass
            
            # Fallback to percentage
            return transaction_amount * (reseller.commission_rate / 100)
        
        return 0
    
    @staticmethod
    async def check_level_progression(session: AsyncSession, reseller_id: int) -> bool:
        """Check if reseller should be promoted to next level"""
        
        reseller = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.id == reseller_id)
        )).scalar_one_or_none()
        
        if not reseller or reseller.status != ResellerStatus.ACTIVE:
            return False
        
        # Get current level rule
        current_rule = await AdvancedResellerService._get_level_rule(session, reseller.level)
        if not current_rule:
            return False
        
        # Check if reseller meets requirements for next level
        next_level = await AdvancedResellerService._get_next_level(reseller.level)
        if not next_level:
            return False  # Already at highest level
        
        next_rule = await AdvancedResellerService._get_level_rule(session, next_level)
        if not next_rule:
            return False
        
        # Check requirements
        months_active = 0
        if reseller.approved_at:
            months_active = (datetime.utcnow() - reseller.approved_at).days // 30
        
        if (reseller.total_sales >= next_rule.min_sales and
            reseller.total_customers >= next_rule.min_customers and
            reseller.total_sub_resellers >= next_rule.min_sub_resellers and
            months_active >= next_rule.min_months_active):
            
            # Promote reseller
            old_level = reseller.level
            reseller.level = next_level
            reseller.commission_rate = next_rule.commission_rate
            reseller.max_sub_resellers = next_rule.max_sub_resellers
            reseller.can_set_commission = next_rule.can_set_commission
            reseller.can_manage_customers = next_rule.can_manage_customers
            reseller.level_updated_at = datetime.utcnow()
            
            # Log activity
            await AdvancedResellerService._log_activity(
                session, reseller.id, "level_promoted",
                f"Promoted from {old_level.value} to {next_level.value}"
            )
            
            return True
        
        return False
    
    @staticmethod
    async def _get_level_rule(session: AsyncSession, level: ResellerLevel) -> Optional[ResellerLevelRule]:
        """Get level rule for a specific level"""
        
        return (await session.execute(
            select(ResellerLevelRule)
            .where(
                and_(
                    ResellerLevelRule.level == level,
                    ResellerLevelRule.is_active == True
                )
            )
        )).scalar_one_or_none()
    
    @staticmethod
    async def _get_next_level(current_level: ResellerLevel) -> Optional[ResellerLevel]:
        """Get next level in hierarchy"""
        
        level_order = [
            ResellerLevel.BRONZE,
            ResellerLevel.SILVER,
            ResellerLevel.GOLD,
            ResellerLevel.PLATINUM,
            ResellerLevel.DIAMOND
        ]
        
        try:
            current_index = level_order.index(current_level)
            if current_index < len(level_order) - 1:
                return level_order[current_index + 1]
        except ValueError:
            pass
        
        return None
    
    @staticmethod
    async def create_monthly_target(
        session: AsyncSession,
        reseller_id: int,
        year: int,
        month: int,
        sales_target: float,
        customer_target: int,
        sub_reseller_target: int = 0
    ) -> ResellerTarget:
        """Create monthly target for reseller"""
        
        # Check if target already exists
        existing = (await session.execute(
            select(ResellerTarget)
            .where(
                and_(
                    ResellerTarget.reseller_id == reseller_id,
                    ResellerTarget.target_year == year,
                    ResellerTarget.target_month == month
                )
            )
        )).scalar_one_or_none()
        
        if existing:
            raise ValueError("Target already exists for this period")
        
        target = ResellerTarget(
            reseller_id=reseller_id,
            target_year=year,
            target_month=month,
            sales_target=sales_target,
            customer_target=customer_target,
            sub_reseller_target=sub_reseller_target
        )
        session.add(target)
        
        # Log activity
        await AdvancedResellerService._log_activity(
            session, reseller_id, "target_created",
            f"Monthly target created: {sales_target:,.0f} IRR sales, {customer_target} customers"
        )
        
        return target
    
    @staticmethod
    async def update_target_achievement(session: AsyncSession, reseller_id: int):
        """Update target achievement for reseller"""
        
        current_date = datetime.utcnow()
        current_month = current_date.month
        current_year = current_date.year
        
        # Get current month target
        target = (await session.execute(
            select(ResellerTarget)
            .where(
                and_(
                    ResellerTarget.reseller_id == reseller_id,
                    ResellerTarget.target_year == current_year,
                    ResellerTarget.target_month == current_month
                )
            )
        )).scalar_one_or_none()
        
        if not target:
            return
        
        # Get reseller
        reseller = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.id == reseller_id)
        )).scalar_one()
        
        # Update achievements
        target.sales_achieved = reseller.monthly_sales
        target.customers_achieved = reseller.total_customers
        target.sub_resellers_achieved = reseller.total_sub_resellers
        
        # Check if target is achieved
        if (target.sales_achieved >= target.sales_target and
            target.customers_achieved >= target.customer_target and
            target.sub_resellers_achieved >= target.sub_reseller_target):
            
            if not target.is_achieved:
                target.is_achieved = True
                target.updated_at = datetime.utcnow()
                
                # Calculate bonus
                level_rule = await AdvancedResellerService._get_level_rule(session, reseller.level)
                if level_rule and level_rule.monthly_bonus_rate > 0:
                    target.bonus_amount = target.sales_achieved * (level_rule.monthly_bonus_rate / 100)
                
                # Log activity
                await AdvancedResellerService._log_activity(
                    session, reseller_id, "target_achieved",
                    f"Monthly target achieved! Bonus: {target.bonus_amount:,.0f} IRR"
                )
    
    @staticmethod
    async def process_commission_payment(
        session: AsyncSession,
        reseller_id: int,
        payment_method: str,
        processed_by: int,
        notes: Optional[str] = None
    ) -> ResellerPayment:
        """Process commission payment for reseller"""
        
        reseller = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.id == reseller_id)
        )).scalar_one_or_none()
        
        if not reseller:
            raise ValueError("Reseller not found")
        
        if reseller.pending_commission <= 0:
            raise ValueError("No pending commission to pay")
        
        # Get pending commissions
        pending_commissions = (await session.execute(
            select(ResellerCommission)
            .where(
                and_(
                    ResellerCommission.reseller_id == reseller_id,
                    ResellerCommission.status == "pending"
                )
            )
        )).scalars().all()
        
        if not pending_commissions:
            raise ValueError("No pending commissions found")
        
        # Create payment record
        payment = ResellerPayment(
            reseller_id=reseller_id,
            amount=reseller.pending_commission,
            payment_method=payment_method,
            commission_ids=[c.id for c in pending_commissions],
            period_start=min(c.created_at for c in pending_commissions),
            period_end=max(c.created_at for c in pending_commissions),
            processed_by=processed_by,
            notes=notes
        )
        session.add(payment)
        
        # Update commission status
        for commission in pending_commissions:
            commission.status = "paid"
            commission.paid_at = datetime.utcnow()
        
        # Update reseller
        reseller.total_paid += reseller.pending_commission
        reseller.pending_commission = 0
        
        # Log activity
        await AdvancedResellerService._log_activity(
            session, reseller_id, "payment_processed",
            f"Commission payment processed: {payment.amount:,.0f} IRR",
            amount=payment.amount
        )
        
        return payment
    
    @staticmethod
    async def get_reseller_hierarchy(session: AsyncSession, reseller_id: int) -> Dict[str, Any]:
        """Get reseller hierarchy tree"""
        
        reseller = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.id == reseller_id)
        )).scalar_one_or_none()
        
        if not reseller:
            return {}
        
        # Get sub-resellers
        sub_resellers = (await session.execute(
            select(AdvancedReseller, TelegramUser)
            .join(TelegramUser, AdvancedReseller.user_id == TelegramUser.id)
            .where(AdvancedReseller.parent_reseller_id == reseller_id)
        )).all()
        
        hierarchy = {
            "reseller": reseller,
            "sub_resellers": []
        }
        
        for sub_reseller, user in sub_resellers:
            sub_hierarchy = await AdvancedResellerService.get_reseller_hierarchy(
                session, sub_reseller.id
            )
            hierarchy["sub_resellers"].append({
                "reseller": sub_reseller,
                "user": user,
                "sub_resellers": sub_hierarchy.get("sub_resellers", [])
            })
        
        return hierarchy
    
    @staticmethod
    async def get_reseller_analytics(session: AsyncSession, reseller_id: int) -> Dict[str, Any]:
        """Get comprehensive reseller analytics"""
        
        reseller = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.id == reseller_id)
        )).scalar_one_or_none()
        
        if not reseller:
            return {}
        
        # Get recent activities
        recent_activities = (await session.execute(
            select(ResellerActivity)
            .where(ResellerActivity.reseller_id == reseller_id)
            .order_by(desc(ResellerActivity.created_at))
            .limit(10)
        )).scalars().all()
        
        # Get monthly performance
        current_month = datetime.utcnow().month
        current_year = datetime.utcnow().year
        
        monthly_commissions = (await session.execute(
            select(func.sum(ResellerCommission.commission_amount))
            .where(
                and_(
                    ResellerCommission.reseller_id == reseller_id,
                    func.extract('year', ResellerCommission.created_at) == current_year,
                    func.extract('month', ResellerCommission.created_at) == current_month
                )
            )
        )).scalar() or 0
        
        # Get pending commissions
        pending_commissions = (await session.execute(
            select(func.sum(ResellerCommission.commission_amount))
            .where(
                and_(
                    ResellerCommission.reseller_id == reseller_id,
                    ResellerCommission.status == "pending"
                )
            )
        )).scalar() or 0
        
        # Get current target
        current_target = (await session.execute(
            select(ResellerTarget)
            .where(
                and_(
                    ResellerTarget.reseller_id == reseller_id,
                    ResellerTarget.target_year == current_year,
                    ResellerTarget.target_month == current_month
                )
            )
        )).scalar_one_or_none()
        
        return {
            "reseller": reseller,
            "recent_activities": recent_activities,
            "monthly_commissions": monthly_commissions,
            "pending_commissions": pending_commissions,
            "current_target": current_target,
            "hierarchy": await AdvancedResellerService.get_reseller_hierarchy(session, reseller_id)
        }
    
    @staticmethod
    async def _log_activity(
        session: AsyncSession,
        reseller_id: int,
        activity_type: str,
        description: str,
        amount: Optional[float] = None,
        transaction_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        service_id: Optional[int] = None
    ):
        """Log reseller activity"""
        
        activity = ResellerActivity(
            reseller_id=reseller_id,
            activity_type=activity_type,
            description=description,
            amount=amount,
            transaction_id=transaction_id,
            customer_id=customer_id,
            service_id=service_id
        )
        session.add(activity)