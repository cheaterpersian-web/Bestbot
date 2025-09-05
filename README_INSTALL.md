# 🚀 ربات تلگرام VPN - نصب آسان
# VPN Telegram Bot - Easy Installation

## ⚡ نصب یک اسکریپتی
## One-Script Installation

### روش 1: دانلود مستقیم
```bash
curl -fsSL https://raw.githubusercontent.com/cheaterpersian-web/Bestbot/main/install.sh | bash
```

### روش 2: دانلود و اجرا
```bash
wget https://raw.githubusercontent.com/cheaterpersian-web/Bestbot/main/install.sh
chmod +x install.sh
./install.sh
```

---

## 📋 پیش نیازها
## Prerequisites

- **سیستم عامل**: Linux (Ubuntu 18.04+), macOS, Windows (WSL2)
- **RAM**: حداقل 2GB، توصیه 4GB+
- **فضای دیسک**: حداقل 10GB
- **اینترنت**: اتصال پایدار

---

## 🎯 مراحل نصب
## Installation Steps

1. **اجرای اسکریپت نصب** - اسکریپت به صورت خودکار:
   - Docker و Docker Compose را نصب می‌کند
   - مخزن را کلون می‌کند
   - فایل تنظیمات را ایجاد می‌کند
   - تمام سرویس‌ها را راه‌اندازی می‌کند

2. **وارد کردن اطلاعات**:
   - توکن ربات تلگرام (از @BotFather)
   - شناسه‌های ادمین
   - نام کاربری ربات
   - رمز عبور پایگاه داده

3. **انتظار برای تکمیل** (5-10 دقیقه)

---

## ✅ بررسی نصب
## Verify Installation

```bash
# بررسی وضعیت سرویس‌ها
docker-compose ps

# مشاهده لاگ‌ها
docker-compose logs -f

# بررسی API
curl http://localhost:8000/health
```

---

## 🔗 دسترسی به سرویس‌ها
## Service Access

- **ربات**: @your_bot_username
- **API**: http://localhost:8000
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

---

## 🛠️ دستورات مفید
## Useful Commands

```bash
# راه‌اندازی سرویس‌ها
docker-compose up -d

# توقف سرویس‌ها
docker-compose down

# راه‌اندازی مجدد
docker-compose restart

# پشتیبان‌گیری
./scripts/backup.sh

# به‌روزرسانی
./scripts/update.sh
```

---

## 📚 مستندات کامل
## Complete Documentation

- **راهنمای کامل نصب**: [INSTALLATION_GUIDE_FA.md](INSTALLATION_GUIDE_FA.md)
- **راهنمای سریع**: [QUICK_START.md](QUICK_START.md)
- **فایل نمونه تنظیمات**: [.env.template](.env.template)

---

## 🆘 پشتیبانی
## Support

- **Issues**: [GitHub Issues](https://github.com/cheaterpersian-web/Bestbot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/cheaterpersian-web/Bestbot/discussions)

---

## 🎉 تبریک!
## Congratulations!

ربات تلگرام VPN شما آماده استفاده است! 🎉

**مرحله بعدی**: تنظیم پنل VPN و شروع فروش خدمات

---

**نکته**: این ربات برای ارائه‌دهندگان قانونی خدمات VPN طراحی شده است.