from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from models.anti_fraud import FraudType, FraudSeverity, FraudAction
from services.anti_fraud_service import AntiFraudService


router = Router(name="anti_fraud")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


# Admin anti-fraud features
@router.message(Command("fraud_dashboard"))
async def fraud_dashboard(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        analytics = await AntiFraudService.get_fraud_analytics(session)
    
    dashboard_text = f"""
🛡️ داشبورد ضد کلاهبرداری:

📊 آمار کلی:
• کل تشخیص‌ها: {analytics['total_detections']}
• تشخیص‌های با شدت بالا: {analytics['high_severity_detections']}

🔍 بر اساس نوع:
"""
    
    type_names = {
        FraudType.FAKE_RECEIPT: "رسید جعلی",
        FraudType.DUPLICATE_PAYMENT: "پرداخت تکراری",
        FraudType.SUSPICIOUS_PATTERN: "الگوی مشکوک",
        FraudType.HIGH_FREQUENCY: "فرکانس بالا",
        FraudType.UNUSUAL_AMOUNT: "مبلغ غیرعادی",
        FraudType.MULTIPLE_ACCOUNTS: "چندین حساب",
        FraudType.CHARGEBACK: "برگشت وجه",
        FraudType.REFUND_ABUSE: "سوء استفاده از بازپرداخت",
        FraudType.ACCOUNT_TAKEOVER: "تصاحب حساب",
        FraudType.BOT_ACTIVITY: "فعالیت ربات"
    }
    
    for fraud_type, count in analytics["type_stats"].items():
        type_name = type_names.get(fraud_type, fraud_type.value)
        dashboard_text += f"• {type_name}: {count}\n"
    
    dashboard_text += f"\n⚠️ بر اساس شدت:\n"
    severity_names = {
        FraudSeverity.LOW: "کم",
        FraudSeverity.MEDIUM: "متوسط",
        FraudSeverity.HIGH: "بالا",
        FraudSeverity.CRITICAL: "بحرانی"
    }
    
    for severity, count in analytics["severity_stats"].items():
        severity_name = severity_names.get(severity, severity.value)
        dashboard_text += f"• {severity_name}: {count}\n"
    
    await message.answer(dashboard_text)


@router.message(Command("recent_fraud_detections"))
async def recent_fraud_detections(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, desc
        from models.anti_fraud import FraudDetection
        
        recent_detections = (await session.execute(
            select(FraudDetection, TelegramUser)
            .join(TelegramUser, FraudDetection.user_id == TelegramUser.id)
            .order_by(desc(FraudDetection.detected_at))
            .limit(10)
        )).all()
    
    if not recent_detections:
        await message.answer("هیچ تشخیص کلاهبرداری اخیری یافت نشد.")
        return
    
    detections_text = "🔍 آخرین تشخیص‌های کلاهبرداری:\n\n"
    
    severity_emojis = {
        FraudSeverity.LOW: "🟢",
        FraudSeverity.MEDIUM: "🟡",
        FraudSeverity.HIGH: "🟠",
        FraudSeverity.CRITICAL: "🔴"
    }
    
    type_names = {
        FraudType.FAKE_RECEIPT: "رسید جعلی",
        FraudType.DUPLICATE_PAYMENT: "پرداخت تکراری",
        FraudType.SUSPICIOUS_PATTERN: "الگوی مشکوک",
        FraudType.HIGH_FREQUENCY: "فرکانس بالا",
        FraudType.UNUSUAL_AMOUNT: "مبلغ غیرعادی",
        FraudType.MULTIPLE_ACCOUNTS: "چندین حساب",
        FraudType.CHARGEBACK: "برگشت وجه",
        FraudType.REFUND_ABUSE: "سوء استفاده از بازپرداخت",
        FraudType.ACCOUNT_TAKEOVER: "تصاحب حساب",
        FraudType.BOT_ACTIVITY: "فعالیت ربات"
    }
    
    for i, (detection, user) in enumerate(recent_detections, 1):
        severity_emoji = severity_emojis.get(detection.severity, "❓")
        type_name = type_names.get(detection.fraud_type, detection.fraud_type.value)
        date_str = detection.detected_at.strftime('%m/%d %H:%M')
        
        detections_text += f"{i}. {severity_emoji} {type_name}\n"
        detections_text += f"   کاربر: @{user.username or 'بدون نام کاربری'}\n"
        detections_text += f"   اعتماد: {detection.confidence_score:.1f}\n"
        detections_text += f"   تاریخ: {date_str}\n"
        detections_text += f"   وضعیت: {detection.status}\n\n"
    
    await message.answer(detections_text)


@router.message(Command("fraud_detection_details"))
async def fraud_detection_details(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract detection ID from command
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer("فرمت: /fraud_detection_details <detection_id>")
        return
    
    try:
        detection_id = int(command_parts[1])
    except ValueError:
        await message.answer("شناسه تشخیص نامعتبر است.")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        from models.anti_fraud import FraudDetection
        
        detection = (await session.execute(
            select(FraudDetection, TelegramUser)
            .join(TelegramUser, FraudDetection.user_id == TelegramUser.id)
            .where(FraudDetection.id == detection_id)
        )).first()
        
        if not detection:
            await message.answer("تشخیص یافت نشد.")
            return
        
        detection, user = detection
    
    severity_emojis = {
        FraudSeverity.LOW: "🟢",
        FraudSeverity.MEDIUM: "🟡",
        FraudSeverity.HIGH: "🟠",
        FraudSeverity.CRITICAL: "🔴"
    }
    
    type_names = {
        FraudType.FAKE_RECEIPT: "رسید جعلی",
        FraudType.DUPLICATE_PAYMENT: "پرداخت تکراری",
        FraudType.SUSPICIOUS_PATTERN: "الگوی مشکوک",
        FraudType.HIGH_FREQUENCY: "فرکانس بالا",
        FraudType.UNUSUAL_AMOUNT: "مبلغ غیرعادی",
        FraudType.MULTIPLE_ACCOUNTS: "چندین حساب",
        FraudType.CHARGEBACK: "برگشت وجه",
        FraudType.REFUND_ABUSE: "سوء استفاده از بازپرداخت",
        FraudType.ACCOUNT_TAKEOVER: "تصاحب حساب",
        FraudType.BOT_ACTIVITY: "فعالیت ربات"
    }
    
    severity_emoji = severity_emojis.get(detection.severity, "❓")
    type_name = type_names.get(detection.fraud_type, detection.fraud_type.value)
    
    details_text = f"""
🔍 جزئیات تشخیص کلاهبرداری:

{severity_emoji} نوع: {type_name}
📊 شدت: {detection.severity.value}
🎯 اعتماد: {detection.confidence_score:.2f}
📅 تاریخ: {detection.detected_at.strftime('%Y/%m/%d %H:%M')}

👤 کاربر:
• شناسه: {user.telegram_user_id}
• نام کاربری: @{user.username or 'ندارد'}
• نام: {user.first_name} {user.last_name or ''}

📝 توضیحات:
{detection.description}

🔍 شواهد:
{detection.evidence}

📊 وضعیت: {detection.status}
🎬 اقدام انجام شده: {detection.action_taken or 'هیچ'}
"""
    
    if detection.action_details:
        details_text += f"\n📋 جزئیات اقدام:\n{detection.action_details}"
    
    if detection.admin_notes:
        details_text += f"\n📝 یادداشت ادمین:\n{detection.admin_notes}"
    
    await message.answer(details_text)


@router.message(Command("blacklist_user"))
async def blacklist_user_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract user ID from command
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer("فرمت: /blacklist_user <user_id>")
        return
    
    try:
        user_id = int(command_parts[1])
    except ValueError:
        await message.answer("شناسه کاربر نامعتبر است.")
        return
    
    # Show fraud types for selection
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="رسید جعلی", callback_data=f"blacklist_type:{user_id}:fake_receipt")],
        [InlineKeyboardButton(text="پرداخت تکراری", callback_data=f"blacklist_type:{user_id}:duplicate_payment")],
        [InlineKeyboardButton(text="الگوی مشکوک", callback_data=f"blacklist_type:{user_id}:suspicious_pattern")],
        [InlineKeyboardButton(text="فرکانس بالا", callback_data=f"blacklist_type:{user_id}:high_frequency")],
        [InlineKeyboardButton(text="مبلغ غیرعادی", callback_data=f"blacklist_type:{user_id}:unusual_amount")],
        [InlineKeyboardButton(text="چندین حساب", callback_data=f"blacklist_type:{user_id}:multiple_accounts")]
    ])
    
    await message.answer("نوع کلاهبرداری را انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("blacklist_type:"))
async def blacklist_user_type(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    parts = callback.data.split(":")
    user_id = int(parts[1])
    fraud_type = parts[2]
    
    # Show severity levels
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 کم", callback_data=f"blacklist_severity:{user_id}:{fraud_type}:low")],
        [InlineKeyboardButton(text="🟡 متوسط", callback_data=f"blacklist_severity:{user_id}:{fraud_type}:medium")],
        [InlineKeyboardButton(text="🟠 بالا", callback_data=f"blacklist_severity:{user_id}:{fraud_type}:high")],
        [InlineKeyboardButton(text="🔴 بحرانی", callback_data=f"blacklist_severity:{user_id}:{fraud_type}:critical")]
    ])
    
    await callback.message.edit_text("سطح شدت را انتخاب کنید:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("blacklist_severity:"))
async def blacklist_user_severity(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    parts = callback.data.split(":")
    user_id = int(parts[1])
    fraud_type = parts[2]
    severity = parts[3]
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            admin_user = (await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
            )).scalar_one()
            
            blacklist_entry = await AntiFraudService.add_to_blacklist(
                session=session,
                user_id=user_id,
                fraud_type=FraudType(fraud_type),
                severity=FraudSeverity(severity),
                reason="Added to blacklist by admin",
                created_by=admin_user.id
            )
        
        await callback.message.edit_text(f"✅ کاربر به سیاه‌لیست اضافه شد!\n"
                                       f"شناسه: {user_id}\n"
                                       f"نوع: {fraud_type}\n"
                                       f"شدت: {severity}")
        
    except Exception as e:
        await callback.message.edit_text(f"❌ خطا در اضافه کردن به سیاه‌لیست: {str(e)}")
    
    await callback.answer()


@router.message(Command("whitelist_user"))
async def whitelist_user_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract user ID from command
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer("فرمت: /whitelist_user <user_id>")
        return
    
    try:
        user_id = int(command_parts[1])
    except ValueError:
        await message.answer("شناسه کاربر نامعتبر است.")
        return
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            admin_user = (await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
            )).scalar_one()
            
            whitelist_entry = await AntiFraudService.add_to_whitelist(
                session=session,
                user_id=user_id,
                reason="Added to whitelist by admin",
                created_by=admin_user.id
            )
        
        await message.answer(f"✅ کاربر به سفید‌لیست اضافه شد!\nشناسه: {user_id}")
        
    except Exception as e:
        await message.answer(f"❌ خطا در اضافه کردن به سفید‌لیست: {str(e)}")


