import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.notifications import (
    Notification, NotificationTemplate, NotificationSettings, NotificationLog,
    NotificationType, NotificationStatus
)
from models.user import TelegramUser
from models.service import Service
from models.billing import Transaction
from core.config import settings


class NotificationService:
    """Service for managing automatic notifications"""
    
    @staticmethod
    async def send_notification(
        session: AsyncSession,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: int = 0,
        context_data: Optional[Dict[str, Any]] = None,
        related_service_id: Optional[int] = None,
        related_transaction_id: Optional[int] = None,
        scheduled_at: Optional[datetime] = None
    ) -> Optional[Notification]:
        """Send a notification to a user"""
        
        # Check user notification settings
        settings = await NotificationService._get_user_settings(session, user_id)
        if not settings.notifications_enabled:
            return None
        
        # Check if user wants this type of notification
        if not await NotificationService._is_notification_type_enabled(
            settings, notification_type
        ):
            return None
        
        # Check daily limits
        if settings.notifications_today >= settings.max_notifications_per_day:
            return None
        
        # Check cooldown
        if settings.last_notification_at:
            cooldown_end = settings.last_notification_at + timedelta(
                minutes=settings.notification_cooldown_minutes
            )
            if datetime.utcnow() < cooldown_end:
                return None
        
        # Check quiet hours
        if await NotificationService._is_quiet_hours(settings):
            # Schedule for later
            scheduled_at = await NotificationService._get_next_available_time(settings)
        
        # Create notification
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            context_data=json.dumps(context_data) if context_data else None,
            related_service_id=related_service_id,
            related_transaction_id=related_transaction_id,
            scheduled_at=scheduled_at or datetime.utcnow()
        )
        session.add(notification)
        await session.flush()
        
        # Update user settings
        settings.notifications_today += 1
        settings.last_notification_at = datetime.utcnow()
        
        return notification
    
    @staticmethod
    async def _get_user_settings(session: AsyncSession, user_id: int) -> NotificationSettings:
        """Get or create user notification settings"""
        
        settings = (await session.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user_id)
        )).scalar_one_or_none()
        
        if not settings:
            settings = NotificationSettings(user_id=user_id)
            session.add(settings)
            await session.flush()
        
        # Reset daily counter if needed
        today = datetime.utcnow().date()
        if not settings.last_reset_date or settings.last_reset_date.date() < today:
            settings.notifications_today = 0
            settings.last_reset_date = today
        
        return settings
    
    @staticmethod
    async def _is_notification_type_enabled(
        settings: NotificationSettings,
        notification_type: NotificationType
    ) -> bool:
        """Check if notification type is enabled for user"""
        
        if notification_type == NotificationType.SERVICE_EXPIRY:
            return settings.service_expiry_enabled
        elif notification_type == NotificationType.WALLET_LOW:
            return settings.wallet_low_enabled
        elif notification_type in [
            NotificationType.PAYMENT_RECEIVED,
            NotificationType.PAYMENT_APPROVED,
            NotificationType.PAYMENT_REJECTED
        ]:
            return settings.payment_notifications_enabled
        elif notification_type in [
            NotificationType.DISCOUNT_AVAILABLE,
            NotificationType.CASHBACK_EARNED
        ]:
            return settings.discount_notifications_enabled
        elif notification_type == NotificationType.REFERRAL_BONUS:
            return settings.referral_notifications_enabled
        elif notification_type in [
            NotificationType.SYSTEM_MAINTENANCE,
            NotificationType.SECURITY_ALERT
        ]:
            return settings.system_notifications_enabled
        
        return True  # Default to enabled for unknown types
    
    @staticmethod
    async def _is_quiet_hours(settings: NotificationSettings) -> bool:
        """Check if current time is within quiet hours"""
        
        if not settings.quiet_hours_start or not settings.quiet_hours_end:
            return False
        
        current_hour = datetime.utcnow().hour
        
        if settings.quiet_hours_start <= settings.quiet_hours_end:
            # Same day quiet hours (e.g., 22:00 to 08:00)
            return settings.quiet_hours_start <= current_hour < settings.quiet_hours_end
        else:
            # Overnight quiet hours (e.g., 22:00 to 08:00)
            return current_hour >= settings.quiet_hours_start or current_hour < settings.quiet_hours_end
    
    @staticmethod
    async def _get_next_available_time(settings: NotificationSettings) -> datetime:
        """Get next available time outside quiet hours"""
        
        now = datetime.utcnow()
        
        if not settings.quiet_hours_start or not settings.quiet_hours_end:
            return now
        
        current_hour = now.hour
        
        if settings.quiet_hours_start <= settings.quiet_hours_end:
            # Same day quiet hours
            if settings.quiet_hours_start <= current_hour < settings.quiet_hours_end:
                # Currently in quiet hours, wait until end
                next_time = now.replace(
                    hour=settings.quiet_hours_end,
                    minute=0,
                    second=0,
                    microsecond=0
                )
                if next_time <= now:
                    next_time += timedelta(days=1)
                return next_time
        else:
            # Overnight quiet hours
            if current_hour >= settings.quiet_hours_start or current_hour < settings.quiet_hours_end:
                # Currently in quiet hours, wait until end
                next_time = now.replace(
                    hour=settings.quiet_hours_end,
                    minute=0,
                    second=0,
                    microsecond=0
                )
                if next_time <= now:
                    next_time += timedelta(days=1)
                return next_time
        
        return now
    
    @staticmethod
    async def process_pending_notifications(session: AsyncSession) -> int:
        """Process pending notifications and send them"""
        
        # Get pending notifications
        pending_notifications = (await session.execute(
            select(Notification)
            .where(
                and_(
                    Notification.status == NotificationStatus.PENDING,
                    Notification.scheduled_at <= datetime.utcnow()
                )
            )
            .order_by(Notification.priority.desc(), Notification.scheduled_at)
            .limit(100)  # Process in batches
        )).scalars().all()
        
        sent_count = 0
        
        for notification in pending_notifications:
            try:
                success = await NotificationService._send_telegram_notification(
                    session, notification
                )
                
                if success:
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = datetime.utcnow()
                    sent_count += 1
                else:
                    notification.delivery_attempts += 1
                    notification.last_attempt_at = datetime.utcnow()
                    
                    # Mark as failed if too many attempts
                    if notification.delivery_attempts >= 3:
                        notification.status = NotificationStatus.FAILED
            
            except Exception as e:
                notification.delivery_attempts += 1
                notification.last_attempt_at = datetime.utcnow()
                notification.error_message = str(e)
                
                if notification.delivery_attempts >= 3:
                    notification.status = NotificationStatus.FAILED
        
        return sent_count
    
    @staticmethod
    async def _send_telegram_notification(
        session: AsyncSession,
        notification: Notification
    ) -> bool:
        """Send notification via Telegram"""
        
        try:
            from aiogram import Bot
            bot = Bot(token=settings.bot_token)
            
            # Get user
            user = (await session.execute(
                select(TelegramUser).where(TelegramUser.id == notification.user_id)
            )).scalar_one()
            
            # Format message
            message_text = f"🔔 {notification.title}\n\n{notification.message}"
            
            # Send message
            sent_message = await bot.send_message(
                chat_id=user.telegram_user_id,
                text=message_text,
                parse_mode="HTML"
            )
            
            # Log delivery
            log = NotificationLog(
                notification_id=notification.id,
                user_id=notification.user_id,
                attempt_number=notification.delivery_attempts + 1,
                status=NotificationStatus.DELIVERED,
                delivered_at=datetime.utcnow(),
                telegram_message_id=sent_message.message_id
            )
            session.add(log)
            
            notification.status = NotificationStatus.DELIVERED
            notification.delivered_at = datetime.utcnow()
            
            return True
            
        except Exception as e:
            # Log failure
            log = NotificationLog(
                notification_id=notification.id,
                user_id=notification.user_id,
                attempt_number=notification.delivery_attempts + 1,
                status=NotificationStatus.FAILED,
                error_message=str(e)
            )
            session.add(log)
            
            return False
    
    @staticmethod
    async def check_service_expiries(session: AsyncSession):
        """Check for expiring services and send notifications"""
        
        # Get services expiring in the next 7 days
        seven_days_from_now = datetime.utcnow() + timedelta(days=7)
        
        expiring_services = (await session.execute(
            select(Service, TelegramUser)
            .join(TelegramUser, Service.user_id == TelegramUser.id)
            .where(
                and_(
                    Service.is_active == True,
                    Service.expires_at.isnot(None),
                    Service.expires_at <= seven_days_from_now,
                    Service.expires_at > datetime.utcnow()
                )
            )
        )).all()
        
        for service, user in expiring_services:
            days_until_expiry = (service.expires_at - datetime.utcnow()).days
            
            # Get user settings to check notification preferences
            settings = await NotificationService._get_user_settings(session, user.id)
            
            if not settings.service_expiry_enabled:
                continue
            
            # Send notification based on days before expiry
            if days_until_expiry <= settings.service_expiry_days_before:
                title = "⚠️ هشدار انقضای سرویس"
                message = f"سرویس شما '{service.remark}' در {days_until_expiry} روز منقضی می‌شود.\n"
                message += f"تاریخ انقضا: {service.expires_at.strftime('%Y/%m/%d %H:%M')}\n\n"
                message += "برای تمدید سرویس از منوی 'سرویس‌های من' استفاده کنید."
                
                await NotificationService.send_notification(
                    session=session,
                    user_id=user.id,
                    notification_type=NotificationType.SERVICE_EXPIRY_WARNING,
                    title=title,
                    message=message,
                    related_service_id=service.id,
                    context_data={"days_until_expiry": days_until_expiry}
                )
    
    @staticmethod
    async def check_low_wallet_balances(session: AsyncSession):
        """Check for users with low wallet balances"""
        
        # Get users with low wallet balances
        users_with_low_balance = (await session.execute(
            select(TelegramUser)
            .where(TelegramUser.wallet_balance < 10000)  # Less than 10K IRR
        )).scalars().all()
        
        for user in users_with_low_balance:
            settings = await NotificationService._get_user_settings(session, user.id)
            
            if not settings.wallet_low_enabled:
                continue
            
            if user.wallet_balance < settings.wallet_low_threshold:
                title = "💰 موجودی کیف پول کم"
                message = f"موجودی کیف پول شما {user.wallet_balance:,.0f} تومان است.\n\n"
                message += "برای شارژ کیف پول از منوی 'کیف پول' استفاده کنید."
                
                await NotificationService.send_notification(
                    session=session,
                    user_id=user.id,
                    notification_type=NotificationType.WALLET_LOW,
                    title=title,
                    message=message,
                    context_data={"current_balance": user.wallet_balance}
                )
    
    @staticmethod
    async def send_payment_notification(
        session: AsyncSession,
        transaction: Transaction,
        notification_type: NotificationType
    ):
        """Send payment-related notification"""
        
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == transaction.user_id)
        )).scalar_one()
        
        if notification_type == NotificationType.PAYMENT_APPROVED:
            title = "✅ پرداخت تایید شد"
            message = f"پرداخت شما به مبلغ {transaction.amount:,.0f} تومان تایید شد.\n"
            message += f"موجودی جدید: {user.wallet_balance:,.0f} تومان"
        elif notification_type == NotificationType.PAYMENT_REJECTED:
            title = "❌ پرداخت رد شد"
            message = f"پرداخت شما به مبلغ {transaction.amount:,.0f} تومان رد شد.\n"
            if transaction.rejected_reason:
                message += f"دلیل: {transaction.rejected_reason}"
        else:
            return
        
        await NotificationService.send_notification(
            session=session,
            user_id=user.id,
            notification_type=notification_type,
            title=title,
            message=message,
            related_transaction_id=transaction.id,
            context_data={"amount": transaction.amount}
        )
    
    @staticmethod
    async def send_discount_notification(
        session: AsyncSession,
        user_id: int,
        discount_name: str,
        discount_amount: float
    ):
        """Send discount notification"""
        
        title = "🎁 تخفیف ویژه برای شما!"
        message = f"تخفیف '{discount_name}' به مبلغ {discount_amount:,.0f} تومان برای شما فعال شد.\n\n"
        message += "از این تخفیف در خرید بعدی خود استفاده کنید."
        
        await NotificationService.send_notification(
            session=session,
            user_id=user_id,
            notification_type=NotificationType.DISCOUNT_AVAILABLE,
            title=title,
            message=message,
            context_data={"discount_name": discount_name, "discount_amount": discount_amount}
        )
    
    @staticmethod
    async def send_cashback_notification(
        session: AsyncSession,
        user_id: int,
        cashback_amount: float
    ):
        """Send cashback notification"""
        
        title = "💰 کش‌بک دریافت کردید!"
        message = f"شما {cashback_amount:,.0f} تومان کش‌بک دریافت کردید.\n\n"
        message += "این مبلغ به کیف پول شما اضافه شده است."
        
        await NotificationService.send_notification(
            session=session,
            user_id=user_id,
            notification_type=NotificationType.CASHBACK_EARNED,
            title=title,
            message=message,
            context_data={"cashback_amount": cashback_amount}
        )
    
    @staticmethod
    async def get_user_notifications(
        session: AsyncSession,
        user_id: int,
        limit: int = 20
    ) -> List[Notification]:
        """Get user's recent notifications"""
        
        notifications = (await session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )).scalars().all()
        
        return notifications
    
    @staticmethod
    async def mark_notification_as_read(
        session: AsyncSession,
        notification_id: int,
        user_id: int
    ) -> bool:
        """Mark notification as read"""
        
        notification = (await session.execute(
            select(Notification)
            .where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id
                )
            )
        )).scalar_one_or_none()
        
        if notification and notification.status == NotificationStatus.DELIVERED:
            notification.status = NotificationStatus.READ
            notification.read_at = datetime.utcnow()
            return True
        
        return False
    
    @staticmethod
    async def update_notification_settings(
        session: AsyncSession,
        user_id: int,
        settings_data: Dict[str, Any]
    ) -> NotificationSettings:
        """Update user notification settings"""
        
        settings = await NotificationService._get_user_settings(session, user_id)
        
        # Update settings based on provided data
        for key, value in settings_data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        
        return settings