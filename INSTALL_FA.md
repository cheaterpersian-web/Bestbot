# نصب ربات VPN روی هاست (گام‌به‌گام)

این راهنما کمک می‌کند ربات را روی سرور لینوکسی (VPS) با Docker اجرا کنید. اگر Docker ندارید، در بخش «اجرای بدون Docker» توضیح داده شده است.

## پیش‌نیازها
- سرور لینوکسی (Ubuntu 20.04+/Debian 11+)
- دسترسی SSH و sudo
- Docker و Docker Compose نصب شده
- توکن ربات از BotFather

نکته: برای نصب Docker از مستندات رسمی استفاده کنید: `https://docs.docker.com/engine/install/`

## 1) دریافت سورس
```bash
cd ~
git clone <REPO_URL>
cd <REPO_DIR>
```

## 2) ساخت فایل .env
ساده‌ترین راه، اسکریپت تعاملی است:
```bash
bash scripts/setup.sh
```
- از شما `BOT_TOKEN`، شناسه ادمین‌ها، و در صورت تمایل `DOMAIN` و `EMAIL` را می‌پرسد.
- فایل `.env` ساخته می‌شود و در صورت تایید، سرویس‌ها بالا می‌آیند.

یا دستی:
```bash
cp .env.example .env
# سپس .env را ویرایش کنید و حداقل BOT_TOKEN را مقداردهی نمایید
```

حداقل متغیرهای مهم:
- `BOT_TOKEN`: توکن ربات تلگرام
- `DATABASE_URL`: پیش‌فرض روی PostgreSQL داخل docker-compose تنظیم است
- (اختیاری) `DOMAIN` و `EMAIL` برای فعال‌سازی HTTPS توسط Caddy

## 3) اجرای سرویس‌ها
- با اسکریپت نصب: در پایان از شما می‌پرسد اجرا شود یا خیر.
- اجرای دستی:
```bash
docker compose up -d --build
```
اگر `DOMAIN` و `EMAIL` را تنظیم نکرده‌اید، سرویس `caddy` اجرا نمی‌شود. بعداً می‌توانید فعال کنید:
```bash
docker compose up -d caddy
```

## 4) بررسی سلامت
- API: روی سرور اجرا کنید: `curl -f http://localhost:8000/health`
- مشاهده لاگ‌های ربات:
```bash
docker compose logs -f bot
```

## 5) اتصال دامنه و HTTPS (اختیاری)
1. رکوردهای DNS دامنه را به IP سرور اشاره دهید (A/AAAA).
2. در `.env` مقدارهای `DOMAIN` و `EMAIL` را تنظیم کنید.
3. اجرا/فعال‌سازی Caddy:
```bash
docker compose up -d caddy
```
Caddy خودکار گواهی‌های SSL را از Let's Encrypt دریافت و تمدید می‌کند.

## 6) مهاجرت دیتابیس
کانتینر API در شروع، اسکیمای اولیه را ایجاد می‌کند. برای اعمال مایگریشن با Alembic:
```bash
docker compose exec api alembic upgrade head
```

## 7) به‌روزرسانی پروژه
```bash
git pull
# در صورت تغییرات مهم
docker compose build --no-cache api bot
docker compose up -d
# (اختیاری) اسکریپت به‌روزرسانی
# bash scripts/update.sh
```

## 8) بکاپ‌گیری (اختیاری)
بکاپ ساده از دیتابیس (روی میزبان):
```bash
mkdir -p backups
source .env
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > backups/db_$(date +%F).sql.gz
```

## 9) اجرای بدون Docker (برای توسعه)
نیاز به Python 3.11+ و PostgreSQL دارید:
```bash
pip install -r app/requirements.txt
# تنظیم DATABASE_URL در .env برای اتصال خارج از کانتینر
uvicorn api.main:app --host 0.0.0.0 --port 8000
python -m bot.main
```

## رفع اشکال‌های رایج
- API بالا نمی‌آید: لاگ `api` را ببینید: `docker compose logs -f api`
- ربات تلگرام وصل نمی‌شود: مقدار `BOT_TOKEN` و دسترسی شبکه VPS را بررسی کنید.
- دامنه SSL نمی‌گیرد: اتصال DNS، باز بودن پورت‌های 80/443 و صحت `DOMAIN`/`EMAIL` را بررسی کنید.

موفق باشید!