@router.message(Command("fraud_rules"))
async def fraud_rules(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        from models.anti_fraud import FraudRule
        
        rules = (await session.execute(
            select(FraudRule).order_by(FraudRule.created_at.desc())
        )).scalars().all()
    
    if not rules:
        await message.answer("هیچ قانون ضد کلاهبرداری تعریف نشده است.")
        return
    
    rules_text = "🛡️ قوانین ضد کلاهبرداری:\n\n"
    
    for i, rule in enumerate(rules, 1):
        status = "✅" if rule.is_active else "❌"
        auto_action = "🤖" if rule.auto_action else "👤"
        
        rules_text += f"{i}. {status} {auto_action} {rule.name}\n"
        rules_text += f"   نوع: {rule.fraud_type.value}\n"
        rules_text += f"   شدت: {rule.severity.value}\n"
        rules_text += f"   اقدام: {rule.action.value}\n"
        rules_text += f"   آستانه: {rule.threshold or 'پیش‌فرض'}\n"
        rules_text += f"   فعال شده: {rule.triggered_count} بار\n\n"
    
    await message.answer(rules_text)


@router.message(Command("fraud_alerts"))
async def fraud_alerts(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, desc
        from models.anti_fraud import FraudAlert
        
        alerts = (await session.execute(
            select(FraudAlert)
            .order_by(desc(FraudAlert.created_at))
            .limit(10)
        )).scalars().all()
    
    if not alerts:
        await message.answer("هیچ هشدار کلاهبرداری اخیری یافت نشد.")
        return
    
    alerts_text = "🚨 هشدارهای کلاهبرداری:\n\n"
    
    status_emojis = {
        "pending": "⏳",
        "sent": "📤",
        "acknowledged": "✅",
        "resolved": "🔒"
    }
    
    severity_emojis = {
        FraudSeverity.LOW: "🟢",
        FraudSeverity.MEDIUM: "🟡",
        FraudSeverity.HIGH: "🟠",
        FraudSeverity.CRITICAL: "🔴"
    }
    
    for i, alert in enumerate(alerts, 1):
        status_emoji = status_emojis.get(alert.status, "❓")
        severity_emoji = severity_emojis.get(alert.severity, "❓")
        date_str = alert.created_at.strftime('%m/%d %H:%M')
        
        alerts_text += f"{i}. {status_emoji} {severity_emoji} {alert.message[:50]}...\n"
        alerts_text += f"   تاریخ: {date_str}\n"
        alerts_text += f"   وضعیت: {alert.status}\n\n"
    
    await message.answer(alerts_text)


@router.message(Command("fraud_help"))
async def fraud_help(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    help_text = """
🛡️ راهنمای سیستم ضد کلاهبرداری:

📊 دستورات نظارت:
• /fraud_dashboard - داشبورد ضد کلاهبرداری
• /recent_fraud_detections - آخرین تشخیص‌ها
• /fraud_detection_details <id> - جزئیات تشخیص
• /fraud_rules - قوانین ضد کلاهبرداری
• /fraud_alerts - هشدارهای کلاهبرداری

🔧 دستورات مدیریت:
• /blacklist_user <user_id> - اضافه به سیاه‌لیست
• /whitelist_user <user_id> - اضافه به سفید‌لیست

🔍 انواع کلاهبرداری:
• رسید جعلی - رسیدهای تقلبی
• پرداخت تکراری - پرداخت‌های مکرر
• الگوی مشکوک - رفتارهای غیرعادی
• فرکانس بالا - تراکنش‌های زیاد
• مبلغ غیرعادی - مبالغ غیرمنطقی
• چندین حساب - استفاده از چند حساب

⚠️ سطوح شدت:
• 🟢 کم - هشدار ساده
• 🟡 متوسط - نظارت بیشتر
• 🟠 بالا - اقدام فوری
• 🔴 بحرانی - مسدودسازی

🎬 اقدامات خودکار:
• هشدار - ارسال هشدار به کاربر
• تعلیق - تعلیق موقت حساب
• مسدود - مسدودسازی دائمی
• حذف کانفیگ - غیرفعال کردن سرویس
• بررسی - بررسی دستی

🔧 ویژگی‌ها:
• تشخیص خودکار الگوهای مشکوک
• سیستم امتیازدهی ریسک
• هشدارهای فوری
• سیاه‌لیست و سفید‌لیست
• گزارش‌گیری پیشرفته
• اقدامات خودکار
"""
    
    await message.answer(help_text)