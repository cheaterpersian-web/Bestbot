from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from services.backup_service import backup_service


router = Router(name="backup")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


@router.message(Command("backup_status"))
async def backup_status(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        status = await backup_service.get_backup_status()
        
        status_text = f"""
💾 وضعیت سیستم پشتیبان‌گیری:

📊 آمار کلی:
• کل پشتیبان‌ها: {status['total_backups']}
• حجم کل: {status['total_size_mb']} مگابایت
• مسیر پشتیبان: {status['backup_directory']}

📁 تعداد پشتیبان‌ها:
"""
        
        for backup_type, count in status['backup_counts'].items():
            type_names = {
                "daily": "روزانه",
                "weekly": "هفتگی", 
                "monthly": "ماهانه",
                "manual": "دستی"
            }
            type_name = type_names.get(backup_type, backup_type)
            status_text += f"• {type_name}: {count}\n"
        
        if status['latest_backup']:
            latest = status['latest_backup']
            created_at = datetime.fromisoformat(latest['created_at']).strftime('%Y/%m/%d %H:%M')
            status_text += f"\n🕐 آخرین پشتیبان:\n"
            status_text += f"• فایل: {latest['file_name']}\n"
            status_text += f"• نوع: {latest['backup_type']}\n"
            status_text += f"• تاریخ: {created_at}\n"
            status_text += f"• حجم: {round(latest['file_size'] / (1024 * 1024), 2)} مگابایت"
        
        await message.answer(status_text)
        
    except Exception as e:
        await message.answer(f"خطا در دریافت وضعیت پشتیبان: {str(e)}")


@router.message(Command("create_backup"))
async def create_backup(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract backup type from command
    command_parts = message.text.split()
    backup_type = "manual"
    
    if len(command_parts) > 1:
        backup_type = command_parts[1].lower()
        if backup_type not in ["daily", "weekly", "monthly", "manual"]:
            backup_type = "manual"
    
    try:
        await message.answer("🔄 در حال ایجاد پشتیبان...")
        
        backup_path = await backup_service.create_database_backup(backup_type, compress=True)
        
        # Get file size
        from pathlib import Path
        file_size = Path(backup_path).stat().st_size
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        type_names = {
            "daily": "روزانه",
            "weekly": "هفتگی",
            "monthly": "ماهانه", 
            "manual": "دستی"
        }
        type_name = type_names.get(backup_type, backup_type)
        
        await message.answer(f"✅ پشتیبان {type_name} با موفقیت ایجاد شد!\n"
                           f"📁 فایل: {Path(backup_path).name}\n"
                           f"📊 حجم: {file_size_mb} مگابایت")
        
    except Exception as e:
        await message.answer(f"❌ خطا در ایجاد پشتیبان: {str(e)}")


@router.message(Command("list_backups"))
async def list_backups(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        # Extract backup type filter from command
        command_parts = message.text.split()
        backup_type_filter = None
        
        if len(command_parts) > 1:
            backup_type_filter = command_parts[1].lower()
            if backup_type_filter not in ["daily", "weekly", "monthly", "manual"]:
                backup_type_filter = None
        
        backups = await backup_service.list_backups(backup_type_filter)
        
        if not backups:
            filter_text = f" از نوع {backup_type_filter}" if backup_type_filter else ""
            await message.answer(f"هیچ پشتیبانی{filter_text} یافت نشد.")
            return
        
        # Limit to 20 most recent backups
        backups = backups[:20]
        
        backups_text = f"📋 لیست پشتیبان‌ها:\n\n"
        
        type_names = {
            "daily": "روزانه",
            "weekly": "هفتگی",
            "monthly": "ماهانه",
            "manual": "دستی"
        }
        
        for i, backup in enumerate(backups, 1):
            created_at = datetime.fromisoformat(backup['created_at']).strftime('%Y/%m/%d %H:%M')
            type_name = type_names.get(backup['backup_type'], backup['backup_type'])
            file_size_mb = round(backup['file_size'] / (1024 * 1024), 2)
            compressed = "🗜️" if backup['compressed'] else "📄"
            
            backups_text += f"{i}. {compressed} {backup['file_name']}\n"
            backups_text += f"   نوع: {type_name}\n"
            backups_text += f"   تاریخ: {created_at}\n"
            backups_text += f"   حجم: {file_size_mb} مگابایت\n\n"
        
        if len(backups) == 20:
            backups_text += "... (نمایش 20 مورد از جدیدترین‌ها)"
        
        await message.answer(backups_text)
        
    except Exception as e:
        await message.answer(f"خطا در دریافت لیست پشتیبان‌ها: {str(e)}")


@router.message(Command("restore_backup"))
async def restore_backup_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        backups = await backup_service.list_backups()
        
        if not backups:
            await message.answer("هیچ پشتیبانی برای بازیابی یافت نشد.")
            return
        
        # Show recent backups for selection
        recent_backups = backups[:10]
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"📄 {backup['file_name'][:30]}...",
                callback_data=f"restore_backup:{backup['file_path']}"
            )]
            for backup in recent_backups
        ])
        
        await message.answer("⚠️ هشدار: بازیابی پشتیبان تمام داده‌های فعلی را جایگزین می‌کند!\n\n"
                           "پشتیبانی را برای بازیابی انتخاب کنید:", reply_markup=kb)
        
    except Exception as e:
        await message.answer(f"خطا در دریافت لیست پشتیبان‌ها: {str(e)}")


