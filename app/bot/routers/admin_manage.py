from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from core.config import settings
from core.db import get_db_session
from models.catalog import Server, Category, Plan
from bot.inline import admin_manage_servers_kb
from models.user import TelegramUser


router = Router(name="admin_manage")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


class AddServerStates(StatesGroup):
    waiting_name = State()
    waiting_base_url = State()
    waiting_api_key = State()
    waiting_panel_type = State()


@router.message(Command("add_server"))
async def add_server_start(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    await message.answer("نام سرور را وارد کنید")
    await state.set_state(AddServerStates.waiting_name)


@router.message(AddServerStates.waiting_name)
async def add_server_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("آدرس API سرور (base_url) را وارد کنید")
    await state.set_state(AddServerStates.waiting_base_url)


@router.message(AddServerStates.waiting_base_url)
async def add_server_base_url(message: Message, state: FSMContext):
    await state.update_data(base_url=message.text.strip())
    await message.answer("API Key را وارد کنید")
    await state.set_state(AddServerStates.waiting_api_key)


@router.message(AddServerStates.waiting_api_key)
async def add_server_api_key(message: Message, state: FSMContext):
    await state.update_data(api_key=message.text.strip())
    await message.answer("نوع پنل (mock/xui/3xui/hiddify)")
    await state.set_state(AddServerStates.waiting_panel_type)


@router.message(AddServerStates.waiting_panel_type)
async def add_server_panel_type(message: Message, state: FSMContext):
    data = await state.get_data()
    panel_type = message.text.strip().lower()
    if panel_type not in {"mock", "xui", "3xui", "hiddify"}:
        await message.answer("نوع نامعتبر است. یکی از mock/xui/3xui/hiddify")
        return
    async with get_db_session() as session:
        s = Server(
            name=data["name"],
            api_base_url=data["base_url"],
            api_key=data["api_key"],
            panel_type=panel_type,
            is_active=True,
        )
        session.add(s)
    await state.clear()
    await message.answer("سرور ثبت شد.")


@router.message(Command("list_servers"))
async def list_servers(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    async with get_db_session() as session:
        from sqlalchemy import select
        servers = (await session.execute(select(Server).order_by(Server.id))).scalars().all()
    if not servers:
        await message.answer("سروری ثبت نشده است.")
        return
    out = [f"#{s.id} - {s.name} ({s.panel_type})" for s in servers]
    await message.answer("\n".join(out))


def servers_inline_kb(servers: list[Server]):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for s in servers:
        rows.append([InlineKeyboardButton(text=f"#{s.id} {s.name}", callback_data=f"adm:server:{s.id}")])
    rows.append([InlineKeyboardButton(text="افزودن سرور جدید", callback_data="adm:server:add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "admin:add_server")
@router.callback_query(F.data == "adm:server:add")
async def cb_add_server(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    await callback.message.answer("نام سرور را وارد کنید")
    await state.set_state(AddServerStates.waiting_name)
    await callback.answer()


@router.callback_query(F.data == "admin:list_servers")
async def cb_list_servers(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    async with get_db_session() as session:
        from sqlalchemy import select
        servers = (await session.execute(select(Server).order_by(Server.sort_order, Server.id))).scalars().all()
    if not servers:
        await callback.message.answer("سروری ثبت نشده است.")
    else:
        await callback.message.answer("لیست سرورها:", reply_markup=servers_inline_kb(servers))
    await callback.answer()


class EditServerStates(StatesGroup):
    waiting_value = State()


def server_actions_kb(server_id: int):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="فعال/غیرفعال", callback_data=f"adm:server:toggle:{server_id}")],
            [InlineKeyboardButton(text="تغییر نام", callback_data=f"adm:server:setname:{server_id}")],
            [InlineKeyboardButton(text="تغییر API URL", callback_data=f"adm:server:seturl:{server_id}")],
            [InlineKeyboardButton(text="تغییر API Key", callback_data=f"adm:server:setkey:{server_id}")],
            [InlineKeyboardButton(text="تغییر نوع پنل", callback_data=f"adm:server:setpanel:{server_id}")],
            [InlineKeyboardButton(text="تعیین Capacity", callback_data=f"adm:server:setcap:{server_id}")],
            [InlineKeyboardButton(text="تغییر sort_order", callback_data=f"adm:server:sort:{server_id}")],
            [InlineKeyboardButton(text="حذف", callback_data=f"adm:server:delete:{server_id}")],
        ]
    )


@router.callback_query(F.data.startswith("adm:server:") & ~F.data.startswith("adm:server:add"))
async def cb_server_item(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    parts = callback.data.split(":")
    if parts[2] in {"toggle", "setname", "seturl", "setkey", "setpanel", "setcap", "sort", "delete"}:
        action = parts[2]
        server_id = int(parts[3])
        async with get_db_session() as session:
            from sqlalchemy import select
            srv = (await session.execute(select(Server).where(Server.id == server_id))).scalar_one_or_none()
            if not srv:
                await callback.answer("یافت نشد", show_alert=True)
                return
            if action == "toggle":
                srv.is_active = not srv.is_active
                await callback.message.answer(f"وضعیت سرور #{server_id} → {'فعال' if srv.is_active else 'غیرفعال'}")
            elif action == "setname":
                await state.update_data(edit_action="setname", server_id=server_id)
                await callback.message.answer("نام جدید را ارسال کنید:")
                await state.set_state(EditServerStates.waiting_value)
                await callback.answer()
                return
            elif action == "seturl":
                await state.update_data(edit_action="seturl", server_id=server_id)
                await callback.message.answer("API URL جدید را ارسال کنید:")
                await state.set_state(EditServerStates.waiting_value)
                await callback.answer()
                return
            elif action == "setkey":
                await state.update_data(edit_action="setkey", server_id=server_id)
                await callback.message.answer("API Key جدید را ارسال کنید:")
                await state.set_state(EditServerStates.waiting_value)
                await callback.answer()
                return
            elif action == "setpanel":
                await state.update_data(edit_action="setpanel", server_id=server_id)
                await callback.message.answer("نوع پنل را وارد کنید (mock/xui/3xui/hiddify):")
                await state.set_state(EditServerStates.waiting_value)
                await callback.answer()
                return
            elif action == "setcap":
                await state.update_data(edit_action="setcap", server_id=server_id)
                await callback.message.answer("ظرفیت (عدد) را وارد کنید؛ 0 برای حذف محدودیت:")
                await state.set_state(EditServerStates.waiting_value)
                await callback.answer()
                return
            elif action == "sort":
                await state.update_data(edit_action="sort", server_id=server_id)
                await callback.message.answer("مقدار sort_order جدید را ارسال کنید (عدد):")
                await state.set_state(EditServerStates.waiting_value)
                await callback.answer()
                return
            elif action == "delete":
                await session.delete(srv)
                await callback.message.answer(f"سرور #{server_id} حذف شد.")
        await callback.answer()
        return
    # view server
    server_id = int(parts[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        srv = (await session.execute(select(Server).where(Server.id == server_id))).scalar_one_or_none()
    if srv:
        details = (
            f"سرور #{srv.id}\n"
            f"نام: {srv.name}\n"
            f"panel: {srv.panel_type}\n"
            f"active: {'بله' if srv.is_active else 'خیر'}\n"
            f"sort_order: {srv.sort_order}\n"
            f"capacity: {srv.capacity_limit or '-'}\n"
            f"api_base_url: {srv.api_base_url}"
        )
        await callback.message.answer(details, reply_markup=server_actions_kb(server_id))
    else:
        await callback.message.answer(f"مدیریت سرور #{server_id}", reply_markup=server_actions_kb(server_id))
    await callback.answer()


@router.message(EditServerStates.waiting_value)
async def edit_server_value(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("edit_action")
    server_id = int(data.get("server_id"))
    val = message.text.strip()
    async with get_db_session() as session:
        from sqlalchemy import select
        srv = (await session.execute(select(Server).where(Server.id == server_id))).scalar_one_or_none()
        if not srv:
            await message.answer("سرور یافت نشد.")
            await state.clear()
            return
        if action == "setname":
            srv.name = val
            await message.answer("نام به‌روزرسانی شد.")
        elif action == "seturl":
            srv.api_base_url = val
            await message.answer("API URL به‌روزرسانی شد.")
        elif action == "setkey":
            srv.api_key = val
            await message.answer("API Key به‌روزرسانی شد.")
        elif action == "setpanel":
            t = val.lower()
            if t not in {"mock", "xui", "3xui", "hiddify"}:
                await message.answer("نوع نامعتبر. یکی از mock/xui/3xui/hiddify")
                return
            srv.panel_type = t
            await message.answer("نوع پنل به‌روزرسانی شد.")
        elif action == "setcap":
            try:
                cap = int(val)
            except Exception:
                await message.answer("عدد نامعتبر.")
                return
            srv.capacity_limit = None if cap == 0 else cap
            await message.answer("Capacity به‌روزرسانی شد.")
        elif action == "sort":
            try:
                order = int(val)
            except Exception:
                await message.answer("عدد نامعتبر.")
                return
            srv.sort_order = order
            await message.answer("sort_order به‌روزرسانی شد.")
    await state.clear()



class AddCategoryStates(StatesGroup):
    waiting_title = State()


@router.message(Command("add_category"))
async def add_category_start(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    await message.answer("عنوان دسته را وارد کنید")
    await state.set_state(AddCategoryStates.waiting_title)


@router.message(AddCategoryStates.waiting_title)
async def add_category_title(message: Message, state: FSMContext):
    async with get_db_session() as session:
        c = Category(title=message.text.strip(), is_active=True)
        session.add(c)
    await state.clear()
    await message.answer("دسته ثبت شد.")


@router.message(Command("list_categories"))
async def list_categories(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    async with get_db_session() as session:
        from sqlalchemy import select
        cats = (await session.execute(select(Category).order_by(Category.sort_order, Category.id))).scalars().all()
    if not cats:
        await message.answer("دسته‌ای ثبت نشده است.")
        return
    out = [f"#{c.id} - {c.title}" for c in cats]
    await message.answer("\n".join(out))


class AddPlanStates(StatesGroup):
    waiting_category_id = State()
    waiting_server_id = State()
    waiting_title = State()
    waiting_price = State()
    waiting_duration = State()
    waiting_traffic = State()


@router.message(Command("add_plan"))
async def add_plan_start(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    await message.answer("ID دسته را وارد کنید (\n/list_categories برای مشاهده)")
    await state.set_state(AddPlanStates.waiting_category_id)


@router.message(AddPlanStates.waiting_category_id, F.text.regexp(r"^\d+$"))
async def add_plan_cat(message: Message, state: FSMContext):
    await state.update_data(category_id=int(message.text))
    await message.answer("ID سرور را وارد کنید (\n/list_servers برای مشاهده)")
    await state.set_state(AddPlanStates.waiting_server_id)


@router.message(AddPlanStates.waiting_server_id, F.text.regexp(r"^\d+$"))
async def add_plan_server(message: Message, state: FSMContext):
    await state.update_data(server_id=int(message.text))
    await message.answer("عنوان پلن را وارد کنید")
    await state.set_state(AddPlanStates.waiting_title)


@router.message(AddPlanStates.waiting_title)
async def add_plan_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("قیمت (تومان) را وارد کنید")
    await state.set_state(AddPlanStates.waiting_price)


@router.message(AddPlanStates.waiting_price, F.text.regexp(r"^\d+$"))
async def add_plan_price(message: Message, state: FSMContext):
    await state.update_data(price_irr=int(message.text))
    await message.answer("مدت (روز) را وارد کنید یا 0 اگر حجمی است")
    await state.set_state(AddPlanStates.waiting_duration)


@router.message(AddPlanStates.waiting_duration, F.text.regexp(r"^\d+$"))
async def add_plan_duration(message: Message, state: FSMContext):
    await state.update_data(duration_days=int(message.text))
    await message.answer("حجم (گیگ) را وارد کنید یا 0 اگر زمانی است")
    await state.set_state(AddPlanStates.waiting_traffic)


@router.message(AddPlanStates.waiting_traffic, F.text.regexp(r"^\d+$"))
async def add_plan_traffic(message: Message, state: FSMContext):
    data = await state.get_data()
    traffic = int(message.text)
    async with get_db_session() as session:
        p = Plan(
            category_id=data["category_id"],
            server_id=data["server_id"],
            title=data["title"],
            price_irr=data["price_irr"],
            duration_days=(None if data["duration_days"] == 0 else data["duration_days"]),
            traffic_gb=(None if traffic == 0 else traffic),
            is_active=True,
        )
        session.add(p)
    await state.clear()
    await message.answer("پلن ثبت شد.")


@router.message(Command("list_plans"))
async def list_plans(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    async with get_db_session() as session:
        from sqlalchemy import select
        plans = (await session.execute(select(Plan).order_by(Plan.id))).scalars().all()
    if not plans:
        await message.answer("پلنی ثبت نشده است.")
        return
    out = []
    for p in plans:
        meta = []
        if p.duration_days:
            meta.append(f"{int(p.duration_days)}روز")
        if p.traffic_gb:
            meta.append(f"{int(p.traffic_gb)}گیگ")
        out.append(f"#{p.id} - {p.title} - {int(p.price_irr):,} ({'،'.join(meta) or 'بدون مشخصه'})")
    await message.answer("\n".join(out))

