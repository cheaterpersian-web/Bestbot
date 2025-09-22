from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from core.config import settings
from core.db import get_db_session
from models.catalog import Server, Category, Plan
from models.admin import Button
from bot.inline import admin_manage_servers_kb
from models.user import TelegramUser


router = Router(name="admin_manage")


# Utilities: normalize Persian/Arabic digits to ASCII and parse integers safely
_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def _parse_int(text: str) -> int:
    t = (text or "").strip().translate(_DIGIT_TRANSLATION)
    return int(t)


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
    waiting_panel_type = State()
    waiting_api_key = State()
    waiting_auth_mode = State()
    waiting_username = State()
    waiting_password = State()


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
    await message.answer("نوع پنل (mock/xui/3xui/hiddify/sanaei)")
    await state.set_state(AddServerStates.waiting_panel_type)


@router.message(AddServerStates.waiting_api_key)
async def add_server_api_key(message: Message, state: FSMContext):
    await state.update_data(api_key=message.text.strip())
    data = await state.get_data()
    async with get_db_session() as session:
        s = Server(
            name=data["name"],
            api_base_url=data["base_url"],
            api_key=data.get("api_key", ""),
            panel_type=data["panel_type"],
            is_active=True,
        )
        session.add(s)
    await state.clear()
    await message.answer("سرور ثبت شد.")


@router.message(AddServerStates.waiting_panel_type)
async def add_server_panel_type(message: Message, state: FSMContext):
    data = await state.get_data()
    panel_type = message.text.strip().lower()
    allowed = {"mock", "xui", "3xui", "hiddify", "sanaei"}
    if panel_type not in allowed:
        await message.answer("نوع نامعتبر است. یکی از mock/xui/3xui/hiddify/sanaei")
        return
    await state.update_data(panel_type=panel_type)
    # Ask for auth mode for all panel types (3xui/sanaei معمولاً password)
    await message.answer("روش احراز هویت را انتخاب کنید: apikey یا password (برای 3xui/sanaei: password توصیه می‌شود)")
    await state.set_state(AddServerStates.waiting_auth_mode)


@router.message(AddServerStates.waiting_auth_mode)
async def add_server_auth_mode(message: Message, state: FSMContext):
    mode = message.text.strip().lower()
    if mode not in {"apikey", "password"}:
        await message.answer("گزینه نامعتبر. یکی از apikey یا password")
        return
    await state.update_data(auth_mode=mode)
    if mode == "apikey":
        await message.answer("API Key را وارد کنید")
        await state.set_state(AddServerStates.waiting_api_key)
    else:
        await message.answer("نام کاربری پنل را وارد کنید")
        await state.set_state(AddServerStates.waiting_username)


@router.message(AddServerStates.waiting_username)
async def add_server_username(message: Message, state: FSMContext):
    await state.update_data(auth_username=message.text.strip())
    await message.answer("رمز عبور پنل را وارد کنید")
    await state.set_state(AddServerStates.waiting_password)


@router.message(AddServerStates.waiting_password)
async def add_server_password(message: Message, state: FSMContext):
    await state.update_data(auth_password=message.text.strip())
    data = await state.get_data()
    async with get_db_session() as session:
        s = Server(
            name=data["name"],
            api_base_url=data["base_url"],
            api_key="",
            panel_type=data["panel_type"],
            is_active=True,
            auth_mode="password",
            auth_username=data.get("auth_username"),
            auth_password=data.get("auth_password"),
        )
        session.add(s)
    await state.clear()
    await message.answer("سرور با احراز هویت پسوردی ثبت شد.")


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


# ========== Category Management (inline) ==========


class EditCategoryStates(StatesGroup):
    waiting_value = State()


def categories_inline_kb(categories: list[Category]):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for c in categories:
        rows.append([InlineKeyboardButton(text=f"#{c.id} {c.title}", callback_data=f"adm:cat:{c.id}")])
    rows.append([InlineKeyboardButton(text="افزودن دسته", callback_data="admin:add_category")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_actions_kb(category_id: int):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="فعال/غیرفعال", callback_data=f"adm:cat:toggle:{category_id}")],
            [InlineKeyboardButton(text="تغییر عنوان", callback_data=f"adm:cat:settitle:{category_id}")],
            [InlineKeyboardButton(text="تغییر sort_order", callback_data=f"adm:cat:sort:{category_id}")],
            [InlineKeyboardButton(text="حذف", callback_data=f"adm:cat:delete:{category_id}")],
        ]
    )


