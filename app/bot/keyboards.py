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

