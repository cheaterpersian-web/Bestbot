# راهنمای نصب ربات تلگرام VPN
# VPN Telegram Bot Installation Guide

## 📋 فهرست مطالب / Table of Contents

- [پیش نیازها / Prerequisites](#پیش-نیازها--prerequisites)
- [نصب سریع / Quick Installation](#نصب-سریع--quick-installation)
- [نصب دستی / Manual Installation](#نصب-دستی--manual-installation)
- [تنظیمات / Configuration](#تنظیمات--configuration)
- [راه اندازی / Startup](#راه-اندازی--startup)
- [عیب یابی / Troubleshooting](#عیب-یابی--troubleshooting)
- [پشتیبان گیری / Backup](#پشتیبان-گیری--backup)
- [به روزرسانی / Updates](#به-روزرسانی--updates)

---

## 🚀 نصب سریع / Quick Installation

### روش یک اسکریپتی (توصیه شده) / One-Script Method (Recommended)

```bash
# دانلود و اجرای اسکریپت نصب
curl -fsSL https://raw.githubusercontent.com/your-repo/vpn-telegram-bot/main/install.sh | bash

# یا
wget -O - https://raw.githubusercontent.com/your-repo/vpn-telegram-bot/main/install.sh | bash
```

**این روش به صورت خودکار:**
- Docker و Docker Compose را نصب می‌کند
- مخزن را کلون می‌کند
- فایل تنظیمات را ایجاد می‌کند
- تمام سرویس‌ها را راه‌اندازی می‌کند

---

## 📋 پیش نیازها / Prerequisites

### سیستم عامل / Operating System
- **Linux**: Ubuntu 18.04+, CentOS 7+, Debian 9+
- **macOS**: 10.14+
- **Windows**: Windows 10+ (با WSL2)

### نرم‌افزارهای مورد نیاز / Required Software
- **Docker**: نسخه 20.10+
- **Docker Compose**: نسخه 2.0+
- **Git**: برای کلون کردن مخزن
- **curl** یا **wget**: برای دانلود

### منابع سیستم / System Resources
- **RAM**: حداقل 2GB، توصیه 4GB+
- **CPU**: 2 هسته، توصیه 4 هسته+
- **فضای دیسک**: حداقل 10GB فضای خالی
- **شبکه**: اتصال اینترنت پایدار

---

## 🛠️ نصب دستی / Manual Installation

### مرحله 1: نصب Docker / Step 1: Install Docker

#### Ubuntu/Debian:
```bash
# به‌روزرسانی پکیج‌ها
sudo apt update

# نصب پکیج‌های مورد نیاز
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# اضافه کردن کلید GPG Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# اضافه کردن مخزن Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# نصب Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# اضافه کردن کاربر به گروه docker
sudo usermod -aG docker $USER
```

#### CentOS/RHEL:
```bash
# نصب پکیج‌های مورد نیاز
sudo yum install -y yum-utils

# اضافه کردن مخزن Docker
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# نصب Docker
sudo yum install -y docker-ce docker-ce-cli containerd.io

# راه‌اندازی Docker
sudo systemctl start docker
sudo systemctl enable docker

# اضافه کردن کاربر به گروه docker
sudo usermod -aG docker $USER
```

### مرحله 2: نصب Docker Compose / Step 2: Install Docker Compose

```bash
# دانلود Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# اعطای مجوز اجرا
sudo chmod +x /usr/local/bin/docker-compose

# بررسی نصب
docker-compose --version
```

### مرحله 3: کلون کردن مخزن / Step 3: Clone Repository

```bash
# کلون کردن مخزن
git clone https://github.com/cheaterpersian-web/Bestbot.git
cd Bestbot
```

### مرحله 4: ایجاد فایل تنظیمات / Step 4: Create Configuration File

```bash
# کپی کردن فایل نمونه
cp .env.template .env

# ویرایش فایل تنظیمات
nano .env
```

---

## ⚙️ تنظیمات / Configuration

### فایل .env / .env File

فایل `.env` شامل تمام تنظیمات مورد نیاز است:

#### تنظیمات ربات تلگرام / Telegram Bot Settings
```env
# توکن ربات از @BotFather
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# شناسه‌های ادمین (جدا شده با کاما)
ADMIN_IDS=[123456789,987654321]

# نام کاربری ربات
BOT_USERNAME=your_bot_username
```

#### تنظیمات پایگاه داده / Database Settings
```env
# تنظیمات MySQL
MYSQL_DATABASE=vpn_bot
MYSQL_USER=vpn_user
MYSQL_PASSWORD=your_secure_password
MYSQL_ROOT_PASSWORD=your_root_password
```

#### تنظیمات فروش / Sales Settings
```env
# فعال/غیرفعال کردن فروش
SALES_ENABLED=true

# تایید خودکار رسیدها
AUTO_APPROVE_RECEIPTS=false

# حداقل و حداکثر مبلغ شارژ
MIN_TOPUP_AMOUNT=50000
MAX_TOPUP_AMOUNT=50000000
```

#### تنظیمات امنیتی / Security Settings
```env
# فعال کردن تشخیص تقلب
ENABLE_FRAUD_DETECTION=true

# محدودیت تراکنش روزانه
MAX_DAILY_TRANSACTIONS=10
MAX_DAILY_AMOUNT=1000000
```

### ایجاد ربات تلگرام / Creating Telegram Bot

1. **رفتن به @BotFather** در تلگرام
2. **ارسال دستور** `/newbot`
3. **انتخاب نام** برای ربات
4. **انتخاب نام کاربری** (باید به `_bot` ختم شود)
5. **کپی کردن توکن** و قرار دادن در فایل `.env`

### تنظیم پنل VPN / VPN Panel Setup

#### برای x-ui:
```env
PANEL_TYPE=x-ui
PANEL_URL=https://your-panel-url.com
PANEL_USERNAME=admin
PANEL_PASSWORD=your_password
```

#### برای 3x-ui:
```env
PANEL_TYPE=3x-ui
PANEL_URL=https://your-panel-url.com
PANEL_USERNAME=admin
PANEL_PASSWORD=your_password
```

#### برای Hiddify:
```env
PANEL_TYPE=hiddify
PANEL_URL=https://your-panel-url.com
PANEL_USERNAME=admin
PANEL_PASSWORD=your_password
```

---

## 🚀 راه‌اندازی / Startup

### راه‌اندازی سرویس‌ها / Starting Services

```bash
# راه‌اندازی تمام سرویس‌ها
docker-compose up -d

# بررسی وضعیت سرویس‌ها
docker-compose ps

# مشاهده لاگ‌ها
docker-compose logs -f
```

### بررسی سلامت سرویس‌ها / Health Check

```bash
# بررسی API
curl http://localhost:8000/health

# بررسی پایگاه داده
docker-compose exec db mysql -u root -p -e "SHOW DATABASES;"

# بررسی Redis
docker-compose exec redis redis-cli ping
```

### دسترسی به پنل‌های نظارت / Accessing Monitoring Panels

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **API Documentation**: http://localhost:8000/docs

---

## 🔧 عیب‌یابی / Troubleshooting

### مشکلات رایج / Common Issues

#### 1. خطای Docker / Docker Error
```bash
# بررسی وضعیت Docker
sudo systemctl status docker

# راه‌اندازی مجدد Docker
sudo systemctl restart docker
```

#### 2. خطای پایگاه داده / Database Error
```bash
# بررسی لاگ‌های پایگاه داده
docker-compose logs db

# راه‌اندازی مجدد پایگاه داده
docker-compose restart db
```

#### 3. خطای ربات / Bot Error
```bash
# بررسی لاگ‌های ربات
docker-compose logs bot

# بررسی توکن ربات
curl "https://api.telegram.org/bot$BOT_TOKEN/getMe"
```

#### 4. خطای اتصال به پنل / Panel Connection Error
```bash
# بررسی اتصال به پنل
curl -k $PANEL_URL/api/inbounds

# بررسی تنظیمات پنل در فایل .env
grep PANEL .env
```

### دستورات مفید / Useful Commands

```bash
# مشاهده لاگ‌های زنده
docker-compose logs -f bot

# راه‌اندازی مجدد سرویس خاص
docker-compose restart bot

# حذف و ایجاد مجدد کانتینر
docker-compose down
docker-compose up -d

# پاک کردن حجم‌های Docker
docker system prune -a

# بررسی استفاده از منابع
docker stats
```

---

## 💾 پشتیبان‌گیری / Backup

### پشتیبان‌گیری خودکار / Automatic Backup

```bash
# فعال کردن پشتیبان‌گیری در فایل .env
ENABLE_AUTO_BACKUP=true
BACKUP_INTERVAL=24
MAX_BACKUP_FILES=7
```

### پشتیبان‌گیری دستی / Manual Backup

```bash
# پشتیبان‌گیری از پایگاه داده
docker-compose exec db mysqldump -u root -p vpn_bot > backup_$(date +%Y%m%d_%H%M%S).sql

# پشتیبان‌گیری از فایل‌های تنظیمات
tar -czf config_backup_$(date +%Y%m%d_%H%M%S).tar.gz .env docker-compose.yml

# پشتیبان‌گیری کامل
./scripts/backup.sh
```

### بازیابی / Restore

```bash
# بازیابی پایگاه داده
docker-compose exec -T db mysql -u root -p vpn_bot < backup_file.sql

# بازیابی تنظیمات
tar -xzf config_backup.tar.gz
```

---

## 🔄 به‌روزرسانی / Updates

### به‌روزرسانی خودکار / Automatic Update

```bash
# اجرای اسکریپت به‌روزرسانی
./scripts/update.sh
```

### به‌روزرسانی دستی / Manual Update

```bash
# دریافت آخرین تغییرات
git pull origin main

# بازسازی و راه‌اندازی مجدد
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# اجرای مایگریشن‌ها
docker-compose exec bot python -m alembic upgrade head
```

---

## 📞 پشتیبانی / Support

### منابع کمک / Help Resources

- **مستندات**: [GitHub Wiki](https://github.com/cheaterpersian-web/Bestbot/wiki)
- **Issues**: [GitHub Issues](https://github.com/cheaterpersian-web/Bestbot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/cheaterpersian-web/Bestbot/discussions)

### گزارش باگ / Bug Reports

هنگام گزارش باگ، لطفاً اطلاعات زیر را ارائه دهید:
- نسخه سیستم عامل
- نسخه Docker
- لاگ‌های مربوطه
- مراحل تکرار مشکل

### درخواست ویژگی / Feature Requests

برای درخواست ویژگی جدید:
- توضیح کامل ویژگی
- دلیل نیاز
- مثال‌های استفاده

---

## 📄 مجوز / License

این پروژه تحت مجوز MIT منتشر شده است. برای جزئیات بیشتر، فایل [LICENSE](LICENSE) را مطالعه کنید.

---

## 🤝 مشارکت / Contributing

ما از مشارکت شما استقبال می‌کنیم! لطفاً:
1. پروژه را Fork کنید
2. شاخه جدید ایجاد کنید
3. تغییرات خود را اعمال کنید
4. Pull Request ارسال کنید

---

**نکته مهم**: این ربات برای ارائه‌دهندگان قانونی خدمات VPN طراحی شده است. لطفاً از قوانین محلی و مقررات حوزه قضایی خود پیروی کنید.