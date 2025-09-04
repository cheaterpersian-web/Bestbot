from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def categories_kb(items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = []
    for cid, title in items:
        rows.append([InlineKeyboardButton(text=title, callback_data=f"buy:cat:{cid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plans_kb(items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = []
    for pid, title in items:
        rows.append([InlineKeyboardButton(text=title, callback_data=f"buy:plan:{pid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pay_options_kb(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="پرداخت از کیف پول", callback_data=f"buy:pay_wallet:{plan_id}")],
            [InlineKeyboardButton(text="ارسال رسید کارت‌به‌کارت", callback_data=f"buy:pay_receipt:{plan_id}")],
        ]
    )


def admin_review_kb(tx_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="تایید", callback_data=f"admin:approve_purchase:{tx_id}"),
                InlineKeyboardButton(text="رد", callback_data=f"admin:reject_purchase:{tx_id}"),
            ]
        ]
    )


def admin_review_tx_kb(tx_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="تایید", callback_data=f"admin:approve_tx:{tx_id}"),
                InlineKeyboardButton(text="رد", callback_data=f"admin:reject_tx:{tx_id}"),
            ]
        ]
    )


def request_add_service_kb(svc_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="درخواست افزودن به حساب", callback_data=f"lookup:reqadd:{svc_id}")]
        ]
    )


def admin_approve_add_service_kb(svc_id: int, tg_user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="تایید انتقال", callback_data=f"admin:approve_addsvc:{svc_id}:{tg_user_id}"),
                InlineKeyboardButton(text="رد", callback_data=f"admin:reject_addsvc:{svc_id}:{tg_user_id}"),
            ]
        ]
    )


def admin_manage_servers_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="افزودن سرور", callback_data="admin:add_server")],
            [InlineKeyboardButton(text="لیست سرورها", callback_data="admin:list_servers")],
        ]
    )


def admin_manage_categories_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="افزودن دسته", callback_data="admin:add_category")],
            [InlineKeyboardButton(text="لیست دسته‌ها", callback_data="admin:list_categories")],
        ]
    )


def admin_manage_plans_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="افزودن پلن", callback_data="admin:add_plan")],
            [InlineKeyboardButton(text="لیست پلن‌ها", callback_data="admin:list_plans")],
        ]
    )

