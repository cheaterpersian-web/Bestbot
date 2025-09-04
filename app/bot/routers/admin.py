from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, BufferedInputFile

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from models.billing import Transaction
from models.orders import PurchaseIntent
from models.catalog import Plan, Server
from services.purchases import create_service_after_payment
from services.qrcode_gen import generate_qr_with_template
from services.admin_dashboard import AdminDashboardService
from services.payment_processor import PaymentProcessor
from bot.inline import admin_review_tx_kb, admin_manage_servers_kb, admin_manage_categories_kb, admin_manage_plans_kb, admin_transaction_actions_kb, user_profile_actions_kb
from datetime import datetime
from bot.inline import admin_approve_add_service_kb


router = Router(name="admin")


def admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 داشبورد"), KeyboardButton(text="📋 بررسی رسیدها")],
            [KeyboardButton(text="👥 مدیریت کاربران"), KeyboardButton(text="🖥️ مدیریت سرورها")],
            [KeyboardButton(text="📁 مدیریت دسته‌ها"), KeyboardButton(text="📦 مدیریت پلن‌ها")],
            [KeyboardButton(text="🎁 سیستم هدیه"), KeyboardButton(text="📢 پیام همگانی")],
            [KeyboardButton(text="🎫 مدیریت تیکت‌ها"), KeyboardButton(text="⚙️ تنظیمات ربات")],
        ],
        resize_keyboard=True,
        input_field_placeholder="یک گزینه ادمین را انتخاب کنید",
    )


async def _is_admin(telegram_id: int) -> bool:
    # runtime check: settings or DB flag
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        return bool(user and user.is_admin)


