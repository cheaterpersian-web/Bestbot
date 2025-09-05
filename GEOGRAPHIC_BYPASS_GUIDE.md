# راهنمای دور زدن محدودیت‌های جغرافیایی Docker Hub

## مشکل
Docker Hub به دلیل قوانین صادرات آمریکا، دسترسی از برخی کشورها (از جمله ایران) را مسدود کرده است. این خطا را دریافت می‌کنید:

```
Error response from daemon: pull access denied for prom/prometheus, repository does not exist or may require 'docker login': denied: <html><body><h1>403 Forbidden</h1>
Since Docker is a US company, we must comply with US export control regulations...
```

## راه‌حل‌های موجود

### 1. استفاده از اسکریپت خودکار (توصیه می‌شود)

```bash
# اجرای اسکریپت دور زدن محدودیت
sudo ./install-geo-bypass.sh
```

این اسکریپت:
- تنظیمات Docker را برای استفاده از آینه‌های ایرانی پیکربندی می‌کند
- سعی می‌کند تصاویر را از منابع مختلف دانلود کند
- گزینه‌های مختلف نصب را ارائه می‌دهد

### 2. نصب دستی با تنظیمات Docker

#### مرحله 1: تنظیم آینه‌های Docker

```bash
# ایجاد فایل تنظیمات Docker
sudo mkdir -p /etc/docker

sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
    "registry-mirrors": [
        "https://docker.mirror.iranrepo.ir",
        "https://docker.iranrepo.ir",
        "https://registry.docker-cn.com",
        "https://dockerhub.azk8s.cn",
        "https://reg-mirror.qiniu.com"
    ],
    "insecure-registries": [
        "docker.mirror.iranrepo.ir",
        "docker.iranrepo.ir"
    ]
}
EOF

# راه‌اندازی مجدد Docker
sudo systemctl restart docker
```

#### مرحله 2: دانلود تصاویر با منابع جایگزین

```bash
# دانلود تصاویر اصلی
docker pull postgres:16-alpine
docker pull nginx:alpine

# دانلود تصاویر مانیتورینگ از منابع جایگزین
docker pull quay.io/prometheus/prometheus:latest
docker pull quay.io/grafana/grafana:latest

# برچسب‌گذاری تصاویر جایگزین
docker tag quay.io/prometheus/prometheus:latest prom/prometheus:latest
docker tag quay.io/grafana/grafana:latest grafana/grafana:latest
```

#### مرحله 3: نصب با فایل‌های جایگزین

**گزینه A: نصب کامل با مانیتورینگ**
```bash
docker compose up -d
```

**گزینه B: نصب حداقلی بدون مانیتورینگ**
```bash
docker compose up -d
```

### 3. استفاده از VPN یا پروکسی

اگر روش‌های بالا کار نکرد، می‌توانید از VPN استفاده کنید:

```bash
# تنظیم پروکسی برای Docker (در صورت داشتن VPN)
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
export NO_PROXY=localhost,127.0.0.1

# سپس اجرای نصب عادی
docker compose up -d
```

### 4. نصب بدون Docker (پیشرفته)

اگر Docker اصلاً کار نمی‌کند، می‌توانید سرویس‌ها را مستقیماً نصب کنید:

#### نصب PostgreSQL (در صورت نیاز نیتیو)
```bash
sudo apt update
sudo apt install postgresql
```

#### نصب Python و وابستگی‌ها
```bash
sudo apt install python3 python3-pip python3-venv
cd app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## بررسی وضعیت نصب

```bash
# بررسی وضعیت کانتینرها
docker ps

# بررسی لاگ‌ها
docker compose logs | cat

# تست API
curl http://localhost:8000/health
```

## دسترسی به سرویس‌ها

- **API**: http://localhost:8000
- **Bot**: در پس‌زمینه اجرا می‌شود
- **Prometheus** (در صورت نصب): http://localhost:9090
- **Grafana** (در صورت نصب): http://localhost:3000 (admin/admin)

## عیب‌یابی

### مشکل: تصاویر دانلود نمی‌شوند
```bash
# پاک کردن کش Docker
docker system prune -a

# تلاش مجدد با آینه‌های مختلف
docker pull --platform linux/amd64 postgres:16-alpine
```

### مشکل: کانتینرها شروع نمی‌شوند
```bash
# بررسی لاگ‌ها
docker compose logs [service_name] | cat

# بررسی پورت‌های استفاده شده
sudo netstat -tulpn | grep :3306
sudo netstat -tulpn | grep :6379
```

### مشکل: دسترسی به دیتابیس
```bash
# اتصال به PostgreSQL
docker exec -it vpn_bot_postgres psql -U vpn_user -d vpn_bot
```

## نکات مهم

1. **امنیت**: پس از نصب، رمزهای عبور پیش‌فرض را تغییر دهید
2. **پشتیبان‌گیری**: از دیتابیس و تنظیمات پشتیبان تهیه کنید
3. **به‌روزرسانی**: تصاویر Docker را به‌طور منظم به‌روزرسانی کنید
4. **مانیتورینگ**: در صورت نیاز، سرویس‌های مانیتورینگ را فعال کنید

## پشتیبانی

در صورت بروز مشکل:
1. لاگ‌های سیستم را بررسی کنید
2. وضعیت سرویس‌ها را چک کنید
3. از اسکریپت‌های جایگزین استفاده کنید
4. در صورت نیاز، نصب دستی را امتحان کنید