@router.callback_query(F.data == "admin:list_categories")
async def cb_list_categories(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    async with get_db_session() as session:
        from sqlalchemy import select
        cats = (await session.execute(select(Category).order_by(Category.sort_order, Category.id))).scalars().all()
    if not cats:
        await callback.message.answer("دسته‌ای ثبت نشده است.")
    else:
        await callback.message.answer("لیست دسته‌ها:", reply_markup=categories_inline_kb(cats))
    await callback.answer()


@router.callback_query(F.data == "admin:add_category")
async def cb_add_category(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    await callback.message.answer("عنوان دسته را وارد کنید:")
    await state.set_state(EditCategoryStates.waiting_value)
    await callback.answer()


@router.message(EditCategoryStates.waiting_value)
async def set_category_title(message: Message, state: FSMContext):
    title = message.text.strip()
    async with get_db_session() as session:
        c = Category(title=title, is_active=True)
        session.add(c)
    await state.clear()
    await message.answer("دسته ثبت شد.")


@router.callback_query(F.data.startswith("adm:cat:"))
async def cb_category_actions(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    parts = callback.data.split(":")
    # adm:cat:<id>  or  adm:cat:<action>:<id>
    if len(parts) == 3 and parts[2].isdigit():
        category_id = int(parts[2])
        async with get_db_session() as session:
            from sqlalchemy import select
            c = (await session.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
        if not c:
            await callback.answer("یافت نشد", show_alert=True)
            return
        details = f"دسته #{c.id}\nعنوان: {c.title}\nactive: {'بله' if c.is_active else 'خیر'}\nsort_order: {c.sort_order}"
        await callback.message.answer(details, reply_markup=category_actions_kb(category_id))
        await callback.answer()
        return

    if len(parts) >= 4:
        action = parts[2]
        category_id = int(parts[3])
        async with get_db_session() as session:
            from sqlalchemy import select
            c = (await session.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
            if not c:
                await callback.answer("یافت نشد", show_alert=True)
                return
            if action == "toggle":
                c.is_active = not c.is_active
                await callback.message.answer(f"وضعیت دسته #{category_id} → {'فعال' if c.is_active else 'غیرفعال'}")
            elif action == "settitle":
                await state.update_data(edit_cat_action="settitle", category_id=category_id)
                await callback.message.answer("عنوان جدید را ارسال کنید:")
                await state.set_state(EditCategoryStates.waiting_value)
                await callback.answer()
                return
            elif action == "sort":
                await state.update_data(edit_cat_action="sort", category_id=category_id)
                await callback.message.answer("sort_order جدید (عدد) را ارسال کنید:")
                await state.set_state(EditCategoryStates.waiting_value)
                await callback.answer()
                return
            elif action == "delete":
                await session.delete(c)
                await callback.message.answer(f"دسته #{category_id} حذف شد.")
        await callback.answer()


# Edit category value input reuse
@router.message(EditCategoryStates.waiting_value)
async def edit_category_value(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("edit_cat_action")
    if not action:
        # handled by set_category_title above for add flow
        return
    category_id = int(data.get("category_id"))
    val = message.text.strip()
    async with get_db_session() as session:
        from sqlalchemy import select
        c = (await session.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
        if not c:
            await message.answer("دسته یافت نشد.")
            await state.clear()
            return
        if action == "settitle":
            c.title = val
            await message.answer("عنوان به‌روزرسانی شد.")
        elif action == "sort":
            try:
                order = int(val)
            except Exception:
                await message.answer("عدد نامعتبر.")
                return
            c.sort_order = order
            await message.answer("sort_order به‌روزرسانی شد.")
    await state.clear()


# ========== Plan Management (inline) ==========


class EditPlanInlineStates(StatesGroup):
    waiting_field_value = State()
    context_action = State()


def plans_inline_kb(plans: list[Plan]):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for p in plans:
        rows.append([InlineKeyboardButton(text=f"#{p.id} {p.title}", callback_data=f"adm:plan:{p.id}")])
    rows.append([InlineKeyboardButton(text="افزودن پلن", callback_data="admin:add_plan")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plan_actions_kb(plan_id: int):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="فعال/غیرفعال", callback_data=f"adm:plan:toggle:{plan_id}")],
            [InlineKeyboardButton(text="تغییر عنوان", callback_data=f"adm:plan:settitle:{plan_id}")],
            [InlineKeyboardButton(text="تغییر قیمت", callback_data=f"adm:plan:setprice:{plan_id}")],
            [InlineKeyboardButton(text="تعیین مدت (روز)", callback_data=f"adm:plan:setduration:{plan_id}")],
            [InlineKeyboardButton(text="تعیین حجم (گیگ)", callback_data=f"adm:plan:settraffic:{plan_id}")],
            [InlineKeyboardButton(text="تغییر دسته", callback_data=f"adm:plan:setcategory:{plan_id}")],
            [InlineKeyboardButton(text="تغییر سرور", callback_data=f"adm:plan:setserver:{plan_id}")],
            [InlineKeyboardButton(text="حذف", callback_data=f"adm:plan:delete:{plan_id}")],
        ]
    )


@router.callback_query(F.data == "admin:list_plans")
async def cb_list_plans(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    async with get_db_session() as session:
        from sqlalchemy import select
        plans = (await session.execute(select(Plan).order_by(Plan.id))).scalars().all()
    if not plans:
        await callback.message.answer("پلنی ثبت نشده است.")
    else:
        await callback.message.answer("لیست پلن‌ها:", reply_markup=plans_inline_kb(plans))
    await callback.answer()


@router.callback_query(F.data == "admin:add_plan")
async def cb_add_plan(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    await callback.message.answer("ID دسته را وارد کنید:")
    await state.set_state(AddPlanStates.waiting_category_id)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:plan:"))
async def cb_plan_actions(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    parts = callback.data.split(":")
    # adm:plan:<id>  or  adm:plan:<action>:<id>
    if len(parts) == 3 and parts[2].isdigit():
        plan_id = int(parts[2])
        async with get_db_session() as session:
            from sqlalchemy import select
            p = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
        if not p:
            await callback.answer("یافت نشد", show_alert=True)
            return
        meta = []
        if p.duration_days:
            meta.append(f"{int(p.duration_days)}روز")
        if p.traffic_gb:
            meta.append(f"{int(p.traffic_gb)}گیگ")
        details = f"پلن #{p.id}\n{p.title} - {int(p.price_irr):,}\nactive: {'بله' if p.is_active else 'خیر'}\n{('،'.join(meta) or 'بدون مشخصه')}"
        await callback.message.answer(details, reply_markup=plan_actions_kb(plan_id))
        await callback.answer()
        return

    if len(parts) >= 4:
        action = parts[2]
        plan_id = int(parts[3])
        async with get_db_session() as session:
            from sqlalchemy import select
            p = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
            if not p:
                await callback.answer("یافت نشد", show_alert=True)
                return
            if action == "toggle":
                p.is_active = not p.is_active
                await callback.message.answer(f"وضعیت پلن #{plan_id} → {'فعال' if p.is_active else 'غیرفعال'}")
            elif action in {"settitle", "setprice", "setduration", "settraffic", "setcategory", "setserver"}:
                await state.update_data(edit_plan_action=action, plan_id=plan_id)
                prompts = {
                    "settitle": "عنوان جدید را ارسال کنید:",
                    "setprice": "قیمت جدید (تومان) را ارسال کنید:",
                    "setduration": "مدت (روز) را وارد کنید یا 0 برای حذف:",
                    "settraffic": "حجم (گیگ) را وارد کنید یا 0 برای حذف:",
                    "setcategory": "ID دسته جدید را وارد کنید:",
                    "setserver": "ID سرور جدید را وارد کنید:",
                }
                await callback.message.answer(prompts[action])
                await state.set_state(EditPlanInlineStates.waiting_field_value)
                await callback.answer()
                return
            elif action == "delete":
                await session.delete(p)
                await callback.message.answer(f"پلن #{plan_id} حذف شد.")
        await callback.answer()


@router.message(EditPlanInlineStates.waiting_field_value)
async def edit_plan_value(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("edit_plan_action")
    plan_id = int(data.get("plan_id"))
    val = message.text.strip()
    async with get_db_session() as session:
        from sqlalchemy import select
        p = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
        if not p:
            await message.answer("پلن یافت نشد.")
            await state.clear()
            return
        if action == "settitle":
            p.title = val
            await message.answer("عنوان به‌روزرسانی شد.")
        elif action == "setprice":
            try:
                price = int(val)
            except Exception:
                await message.answer("عدد نامعتبر.")
                return
            p.price_irr = price
            await message.answer("قیمت به‌روزرسانی شد.")
        elif action == "setduration":
            try:
                days = int(val)
            except Exception:
                await message.answer("عدد نامعتبر.")
                return
            p.duration_days = None if days == 0 else days
            await message.answer("مدت به‌روزرسانی شد.")
        elif action == "settraffic":
            try:
                gb = int(val)
            except Exception:
                await message.answer("عدد نامعتبر.")
                return
            p.traffic_gb = None if gb == 0 else gb
            await message.answer("حجم به‌روزرسانی شد.")
        elif action == "setcategory":
            try:
                cat_id = int(val)
            except Exception:
                await message.answer("عدد نامعتبر.")
                return
            p.category_id = cat_id
            await message.answer("دسته پلن تغییر کرد.")
        elif action == "setserver":
            try:
                srv_id = int(val)
            except Exception:
                await message.answer("عدد نامعتبر.")
                return
            p.server_id = srv_id
            await message.answer("سرور پلن تغییر کرد.")
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


@router.message(AddPlanStates.waiting_category_id)
async def add_plan_cat(message: Message, state: FSMContext):
    try:
        await state.update_data(category_id=_parse_int(message.text))
    except Exception:
        await message.answer("عدد نامعتبر.")
        return
    await message.answer("ID سرور را وارد کنید (\n/list_servers برای مشاهده)")
    await state.set_state(AddPlanStates.waiting_server_id)


@router.message(AddPlanStates.waiting_server_id)
async def add_plan_server(message: Message, state: FSMContext):
    try:
        await state.update_data(server_id=_parse_int(message.text))
    except Exception:
        await message.answer("عدد نامعتبر.")
        return
    await message.answer("عنوان پلن را وارد کنید")
    await state.set_state(AddPlanStates.waiting_title)


@router.message(AddPlanStates.waiting_title)
async def add_plan_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("قیمت (تومان) را وارد کنید")
    await state.set_state(AddPlanStates.waiting_price)


@router.message(AddPlanStates.waiting_price)
async def add_plan_price(message: Message, state: FSMContext):
    try:
        await state.update_data(price_irr=_parse_int(message.text))
    except Exception:
        await message.answer("عدد نامعتبر.")
        return
    await message.answer("مدت (روز) را وارد کنید یا 0 اگر حجمی است")
    await state.set_state(AddPlanStates.waiting_duration)


@router.message(AddPlanStates.waiting_duration)
async def add_plan_duration(message: Message, state: FSMContext):
    try:
        await state.update_data(duration_days=_parse_int(message.text))
    except Exception:
        await message.answer("عدد نامعتبر.")
        return
    await message.answer("حجم (گیگ) را وارد کنید یا 0 اگر زمانی است")
    await state.set_state(AddPlanStates.waiting_traffic)


@router.message(AddPlanStates.waiting_traffic)
async def add_plan_traffic(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        # Accept inputs like "10", "۱۰", "10 گیگ", "10GB", with spaces
        cleaned = (message.text or "").strip().translate(_DIGIT_TRANSLATION)
        # remove non-digits at ends
        import re
        m = re.search(r"(\d+)", cleaned)
        if not m:
            raise ValueError
        traffic = int(m.group(1))
    except Exception:
        await message.answer("عدد نامعتبر.")
        return
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


# Button Management System
class AddButtonStates(StatesGroup):
    waiting_key = State()
    waiting_title = State()
    waiting_type = State()
    waiting_content = State()


@router.message(Command("add_button"))
async def add_button_start(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    await message.answer("کلید دکمه را وارد کنید (مثال: price_list)")
    await state.set_state(AddButtonStates.waiting_key)


@router.message(AddButtonStates.waiting_key)
async def add_button_key(message: Message, state: FSMContext):
    key = message.text.strip().lower()
    async with get_db_session() as session:
        from sqlalchemy import select
        existing = (await session.execute(select(Button).where(Button.key == key))).scalar_one_or_none()
        if existing:
            await message.answer("این کلید قبلاً استفاده شده است. کلید دیگری انتخاب کنید.")
            return
    await state.update_data(key=key)
    await message.answer("عنوان دکمه را وارد کنید (مثال: لیست قیمت‌ها)")
    await state.set_state(AddButtonStates.waiting_title)


@router.message(AddButtonStates.waiting_title)
async def add_button_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("نوع دکمه را انتخاب کنید:\n1. link - لینک\n2. text - متن\n3. image - تصویر")
    await state.set_state(AddButtonStates.waiting_type)


@router.message(AddButtonStates.waiting_type)
async def add_button_type(message: Message, state: FSMContext):
    button_type = message.text.strip().lower()
    if button_type not in ["link", "text", "image", "1", "2", "3"]:
        await message.answer("نوع نامعتبر است. یکی از link، text یا image انتخاب کنید.")
        return
    
    # Convert numbers to types
    type_map = {"1": "link", "2": "text", "3": "image"}
    button_type = type_map.get(button_type, button_type)
    
    await state.update_data(type=button_type)
    
    if button_type == "link":
        await message.answer("لینک را وارد کنید (مثال: https://example.com)")
    elif button_type == "text":
        await message.answer("متن را وارد کنید")
    else:  # image
        await message.answer("تصویر را ارسال کنید")
    
    await state.set_state(AddButtonStates.waiting_content)


@router.message(AddButtonStates.waiting_content)
async def add_button_content(message: Message, state: FSMContext):
    data = await state.get_data()
    button_type = data["type"]
    
    if button_type == "image":
        if not message.photo:
            await message.answer("لطفاً یک تصویر ارسال کنید.")
            return
        content = message.photo[-1].file_id  # Get highest resolution
    else:
        content = message.text.strip()
    
    async with get_db_session() as session:
        from sqlalchemy import select
        # Get next sort order
        max_order = (await session.execute(select(Button.sort_order).order_by(Button.sort_order.desc()).limit(1))).scalar_one_or_none()
        next_order = (max_order or 0) + 1
        
        button = Button(
            key=data["key"],
            title=data["title"],
            type=button_type,
            content=content,
            is_active=True,
            sort_order=next_order
        )
        session.add(button)
    
    await state.clear()
    await message.answer("دکمه با موفقیت اضافه شد.")


@router.message(Command("list_buttons"))
async def list_buttons(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        buttons = (await session.execute(select(Button).order_by(Button.sort_order))).scalars().all()
    
    if not buttons:
        await message.answer("دکمه‌ای ثبت نشده است.")
        return
    
    out = []
    for b in buttons:
        status = "✅" if b.is_active else "❌"
        content_preview = b.content[:30] + "..." if len(b.content) > 30 else b.content
        out.append(f"{status} #{b.id} - {b.key} - {b.title} ({b.type})\n   محتوا: {content_preview}")
    
    await message.answer("\n\n".join(out))


@router.message(Command("toggle_button"))
async def toggle_button_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        buttons = (await session.execute(select(Button).order_by(Button.sort_order))).scalars().all()
    
    if not buttons:
        await message.answer("دکمه‌ای ثبت نشده است.")
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'✅' if b.is_active else '❌'} {b.title}", callback_data=f"toggle_button:{b.id}")]
        for b in buttons
    ])
    
    await message.answer("دکمه‌ای را برای تغییر وضعیت انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("toggle_button:"))
async def toggle_button_callback(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    button_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        button = (await session.execute(select(Button).where(Button.id == button_id))).scalar_one_or_none()
        if not button:
            await callback.answer("دکمه یافت نشد")
            return
        
        button.is_active = not button.is_active
    
    await callback.answer(f"وضعیت دکمه {'فعال' if button.is_active else 'غیرفعال'} شد")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.message(Command("delete_button"))
async def delete_button_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        buttons = (await session.execute(select(Button).order_by(Button.sort_order))).scalars().all()
    
    if not buttons:
        await message.answer("دکمه‌ای ثبت نشده است.")
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑️ {b.title}", callback_data=f"delete_button:{b.id}")]
        for b in buttons
    ])
    
    await message.answer("دکمه‌ای را برای حذف انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("delete_button:"))
async def delete_button_callback(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    button_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        button = (await session.execute(select(Button).where(Button.id == button_id))).scalar_one_or_none()
        if not button:
            await callback.answer("دکمه یافت نشد")
            return
        
        await session.delete(button)
    
    await callback.answer("دکمه حذف شد")
    await callback.message.edit_reply_markup(reply_markup=None)