@router.message(Command("admin"))
async def admin_entry(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("پنل مدیریت:", reply_markup=admin_kb())


@router.message(F.text == "📊 داشبورد")
async def admin_dashboard(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    
    async with get_db_session() as session:
        stats = await AdminDashboardService.get_dashboard_stats(session)
        recent_activities = await AdminDashboardService.get_recent_activities(session, 5)
    
    # Format dashboard text
    text = f"""
📊 داشبورد مدیریت

👥 کاربران:
• کل کاربران: {stats['users']['total']:,}
• کاربران جدید امروز: {stats['users']['new_today']:,}
• کاربران جدید این هفته: {stats['users']['new_week']:,}
• کاربران جدید این ماه: {stats['users']['new_month']:,}
• کاربران فعال امروز: {stats['users']['active_today']:,}
• کاربران مسدود: {stats['users']['blocked']:,}

🔗 سرویس‌ها:
• کل سرویس‌ها: {stats['services']['total']:,}
• سرویس‌های فعال: {stats['services']['active']:,}
• سرویس‌های جدید امروز: {stats['services']['new_today']:,}

💰 درآمد:
• کل درآمد: {stats['revenue']['total']:,.0f} تومان
• درآمد امروز: {stats['revenue']['today']:,.0f} تومان
• درآمد این هفته: {stats['revenue']['week']:,.0f} تومان
• درآمد این ماه: {stats['revenue']['month']:,.0f} تومان

💳 تراکنش‌ها:
• کل تراکنش‌ها: {stats['transactions']['total']:,}
• تراکنش‌های در انتظار: {stats['transactions']['pending']:,}

🎁 دعوت‌ها:
• کل دعوت‌ها: {stats['referrals']['total']:,}
• پاداش پرداخت شده: {stats['referrals']['bonus_paid']:,.0f} تومان

🎫 پشتیبانی:
• تیکت‌های باز: {stats['support']['open_tickets']:,}
• کل تیکت‌ها: {stats['support']['total_tickets']:,}

🖥️ زیرساخت:
• سرورها: {stats['infrastructure']['servers']['active']}/{stats['infrastructure']['servers']['total']}
• دسته‌ها: {stats['infrastructure']['categories']['active']}/{stats['infrastructure']['categories']['total']}
• پلن‌ها: {stats['infrastructure']['plans']['active']}/{stats['infrastructure']['plans']['total']}
    """.strip()
    
    await message.answer(text)
    
    # Show recent activities
    if recent_activities:
        activities_text = "\n🕐 آخرین فعالیت‌ها:\n"
        for activity in recent_activities:
            timestamp = activity['timestamp'].strftime("%H:%M")
            if activity['type'] == 'new_user':
                data = activity['data']
                activities_text += f"• {timestamp} - کاربر جدید: {data['first_name']} (@{data['username'] or 'بدون نام کاربری'})\n"
            elif activity['type'] == 'transaction':
                data = activity['data']
                activities_text += f"• {timestamp} - تراکنش: {data['amount']:,.0f} تومان ({data['type']})\n"
            elif activity['type'] == 'new_service':
                data = activity['data']
                activities_text += f"• {timestamp} - سرویس جدید: {data['remark']}\n"
        
        await message.answer(activities_text)


@router.message(F.text == "📢 پیام همگانی")
async def admin_broadcast(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("این بخش به‌زودی تکمیل می‌شود.")


@router.message(F.text == "🖥️ مدیریت سرورها")
async def admin_manage_servers(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("مدیریت سرورها:", reply_markup=admin_manage_servers_kb())


@router.message(F.text == "📁 مدیریت دسته‌ها")
async def admin_manage_categories(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("مدیریت دسته‌ها:", reply_markup=admin_manage_categories_kb())


@router.message(F.text == "📦 مدیریت پلن‌ها")
async def admin_manage_plans(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("مدیریت پلن‌ها:", reply_markup=admin_manage_plans_kb())


@router.message(F.text == "👥 مدیریت کاربران")
async def admin_manage_users(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("👥 مدیریت کاربران\n\nبرای مدیریت کاربران، شناسه کاربری (User ID) را ارسال کنید.")


@router.message(F.text.regexp(r"^\d+$"))
async def admin_user_lookup(message: Message):
    """Handle user ID lookup for admin management"""
    if not await _is_admin(message.from_user.id):
        return
    
    user_id = int(message.text)
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_id)
        )).scalar_one_or_none()
        
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            return
        
        # Get user statistics
        user_stats = await AdminDashboardService.get_user_stats(session, user.id)
        
        text = f"""
👤 اطلاعات کاربر

🆔 شناسه: {user.telegram_user_id}
👤 نام: {user.first_name or 'بدون نام'} {user.last_name or ''}
📱 نام کاربری: @{user.username or 'بدون نام کاربری'}
💰 موجودی: {user.wallet_balance:,.0f} تومان
🔒 وضعیت: {'مسدود' if user.is_blocked else 'فعال'}
📅 عضویت: {user.created_at.strftime('%Y/%m/%d')}
🕐 آخرین بازدید: {user.last_seen_at.strftime('%Y/%m/%d %H:%M') if user.last_seen_at else 'هرگز'}

📊 آمار:
🔗 سرویس‌ها: {user_stats['services']['total']} (فعال: {user_stats['services']['active']})
💳 تراکنش‌ها: {user_stats['transactions']['total']}
👥 دعوت‌ها: {user_stats['referrals']['made']}
💰 درآمد از دعوت: {user_stats['referrals']['earnings']:,.0f} تومان
        """.strip()
        
        await message.answer(text, reply_markup=user_profile_actions_kb(user.telegram_user_id))


@router.message(F.text == "🎁 سیستم هدیه")
async def admin_gift_system(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("این بخش به‌زودی تکمیل می‌شود.")


@router.message(F.text == "🎫 مدیریت تیکت‌ها")
async def admin_manage_tickets(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("این بخش به‌زودی تکمیل می‌شود.")


@router.message(F.text == "⚙️ تنظیمات ربات")
async def admin_bot_settings(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("این بخش به‌زودی تکمیل می‌شود.")


@router.message(F.text == "📋 بررسی رسیدها")
async def admin_review_menu(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    async with get_db_session() as session:
        from sqlalchemy import select
        txs = (
            await session.execute(
                select(Transaction).where(
                    Transaction.status == "pending",
                    Transaction.type.in_(["purchase", "wallet_topup"]),
                )
            )
        ).scalars().all()
    if not txs:
        await message.answer("هیچ رسید در انتظاری وجود ندارد.")
        return
    for tx in txs:
        # Get user info for better display
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == tx.user_id)
        )).scalar_one_or_none()
        
        user_info = f"{user.first_name or 'بدون نام'}" if user else f"ID:{tx.user_id}"
        fraud_info = f"\n🚨 Fraud Score: {tx.fraud_score:.2f}" if tx.fraud_score > 0 else ""
        
        caption = f"📋 TX#{tx.id} | نوع: {tx.type} | مبلغ: {int(tx.amount):,} تومان\n👤 کاربر: {user_info} (ID: {tx.user_id}){fraud_info}"
        
        if tx.receipt_image_file_id:
            try:
                await message.answer_photo(photo=tx.receipt_image_file_id, caption=caption, reply_markup=admin_transaction_actions_kb(tx.id))
            except Exception:
                await message.answer(caption, reply_markup=admin_transaction_actions_kb(tx.id))
        else:
            await message.answer(caption, reply_markup=admin_transaction_actions_kb(tx.id))


@router.callback_query(F.data.startswith("admin:approve_tx:"))
async def cb_approve_tx(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    tx_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalar_one_or_none()
        if not tx or tx.status != "pending":
            await callback.answer("یافت نشد/در انتظار نیست", show_alert=True)
            return
        
        admin_db_user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id))
        ).scalar_one_or_none()
        
        # Use payment processor to approve transaction
        success = await PaymentProcessor.approve_transaction(
            session, tx, admin_db_user.id if admin_db_user else callback.from_user.id, "تایید دستی توسط ادمین"
        )
        
        if not success:
            await callback.answer("خطا در تایید تراکنش", show_alert=True)
            return

        created_service = None
        user = None
        if tx.type == "purchase":
            intent = (
                await session.execute(select(PurchaseIntent).where(PurchaseIntent.receipt_transaction_id == tx.id))
            ).scalar_one_or_none()
            if intent:
                plan = (await session.execute(select(Plan).where(Plan.id == intent.plan_id))).scalar_one()
                server = (await session.execute(select(Server).where(Server.id == intent.server_id))).scalar_one()
                user = (await session.execute(select(TelegramUser).where(TelegramUser.id == intent.user_id))).scalar_one()
                intent.status = "paid"
                created_service = await create_service_after_payment(session, user, plan, server, remark=f"u{user.id}-{plan.title}")

    # notify user and update wallet if needed
    if tx.type == "purchase" and created_service and user:
        qr_bytes = generate_qr_with_template(created_service.subscription_url)
        await callback.message.bot.send_message(chat_id=user.telegram_user_id, text="✅ خرید شما تایید شد. لینک اتصال:")
        await callback.message.bot.send_message(chat_id=user.telegram_user_id, text=created_service.subscription_url)
        await callback.message.bot.send_photo(chat_id=user.telegram_user_id, photo=BufferedInputFile(qr_bytes, filename="sub.png"), caption="QR اتصال")
    elif tx.type == "wallet_topup":
        # Wallet balance is already updated by PaymentProcessor
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == tx.user_id))).scalar_one_or_none()
        if user:
            await callback.message.bot.send_message(chat_id=user.telegram_user_id, text=f"✅ شارژ کیف پول تایید شد. مبلغ {int(tx.amount):,} تومان افزوده شد.")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("تایید شد")


