from aiogram import Router, F
from aiogram.types import Message

from core.db import get_db_session
from models.tutorials import Tutorial


router = Router(name="tutorials")


@router.message(F.text == "آموزش اتصال")
async def show_tutorials(message: Message):
    async with get_db_session() as session:
        from sqlalchemy import select
        items = (await session.execute(select(Tutorial).order_by(Tutorial.os_key, Tutorial.id))).scalars().all()
    if not items:
        await message.answer("فعلاً آموزشی ثبت نشده است.")
        return
    out = []
    for t in items:
        line = f"[{t.os_key}] {t.title}"
        if t.link_url:
            line += f"\n{t.link_url}"
        if t.text_content:
            line += f"\n{t.text_content[:400]}"  # preview
        out.append(line)
    await message.answer("\n\n".join(out))

