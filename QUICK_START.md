# 🚀 راهنمای نصب سریع ربات تلگرام VPN
# VPN Telegram Bot Quick Start Guide

## ⚡ نصب یک اسکریپتی (توصیه شده)
## One-Script Installation (Recommended)

> نسخه 1.0.1: نصب یک‌اسکریپتی حذف شده است. از Docker Compose استفاده کنید.

---

## 📋 پیش نیازها
## Prerequisites

### سیستم عامل مورد نیاز
- **Linux**: Ubuntu 18.04+, CentOS 7+, Debian 9+
- **macOS**: 10.14+
- **Windows**: Windows 10+ (با WSL2)

### منابع سیستم
- **RAM**: حداقل 2GB، توصیه 4GB+
- **CPU**: 2 هسته، توصیه 4 هسته+
- **فضای دیسک**: حداقل 10GB فضای خالی

---

## 🔧 مراحل نصب
## Installation Steps

### 1. اجرای اسکریپت نصب
اسکریپت به صورت خودکار:
- Docker و Docker Compose را نصب می‌کند
- مخزن را کلون می‌کند
- فایل تنظیمات را ایجاد می‌کند
- تمام سرویس‌ها را راه‌اندازی می‌کند

### 2. وارد کردن اطلاعات
در حین نصب، اطلاعات زیر را وارد کنید:
- **توکن ربات تلگرام** (از @BotFather)
- **شناسه‌های ادمین** (جدا شده با کاما)
- **نام کاربری ربات**
- **رمز عبور پایگاه داده**

### 3. انتظار برای تکمیل
نصب معمولاً 5-10 دقیقه طول می‌کشد.

---

## ✅ بررسی نصب
## Verify Installation

### دستورات بررسی
```bash
# آماده‌سازی و اجرا
cp .env.example .env
docker compose up -d --build

# بررسی وضعیت سرویس‌ها
docker compose ps

# مشاهده لاگ‌ها
docker compose logs -f api | cat

# بررسی API
curl http://localhost:8000/health
```

### دسترسی به پنل‌ها
- **ربات**: @your_bot_username
- **API**: http://localhost:8000
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

---

## ⚙️ تنظیمات اولیه
## Initial Configuration

### 1. ویرایش تنظیمات
```bash
nano .env
```

### 2. تنظیمات مهم
```env
# توکن ربات
BOT_TOKEN=your_bot_token

# شناسه‌های ادمین
ADMIN_IDS=[123456789,987654321]

# تنظیمات پنل VPN
PANEL_TYPE=x-ui
PANEL_URL=https://your-panel.com
PANEL_USERNAME=admin
PANEL_PASSWORD=your_password
```

### 3. راه‌اندازی مجدد
```bash
docker compose restart
```

---

## 🛠️ دستورات مفید
## Useful Commands

### مدیریت سرویس‌ها
```bash
# راه‌اندازی
docker compose up -d

# توقف
docker compose down

# راه‌اندازی مجدد
docker compose restart

# مشاهده لاگ‌ها
docker compose logs -f bot | cat
```

### پشتیبان‌گیری
```bash
# پشتیبان‌گیری دستی
./scripts/backup.sh

# به‌روزرسانی
./scripts/update.sh
```

### عیب‌یابی
```bash
# بررسی وضعیت
docker compose ps

# بررسی لاگ‌ها
docker compose logs | cat

# بررسی منابع
docker stats
```

---

## 🔍 عیب‌یابی سریع
## Quick Troubleshooting

### مشکل: Docker نصب نیست
```bash
# نصب Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### مشکل: سرویس‌ها راه‌اندازی نمی‌شوند
```bash
# بررسی لاگ‌ها
docker-compose logs

# راه‌اندازی مجدد
docker-compose down
docker-compose up -d
```

### مشکل: ربات پاسخ نمی‌دهد
```bash
# بررسی توکن
curl "https://api.telegram.org/bot$BOT_TOKEN/getMe"

# بررسی لاگ‌های ربات
docker compose logs bot | cat
```

---

## 📞 پشتیبانی
## Support

### منابع کمک
- **مستندات کامل**: [INSTALLATION_GUIDE_FA.md](INSTALLATION_GUIDE_FA.md)
- **Issues**: [GitHub Issues](https://github.com/cheaterpersian-web/Bestbot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/cheaterpersian-web/Bestbot/discussions)

### گزارش مشکل
هنگام گزارش مشکل، لطفاً اطلاعات زیر را ارائه دهید:
- نسخه سیستم عامل
- لاگ‌های مربوطه
- مراحل تکرار مشکل

---

## 🎉 تبریک!
## Congratulations!

ربات تلگرام VPN شما با موفقیت نصب شد! 🎉

**مرحله بعدی**: تنظیم پنل VPN و شروع فروش خدمات

**Next Step**: Configure VPN panel and start selling services

---

**نکته**: این ربات برای ارائه‌دهندگان قانونی خدمات VPN طراحی شده است.

**Note**: This bot is designed for legitimate VPN service providers.