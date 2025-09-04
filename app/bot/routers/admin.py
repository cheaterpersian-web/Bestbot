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
from bot.inline import admin_review_tx_kb
from datetime import datetime


router = Router(name="admin")


def admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="داشبورد"), KeyboardButton(text="بررسی رسیدها")],
            [KeyboardButton(text="مدیریت سرورها"), KeyboardButton(text="مدیریت دسته‌ها")],
            [KeyboardButton(text="مدیریت پلن‌ها"), KeyboardButton(text="پیام همگانی")],
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


@router.message(lambda m: m.text in {"داشبورد", "مدیریت سرورها", "مدیریت دسته‌ها", "مدیریت پلن‌ها", "پیام همگانی"})
async def admin_placeholders(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("این بخش به‌زودی تکمیل می‌شود.")


@router.message(F.text == "بررسی رسیدها")
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
                    Transaction.type.in_(["purchase_receipt", "wallet_topup"]),
                )
            )
        ).scalars().all()
    if not txs:
        await message.answer("هیچ رسید در انتظاری وجود ندارد.")
        return
    for tx in txs:
        caption = f"TX#{tx.id} | نوع: {tx.type} | مبلغ: {int(tx.amount):,} | کاربر: {tx.user_id}"
        if tx.receipt_image_file_id:
            try:
                await message.answer_photo(photo=tx.receipt_image_file_id, caption=caption, reply_markup=admin_review_tx_kb(tx.id))
            except Exception:
                await message.answer(caption, reply_markup=admin_review_tx_kb(tx.id))
        else:
            await message.answer(caption, reply_markup=admin_review_tx_kb(tx.id))


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
        tx.status = "approved"
        if admin_db_user:
            tx.approved_by_admin_id = admin_db_user.id
        tx.approved_at = datetime.utcnow()

        created_service = None
        user = None
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

    # notify user and update wallet if needed
    if tx.type == "purchase_receipt" and created_service and user:
        qr_bytes = generate_qr_with_template(created_service.subscription_url)
        await callback.message.bot.send_message(chat_id=user.telegram_user_id, text="خرید شما تایید شد. لینک اتصال:")
        await callback.message.bot.send_message(chat_id=user.telegram_user_id, text=created_service.subscription_url)
        await callback.message.bot.send_photo(chat_id=user.telegram_user_id, photo=BufferedInputFile(qr_bytes, filename="sub.png"), caption="QR اتصال")
    elif tx.type == "wallet_topup":
        async with get_db_session() as session:
            from sqlalchemy import select
            me = (await session.execute(select(TelegramUser).where(TelegramUser.id == tx.user_id))).scalar_one_or_none()
            if me:
                me.wallet_balance = (me.wallet_balance or 0) + int(tx.amount)
        if me:
            await callback.message.bot.send_message(chat_id=me.telegram_user_id, text=f"شارژ کیف پول تایید شد. مبلغ {int(tx.amount):,} تومان افزوده شد.")

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
        tx.status = "rejected"
        if tx.type == "purchase_receipt":
            intent = (
                await session.execute(select(PurchaseIntent).where(PurchaseIntent.receipt_transaction_id == tx.id))
            ).scalar_one_or_none()
            if intent:
                intent.status = "cancelled"
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == tx.user_id))).scalar_one_or_none()

    if user:
        await callback.message.bot.send_message(chat_id=user.telegram_user_id, text=f"رسید شما رد شد.")
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


