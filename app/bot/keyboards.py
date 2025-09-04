from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="خرید جدید"),
                KeyboardButton(text="کانفیگ‌های من"),
            ],
            [
                KeyboardButton(text="کیف پول / پرداخت‌ها"),
                KeyboardButton(text="حساب کاربری"),
            ],
            [
                KeyboardButton(text="دعوت دوستان"),
                KeyboardButton(text="تیکت‌ها"),
            ],
            [
                KeyboardButton(text="آموزش اتصال"),
                KeyboardButton(text="استعلام کانفیگ"),
            ],
            [
                KeyboardButton(text="سایر امکانات"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="یک گزینه را انتخاب کنید",
    )


def wallet_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💰 شارژ کیف پول"),
                KeyboardButton(text="💸 انتقال موجودی"),
            ],
            [
                KeyboardButton(text="📊 تاریخچه تراکنش‌ها"),
                KeyboardButton(text="💳 کارت‌های پرداخت"),
            ],
            [
                KeyboardButton(text="🔙 بازگشت به منوی اصلی"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="یک گزینه کیف پول را انتخاب کنید",
    )

