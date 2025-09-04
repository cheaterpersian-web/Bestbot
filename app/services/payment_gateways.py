import httpx
import json
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import Transaction
from models.user import TelegramUser
from core.config import settings


class StarsPaymentGateway:
    """Telegram Stars payment gateway integration"""
    
    @staticmethod
    async def create_payment_link(
        amount: int,  # Amount in stars
        description: str,
        user_id: int
    ) -> Optional[str]:
        """Create a payment link for Telegram Stars"""
        if not settings.enable_stars:
            return None
        
        try:
            # This is a simplified implementation
            # In a real implementation, you would use Telegram's Stars API
            # For now, we'll return a placeholder
            return f"https://t.me/{settings.bot_username}?start=stars_pay_{user_id}_{amount}"
        except Exception:
            return None
    
    @staticmethod
    async def verify_payment(
        payment_id: str,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Verify a Stars payment"""
        if not settings.enable_stars:
            return None
        
        try:
            # This would integrate with Telegram's Stars API
            # For now, return a mock verification
            return {
                "success": True,
                "amount": 100,  # stars
                "currency": "XTR",
                "transaction_id": payment_id
            }
        except Exception:
            return None


class ZarinpalPaymentGateway:
    """Zarinpal payment gateway integration"""
    
    @staticmethod
    async def create_payment_request(
        amount: int,  # Amount in IRR
        description: str,
        user_id: int,
        callback_url: str
    ) -> Optional[Dict[str, Any]]:
        """Create a payment request with Zarinpal"""
        if not settings.enable_zarinpal or not settings.zarinpal_merchant_id:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "merchant_id": settings.zarinpal_merchant_id,
                    "amount": amount,
                    "description": description,
                    "callback_url": callback_url,
                    "metadata": {
                        "user_id": user_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                
                response = await client.post(
                    "https://api.zarinpal.com/pg/v4/payment/request.json",
                    json=data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("data", {}).get("code") == 100:
                        return {
                            "success": True,
                            "authority": result["data"]["authority"],
                            "payment_url": f"https://www.zarinpal.com/pg/StartPay/{result['data']['authority']}"
                        }
                
                return None
        except Exception:
            return None
    
    @staticmethod
    async def verify_payment(
        authority: str,
        amount: int
    ) -> Optional[Dict[str, Any]]:
        """Verify a Zarinpal payment"""
        if not settings.enable_zarinpal or not settings.zarinpal_merchant_id:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "merchant_id": settings.zarinpal_merchant_id,
                    "amount": amount,
                    "authority": authority
                }
                
                response = await client.post(
                    "https://api.zarinpal.com/pg/v4/payment/verify.json",
                    json=data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("data", {}).get("code") == 100:
                        return {
                            "success": True,
                            "ref_id": result["data"]["ref_id"],
                            "amount": result["data"]["amount"],
                            "currency": "IRR"
                        }
                
                return None
        except Exception:
            return None


class PaymentGatewayManager:
    """Manages all payment gateways"""
    
    @staticmethod
    async def process_payment(
        session: AsyncSession,
        user: TelegramUser,
        amount: int,
        description: str,
        gateway: str,
        callback_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Process payment through specified gateway"""
        
        if gateway == "stars":
            if not settings.enable_stars:
                return None
            
            payment_link = await StarsPaymentGateway.create_payment_link(
                amount=amount,
                description=description,
                user_id=user.telegram_user_id
            )
            
            if payment_link:
                # Create pending transaction
                transaction = Transaction(
                    user_id=user.id,
                    amount=amount,
                    currency="XTR",
                    type="wallet_topup",
                    status="pending",
                    description=description,
                    payment_gateway="stars"
                )
                session.add(transaction)
                await session.flush()
                
                return {
                    "success": True,
                    "payment_url": payment_link,
                    "transaction_id": transaction.id,
                    "gateway": "stars"
                }
        
        elif gateway == "zarinpal":
            if not settings.enable_zarinpal:
                return None
            
            payment_request = await ZarinpalPaymentGateway.create_payment_request(
                amount=amount,
                description=description,
                user_id=user.telegram_user_id,
                callback_url=callback_url or f"https://t.me/{settings.bot_username}"
            )
            
            if payment_request and payment_request.get("success"):
                # Create pending transaction
                transaction = Transaction(
                    user_id=user.id,
                    amount=amount,
                    currency="IRR",
                    type="wallet_topup",
                    status="pending",
                    description=description,
                    payment_gateway="zarinpal",
                    gateway_transaction_id=payment_request["authority"]
                )
                session.add(transaction)
                await session.flush()
                
                return {
                    "success": True,
                    "payment_url": payment_request["payment_url"],
                    "transaction_id": transaction.id,
                    "authority": payment_request["authority"],
                    "gateway": "zarinpal"
                }
        
        return None
    
    @staticmethod
    async def verify_payment(
        session: AsyncSession,
        transaction_id: int,
        gateway_data: Dict[str, Any]
    ) -> bool:
        """Verify payment and update transaction status"""
        
        from sqlalchemy import select
        transaction = (await session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )).scalar_one_or_none()
        
        if not transaction:
            return False
        
        if transaction.status != "pending":
            return False
        
        verification_result = None
        
        if transaction.payment_gateway == "stars":
            verification_result = await StarsPaymentGateway.verify_payment(
                payment_id=gateway_data.get("payment_id", ""),
                user_id=transaction.user_id
            )
        
        elif transaction.payment_gateway == "zarinpal":
            verification_result = await ZarinpalPaymentGateway.verify_payment(
                authority=gateway_data.get("authority", ""),
                amount=int(transaction.amount)
            )
        
        if verification_result and verification_result.get("success"):
            # Update transaction status
            transaction.status = "approved"
            transaction.approved_at = datetime.utcnow()
            transaction.gateway_transaction_id = verification_result.get("ref_id") or verification_result.get("transaction_id")
            
            # Update user wallet
            user = (await session.execute(
                select(TelegramUser).where(TelegramUser.id == transaction.user_id)
            )).scalar_one()
            
            user.wallet_balance += transaction.amount
            
            return True
        
        return False


