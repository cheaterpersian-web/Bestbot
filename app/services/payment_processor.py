import random
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import PaymentCard, Transaction
from models.user import TelegramUser
from models.orders import PurchaseIntent
from services.fraud_detection import FraudDetectionService
from core.config import settings


class PaymentProcessor:
    """Service for processing payments and managing payment cards"""
    
    @staticmethod
    async def get_random_payment_card(session: AsyncSession) -> Optional[PaymentCard]:
        """Get a random active payment card"""
        result = await session.execute(
            select(PaymentCard)
            .where(PaymentCard.active == True)
            .order_by(PaymentCard.sort_order, PaymentCard.id)
        )
        cards = result.scalars().all()
        
        if not cards:
            return None
            
        # If there's a primary card, use it 70% of the time
        primary_cards = [card for card in cards if card.is_primary]
        if primary_cards and random.random() < 0.7:
            return primary_cards[0]
            
        return random.choice(cards)
    
    @staticmethod
    async def get_all_payment_cards(session: AsyncSession) -> List[PaymentCard]:
        """Get all active payment cards ordered by priority"""
        result = await session.execute(
            select(PaymentCard)
            .where(PaymentCard.active == True)
            .order_by(PaymentCard.is_primary.desc(), PaymentCard.sort_order, PaymentCard.id)
        )
        return result.scalars().all()
    
    @staticmethod
    async def process_wallet_topup(
        session: AsyncSession,
        user: TelegramUser,
        amount: float,
        receipt_file_id: str,
        description: Optional[str] = None
    ) -> Transaction:
        """Process wallet top-up transaction"""
        
        # Calculate fraud score
        fraud_score = 0.0
        if settings.enable_fraud_detection:
            fraud_score = await FraudDetectionService.calculate_fraud_score(
                session, user.id, amount, receipt_file_id
            )
        
        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            type="wallet_topup",
            status="pending" if not settings.auto_approve_receipts else "approved",
            description=description or f"شارژ کیف پول - {amount:,.0f} تومان",
            receipt_image_file_id=receipt_file_id,
            fraud_score=fraud_score,
            payment_gateway="card_to_card"
        )
        
        session.add(transaction)
        await session.flush()
        
        # Auto-approve if enabled and fraud score is low
        if settings.auto_approve_receipts and fraud_score < 0.3:
            await PaymentProcessor.approve_transaction(
                session, transaction, user.id, "تایید خودکار"
            )
        
        return transaction
    
    @staticmethod
    async def process_purchase_payment(
        session: AsyncSession,
        user: TelegramUser,
        purchase_intent: PurchaseIntent,
        receipt_file_id: Optional[str] = None
    ) -> Transaction:
        """Process purchase payment transaction"""
        
        amount = purchase_intent.amount_due_receipt
        
        # Calculate fraud score if receipt provided
        fraud_score = 0.0
        if receipt_file_id and settings.enable_fraud_detection:
            fraud_score = await FraudDetectionService.calculate_fraud_score(
                session, user.id, amount, receipt_file_id
            )
        
        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            type="purchase",
            status="pending" if receipt_file_id and not settings.auto_approve_receipts else "approved",
            description=f"خرید سرویس - {amount:,.0f} تومان",
            receipt_image_file_id=receipt_file_id,
            fraud_score=fraud_score,
            payment_gateway="card_to_card",
            related_transaction_id=purchase_intent.id
        )
        
        session.add(transaction)
        await session.flush()
        
        # Update purchase intent
        purchase_intent.receipt_transaction_id = transaction.id
        purchase_intent.status = "paid" if transaction.status == "approved" else "pending"
        
        # Auto-approve if enabled and fraud score is low
        if settings.auto_approve_receipts and fraud_score < 0.3:
            await PaymentProcessor.approve_transaction(
                session, transaction, user.id, "تایید خودکار"
            )
        
        return transaction
    
    @staticmethod
    async def approve_transaction(
        session: AsyncSession,
        transaction: Transaction,
        admin_id: int,
        notes: Optional[str] = None
    ) -> bool:
        """Approve a transaction and update user wallet"""
        if transaction.status != "pending":
            return False
        
        # Update transaction
        transaction.status = "approved"
        transaction.approved_by_admin_id = admin_id
        transaction.approved_at = datetime.utcnow()
        if notes:
            transaction.description = f"{transaction.description} - {notes}"
        
        # Update user wallet
        user = await session.get(TelegramUser, transaction.user_id)
        if user:
            user.wallet_balance += transaction.amount + transaction.bonus_amount
        
        return True
    
    @staticmethod
    async def reject_transaction(
        session: AsyncSession,
        transaction: Transaction,
        admin_id: int,
        reason: str
    ) -> bool:
        """Reject a transaction with reason"""
        if transaction.status != "pending":
            return False
        
        transaction.status = "rejected"
        transaction.approved_by_admin_id = admin_id
        transaction.approved_at = datetime.utcnow()
        transaction.rejected_reason = reason
        
        return True
    
    @staticmethod
    async def process_wallet_deduction(
        session: AsyncSession,
        user: TelegramUser,
        amount: float,
        description: str
    ) -> bool:
        """Process wallet deduction for purchases"""
        if user.wallet_balance < amount:
            return False
        
        # Create deduction transaction
        transaction = Transaction(
            user_id=user.id,
            amount=-amount,  # Negative amount for deduction
            type="purchase",
            status="approved",
            description=description,
            payment_gateway="wallet"
        )
        
        session.add(transaction)
        
        # Update user wallet
        user.wallet_balance -= amount
        
        return True
    
    @staticmethod
    async def transfer_balance(
        session: AsyncSession,
        from_user: TelegramUser,
        to_user: TelegramUser,
        amount: float,
        description: Optional[str] = None
    ) -> bool:
        """Transfer balance between users"""
        if from_user.wallet_balance < amount:
            return False
        
        # Create transfer transactions
        from_transaction = Transaction(
            user_id=from_user.id,
            amount=-amount,
            type="transfer",
            status="approved",
            description=description or f"انتقال به کاربر {to_user.telegram_user_id}",
            payment_gateway="wallet"
        )
        
        to_transaction = Transaction(
            user_id=to_user.id,
            amount=amount,
            type="transfer",
            status="approved",
            description=description or f"دریافت از کاربر {from_user.telegram_user_id}",
            payment_gateway="wallet"
        )
        
        session.add(from_transaction)
        session.add(to_transaction)
        
        # Update wallets
        from_user.wallet_balance -= amount
        to_user.wallet_balance += amount
        
        return True