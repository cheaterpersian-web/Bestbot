# 📱 Telegram Mini App - ربات VPN

## 🚀 ویژگی‌ها

### ✨ رابط کاربری پیشرفته
- **طراحی مدرن**: رابط کاربری زیبا و کاربرپسند
- **پشتیبانی از تم**: سازگار با تم تلگرام
- **واکنش‌گرا**: سازگار با تمام اندازه‌های صفحه
- **پشتیبانی از RTL**: پشتیبانی کامل از زبان فارسی

### 🛠️ قابلیت‌های اصلی
- **مدیریت سرویس‌ها**: مشاهده، تمدید و مدیریت سرویس‌های VPN
- **خرید آسان**: خرید سرویس جدید با چند کلیک
- **کیف پول**: مدیریت موجودی و تراکنش‌ها
- **پروفایل کاربری**: اطلاعات کامل کاربر
- **QR Code**: نمایش QR Code برای اتصال سریع

### 🔧 ویژگی‌های فنی
- **امنیت بالا**: احراز هویت با Telegram Web App
- **API RESTful**: API کامل برای تمام عملیات
- **Real-time**: بروزرسانی لحظه‌ای اطلاعات
- **Cache**: سیستم کش برای بهبود عملکرد

## 📁 ساختار فایل‌ها

```
app/webapp/
├── __init__.py          # Package initialization
├── config.py            # Configuration settings
├── api.py              # API endpoints
├── static/             # Static files
│   ├── index.html      # Main HTML file
│   ├── app.js          # JavaScript application
│   └── style.css       # Custom styles (optional)
└── README.md           # This file
```

## 🚀 راه‌اندازی

### 1. تنظیمات محیطی
```env
# Bot settings
BOT_TOKEN=your_bot_token_here
WEBHOOK_URL=https://yourdomain.com/webhook

# WebApp settings
WEBAPP_URL=https://yourdomain.com
WEBAPP_SECRET=your-secret-key

# API settings
API_BASE_URL=https://yourdomain.com/api

# Feature flags
ENABLE_WEBAPP=true
ENABLE_PAYMENTS=true
ENABLE_QR_CODES=true
```

### 2. تنظیم Bot
```python
# در فایل main.py
from app.webapp import api as webapp_router
dp.include_router(webapp_router.router)
```

### 3. تنظیم Webhook
```python
# تنظیم webhook برای Mini App
await bot.set_webhook(
    url="https://yourdomain.com/webhook",
    allowed_updates=["message", "callback_query"]
)
```

## 📱 استفاده از Mini App

### 1. فعال‌سازی در Bot
```python
# در روتور اصلی bot
@router.message(Command("webapp"))
async def open_webapp(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🖥️ باز کردن پنل کاربری",
            web_app=WebAppInfo(url="https://yourdomain.com")
        )]
    ])
    await message.answer("پنل کاربری خود را باز کنید:", reply_markup=kb)
```

### 2. دسترسی به Mini App
- کاربران می‌توانند از طریق دکمه "پنل کاربری" در ربات به Mini App دسترسی پیدا کنند
- Mini App در داخل تلگرام باز می‌شود
- تمام عملیات بدون خروج از تلگرام انجام می‌شود

## 🔌 API Endpoints

### کاربری
- `GET /api/user/stats` - آمار کاربر
- `GET /api/user/services` - سرویس‌های کاربر
- `POST /api/purchase` - خرید سرویس جدید

### سرویس‌ها
- `GET /api/servers` - لیست سرورها
- `GET /api/servers/{id}/categories` - دسته‌بندی‌های سرور
- `GET /api/categories/{id}/plans` - پلن‌های دسته‌بندی
- `GET /api/service/{id}/config` - کانفیگ سرویس
- `POST /api/service/{id}/renew` - تمدید سرویس

### کیف پول
- `POST /api/wallet/topup` - شارژ کیف پول
- `GET /api/wallet/transactions` - تاریخچه تراکنش‌ها

## 🎨 سفارشی‌سازی

### تغییر تم
```css
:root {
    --tg-theme-bg-color: #ffffff;
    --tg-theme-text-color: #000000;
    --tg-theme-button-color: #2481cc;
    --tg-theme-button-text-color: #ffffff;
}
```

### اضافه کردن تب جدید
```javascript
// در app.js
function addNewTab() {
    // اضافه کردن تب جدید
    const newTab = document.createElement('li');
    newTab.className = 'nav-item';
    newTab.innerHTML = `
        <button class="nav-link" id="new-tab" data-bs-toggle="tab" data-bs-target="#new-content">
            <i class="fas fa-icon"></i> تب جدید
        </button>
    `;
    document.getElementById('mainTabs').appendChild(newTab);
}
```

## 🔒 امنیت

### احراز هویت
- تمام درخواست‌ها با Telegram Web App authentication تأیید می‌شوند
- Hash verification برای اطمینان از صحت داده‌ها
- Rate limiting برای جلوگیری از سوء استفاده

### محافظت از داده‌ها
- تمام داده‌های حساس رمزنگاری می‌شوند
- Session management امن
- Input validation کامل

## 📊 مانیتورینگ

### لاگ‌ها
```python
import logging

logger = logging.getLogger(__name__)

@router.get("/api/user/stats")
async def get_user_stats(user_data: dict = Depends(verify_telegram_auth)):
    logger.info(f"User {user_data['id']} requested stats")
    # ...
```

### متریک‌ها
- تعداد کاربران فعال
- تعداد درخواست‌های API
- زمان پاسخ API
- نرخ خطا

## 🚀 بهینه‌سازی

### کش
```python
from functools import lru_cache

@lru_cache(maxsize=128)
async def get_cached_servers():
    # کش کردن لیست سرورها
    pass
```

### فشرده‌سازی
```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

## 🐛 عیب‌یابی

### مشکلات رایج
1. **Mini App باز نمی‌شود**: بررسی URL و تنظیمات webhook
2. **احراز هویت ناموفق**: بررسی bot token و secret key
3. **API errors**: بررسی لاگ‌ها و تنظیمات دیتابیس

### لاگ‌ها
```bash
# مشاهده لاگ‌های Mini App
tail -f logs/webapp.log

# لاگ‌های API
tail -f logs/api.log
```

## 📈 آمار استفاده

### Google Analytics
```javascript
// اضافه کردن Google Analytics
gtag('config', 'GA_MEASUREMENT_ID');
```

### Telegram Analytics
```javascript
// ارسال رویداد به Telegram
tg.sendData(JSON.stringify({
    event: 'user_action',
    action: 'service_purchased',
    timestamp: Date.now()
}));
```

## 🎉 نتیجه‌گیری

Telegram Mini App ربات VPN یک رابط کاربری پیشرفته و حرفه‌ای است که:

- ✅ تجربه کاربری عالی ارائه می‌دهد
- ✅ تمام قابلیت‌های ربات را پوشش می‌دهد
- ✅ امنیت بالا دارد
- ✅ عملکرد بهینه دارد
- ✅ قابل سفارشی‌سازی است

**آماده برای استفاده در تولید!** 🚀