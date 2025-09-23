from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.db import get_db_session
from services.bot_settings import get_payment_methods


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
    # Note: this is a sync function in a module; we will build keyboard lazily via a small async helper
    # For aiogram usage simplicity, we keep it sync but fetch settings at call time with a simple event loop if needed.
    # However, to avoid event loop issues, we provide a default keyboard and let buy router rebuild if needed.
    rows = [
        [InlineKeyboardButton(text="پرداخت از کیف پول", callback_data=f"buy:pay_wallet:{plan_id}")],
        [InlineKeyboardButton(text="ارسال رسید کارت‌به‌کارت", callback_data=f"buy:pay_receipt:{plan_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def build_pay_options_kb(plan_id: int) -> InlineKeyboardMarkup:
    methods = []
    async with get_db_session() as session:
        methods = await get_payment_methods(session)
    rows = []
    for m in methods:
        if m == "wallet":
            rows.append([InlineKeyboardButton(text="پرداخت از کیف پول", callback_data=f"buy:pay_wallet:{plan_id}")])
        elif m == "card":
            rows.append([InlineKeyboardButton(text="ارسال رسید کارت‌به‌کارت", callback_data=f"buy:pay_receipt:{plan_id}")])
        elif m == "stars":
            rows.append([InlineKeyboardButton(text="پرداخت با استارز", callback_data=f"buy:pay_stars:{plan_id}")])
        elif m == "zarinpal":
            rows.append([InlineKeyboardButton(text="پرداخت آنلاین (زرین‌پال)", callback_data=f"buy:pay_zarin:{plan_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text="ارسال رسید کارت‌به‌کارت", callback_data=f"buy:pay_receipt:{plan_id}")]])


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


def payment_cards_kb(cards: list) -> InlineKeyboardMarkup:
    """Keyboard for displaying payment cards"""
    rows = []
    for card in cards:
        text = f"💳 {card.holder_name} - {card.card_number}"
        if card.is_primary:
            text = f"⭐ {text}"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"card:{card.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_transaction_actions_kb(tx_id: int) -> InlineKeyboardMarkup:
    """Enhanced admin transaction review keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید", callback_data=f"admin:approve_tx:{tx_id}"),
                InlineKeyboardButton(text="❌ رد", callback_data=f"admin:reject_tx:{tx_id}"),
            ],
            [
                InlineKeyboardButton(text="🔍 جزئیات", callback_data=f"admin:tx_details:{tx_id}"),
                InlineKeyboardButton(text="🚨 گزارش کلاهبرداری", callback_data=f"admin:report_fraud:{tx_id}"),
            ]
        ]
    )


def user_profile_actions_kb(user_id: int) -> InlineKeyboardMarkup:
    """User profile management keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔒 مسدود کردن", callback_data=f"admin:block_user:{user_id}"),
                InlineKeyboardButton(text="🔓 آزاد کردن", callback_data=f"admin:unblock_user:{user_id}"),
            ],
            [
                InlineKeyboardButton(text="💰 تنظیم موجودی", callback_data=f"admin:set_wallet:{user_id}"),
                InlineKeyboardButton(text="🎁 هدیه", callback_data=f"admin:gift_user:{user_id}"),
            ],
            [
                InlineKeyboardButton(text="📊 آمار کاربر", callback_data=f"admin:user_stats:{user_id}"),
                InlineKeyboardButton(text="📝 تراکنش‌ها", callback_data=f"admin:user_transactions:{user_id}"),
            ]
        ]
    )


def service_management_kb(service_id: int) -> InlineKeyboardMarkup:
    """Service management keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 تمدید", callback_data=f"service:renew:{service_id}"),
                InlineKeyboardButton(text="📊 افزودن ترافیک", callback_data=f"service:add_traffic:{service_id}"),
            ],
            [
                InlineKeyboardButton(text="🆔 تغییر UUID", callback_data=f"service:regenerate_uuid:{service_id}"),
                InlineKeyboardButton(text="🗑️ حذف", callback_data=f"service:delete:{service_id}"),
            ]
        ]
    )


def discount_code_actions_kb(code_id: int) -> InlineKeyboardMarkup:
    """Discount code management keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"admin:edit_discount:{code_id}"),
                InlineKeyboardButton(text="🗑️ حذف", callback_data=f"admin:delete_discount:{code_id}"),
            ],
            [
                InlineKeyboardButton(text="📊 آمار استفاده", callback_data=f"admin:discount_stats:{code_id}"),
                InlineKeyboardButton(text="🔄 فعال/غیرفعال", callback_data=f"admin:toggle_discount:{code_id}"),
            ]
        ]
    )


def reseller_request_actions_kb(request_id: int) -> InlineKeyboardMarkup:
    """Reseller request management keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید", callback_data=f"admin:approve_reseller:{request_id}"),
                InlineKeyboardButton(text="❌ رد", callback_data=f"admin:reject_reseller:{request_id}"),
            ],
            [
                InlineKeyboardButton(text="🚫 سیاه‌چاله", callback_data=f"admin:blacklist_reseller:{request_id}"),
                InlineKeyboardButton(text="📝 جزئیات", callback_data=f"admin:reseller_details:{request_id}"),
            ]
        ]
    )


def broadcast_options_kb() -> InlineKeyboardMarkup:
    """Broadcast options keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 متن", callback_data="broadcast:text"),
                InlineKeyboardButton(text="🖼️ تصویر", callback_data="broadcast:image"),
            ],
            [
                InlineKeyboardButton(text="📤 فوروارد", callback_data="broadcast:forward"),
                InlineKeyboardButton(text="📊 آمار ارسال", callback_data="broadcast:stats"),
            ]
        ]
    )


def broadcast_presets_kb() -> InlineKeyboardMarkup:
    """Quick presets for target segments"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 همه", callback_data="broadcast:preset:all"),
                InlineKeyboardButton(text="🆕 جدیدها", callback_data="broadcast:preset:new_users"),
                InlineKeyboardButton(text="⭐ فعال‌ها", callback_data="broadcast:preset:active_users"),
            ],
            [
                InlineKeyboardButton(text="💎 VIP", callback_data="broadcast:preset:vip_users"),
                InlineKeyboardButton(text="⚠️ ریزشی‌ها", callback_data="broadcast:preset:churned_users"),
            ]
        ]
    )

