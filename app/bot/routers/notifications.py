from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from models.notifications import NotificationType, NotificationStatus
from services.notification_service import NotificationService


router = Router(name="notifications")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


# User-side notification features
@router.message(Command("notifications"))
async def my_notifications(message: Message):
    """Show user's recent notifications"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        notifications = await NotificationService.get_user_notifications(session, user.id, 10)
    
    if not notifications:
        await message.answer("هیچ اعلانی دریافت نکرده‌اید.")
        return
    
    notifications_text = "🔔 اعلان‌های شما:\n\n"
    
    for i, notification in enumerate(notifications, 1):
        status_emoji = {
            NotificationStatus.DELIVERED: "✅",
            NotificationStatus.READ: "👁️",
            NotificationStatus.PENDING: "⏳",
            NotificationStatus.FAILED: "❌"
        }.get(notification.status, "❓")
        
        date_str = notification.created_at.strftime('%m/%d %H:%M')
        notifications_text += f"{i}. {status_emoji} {notification.title}\n"
        notifications_text += f"   {date_str}\n\n"
    
    await message.answer(notifications_text)


@router.message(Command("notification_settings"))
async def notification_settings(message: Message):
    """Show and manage notification settings"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        from models.notifications import NotificationSettings
        settings = (await session.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user.id)
        )).scalar_one_or_none()
        
        if not settings:
            settings = NotificationSettings(user_id=user.id)
            session.add(settings)
            await session.flush()
    
    settings_text = f"""
⚙️ تنظیمات اعلان‌ها:

🔔 اعلان‌ها: {'فعال' if settings.notifications_enabled else 'غیرفعال'}
📅 انقضای سرویس: {'فعال' if settings.service_expiry_enabled else 'غیرفعال'}
💰 موجودی کم: {'فعال' if settings.wallet_low_enabled else 'غیرفعال'}
💳 پرداخت‌ها: {'فعال' if settings.payment_notifications_enabled else 'غیرفعال'}
🎁 تخفیف‌ها: {'فعال' if settings.discount_notifications_enabled else 'غیرفعال'}
🤝 معرفی: {'فعال' if settings.referral_notifications_enabled else 'غیرفعال'}
🔧 سیستم: {'فعال' if settings.system_notifications_enabled else 'غیرفعال'}

⏰ ساعت سکوت: {f"{settings.quiet_hours_start}:00 - {settings.quiet_hours_end}:00" if settings.quiet_hours_start and settings.quiet_hours_end else "تنظیم نشده"}
📊 حداکثر اعلان روزانه: {settings.max_notifications_per_day}
⏱️ فاصله بین اعلان‌ها: {settings.notification_cooldown_minutes} دقیقه
"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 فعال/غیرفعال کردن اعلان‌ها", callback_data="toggle_notifications")],
        [InlineKeyboardButton(text="📅 تنظیم انقضای سرویس", callback_data="settings_expiry")],
        [InlineKeyboardButton(text="💰 تنظیم موجودی کم", callback_data="settings_wallet")],
        [InlineKeyboardButton(text="⏰ تنظیم ساعت سکوت", callback_data="settings_quiet")],
        [InlineKeyboardButton(text="📊 تنظیم محدودیت‌ها", callback_data="settings_limits")]
    ])
    
    await message.answer(settings_text, reply_markup=kb)


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
        )).scalar_one()
        
        from models.notifications import NotificationSettings
        settings = (await session.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user.id)
        )).scalar_one_or_none()
        
        if not settings:
            settings = NotificationSettings(user_id=user.id)
            session.add(settings)
        
        settings.notifications_enabled = not settings.notifications_enabled
    
    status = "فعال" if settings.notifications_enabled else "غیرفعال"
    await callback.answer(f"اعلان‌ها {status} شد")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data == "settings_expiry")
async def settings_expiry(callback: CallbackQuery):
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
        )).scalar_one()
        
        from models.notifications import NotificationSettings
        settings = (await session.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user.id)
        )).scalar_one_or_none()
        
        if not settings:
            settings = NotificationSettings(user_id=user.id)
            session.add(settings)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="فعال/غیرفعال", callback_data="toggle_expiry")],
        [InlineKeyboardButton(text="1 روز قبل", callback_data="expiry_days:1")],
        [InlineKeyboardButton(text="3 روز قبل", callback_data="expiry_days:3")],
        [InlineKeyboardButton(text="7 روز قبل", callback_data="expiry_days:7")]
    ])
    
    await callback.message.edit_text(
        f"📅 تنظیمات انقضای سرویس:\n\n"
        f"وضعیت: {'فعال' if settings.service_expiry_enabled else 'غیرفعال'}\n"
        f"روزهای قبل از انقضا: {settings.service_expiry_days_before}",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_expiry")
async def toggle_expiry(callback: CallbackQuery):
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
        )).scalar_one()
        
        from models.notifications import NotificationSettings
        settings = (await session.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user.id)
        )).scalar_one_or_none()
        
        if not settings:
            settings = NotificationSettings(user_id=user.id)
            session.add(settings)
        
        settings.service_expiry_enabled = not settings.service_expiry_enabled
    
    status = "فعال" if settings.service_expiry_enabled else "غیرفعال"
    await callback.answer(f"اعلان انقضا {status} شد")


@router.callback_query(F.data.startswith("expiry_days:"))
async def set_expiry_days(callback: CallbackQuery):
    days = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
        )).scalar_one()
        
        from models.notifications import NotificationSettings
        settings = (await session.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user.id)
        )).scalar_one_or_none()
        
        if not settings:
            settings = NotificationSettings(user_id=user.id)
            session.add(settings)
        
        settings.service_expiry_days_before = days
    
    await callback.answer(f"اعلان {days} روز قبل از انقضا تنظیم شد")


# Admin notification features
@router.message(Command("process_notifications"))
async def process_notifications(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        async with get_db_session() as session:
            sent_count = await NotificationService.process_pending_notifications(session)
        
        await message.answer(f"✅ {sent_count} اعلان ارسال شد.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در پردازش اعلان‌ها: {str(e)}")


@router.message(Command("check_expiries"))
async def check_expiries(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        async with get_db_session() as session:
            await NotificationService.check_service_expiries(session)
        
        await message.answer("✅ بررسی انقضاهای سرویس تکمیل شد.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در بررسی انقضاها: {str(e)}")


@router.message(Command("check_wallets"))
async def check_wallets(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        async with get_db_session() as session:
            await NotificationService.check_low_wallet_balances(session)
        
        await message.answer("✅ بررسی موجودی‌های کم تکمیل شد.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در بررسی موجودی‌ها: {str(e)}")


@router.message(Command("notification_stats"))
async def notification_stats(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, func
        from models.notifications import Notification
        
        # Get notification statistics
        total_notifications = (await session.execute(
            select(func.count(Notification.id))
        )).scalar()
        
        pending_notifications = (await session.execute(
            select(func.count(Notification.id))
            .where(Notification.status == NotificationStatus.PENDING)
        )).scalar()
        
        sent_today = (await session.execute(
            select(func.count(Notification.id))
            .where(
                and_(
                    Notification.status == NotificationStatus.SENT,
                    Notification.sent_at >= datetime.utcnow().date()
                )
            )
        )).scalar()
        
        failed_notifications = (await session.execute(
            select(func.count(Notification.id))
            .where(Notification.status == NotificationStatus.FAILED)
        )).scalar()
        
        # Get notifications by type
        type_stats = (await session.execute(
            select(Notification.notification_type, func.count(Notification.id))
            .group_by(Notification.notification_type)
            .order_by(func.count(Notification.id).desc())
        )).all()
    
    stats_text = f"""