# Webhook handlers for payment gateways
class PaymentWebhookHandler:
    """Handles webhooks from payment gateways"""
    
    @staticmethod
    async def handle_zarinpal_webhook(
        session: AsyncSession,
        authority: str,
        status: str
    ) -> bool:
        """Handle Zarinpal payment webhook"""
        
        if status != "OK":
            return False
        
        from sqlalchemy import select
        transaction = (await session.execute(
            select(Transaction)
            .where(Transaction.payment_gateway == "zarinpal")
            .where(Transaction.gateway_transaction_id == authority)
            .where(Transaction.status == "pending")
        )).scalar_one_or_none()
        
        if not transaction:
            return False
        
        # Verify the payment
        verification_result = await ZarinpalPaymentGateway.verify_payment(
            authority=authority,
            amount=int(transaction.amount)
        )
        
        if verification_result and verification_result.get("success"):
            # Update transaction
            transaction.status = "approved"
            transaction.approved_at = datetime.utcnow()
            transaction.gateway_transaction_id = verification_result["ref_id"]
            
            # Update user wallet
            user = (await session.execute(
                select(TelegramUser).where(TelegramUser.id == transaction.user_id)
            )).scalar_one()
            
            user.wallet_balance += transaction.amount
            
            # Notify user
            try:
                from aiogram import Bot
                bot = Bot(token=settings.bot_token)
                await bot.send_message(
                    user.telegram_user_id,
                    f"✅ پرداخت شما با موفقیت انجام شد!\n"
                    f"مبلغ: {transaction.amount:,.0f} تومان\n"
                    f"کد پیگیری: {verification_result['ref_id']}"
                )
            except Exception:
                pass  # User might have blocked the bot
            
            return True
        
        return False