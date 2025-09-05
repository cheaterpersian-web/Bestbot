import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.refund_system import (
    RefundRequest, ServiceUpgrade, WalletTransaction, RefundPolicy,
    UpgradeRule, RefundAnalytics, RefundType, RefundStatus, RefundReason
)
from models.user import TelegramUser
from models.billing import Transaction
from models.service import Service
from models.catalog import Plan


class RefundService:
    """Service for managing refunds and service upgrades"""
    
    @staticmethod
    async def create_refund_request(
        session: AsyncSession,
        user_id: int,
        service_id: int,
        refund_type: RefundType,
        refund_reason: RefundReason,
        requested_amount: float,
        description: str
    ) -> RefundRequest:
        """Create a new refund request"""
        
        # Get service and transaction
        service = (await session.execute(
            select(Service).where(Service.id == service_id)
        )).scalar_one_or_none()
        
        if not service:
            raise ValueError("Service not found")
        
        if service.user_id != user_id:
            raise ValueError("Service does not belong to user")
        
        # Get original transaction
        transaction = (await session.execute(
            select(Transaction).where(Transaction.service_id == service_id)
        )).scalar_one_or_none()
        
        if not transaction:
            raise ValueError("Original transaction not found")
        
        # Check if refund is allowed
        is_allowed, max_amount = await RefundService._check_refund_eligibility(
            session, service, transaction, refund_type
        )
        
        if not is_allowed:
            raise ValueError("Refund not allowed for this service")
        
        # Validate requested amount
        if requested_amount > max_amount:
            raise ValueError(f"Requested amount exceeds maximum allowed: {max_amount}")
        
        # Create refund request
        refund_request = RefundRequest(
            user_id=user_id,
            service_id=service_id,
            transaction_id=transaction.id,
            refund_type=refund_type,
            refund_reason=refund_reason,
            requested_amount=requested_amount,
            request_description=description
        )
        session.add(refund_request)
        await session.flush()
        
        return refund_request
    
    @staticmethod
    async def _check_refund_eligibility(
        session: AsyncSession,
        service: Service,
        transaction: Transaction,
        refund_type: RefundType
    ) -> Tuple[bool, float]:
        """Check if refund is eligible and calculate maximum amount"""
        
        # Check if service is still active
        if not service.is_active:
            return False, 0
        
        # Check service age
        service_age_days = (datetime.utcnow() - service.purchased_at).days
        
        # Get applicable refund policy
        policy = await RefundService._get_applicable_policy(session, service, refund_type)
        
        if not policy:
            return False, 0
        
        # Check age limit
        if service_age_days > policy.max_refund_days:
            return False, 0
        
        # Calculate maximum refund amount
        if refund_type == RefundType.FULL_REFUND:
            max_amount = transaction.amount * (policy.max_refund_percent / 100)
        elif refund_type == RefundType.PARTIAL_REFUND:
            # For partial refunds, allow up to 50% of original amount
            max_amount = transaction.amount * 0.5
        else:
            max_amount = transaction.amount * (policy.max_refund_percent / 100)
        
        return True, max_amount
    
    @staticmethod
    async def _get_applicable_policy(
        session: AsyncSession,
        service: Service,
        refund_type: RefundType
    ) -> Optional[RefundPolicy]:
        """Get applicable refund policy for service"""
        
        # Get service plan
        plan = (await session.execute(
            select(Plan).where(Plan.id == service.plan_id)
        )).scalar_one_or_none()
        
        if not plan:
            return None
        
        # Get active policies
        policies = (await session.execute(
            select(RefundPolicy).where(RefundPolicy.is_active == True)
        )).scalars().all()
        
        # Find applicable policy
        for policy in policies:
            try:
                conditions = json.loads(policy.conditions)
                
                # Check service type condition
                if "service_type" in conditions:
                    if conditions["service_type"] != "all" and conditions["service_type"] != plan.category_id:
                        continue
                
                # Check refund type condition
                if "refund_type" in conditions:
                    if refund_type.value not in conditions["refund_type"]:
                        continue
                
                return policy
            
            except (json.JSONDecodeError, KeyError):
                continue
        
        return None
    
    @staticmethod
    async def approve_refund_request(
        session: AsyncSession,
        refund_request_id: int,
        approved_amount: float,
        processed_by: int,
        admin_notes: Optional[str] = None
    ) -> RefundRequest:
        """Approve a refund request"""
        
        refund_request = (await session.execute(
            select(RefundRequest).where(RefundRequest.id == refund_request_id)
        )).scalar_one_or_none()
        
        if not refund_request:
            raise ValueError("Refund request not found")
        
        if refund_request.status != RefundStatus.PENDING:
            raise ValueError("Refund request is not pending")
        
        # Validate approved amount
        if approved_amount > refund_request.requested_amount:
            raise ValueError("Approved amount cannot exceed requested amount")
        
        # Update refund request
        refund_request.status = RefundStatus.APPROVED
        refund_request.approved_amount = approved_amount
        refund_request.processed_by = processed_by
        refund_request.processed_at = datetime.utcnow()
        refund_request.admin_notes = admin_notes
        
        return refund_request
    
    @staticmethod
    async def process_refund(
        session: AsyncSession,
        refund_request_id: int
    ) -> bool:
        """Process approved refund"""
        
        refund_request = (await session.execute(
            select(RefundRequest).where(RefundRequest.id == refund_request_id)
        )).scalar_one_or_none()
        
        if not refund_request:
            return False
        
        if refund_request.status != RefundStatus.APPROVED:
            return False
        
        try:
            # Update status to processing
            refund_request.status = RefundStatus.PROCESSING
            
            # Process based on refund type
            if refund_request.refund_type in [RefundType.WALLET_CREDIT, RefundType.SERVICE_CREDIT]:
                # Add to user wallet
                await RefundService._add_wallet_credit(
                    session, refund_request.user_id, refund_request.approved_amount,
                    f"Refund for service {refund_request.service_id}",
                    refund_request.id
                )
            
            elif refund_request.refund_type == RefundType.FULL_REFUND:
                # Deactivate service and refund
                service = (await session.execute(
                    select(Service).where(Service.id == refund_request.service_id)
                )).scalar_one()
                
                service.is_active = False
                service.refunded_at = datetime.utcnow()
                
                # Add to wallet
                await RefundService._add_wallet_credit(
                    session, refund_request.user_id, refund_request.approved_amount,
                    f"Full refund for service {refund_request.service_id}",
                    refund_request.id
                )
            
            elif refund_request.refund_type == RefundType.PARTIAL_REFUND:
                # Partial refund - extend service or add credit
                await RefundService._add_wallet_credit(
                    session, refund_request.user_id, refund_request.approved_amount,
                    f"Partial refund for service {refund_request.service_id}",
                    refund_request.id
                )
            
            # Update refund request status
            refund_request.status = RefundStatus.COMPLETED
            
            return True
        
        except Exception as e:
            refund_request.status = RefundStatus.REJECTED
            refund_request.rejection_reason = str(e)
            return False
    
    @staticmethod
    async def _add_wallet_credit(
        session: AsyncSession,
        user_id: int,
        amount: float,
        description: str,
        reference_id: Optional[int] = None
    ):
        """Add credit to user wallet"""
        
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == user_id)
        )).scalar_one()
        
        # Update wallet balance
        balance_before = user.wallet_balance
        user.wallet_balance += amount
        balance_after = user.wallet_balance
        
        # Create wallet transaction record
        wallet_transaction = WalletTransaction(
            user_id=user_id,
            transaction_type="credit",
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_type="refund",
            reference_id=reference_id,
            description=description
        )
        session.add(wallet_transaction)
    
    @staticmethod
    async def create_service_upgrade(
        session: AsyncSession,
        user_id: int,
        current_service_id: int,
        target_plan_id: int,
        payment_method: str = "wallet"
    ) -> ServiceUpgrade:
        """Create a service upgrade request"""
        
        # Get current service
        current_service = (await session.execute(
            select(Service).where(Service.id == current_service_id)
        )).scalar_one_or_none()
        
        if not current_service:
            raise ValueError("Current service not found")
        
        if current_service.user_id != user_id:
            raise ValueError("Service does not belong to user")
        
        # Get target plan
        target_plan = (await session.execute(
            select(Plan).where(Plan.id == target_plan_id)
        )).scalar_one_or_none()
        
        if not target_plan:
            raise ValueError("Target plan not found")
        
        # Get current plan
        current_plan = (await session.execute(
            select(Plan).where(Plan.id == current_service.plan_id)
        )).scalar_one_or_none()
        
        if not current_plan:
            raise ValueError("Current plan not found")
        
        # Check upgrade eligibility
        is_eligible, upgrade_cost = await RefundService._calculate_upgrade_cost(
            session, current_service, current_plan, target_plan
        )
        
        if not is_eligible:
            raise ValueError("Upgrade not eligible")
        
        # Create upgrade request
        upgrade = ServiceUpgrade(
            user_id=user_id,
            current_service_id=current_service_id,
            target_plan_id=target_plan_id,
            upgrade_type="plan_upgrade",
            current_plan_price=current_plan.price_irr,
            target_plan_price=target_plan.price_irr,
            upgrade_cost=upgrade_cost,
            payment_method=payment_method
        )
        session.add(upgrade)
        await session.flush()
        
        return upgrade
    
    @staticmethod
    async def _calculate_upgrade_cost(
        session: AsyncSession,
        current_service: Service,
        current_plan: Plan,
        target_plan: Plan
    ) -> Tuple[bool, float]:
        """Calculate upgrade cost"""
        
        # Check if upgrade is allowed
        upgrade_rule = (await session.execute(
            select(UpgradeRule)
            .where(
                and_(
                    UpgradeRule.from_plan_id == current_plan.id,
                    UpgradeRule.to_plan_id == target_plan.id,
                    UpgradeRule.is_active == True
                )
            )
        )).scalar_one_or_none()
        
        if not upgrade_rule:
            return False, 0
        
        # Check service age
        service_age_days = (datetime.utcnow() - current_service.purchased_at).days
        
        if service_age_days < upgrade_rule.min_service_age_days:
            return False, 0
        
        if upgrade_rule.max_service_age_days and service_age_days > upgrade_rule.max_service_age_days:
            return False, 0
        
        # Calculate upgrade cost
        if upgrade_rule.prorated_refund:
            # Calculate remaining value of current service
            total_days = current_plan.duration_days or 30
            remaining_days = max(0, total_days - service_age_days)
            remaining_value = (current_plan.price_irr / total_days) * remaining_days
            
            # Calculate upgrade cost
            upgrade_cost = target_plan.price_irr - remaining_value
        else:
            upgrade_cost = target_plan.price_irr
        
        # Apply discount
        if upgrade_rule.upgrade_discount_percent > 0:
            discount_amount = upgrade_cost * (upgrade_rule.upgrade_discount_percent / 100)
            upgrade_cost -= discount_amount
        
        return True, max(0, upgrade_cost)
    
    @staticmethod
    async def process_service_upgrade(
        session: AsyncSession,
        upgrade_id: int
    ) -> bool:
        """Process service upgrade"""
        
        upgrade = (await session.execute(
            select(ServiceUpgrade).where(ServiceUpgrade.id == upgrade_id)
        )).scalar_one_or_none()
        
        if not upgrade:
            return False
        
        if upgrade.status != "pending":
            return False
        
        try:
            # Update status to processing
            upgrade.status = "processing"
            
            # Process payment
            if upgrade.payment_method == "wallet":
                user = (await session.execute(
                    select(TelegramUser).where(TelegramUser.id == upgrade.user_id)
                )).scalar_one()
                
                if user.wallet_balance < upgrade.upgrade_cost:
                    raise ValueError("Insufficient wallet balance")
                
                # Deduct from wallet
                balance_before = user.wallet_balance
                user.wallet_balance -= upgrade.upgrade_cost
                balance_after = user.wallet_balance
                
                # Create wallet transaction
                wallet_transaction = WalletTransaction(
                    user_id=upgrade.user_id,
                    transaction_type="debit",
                    amount=upgrade.upgrade_cost,
                    balance_before=balance_before,
                    balance_after=balance_after,
                    reference_type="upgrade",
                    reference_id=upgrade.id,
                    description=f"Service upgrade to plan {upgrade.target_plan_id}"
                )
                session.add(wallet_transaction)
            
            # Deactivate current service
            current_service = (await session.execute(
                select(Service).where(Service.id == upgrade.current_service_id)
            )).scalar_one()
            
            current_service.is_active = False
            current_service.upgraded_at = datetime.utcnow()
            
            # Create new service
            target_plan = (await session.execute(
                select(Plan).where(Plan.id == upgrade.target_plan_id)
            )).scalar_one()
            
            new_service = Service(
                user_id=upgrade.user_id,
                plan_id=upgrade.target_plan_id,
                server_id=current_service.server_id,
                remark=f"Upgraded from service {current_service.id}",
                is_active=True,
                purchased_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=target_plan.duration_days or 30)
            )
            session.add(new_service)
            await session.flush()
            
            # Update upgrade record
            upgrade.status = "completed"
            upgrade.processed_at = datetime.utcnow()
            upgrade.new_service_id = new_service.id
            
            return True
        
        except Exception as e:
            upgrade.status = "failed"
            upgrade.processed_at = datetime.utcnow()
            return False
    
    @staticmethod
    async def get_refund_analytics(
        session: AsyncSession,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get refund analytics for date range"""
        
        # Refund statistics
        refund_stats = (await session.execute(
            select(
                func.count(RefundRequest.id),
                func.sum(RefundRequest.approved_amount),
                func.count(RefundRequest.id).filter(RefundRequest.status == RefundStatus.APPROVED),
                func.count(RefundRequest.id).filter(RefundRequest.status == RefundStatus.REJECTED)
            )
            .where(
                and_(
                    RefundRequest.created_at >= start_date,
                    RefundRequest.created_at <= end_date
                )
            )
        )).first()
        
        # Upgrade statistics
        upgrade_stats = (await session.execute(
            select(
                func.count(ServiceUpgrade.id),
                func.sum(ServiceUpgrade.upgrade_cost),
                func.count(ServiceUpgrade.id).filter(ServiceUpgrade.status == "completed")
            )
            .where(
                and_(
                    ServiceUpgrade.created_at >= start_date,
                    ServiceUpgrade.created_at <= end_date
                )
            )
        )).first()
        
        return {
            "refunds": {
                "total_requests": refund_stats[0] or 0,
                "total_amount": refund_stats[1] or 0,
                "approved_count": refund_stats[2] or 0,
                "rejected_count": refund_stats[3] or 0
            },
            "upgrades": {
                "total_requests": upgrade_stats[0] or 0,
                "total_revenue": upgrade_stats[1] or 0,
                "completed_count": upgrade_stats[2] or 0
            }
        }