@router.callback_query(F.data.startswith("restore_backup:"))
async def restore_backup_confirm(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    backup_path = callback.data.split(":", 1)[1]
    
    # Show confirmation
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید بازیابی", callback_data=f"confirm_restore:{backup_path}")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="cancel_restore")]
    ])
    
    await callback.message.edit_text(
        f"⚠️ تایید نهایی بازیابی\n\n"
        f"فایل: {backup_path}\n\n"
        f"این عمل غیرقابل بازگشت است و تمام داده‌های فعلی را جایگزین می‌کند.\n"
        f"آیا مطمئن هستید؟",
        reply_markup=kb
    )
    
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_restore:"))
async def restore_backup_execute(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    backup_path = callback.data.split(":", 1)[1]
    
    try:
        await callback.message.edit_text("🔄 در حال بازیابی پشتیبان...")
        
        success = await backup_service.restore_database_backup(backup_path)
        
        if success:
            await callback.message.edit_text("✅ پشتیبان با موفقیت بازیابی شد!")
        else:
            await callback.message.edit_text("❌ خطا در بازیابی پشتیبان")
        
    except Exception as e:
        await callback.message.edit_text(f"❌ خطا در بازیابی پشتیبان: {str(e)}")
    
    await callback.answer()


@router.callback_query(F.data == "cancel_restore")
async def cancel_restore(callback: CallbackQuery):
    await callback.message.edit_text("❌ بازیابی لغو شد.")
    await callback.answer()


@router.message(Command("cleanup_backups"))
async def cleanup_backups(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        await message.answer("🧹 در حال پاک‌سازی پشتیبان‌های قدیمی...")
        
        # Default retention policy
        retention_policy = {
            "daily": 7,    # Keep daily backups for 7 days
            "weekly": 4,   # Keep weekly backups for 4 weeks
            "monthly": 12, # Keep monthly backups for 12 months
            "manual": 30   # Keep manual backups for 30 days
        }
        
        await backup_service.cleanup_old_backups(retention_policy)
        
        await message.answer("✅ پاک‌سازی پشتیبان‌های قدیمی تکمیل شد.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در پاک‌سازی: {str(e)}")


@router.message(Command("backup_help"))
async def backup_help(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    help_text = """
💾 راهنمای سیستم پشتیبان‌گیری:

📋 دستورات موجود:
• /backup_status - وضعیت سیستم پشتیبان‌گیری
• /create_backup [type] - ایجاد پشتیبان جدید
• /list_backups [type] - لیست پشتیبان‌ها
• /restore_backup - بازیابی پشتیبان
• /cleanup_backups - پاک‌سازی پشتیبان‌های قدیمی

📁 انواع پشتیبان:
• daily - پشتیبان روزانه
• weekly - پشتیبان هفتگی
• monthly - پشتیبان ماهانه
• manual - پشتیبان دستی

⏰ پشتیبان‌گیری خودکار:
• روزانه: ساعت 2 صبح
• هفتگی: یکشنبه ساعت 3 صبح
• ماهانه: روز اول ماه ساعت 4 صبح
• پاک‌سازی: روزانه ساعت 5 صبح

📊 سیاست نگهداری:
• روزانه: 7 روز
• هفتگی: 4 هفته
• ماهانه: 12 ماه
• دستی: 30 روز

⚠️ نکات مهم:
• پشتیبان‌ها به صورت فشرده ذخیره می‌شوند
• بازیابی پشتیبان تمام داده‌های فعلی را جایگزین می‌کند
• همیشه قبل از بازیابی، پشتیبان جدیدی ایجاد کنید
"""
    
    await message.answer(help_text)


@router.message(Command("test_backup"))
async def test_backup(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        await message.answer("🧪 در حال تست سیستم پشتیبان‌گیری...")
        
        # Create a test backup
        backup_path = await backup_service.create_database_backup("manual", compress=True)
        
        # Get file info
        from pathlib import Path
        file_size = Path(backup_path).stat().st_size
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        await message.answer(f"✅ تست پشتیبان‌گیری موفق!\n"
                           f"📁 فایل تست: {Path(backup_path).name}\n"
                           f"📊 حجم: {file_size_mb} مگابایت\n\n"
                           f"💡 سیستم پشتیبان‌گیری به درستی کار می‌کند.")
        
    except Exception as e:
        await message.answer(f"❌ تست پشتیبان‌گیری ناموفق: {str(e)}")


# Scheduled backup task (to be called by cron or scheduler)
@router.message(Command("run_scheduled_backups"))
async def run_scheduled_backups(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        await message.answer("⏰ در حال اجرای پشتیبان‌گیری‌های زمان‌بندی شده...")
        
        await backup_service.schedule_automatic_backups()
        
        await message.answer("✅ پشتیبان‌گیری‌های زمان‌بندی شده اجرا شد.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در اجرای پشتیبان‌گیری‌های زمان‌بندی شده: {str(e)}")