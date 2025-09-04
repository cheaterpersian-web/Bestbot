from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import main_menu_kb


router = Router(name="user_main")


@router.message(Command(commands=["menu"]))
async def show_menu(message: Message):
    await message.answer("منوی اصلی:", reply_markup=main_menu_kb())