@router.callback_query(F.data.startswith("admin:reject_tx:"))
async def cb_reject_tx(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    tx_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalar_one_or_none()
        if not tx or tx.status != "pending":
            await callback.answer("یافت نشد/در انتظار نیست", show_alert=True)
            return
        
        admin_db_user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id))
        ).scalar_one_or_none()
        
        # Use payment processor to reject transaction
        success = await PaymentProcessor.reject_transaction(
            session, tx, admin_db_user.id if admin_db_user else callback.from_user.id, "رد توسط ادمین"
        )
        
        if not success:
            await callback.answer("خطا در رد تراکنش", show_alert=True)
            return
        
        if tx.type == "purchase":
            intent = (
                await session.execute(select(PurchaseIntent).where(PurchaseIntent.receipt_transaction_id == tx.id))
            ).scalar_one_or_none()
            if intent:
                intent.status = "cancelled"
        
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == tx.user_id))).scalar_one_or_none()

    if user:
        await callback.message.bot.send_message(chat_id=user.telegram_user_id, text=f"❌ رسید شما رد شد. لطفاً با پشتیبانی تماس بگیرید.")
    
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("رد شد")


@router.message(Command("pending"))
async def list_pending_receipts(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    async with get_db_session() as session:
        from sqlalchemy import select
        txs = (
            await session.execute(select(Transaction).where(Transaction.type == "purchase_receipt", Transaction.status == "pending"))
        ).scalars().all()
    if not txs:
        await message.answer("رسید در انتظار تایید یافت نشد.")
        return
    for tx in txs:
        await message.answer(
            f"TX#{tx.id} | مبلغ: {int(tx.amount):,} | کاربر: {tx.user_id}\nبرای تایید از دکمه‌های اختصاصی (در نسخه بعد) یا دستورات دستی استفاده کنید."
        )


@router.message(Command("reply_ticket"))
async def admin_reply_ticket(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    # format: /reply_ticket <ticket_id> <text>
    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("فرمت: /reply_ticket <ticket_id> <متن>")
        return
    ticket_id = int(parts[1])
    body = parts[2]
    async with get_db_session() as session:
        from sqlalchemy import select
        t = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
        if not t:
            await message.answer("تیکت یافت نشد.")
            return
        admin_user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one_or_none()
        session.add(TicketMessage(ticket_id=ticket_id, sender_user_id=admin_user.id if admin_user else 0, body=body, by_admin=True))
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == t.user_id))).scalar_one_or_none()
    if user:
        await message.bot.send_message(chat_id=user.telegram_user_id, text=f"پاسخ پشتیبانی: {body}")
    await message.answer("ارسال شد.")


