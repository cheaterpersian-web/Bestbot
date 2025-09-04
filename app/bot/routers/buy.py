from aiogram import Router, F
from aiogram.types import Message

from core.db import get_db_session
from models.catalog import Category, Plan, Server


router = Router(name="buy")


@router.message(F.text == "خرید جدید")
async def buy_entry(message: Message):
    # For MVP, just list active categories as text
    async with get_db_session() as session:
        from sqlalchemy import select
        cats = (await session.execute(select(Category).where(Category.is_active == True).order_by(Category.sort_order))).scalars().all()
    if not cats:
        await message.answer("در حال حاضر دسته‌بندی فعالی وجود ندارد.")
        return
    text = "دسته‌بندی‌ها:\n" + "\n".join([f"- {c.title}" for c in cats]) + "\nبه‌زودی انتخاب سرور و پلن اضافه می‌شود."
    await message.answer(text)

