from decimal import Decimal

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from bot.inline import categories_kb, plans_kb, pay_options_kb
from core.db import get_db_session
from core.config import settings
from models.catalog import Category, Plan, Server
from models.user import TelegramUser
from models.service import Service
from models.billing import Transaction
from models.orders import PurchaseIntent
from services.purchases import create_service_after_payment
from services.qrcode_gen import generate_qr_with_template
from bot.inline import admin_review_tx_kb


router = Router(name="buy")


class PurchaseStates(StatesGroup):
    waiting_purchase_receipt = State()
    waiting_alias = State()
async def _generate_unique_alias(session, user_id: int, base_alias: str) -> str:
    """Ensure alias is unique for this user by appending -NN if needed."""
    alias = base_alias
    from sqlalchemy import select
    exists = (await session.execute(
        select(Service.id).where(Service.user_id == user_id, Service.remark == alias)
    )).first() is not None
    if not exists:
        return alias
    import random
    tried = set()
    for _ in range(50):
        n = random.randint(10, 99)
        if n in tried:
            continue
        tried.add(n)
        candidate = f"{base_alias}-{n}"
        exists = (await session.execute(
            select(Service.id).where(Service.user_id == user_id, Service.remark == candidate)
        )).first() is not None
        if not exists:
            return candidate
    return f"{base_alias}-99"



def _to_int_money(v) -> int:
    if v is None:
        return 0
    if isinstance(v, Decimal):
        return int(v)
    try:
        return int(v)
    except Exception:
        return int(float(v))


@router.message(F.text == "خرید جدید")
async def buy_entry(message: Message):
    async with get_db_session() as session:
        from sqlalchemy import select
        cats = (
            await session.execute(
                select(Category).where(Category.is_active == True).order_by(Category.sort_order)
            )
        ).scalars().all()
    if not cats:
        await message.answer("در حال حاضر دسته‌بندی فعالی وجود ندارد.")
        return
    items = [(c.id, c.title) for c in cats]
    await message.answer("یک دسته‌بندی را انتخاب کنید:", reply_markup=categories_kb(items))