@router.message(Command("close_ticket"))
async def admin_close_ticket(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("فرمت: /close_ticket <ticket_id>")
        return
    ticket_id = int(parts[1])
    async with get_db_session() as session:
        from sqlalchemy import select
        t = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
        if not t:
            await message.answer("تیکت یافت نشد.")
            return
        t.status = "closed"
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == t.user_id))).scalar_one_or_none()
    if user:
        await message.bot.send_message(chat_id=user.telegram_user_id, text=f"تیکت #{ticket_id} بسته شد.")
    await message.answer("بسته شد.")


@router.message(F.text.regexp(r"^/approve_tx\s+\d+$"))
async def approve_tx(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    parts = message.text.strip().split()
    tx_id = int(parts[1])
    async with get_db_session() as session:
        from sqlalchemy import select
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalar_one_or_none()
        if not tx or tx.status != "pending":
            await message.answer("تراکنش معتبر یا در انتظار یافت نشد.")
            return
        admin_db_user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one_or_none()

        tx.status = "approved"
        if admin_db_user:
            tx.approved_by_admin_id = admin_db_user.id
        tx.approved_at = datetime.utcnow()

        # purchase receipt: create service
        created_service = None
        if tx.type == "purchase_receipt":
            intent = (
                await session.execute(select(PurchaseIntent).where(PurchaseIntent.receipt_transaction_id == tx.id))
            ).scalar_one_or_none()
            if intent:
                plan = (await session.execute(select(Plan).where(Plan.id == intent.plan_id))).scalar_one()
                server = (await session.execute(select(Server).where(Server.id == intent.server_id))).scalar_one()
                user = (await session.execute(select(TelegramUser).where(TelegramUser.id == intent.user_id))).scalar_one()
                intent.status = "paid"
                created_service = await create_service_after_payment(session, user, plan, server, remark=f"u{user.id}-{plan.title}")

    # notify user
    if tx.type == "purchase_receipt" and created_service:
        qr_bytes = generate_qr_with_template(created_service.subscription_url)
        await message.bot.send_message(chat_id=user.telegram_user_id, text="خرید شما تایید شد. لینک اتصال:")
        await message.bot.send_message(chat_id=user.telegram_user_id, text=created_service.subscription_url)
        await message.bot.send_photo(chat_id=user.telegram_user_id, photo=BufferedInputFile(qr_bytes, filename="sub.png"), caption="QR اتصال")
        await message.answer(f"TX#{tx_id} تایید شد و سرویس ساخته شد.")
    elif tx.type == "wallet_topup":
        # update wallet balance now that approved
        async with get_db_session() as session:
            from sqlalchemy import select
            me = (await session.execute(select(TelegramUser).where(TelegramUser.id == tx.user_id))).scalar_one_or_none()
            if me:
                me.wallet_balance = (me.wallet_balance or 0) + int(tx.amount)
        if me:
            await message.bot.send_message(chat_id=me.telegram_user_id, text=f"شارژ کیف پول تایید شد. مبلغ {int(tx.amount):,} تومان افزوده شد.")
        await message.answer(f"TX#{tx_id} شارژ کیف تایید شد.")


@router.message(F.text.regexp(r"^/reject_tx\s+\d+(\s+.*)?$"))
async def reject_tx(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    parts = message.text.strip().split(maxsplit=2)
    tx_id = int(parts[1])
    reason = parts[2] if len(parts) > 2 else "رسید نامعتبر"
    async with get_db_session() as session:
        from sqlalchemy import select
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalar_one_or_none()
        if not tx or tx.status != "pending":
            await message.answer("تراکنش معتبر یا در انتظار یافت نشد.")
            return
        tx.status = "rejected"
        if tx.type == "purchase_receipt":
            intent = (
                await session.execute(select(PurchaseIntent).where(PurchaseIntent.receipt_transaction_id == tx.id))
            ).scalar_one_or_none()
            if intent:
                intent.status = "cancelled"
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == tx.user_id))).scalar_one_or_none()

    if user:
        await message.bot.send_message(chat_id=user.telegram_user_id, text=f"رسید شما رد شد. علت: {reason}")
    await message.answer(f"TX#{tx_id} رد شد.")