📊 آمار اعلان‌ها:

📈 کلی:
• کل اعلان‌ها: {total_notifications}
• در انتظار: {pending_notifications}
• ارسال شده امروز: {sent_today}
• ناموفق: {failed_notifications}

📋 بر اساس نوع:
"""
    
    for notification_type, count in type_stats:
        type_names = {
            NotificationType.SERVICE_EXPIRY: "انقضای سرویس",
            NotificationType.SERVICE_EXPIRY_WARNING: "هشدار انقضا",
            NotificationType.WALLET_LOW: "موجودی کم",
            NotificationType.PAYMENT_RECEIVED: "دریافت پرداخت",
            NotificationType.PAYMENT_APPROVED: "تایید پرداخت",
            NotificationType.PAYMENT_REJECTED: "رد پرداخت",
            NotificationType.NEW_SERVICE: "سرویس جدید",
            NotificationType.SERVICE_RENEWED: "تمدید سرویس",
            NotificationType.DISCOUNT_AVAILABLE: "تخفیف موجود",
            NotificationType.CASHBACK_EARNED: "کش‌بک",
            NotificationType.REFERRAL_BONUS: "پاداش معرفی",
            NotificationType.TRIAL_APPROVED: "تایید تست",
            NotificationType.TRIAL_EXPIRED: "انقضای تست",
            NotificationType.RESELLER_APPROVED: "تایید نمایندگی",
            NotificationType.SYSTEM_MAINTENANCE: "تعمیرات سیستم",
            NotificationType.SECURITY_ALERT: "هشدار امنیتی"
        }
        type_name = type_names.get(notification_type, notification_type)
        stats_text += f"• {type_name}: {count}\n"
    
    await message.answer(stats_text)


@router.message(Command("send_broadcast"))
async def send_broadcast_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract message from command
    command_parts = message.text.split(" ", 1)
    if len(command_parts) < 2:
        await message.answer("فرمت: /send_broadcast <پیام>")
        return
    
    broadcast_message = command_parts[1]
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            
            # Get all active users
            users = (await session.execute(
                select(TelegramUser).where(TelegramUser.is_blocked == False)
            )).scalars().all()
            
            sent_count = 0
            failed_count = 0
            
            for user in users:
                try:
                    await NotificationService.send_notification(
                        session=session,
                        user_id=user.id,
                        notification_type=NotificationType.SYSTEM_MAINTENANCE,
                        title="📢 اطلاعیه سیستم",
                        message=broadcast_message,
                        priority=1
                    )
                    sent_count += 1
                except Exception:
                    failed_count += 1
        
        await message.answer(f"✅ پیام همگانی ارسال شد.\n"
                           f"ارسال شده: {sent_count}\n"
                           f"ناموفق: {failed_count}")
        
    except Exception as e:
        await message.answer(f"❌ خطا در ارسال پیام همگانی: {str(e)}")


@router.message(Command("notification_help"))
async def notification_help(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    help_text = """
🔔 راهنمای سیستم اعلان‌ها:

👤 دستورات کاربری:
• /notifications - مشاهده اعلان‌ها
• /notification_settings - تنظیمات اعلان‌ها

🔧 دستورات ادمین:
• /process_notifications - پردازش اعلان‌های در انتظار
• /check_expiries - بررسی انقضاهای سرویس
• /check_wallets - بررسی موجودی‌های کم
• /notification_stats - آمار اعلان‌ها
• /send_broadcast <پیام> - ارسال پیام همگانی

⏰ اعلان‌های خودکار:
• انقضای سرویس (قابل تنظیم)
• موجودی کم کیف پول
• تایید/رد پرداخت‌ها
• تخفیف‌های جدید
• کش‌بک‌ها
• پاداش‌های معرفی

⚙️ ویژگی‌ها:
• ساعت سکوت (عدم ارسال در ساعات خاص)
• محدودیت تعداد اعلان روزانه
• فاصله زمانی بین اعلان‌ها
• تنظیمات شخصی‌سازی شده
• ردیابی وضعیت ارسال
"""
    
    await message.answer(help_text)