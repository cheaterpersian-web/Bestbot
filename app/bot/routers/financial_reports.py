from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from services.financial_report_service import FinancialReportService


router = Router(name="financial_reports")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


@router.message(Command("daily_report"))
async def daily_report(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract date from command if provided
    command_parts = message.text.split()
    date = None
    
    if len(command_parts) > 1:
        try:
            date = datetime.strptime(command_parts[1], "%Y-%m-%d").date()
        except ValueError:
            await message.answer("فرمت تاریخ نامعتبر است. از YYYY-MM-DD استفاده کنید.")
            return
    
    try:
        async with get_db_session() as session:
            report = await FinancialReportService.generate_daily_report(session, date)
        
        report_text = f"""
📊 گزارش روزانه - {report['date']}

💰 درآمد:
• کل درآمد: {report['revenue']['total']:,.0f} تومان
• کل تراکنش‌ها: {report['revenue']['transactions']['total']}
• تایید شده: {report['revenue']['transactions']['approved']}
• در انتظار: {report['revenue']['transactions']['pending']}
• رد شده: {report['revenue']['transactions']['rejected']}
• نرخ تایید: {report['revenue']['approval_rate']:.1f}%

💳 روش‌های پرداخت:
"""
        
        for method, data in report['payment_methods'].items():
            method_names = {
                "card_to_card": "کارت به کارت",
                "wallet": "کیف پول",
                "stars": "ستاره‌های تلگرام",
                "zarinpal": "زرین‌پال"
            }
            method_name = method_names.get(method, method)
            report_text += f"• {method_name}: {data['count']} تراکنش، {data['amount']:,.0f} تومان\n"
        
        report_text += f"""
📈 رشد:
• کاربران جدید: {report['growth']['new_users']}
• سرویس‌های جدید: {report['growth']['new_services']}
"""
        
        await message.answer(report_text)
        
    except Exception as e:
        await message.answer(f"❌ خطا در تولید گزارش: {str(e)}")


@router.message(Command("weekly_report"))
async def weekly_report(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        async with get_db_session() as session:
            report = await FinancialReportService.generate_weekly_report(session)
        
        report_text = f"""
📊 گزارش هفتگی - {report['week_start']} تا {report['week_end']}

📅 درآمد روزانه:
"""
        
        for date, data in report['daily_breakdown'].items():
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            day_name = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه', 'یکشنبه'][date_obj.weekday()]
            report_text += f"• {day_name} ({date}): {data['revenue']:,.0f} تومان، {data['transactions']} تراکنش\n"
        
        report_text += f"\n🏆 برترین پلن‌ها:\n"
        for i, plan in enumerate(report['plan_performance'][:5], 1):
            report_text += f"{i}. {plan['title']}: {plan['sales_count']} فروش، {plan['revenue']:,.0f} تومان\n"
        
        report_text += f"\n🖥️ برترین سرورها:\n"
        for i, server in enumerate(report['server_performance'][:5], 1):
            report_text += f"{i}. {server['name']}: {server['sales_count']} فروش، {server['revenue']:,.0f} تومان\n"
        
        await message.answer(report_text)
        
    except Exception as e:
        await message.answer(f"❌ خطا در تولید گزارش: {str(e)}")


@router.message(Command("monthly_report"))
async def monthly_report(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract year and month from command
    command_parts = message.text.split()
    if len(command_parts) < 3:
        await message.answer("فرمت: /monthly_report <سال> <ماه>")
        return
    
    try:
        year = int(command_parts[1])
        month = int(command_parts[2])
    except ValueError:
        await message.answer("سال و ماه باید عدد باشند.")
        return
    
    try:
        async with get_db_session() as session:
            report = await FinancialReportService.generate_monthly_report(session, year, month)
        
        month_names = [
            "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
        ]
        
        report_text = f"""
📊 گزارش ماهانه - {month_names[month-1]} {year}

💰 درآمد:
• کل درآمد: {report['revenue']['total']:,.0f} تومان
• رشد نسبت به ماه قبل: {report['revenue']['growth_percent']:+.1f}%
• درآمد ماه قبل: {report['revenue']['previous_month']:,.0f} تومان

📂 درآمد بر اساس دسته‌بندی:
"""
        
        for category in report['category_revenue'][:5]:
            report_text += f"• {category['title']}: {category['revenue']:,.0f} تومان\n"
        
        report_text += f"""
👥 تحلیل مشتریان:
• کل مشتریان: {report['customer_analysis']['total_customers']}
• میانگین تراکنش: {report['customer_analysis']['avg_transaction']:,.0f} تومان
• بیشترین تراکنش: {report['customer_analysis']['max_transaction']:,.0f} تومان
• کمترین تراکنش: {report['customer_analysis']['min_transaction']:,.0f} تومان

🏢 برترین نمایندگان:
"""
        
        for i, reseller in enumerate(report['reseller_performance'][:5], 1):
            username = reseller['username'] or 'بدون نام کاربری'
            report_text += f"{i}. @{username}: {reseller['commission_count']} کمیسیون، {reseller['total_commission']:,.0f} تومان\n"
        
        await message.answer(report_text)
        
    except Exception as e:
        await message.answer(f"❌ خطا در تولید گزارش: {str(e)}")


@router.message(Command("profit_loss_report"))
async def profit_loss_report(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract date range from command
    command_parts = message.text.split()
    if len(command_parts) < 3:
        await message.answer("فرمت: /profit_loss_report <تاریخ_شروع> <تاریخ_پایان>\nمثال: /profit_loss_report 2024-01-01 2024-01-31")
        return
    
    try:
        start_date = datetime.strptime(command_parts[1], "%Y-%m-%d")
        end_date = datetime.strptime(command_parts[2], "%Y-%m-%d")
    except ValueError:
        await message.answer("فرمت تاریخ نامعتبر است. از YYYY-MM-DD استفاده کنید.")
        return
    
    try:
        async with get_db_session() as session:
            report = await FinancialReportService.generate_profit_loss_report(session, start_date, end_date)
        
        report_text = f"""
📊 گزارش سود و زیان - {report['period']['start_date']} تا {report['period']['end_date']}

💰 درآمد:
• کل درآمد: {report['revenue']['total']:,.0f} تومان

💸 هزینه‌ها:
• کمیسیون نمایندگان: {report['expenses']['commissions']:,.0f} تومان
• بازپرداخت‌ها: {report['expenses']['refunds']:,.0f} تومان
• کل هزینه‌ها: {report['expenses']['total']:,.0f} تومان

📈 سود:
• سود ناخالص: {report['profit']['gross_profit']:,.0f} تومان
• حاشیه سود: {report['profit']['profit_margin']:.1f}%
"""
        
        # Add profit analysis
        if report['profit']['profit_margin'] > 20:
            report_text += "\n✅ عملکرد عالی - حاشیه سود بالا"
        elif report['profit']['profit_margin'] > 10:
            report_text += "\n🟡 عملکرد متوسط - حاشیه سود قابل قبول"
        else:
            report_text += "\n🔴 نیاز به بهبود - حاشیه سود پایین"
        
        await message.answer(report_text)
        
    except Exception as e:
        await message.answer(f"❌ خطا در تولید گزارش: {str(e)}")


@router.message(Command("trend_analysis"))
async def trend_analysis(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract days from command
    command_parts = message.text.split()
    days = 30  # Default
    
    if len(command_parts) > 1:
        try:
            days = int(command_parts[1])
        except ValueError:
            await message.answer("تعداد روزها باید عدد باشد.")
            return
    
    try:
        async with get_db_session() as session:
            report = await FinancialReportService.generate_trend_analysis(session, days)
        
        report_text = f"""
📈 تحلیل روند - {days} روز گذشته

📊 میانگین‌ها:
• میانگین درآمد روزانه: {report['averages']['daily_revenue']:,.0f} تومان
• میانگین تراکنش روزانه: {report['averages']['daily_transactions']:.1f}

📅 روند روزانه (آخرین 7 روز):
"""
        
        # Show last 7 days
        recent_days = report['daily_trend'][-7:]
        for day_data in recent_days:
            date_obj = datetime.strptime(day_data['date'], '%Y-%m-%d')
            day_name = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه', 'یکشنبه'][date_obj.weekday()]
            growth_emoji = "📈" if day_data['growth_rate'] > 0 else "📉" if day_data['growth_rate'] < 0 else "➡️"
            
            report_text += f"• {day_name}: {day_data['revenue']:,.0f} تومان {growth_emoji} {day_data['growth_rate']:+.1f}%\n"
        
        # Calculate overall trend
        if len(report['daily_trend']) >= 2:
            first_week_avg = sum(d['revenue'] for d in report['daily_trend'][:7]) / 7
            last_week_avg = sum(d['revenue'] for d in report['daily_trend'][-7:]) / 7
            overall_growth = ((last_week_avg - first_week_avg) / first_week_avg * 100) if first_week_avg > 0 else 0
            
            report_text += f"\n📊 روند کلی: {overall_growth:+.1f}%"
            
            if overall_growth > 5:
                report_text += "\n✅ روند صعودی قوی"
            elif overall_growth > 0:
                report_text += "\n🟡 روند صعودی ملایم"
            elif overall_growth > -5:
                report_text += "\n🟠 روند نزولی ملایم"
            else:
                report_text += "\n🔴 روند نزولی قوی"
        
        await message.answer(report_text)
        
    except Exception as e:
        await message.answer(f"❌ خطا در تولید گزارش: {str(e)}")


@router.message(Command("custom_report"))
async def custom_report_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Show filter options
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 انتخاب بازه زمانی", callback_data="custom_report:date_range")],
        [InlineKeyboardButton(text="💳 فیلتر روش پرداخت", callback_data="custom_report:payment_method")],
        [InlineKeyboardButton(text="💰 فیلتر مبلغ", callback_data="custom_report:amount")],
        [InlineKeyboardButton(text="📊 تولید گزارش", callback_data="custom_report:generate")]
    ])
    
    await message.answer("گزارش سفارشی - فیلترها را انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("custom_report:"))
async def custom_report_handler(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    action = callback.data.split(":")[1]
    
    if action == "date_range":
        await callback.message.edit_text(
            "📅 بازه زمانی را وارد کنید:\n"
            "فرمت: YYYY-MM-DD تا YYYY-MM-DD\n"
            "مثال: 2024-01-01 تا 2024-01-31"
        )
        await callback.answer()
    
    elif action == "payment_method":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="کارت به کارت", callback_data="filter:payment:card_to_card")],
            [InlineKeyboardButton(text="کیف پول", callback_data="filter:payment:wallet")],
            [InlineKeyboardButton(text="ستاره‌های تلگرام", callback_data="filter:payment:stars")],
            [InlineKeyboardButton(text="زرین‌پال", callback_data="filter:payment:zarinpal")]
        ])
        await callback.message.edit_text("روش پرداخت را انتخاب کنید:", reply_markup=kb)
        await callback.answer()
    
    elif action == "amount":
        await callback.message.edit_text(
            "💰 محدوده مبلغ را وارد کنید:\n"
            "فرمت: حداقل تا حداکثر\n"
            "مثال: 100000 تا 1000000"
        )
        await callback.answer()
    
    elif action == "generate":
        # Generate report with default filters
        try:
            start_date = datetime.utcnow() - timedelta(days=30)
            end_date = datetime.utcnow()
            
            async with get_db_session() as session:
                report = await FinancialReportService.generate_custom_report(
                    session, start_date, end_date
                )
            
            report_text = f"""
📊 گزارش سفارشی - {report['period']['start_date']} تا {report['period']['end_date']}

📈 خلاصه:
• کل درآمد: {report['summary']['total_revenue']:,.0f} تومان
• کل تراکنش‌ها: {report['summary']['total_transactions']}
• میانگین تراکنش: {report['summary']['avg_transaction']:,.0f} تومان

👥 برترین مشتریان:
"""
            
            for i, customer in enumerate(report['top_customers'][:5], 1):
                username = customer['username'] or 'بدون نام کاربری'
                report_text += f"{i}. @{username}: {customer['revenue']:,.0f} تومان\n"
            
            await callback.message.edit_text(report_text)
            
        except Exception as e:
            await callback.message.edit_text(f"❌ خطا در تولید گزارش: {str(e)}")
        
        await callback.answer()


@router.message(Command("financial_help"))
async def financial_help(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    help_text = """
📊 راهنمای گزارش‌های مالی:

📅 گزارش‌های زمانی:
• /daily_report [تاریخ] - گزارش روزانه
• /weekly_report - گزارش هفتگی
• /monthly_report <سال> <ماه> - گزارش ماهانه

📈 گزارش‌های تحلیلی:
• /profit_loss_report <شروع> <پایان> - گزارش سود و زیان
• /trend_analysis [روزها] - تحلیل روند
• /custom_report - گزارش سفارشی

📋 مثال‌های استفاده:
• /daily_report 2024-01-15
• /monthly_report 2024 1
• /profit_loss_report 2024-01-01 2024-01-31
• /trend_analysis 14

📊 اطلاعات موجود:
• درآمد و تراکنش‌ها
• روش‌های پرداخت
• عملکرد پلن‌ها و سرورها
• تحلیل مشتریان
• عملکرد نمایندگان
• روند رشد
• سود و زیان
• فیلترهای پیشرفته

💡 نکات:
• تاریخ‌ها به فرمت YYYY-MM-DD
• گزارش‌ها بر اساس زمان UTC
• فیلترها برای گزارش‌های سفارشی
• تحلیل‌های مقایسه‌ای
"""
    
    await message.answer(help_text)