@router.callback_query(F.data.startswith("admin:approve_addsvc:"))
async def approve_add_service(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    _, _, svc_id_str, tg_user_id_str = callback.data.split(":")
    svc_id = int(svc_id_str)
    tg_user_id = int(tg_user_id_str)
    async with get_db_session() as session:
        from sqlalchemy import select
        svc = (await session.execute(select(Service).where(Service.id == svc_id))).scalar_one_or_none()
        user = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == tg_user_id))).scalar_one_or_none()
        if not svc or not user:
            await callback.answer("یافت نشد", show_alert=True)
            return
        svc.user_id = user.id
    await callback.message.answer(f"سرویس #{svc_id} به کاربر {tg_user_id} منتقل شد.")
    await callback.answer("انجام شد")


@router.callback_query(F.data.startswith("admin:reject_addsvc:"))
async def reject_add_service(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    await callback.message.answer("درخواست انتقال رد شد.")
    await callback.answer("رد شد")


@router.callback_query(F.data.startswith("admin:block_user:"))
async def cb_block_user(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_id)
        )).scalar_one_or_none()
        
        if not user:
            await callback.answer("کاربر یافت نشد", show_alert=True)
            return
        
        user.is_blocked = True
        await session.commit()
    
    await callback.answer("کاربر مسدود شد")
    await callback.message.edit_text(
        callback.message.text + "\n\n🔒 کاربر مسدود شد.",
        reply_markup=user_profile_actions_kb(user_id)
    )


@router.callback_query(F.data.startswith("admin:unblock_user:"))
async def cb_unblock_user(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_id)
        )).scalar_one_or_none()
        
        if not user:
            await callback.answer("کاربر یافت نشد", show_alert=True)
            return
        
        user.is_blocked = False
        await session.commit()
    
    await callback.answer("کاربر آزاد شد")
    await callback.message.edit_text(
        callback.message.text + "\n\n🔓 کاربر آزاد شد.",
        reply_markup=user_profile_actions_kb(user_id)
    )


@router.callback_query(F.data.startswith("admin:user_stats:"))
async def cb_user_stats(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_id)
        )).scalar_one_or_none()
        
        if not user:
            await callback.answer("کاربر یافت نشد", show_alert=True)
            return
        
        user_stats = await AdminDashboardService.get_user_stats(session, user.id)
        
        # Get detailed transaction history
        transactions = (await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
            .limit(10)
        )).scalars().all()
        
        stats_text = f"""
📊 آمار تفصیلی کاربر {user.first_name or 'بدون نام'}

💰 موجودی فعلی: {user.wallet_balance:,.0f} تومان
🔗 کل سرویس‌ها: {user_stats['services']['total']}
🔗 سرویس‌های فعال: {user_stats['services']['active']}
💳 کل تراکنش‌ها: {user_stats['transactions']['total']}
👥 دعوت‌ها: {user_stats['referrals']['made']}
💰 درآمد از دعوت: {user_stats['referrals']['earnings']:,.0f} تومان

📝 آخرین تراکنش‌ها:
        """.strip()
        
        for tx in transactions:
            status_emoji = "✅" if tx.status == "approved" else "⏳" if tx.status == "pending" else "❌"
            date_str = tx.created_at.strftime("%m/%d %H:%M")
            stats_text += f"\n{status_emoji} {tx.amount:,.0f} تومان - {tx.type} ({date_str})"
    
    await callback.message.answer(stats_text)


