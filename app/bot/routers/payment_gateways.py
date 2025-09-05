from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from services.payment_gateways import PaymentGatewayManager


router = Router(name="payment_gateways")


class PaymentStates(StatesGroup):
    waiting_amount = State()
    waiting_gateway = State()


@router.message(Command("topup_stars"))
async def topup_stars_start(message: Message, state: FSMContext):
    if not settings.enable_stars:
        await message.answer("پرداخت با Stars غیرفعال است.")
        return
    
    await message.answer("مبلغ شارژ را وارد کنید (تعداد Stars):")
    await state.set_state(PaymentStates.waiting_amount)
    await state.update_data(gateway="stars")


@router.message(Command("topup_zarinpal"))
async def topup_zarinpal_start(message: Message, state: FSMContext):
    if not settings.enable_zarinpal:
        await message.answer("پرداخت با زرین‌پال غیرفعال است.")
        return
    
    await message.answer("مبلغ شارژ را وارد کنید (تومان):")
    await state.set_state(PaymentStates.waiting_amount)
    await state.update_data(gateway="zarinpal")


@router.message(PaymentStates.waiting_amount)
async def process_payment_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            await message.answer("مبلغ باید مثبت باشد.")
            return
    except ValueError:
        await message.answer("لطفاً یک عدد معتبر وارد کنید.")
        return
    
    data = await state.get_data()
    gateway = data["gateway"]
    
    # Validate amount limits
    if gateway == "zarinpal":
        if amount < settings.min_topup_amount:
            await message.answer(f"حداقل مبلغ شارژ {settings.min_topup_amount:,} تومان است.")
            return
        if amount > settings.max_topup_amount:
            await message.answer(f"حداکثر مبلغ شارژ {settings.max_topup_amount:,} تومان است.")
            return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        # Create payment
        payment_result = await PaymentGatewayManager.process_payment(
            session=session,
            user=user,
            amount=amount,
            description=f"شارژ کیف پول - {gateway}",
            gateway=gateway,
            callback_url=f"https://t.me/{settings.bot_username}"
        )
        
        if payment_result and payment_result.get("success"):
            # Create inline keyboard for payment
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="💳 پرداخت",
                    url=payment_result["payment_url"]
                )],
                [InlineKeyboardButton(
                    text="✅ تایید پرداخت",
                    callback_data=f"verify_payment:{payment_result['transaction_id']}"
                )]
            ])
            
            gateway_name = "Stars" if gateway == "stars" else "زرین‌پال"
            await message.answer(
                f"🔗 لینک پرداخت {gateway_name} ایجاد شد:\n\n"
                f"مبلغ: {amount:,} {'Stars' if gateway == 'stars' else 'تومان'}\n"
                f"کد تراکنش: {payment_result['transaction_id']}\n\n"
                f"لطفاً روی دکمه پرداخت کلیک کنید و پس از انجام پرداخت، دکمه تایید را فشار دهید.",
                reply_markup=kb
            )
        else:
            await message.answer("خطا در ایجاد لینک پرداخت. لطفاً دوباره تلاش کنید.")
    
    await state.clear()


@router.callback_query(F.data.startswith("verify_payment:"))
async def verify_payment_callback(callback: CallbackQuery):
    transaction_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        transaction = (await session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )).scalar_one_or_none()
        
        if not transaction:
            await callback.answer("تراکنش یافت نشد")
            return
        
        if transaction.status != "pending":
            if transaction.status == "approved":
                await callback.answer("این پرداخت قبلاً تایید شده است")
            else:
                await callback.answer("این تراکنش نامعتبر است")
            return
        
        # Verify payment based on gateway
        gateway_data = {}
        if transaction.payment_gateway == "zarinpal":
            gateway_data["authority"] = transaction.gateway_transaction_id
        elif transaction.payment_gateway == "stars":
            gateway_data["payment_id"] = transaction.gateway_transaction_id
        
        success = await PaymentGatewayManager.verify_payment(
            session=session,
            transaction_id=transaction_id,
            gateway_data=gateway_data
        )
        
        if success:
            await callback.answer("✅ پرداخت با موفقیت تایید شد!")
            await callback.message.edit_text(
                f"✅ پرداخت شما تایید شد!\n\n"
                f"مبلغ: {transaction.amount:,.0f} {'Stars' if transaction.currency == 'XTR' else 'تومان'}\n"
                f"موجودی جدید: {transaction.user.wallet_balance:,.0f} تومان"
            )
        else:
            await callback.answer("❌ پرداخت تایید نشد. لطفاً دوباره تلاش کنید.")


@router.message(Command("payment_methods"))
async def payment_methods(message: Message):
    """Show available payment methods"""
    
    methods = []
    
    if settings.enable_stars:
        methods.append("⭐ Stars (ارز دیجیتال تلگرام)")
    
    if settings.enable_zarinpal:
        methods.append("🏦 زرین‌پال (درگاه پرداخت ایرانی)")
    
    # Always show card-to-card
    methods.append("💳 کارت به کارت (با ارسال رسید)")
    
    if not methods:
        await message.answer("در حال حاضر روش پرداختی فعال نیست.")
        return
    
    text = "💳 روش‌های پرداخت موجود:\n\n"
    for i, method in enumerate(methods, 1):
        text += f"{i}. {method}\n"
    
    text += "\nبرای شارژ کیف پول از دستورات زیر استفاده کنید:\n"
    if settings.enable_stars:
        text += "• /topup_stars - شارژ با Stars\n"
    if settings.enable_zarinpal:
        text += "• /topup_zarinpal - شارژ با زرین‌پال\n"
    text += "• /wallet - شارژ با کارت به کارت"
    
    await message.answer(text)


# Webhook endpoint for Zarinpal (would be handled by API)
@router.message(Command("zarinpal_webhook"))
async def zarinpal_webhook_handler(message: Message):
    """Handle Zarinpal webhook (for testing purposes)"""
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # This would normally be handled by the API webhook endpoint
    # For testing, we can manually trigger verification
    text = message.text.split(" ", 1)[1] if " " in message.text else ""
    
    if not text:
        await message.answer("فرمت: /zarinpal_webhook AUTHORITY")
        return
    
    authority = text.strip()
    
    async with get_db_session() as session:
        from services.payment_gateways import PaymentWebhookHandler
        success = await PaymentWebhookHandler.handle_zarinpal_webhook(
            session=session,
            authority=authority,
            status="OK"
        )
        
        if success:
            await message.answer(f"✅ پرداخت با کد {authority} تایید شد")
        else:
            await message.answer(f"❌ پرداخت با کد {authority} تایید نشد")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)