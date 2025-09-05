import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.smart_discounts import (
    SmartDiscount, DiscountUsage, CashbackRule, CashbackTransaction, 
    UserDiscountProfile, DiscountType
)
from models.user import TelegramUser
from models.billing import Transaction
from models.service import Service
from models.catalog import Plan


class SmartDiscountService:
    """Service for managing smart discounts and cashback"""
    
    @staticmethod
    async def get_eligible_discounts(
        session: AsyncSession,
        user_id: int,
        purchase_amount: float,
        plan_id: Optional[int] = None,
        server_id: Optional[int] = None
    ) -> List[SmartDiscount]:
        """Get all eligible discounts for a user and purchase"""
        
        now = datetime.utcnow()
        
        # Get user profile
        user_profile = await SmartDiscountService._get_user_profile(session, user_id)
        
        # Base query for active discounts
        query = select(SmartDiscount).where(
            and_(
                SmartDiscount.is_active == True,
                or_(
                    SmartDiscount.valid_from.is_(None),
                    SmartDiscount.valid_from <= now
                ),
                or_(
                    SmartDiscount.valid_to.is_(None),
                    SmartDiscount.valid_to >= now
                )
            )
        ).order_by(SmartDiscount.priority.desc())
        
        discounts = (await session.execute(query)).scalars().all()
        
        eligible_discounts = []
        
        for discount in discounts:
            if await SmartDiscountService._is_discount_eligible(
                session, discount, user_profile, purchase_amount, plan_id, server_id
            ):
                eligible_discounts.append(discount)
        
        return eligible_discounts
    
    @staticmethod
    async def _is_discount_eligible(
        session: AsyncSession,
        discount: SmartDiscount,
        user_profile: UserDiscountProfile,
        purchase_amount: float,
        plan_id: Optional[int] = None,
        server_id: Optional[int] = None
    ) -> bool:
        """Check if a discount is eligible for the given context"""
        
        # Check daily and total limits
        if discount.daily_limit and discount.daily_used_count >= discount.daily_limit:
            return False
        
        if discount.total_limit and discount.used_count >= discount.total_limit:
            return False
        
        # Check minimum purchase amount
        if discount.min_purchase_amount and purchase_amount < discount.min_purchase_amount:
            return False
        
        # Check discount type specific conditions
        if discount.discount_type == DiscountType.FIRST_PURCHASE:
            if not user_profile.is_first_time_buyer:
                return False
        
        elif discount.discount_type == DiscountType.HOURLY:
            # Check if it's within the specified hour range
            current_hour = datetime.utcnow().hour
            try:
                conditions = json.loads(discount.trigger_conditions)
                if 'hours' in conditions:
                    if current_hour not in conditions['hours']:
                        return False
            except (json.JSONDecodeError, KeyError):
                pass
        
        elif discount.discount_type == DiscountType.LOYALTY:
            # Check loyalty level
            try:
                conditions = json.loads(discount.trigger_conditions)
                if 'min_loyalty_level' in conditions:
                    if user_profile.loyalty_level < conditions['min_loyalty_level']:
                        return False
            except (json.JSONDecodeError, KeyError):
                pass
        
        elif discount.discount_type == DiscountType.BIRTHDAY:
            # Check if it's user's birthday month
            if not user_profile.birthday_month:
                return False
            current_month = datetime.utcnow().month
            if user_profile.birthday_month != current_month:
                return False
        
        # Check target criteria
        if discount.target_user_groups:
            try:
                target_groups = json.loads(discount.target_user_groups)
                if not await SmartDiscountService._user_matches_criteria(
                    session, user_profile, target_groups
                ):
                    return False
            except (json.JSONDecodeError, KeyError):
                pass
        
        if discount.target_plans and plan_id:
            try:
                target_plans = json.loads(discount.target_plans)
                if plan_id not in target_plans:
                    return False
            except (json.JSONDecodeError, KeyError):
                pass
        
        if discount.target_servers and server_id:
            try:
                target_servers = json.loads(discount.target_servers)
                if server_id not in target_servers:
                    return False
            except (json.JSONDecodeError, KeyError):
                pass
        
        return True
    
    @staticmethod
    async def apply_discount(
        session: AsyncSession,
        user_id: int,
        discount: SmartDiscount,
        original_amount: float,
        transaction_id: Optional[int] = None
    ) -> Tuple[float, float]:
        """Apply a discount and return (discount_amount, final_amount)"""
        
        discount_amount = 0
        
        # Calculate discount amount
        if discount.percent_off > 0:
            discount_amount = original_amount * (discount.percent_off / 100)
        elif discount.fixed_off > 0:
            discount_amount = discount.fixed_off
        
        # Apply maximum discount limit
        if discount.max_discount_amount and discount_amount > discount.max_discount_amount:
            discount_amount = discount.max_discount_amount
        
        # Ensure discount doesn't exceed original amount
        discount_amount = min(discount_amount, original_amount)
        
        final_amount = original_amount - discount_amount
        
        # Record usage
        usage = DiscountUsage(
            user_id=user_id,
            smart_discount_id=discount.id,
            transaction_id=transaction_id,
            original_amount=original_amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            context_data=json.dumps({
                "discount_type": discount.discount_type,
                "applied_at": datetime.utcnow().isoformat()
            })
        )
        session.add(usage)
        
        # Update discount usage counters
        discount.used_count += 1
        discount.daily_used_count += 1
        
        # Update user profile
        await SmartDiscountService._update_user_profile(session, user_id, discount_amount)
        
        return discount_amount, final_amount
    
    @staticmethod
    async def process_cashback(
        session: AsyncSession,
        user_id: int,
        transaction: Transaction,
        plan_id: Optional[int] = None,
        server_id: Optional[int] = None
    ) -> Optional[CashbackTransaction]:
        """Process cashback for a transaction"""
        
        # Get applicable cashback rules
        cashback_rules = await SmartDiscountService._get_applicable_cashback_rules(
            session, user_id, transaction.amount, plan_id, server_id
        )
        
        if not cashback_rules:
            return None
        
        # Use the highest priority rule
        best_rule = max(cashback_rules, key=lambda r: r.priority if hasattr(r, 'priority') else 0)
        
        # Calculate cashback amount
        cashback_amount = 0
        
        if best_rule.percent_cashback > 0:
            cashback_amount = transaction.amount * (best_rule.percent_cashback / 100)
        elif best_rule.fixed_cashback > 0:
            cashback_amount = best_rule.fixed_cashback
        
        # Apply maximum cashback limit
        if best_rule.max_cashback_amount and cashback_amount > best_rule.max_cashback_amount:
            cashback_amount = best_rule.max_cashback_amount
        
        # Create cashback transaction
        cashback_tx = CashbackTransaction(
            user_id=user_id,
            cashback_rule_id=best_rule.id,
            original_transaction_id=transaction.id,
            original_amount=transaction.amount,
            cashback_amount=cashback_amount,
            status="pending"
        )
        session.add(cashback_tx)
        
        # Update rule usage
        best_rule.used_count += 1
        
        return cashback_tx
    
    @staticmethod
    async def _get_user_profile(session: AsyncSession, user_id: int) -> UserDiscountProfile:
        """Get or create user discount profile"""
        
        profile = (await session.execute(
            select(UserDiscountProfile).where(UserDiscountProfile.user_id == user_id)
        )).scalar_one_or_none()
        
        if not profile:
            # Create new profile
            profile = UserDiscountProfile(user_id=user_id)
            session.add(profile)
            await session.flush()
        
        return profile
    
    @staticmethod
    async def _update_user_profile(
        session: AsyncSession, 
        user_id: int, 
        discount_amount: float
    ):
        """Update user profile with discount usage"""
        
        profile = await SmartDiscountService._get_user_profile(session, user_id)
        
        profile.total_discounts_used += 1
        profile.total_discount_savings += discount_amount
        profile.last_updated = datetime.utcnow()
        
        # Update loyalty level based on total spent
        if profile.total_spent >= 1000000:  # 1M IRR
            profile.loyalty_level = 5
        elif profile.total_spent >= 500000:  # 500K IRR
            profile.loyalty_level = 4
        elif profile.total_spent >= 200000:  # 200K IRR
            profile.loyalty_level = 3
        elif profile.total_spent >= 100000:  # 100K IRR
            profile.loyalty_level = 2
        elif profile.total_spent >= 50000:  # 50K IRR
            profile.loyalty_level = 1
        else:
            profile.loyalty_level = 0
    
    @staticmethod
    async def _get_applicable_cashback_rules(
        session: AsyncSession,
        user_id: int,
        amount: float,
        plan_id: Optional[int] = None,
        server_id: Optional[int] = None
    ) -> List[CashbackRule]:
        """Get applicable cashback rules"""
        
        now = datetime.utcnow()
        
        query = select(CashbackRule).where(
            and_(
                CashbackRule.is_active == True,
                or_(
                    CashbackRule.valid_from.is_(None),
                    CashbackRule.valid_from <= now
                ),
                or_(
                    CashbackRule.valid_to.is_(None),
                    CashbackRule.valid_to >= now
                ),
                or_(
                    CashbackRule.min_purchase_amount.is_(None),
                    CashbackRule.min_purchase_amount <= amount
                )
            )
        )
        
        rules = (await session.execute(query)).scalars().all()
        
        applicable_rules = []
        for rule in rules:
            if await SmartDiscountService._is_cashback_rule_applicable(
                session, rule, user_id, amount, plan_id, server_id
            ):
                applicable_rules.append(rule)
        
        return applicable_rules
    
    @staticmethod
    async def _is_cashback_rule_applicable(
        session: AsyncSession,
        rule: CashbackRule,
        user_id: int,
        amount: float,
        plan_id: Optional[int] = None,
        server_id: Optional[int] = None
    ) -> bool:
        """Check if cashback rule is applicable"""
        
        # Check limits
        if rule.daily_limit and rule.used_count >= rule.daily_limit:
            return False
        
        if rule.total_limit and rule.used_count >= rule.total_limit:
            return False
        
        # Check trigger conditions
        if rule.trigger_type == "purchase_amount":
            try:
                trigger_value = float(rule.trigger_value)
                if amount < trigger_value:
                    return False
            except ValueError:
                return False
        
        elif rule.trigger_type == "plan_id" and plan_id:
            try:
                trigger_plan_id = int(rule.trigger_value)
                if plan_id != trigger_plan_id:
                    return False
            except ValueError:
                return False
        
        elif rule.trigger_type == "server_id" and server_id:
            try:
                trigger_server_id = int(rule.trigger_value)
                if server_id != trigger_server_id:
                    return False
            except ValueError:
                return False
        
        return True
    
    @staticmethod
    async def _user_matches_criteria(
        session: AsyncSession,
        user_profile: UserDiscountProfile,
        criteria: Dict[str, Any]
    ) -> bool:
        """Check if user matches target criteria"""
        
        if "min_total_spent" in criteria:
            if user_profile.total_spent < criteria["min_total_spent"]:
                return False
        
        if "min_purchases" in criteria:
            if user_profile.total_purchases < criteria["min_purchases"]:
                return False
        
        if "loyalty_level" in criteria:
            if user_profile.loyalty_level < criteria["loyalty_level"]:
                return False
        
        if "is_first_time_buyer" in criteria:
            if user_profile.is_first_time_buyer != criteria["is_first_time_buyer"]:
                return False
        
        return True
    
    @staticmethod
    async def reset_daily_counters(session: AsyncSession):
        """Reset daily counters for all discounts"""
        
        today = datetime.utcnow().date()
        
        # Reset discounts
        discounts_to_reset = (await session.execute(
            select(SmartDiscount).where(
                or_(
                    SmartDiscount.last_reset_date.is_(None),
                    SmartDiscount.last_reset_date < today
                )
            )
        )).scalars().all()
        
        for discount in discounts_to_reset:
            discount.daily_used_count = 0
            discount.last_reset_date = today
        
        # Reset cashback rules
        cashback_rules_to_reset = (await session.execute(
            select(CashbackRule).where(
                or_(
                    CashbackRule.last_reset_date.is_(None),
                    CashbackRule.last_reset_date < today
                )
            )
        )).scalars().all()
        
        for rule in cashback_rules_to_reset:
            rule.daily_used_count = 0
            rule.last_reset_date = today
    
    @staticmethod
    async def get_user_discount_summary(
        session: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """Get user's discount and cashback summary"""
        
        profile = await SmartDiscountService._get_user_profile(session, user_id)
        
        # Get recent discount usage
        recent_usage = (await session.execute(
            select(DiscountUsage)
            .where(DiscountUsage.user_id == user_id)
            .order_by(DiscountUsage.applied_at.desc())
            .limit(10)
        )).scalars().all()
        
        # Get pending cashback
        pending_cashback = (await session.execute(
            select(func.sum(CashbackTransaction.cashback_amount))
            .where(
                and_(
                    CashbackTransaction.user_id == user_id,
                    CashbackTransaction.status == "pending"
                )
            )
        )).scalar() or 0
        
        return {
            "profile": profile,
            "recent_usage": recent_usage,
            "pending_cashback": pending_cashback,
            "loyalty_level": profile.loyalty_level,
            "total_savings": profile.total_discount_savings,
            "total_cashback": profile.total_cashback_earned
        }