@router.callback_query(F.data.startswith("buy:cat:"))
async def choose_category(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        plans = (
            await session.execute(
                select(Plan).where(Plan.category_id == cat_id, Plan.is_active == True)
            )
        ).scalars().all()
    if not plans:
        await callback.message.answer("پلنی در این دسته وجود ندارد.")
        await callback.answer()
        return
    items = [(p.id, f"{p.title} - { _to_int_money(p.price_irr):,} تومان") for p in plans]
    await callback.message.answer("یک پلن را انتخاب کنید:", reply_markup=plans_kb(items))
    await callback.answer()


@router.callback_query(F.data.startswith("buy:plan:"))
async def show_plan(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        plan = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
        if not plan:
            await callback.message.answer("پلن یافت نشد.")
            await callback.answer()
            return
        server = (await session.execute(select(Server).where(Server.id == plan.server_id))).scalar_one_or_none()

    price = _to_int_money(plan.price_irr)
    desc = [f"نام پلن: {plan.title}", f"قیمت: {price:,} تومان"]
    if plan.duration_days:
        desc.append(f"مدت: {int(plan.duration_days)} روز")
    if plan.traffic_gb:
        desc.append(f"حجم: {int(plan.traffic_gb)} گیگ")
    if server:
        desc.append(f"سرور: {server.name}")

    await callback.message.answer("\n".join(desc) + "\n\nلطفاً نام سرویس را ارسال کنید (مثلاً milad یا phone).", reply_markup=None)
    await state.update_data(selected_plan_id=plan_id)
    await state.set_state(PurchaseStates.waiting_alias)
    await callback.message.answer("نام سرویس را تایپ کنید و بفرستید.")
    await callback.answer()
@router.message(PurchaseStates.waiting_alias)
async def receive_alias(message: Message, state: FSMContext):
    alias = (message.text or "").strip()
    if not alias:
        await message.answer("نام نامعتبر است. دوباره ارسال کنید.")
        return
    data = await state.get_data()
    plan_id = int(data.get("selected_plan_id"))
    await state.update_data(alias=alias)
    await message.answer("روش پرداخت را انتخاب کنید:", reply_markup=pay_options_kb(plan_id))
    # Store selected plan id from previous step if needed via inline callback; for simplicity, encode plan id in state earlier



@router.callback_query(F.data.startswith("buy:pay_wallet:"))
async def pay_with_wallet(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        plan = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one()
        server = (await session.execute(select(Server).where(Server.id == plan.server_id))).scalar_one()
        me = (
            await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
            )
        ).scalar_one()

        price = _to_int_money(plan.price_irr)
        wallet = _to_int_money(me.wallet_balance)

        if wallet >= price:
            me.wallet_balance = wallet - price
            tx = Transaction(
                user_id=me.id,
                amount=price,
                type="purchase",
                status="approved",
                description=f"Purchase plan #{plan.id} via wallet",
            )
            session.add(tx)

            # build alias/remark and ensure uniqueness
            data = await state.get_data()
            base_alias = (data.get("alias") or f"u{me.id}-{plan.title}").strip()
            alias = await _generate_unique_alias(session, me.id, base_alias)
            service = await create_service_after_payment(session, me, plan, server, remark=alias)
            # commit before sending files
        else:
            # partial wallet deduction + request receipt for remainder
            paid = wallet
            due = price - wallet
            me.wallet_balance = 0
            if paid > 0:
                session.add(
                    Transaction(
                        user_id=me.id,
                        amount=paid,
                        type="purchase",
                        status="approved",
                        description=f"Partial wallet deduction for plan #{plan.id}",
                    )
                )
            intent = PurchaseIntent(
                user_id=me.id,
                plan_id=plan.id,
                server_id=server.id,
                amount_total=price,
                amount_paid_wallet=paid,
                amount_due_receipt=due,
                status="pending",
            )
            session.add(intent)

    if wallet >= price:
        # Generate QR and send
        qr_bytes = generate_qr_with_template(service.subscription_url)
        await callback.message.answer(
            "خرید با موفقیت انجام شد!\nلینک اتصال شما:")
        await callback.message.answer(service.subscription_url)
        await callback.message.answer_photo(
            BufferedInputFile(qr_bytes, filename="sub.png"),
            caption="QR اتصال"
        )
    else:
        await callback.message.answer(
            f"{paid:,} تومان از کیف پول شما کسر شد. لطفاً رسید کارت‌به‌کارت مبلغ باقی‌مانده ({due:,} تومان) را ارسال کنید."
        )
        await state.update_data(purchase_intent_id=intent.id)
        await state.set_state(PurchaseStates.waiting_purchase_receipt)
    await callback.answer()


@router.callback_query(F.data.startswith("buy:pay_receipt:"))
async def start_receipt_flow(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        plan = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one()
        server = (await session.execute(select(Server).where(Server.id == plan.server_id))).scalar_one()
        me = (
            await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
            )
        ).scalar_one()

        price = _to_int_money(plan.price_irr)
        wallet = _to_int_money(me.wallet_balance)
        paid = min(wallet, price)
        due = price - paid
        me.wallet_balance = wallet - paid
        if paid > 0:
            session.add(
                Transaction(
                    user_id=me.id,
                    amount=paid,
                    type="purchase",
                    status="approved",
                    description=f"Partial wallet deduction for plan #{plan.id}",
                )
            )
        # Persist intent with alias for later creation
        data = await state.get_data()
        base_alias = (data.get("alias") or f"u{me.id}-{plan.title}").strip()
        # don't need uniqueness here yet; on approval we'll enforce before creation
        alias = base_alias
        intent = PurchaseIntent(
            user_id=me.id,
            plan_id=plan.id,
            server_id=server.id,
            amount_total=price,
            amount_paid_wallet=paid,
            amount_due_receipt=due,
            status="pending",
            alias=alias,
        )
        session.add(intent)
        await session.flush()
        await state.update_data(purchase_intent_id=intent.id)

    await callback.message.answer(
        f"{paid:,} تومان از کیف پول شما کسر شد. لطفاً رسید کارت‌به‌کارت مبلغ باقی‌مانده ({due:,} تومان) را ارسال کنید."
    )
    await state.set_state(PurchaseStates.waiting_purchase_receipt)
    await callback.answer()


@router.message(PurchaseStates.waiting_purchase_receipt, F.photo)
async def receive_purchase_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    intent_id = data.get("purchase_intent_id")
    file_id = message.photo[-1].file_id

    async with get_db_session() as session:
        from sqlalchemy import select
        intent = (
            await session.execute(select(PurchaseIntent).where(PurchaseIntent.id == intent_id))
        ).scalar_one_or_none()
        if not intent:
            await message.answer("سفارش یافت نشد.")
            await state.clear()
            return
        tx = Transaction(
            user_id=intent.user_id,
            amount=intent.amount_due_receipt,
            type="purchase_receipt",
            status="pending",
            description=f"Receipt for plan #{intent.plan_id}",
            receipt_image_file_id=file_id,
        )
        session.add(tx)
        await session.flush()
        intent.receipt_transaction_id = tx.id

    await state.clear()
    await message.answer("رسید دریافت شد. پس از تایید ادمین، سرویس شما ساخته می‌شود.")
    # notify admins
    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=f"رسید جدید خرید\nTX#{tx.id} | مبلغ: {int(intent.amount_due_receipt):,} | کاربر: {intent.user_id}",
                reply_markup=admin_review_tx_kb(tx.id),
            )
        except Exception:
            await message.bot.send_message(
                chat_id=admin_id,
                text=f"رسید جدید خرید\nTX#{tx.id} | مبلغ: {int(intent.amount_due_receipt):,} | کاربر: {intent.user_id}",
                reply_markup=admin_review_tx_kb(tx.id),
            )

