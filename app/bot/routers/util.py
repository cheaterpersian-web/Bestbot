from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


router = Router(name="util")


@router.message(Command("id"))
async def show_id(message: Message):
    await message.answer(f"آیدی شما: <code>{message.from_user.id}</code>")

