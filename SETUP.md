# VPN Telegram Bot - Setup Guide

This guide will walk you through setting up the VPN Telegram Bot from scratch.

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **RAM**: Minimum 2GB, Recommended 4GB+
- **Storage**: Minimum 20GB free space
- **CPU**: 2+ cores recommended

### Software Requirements
- Docker & Docker Compose
- Git
- A domain name (optional but recommended)
- SSL certificate (for production)

## 🚀 Step-by-Step Setup

### Step 1: Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Step 2: Clone Repository

```bash
# Clone the repository
git clone <repository-url>
cd vpn-telegram-bot

# Make scripts executable
chmod +x scripts/*.sh
```

### Step 3: Environment Configuration (v1.0.1)

Create the `.env` file:

```bash
cp .env.example .env
nano .env
```

Configure the following variables:

```env
# ===========================================
# TELEGRAM BOT CONFIGURATION
# ===========================================
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS=[123456789,987654321]
BOT_USERNAME=your_bot_username

# ===========================================
# DATABASE CONFIGURATION
# ===========================================
DATABASE_URL=postgresql+asyncpg://vpn_user:vpn_pass@db:5432/vpn_bot

# ===========================================
# SALES & PAYMENT CONFIGURATION
# ===========================================
SALES_ENABLED=true
AUTO_APPROVE_RECEIPTS=false
MIN_TOPUP_AMOUNT=50000
MAX_TOPUP_AMOUNT=50000000
ENABLE_TEST_ACCOUNTS=false

# ===========================================
# SECURITY CONFIGURATION
# ===========================================
ENABLE_FRAUD_DETECTION=true
MAX_DAILY_TRANSACTIONS=10
MAX_DAILY_AMOUNT=1000000

# ===========================================
# REFERRAL SYSTEM
# ===========================================
REFERRAL_PERCENT=10
REFERRAL_FIXED=0

# ===========================================
# PAYMENT GATEWAYS
# ===========================================
ENABLE_STARS=false
ENABLE_ZARINPAL=false
ZARINPAL_MERCHANT_ID=

# ===========================================
# MISCELLANEOUS
# ===========================================
STATUS_URL=https://your-status-page.com
UPTIME_ROBOT_API_KEY=
SUPPORT_CHANNEL=@your_support_channel
CHANNEL_USERNAME=@your_channel
JOIN_CHANNEL_REQUIRED=false
REQUIRE_PHONE_VERIFICATION=false
```

### Step 4: Telegram Bot Setup

1. **Create a Bot**:
   - Message @BotFather on Telegram
   - Send `/newbot`
   - Choose a name and username
   - Copy the bot token to `BOT_TOKEN` in `.env`

2. **Configure Bot Commands**:
   ```
   start - شروع ربات
   admin - پنل مدیریت
   help - راهنما
   ```

3. **Set Bot Description**:
   ```
   ربات فروش VPN - خرید و مدیریت سرویس‌های VPN
   ```

### Step 5: Database Setup

The bot now uses PostgreSQL by default via Docker. The database will be automatically created when you start the containers.

### Step 6: VPN Panel Configuration

#### For x-ui Panel:
1. Install x-ui panel on your server
2. Create an API user with full permissions
3. Note the API URL and credentials

#### For 3x-ui Panel:
1. Install 3x-ui panel
2. Enable API access
3. Create API credentials

#### For Hiddify Panel:
1. Install Hiddify panel
2. Configure API access
3. Set up authentication

### Step 7: Start the Application (v1.0.1)

```bash
# Start all services
cp .env.example .env
docker compose up -d --build

# Check logs
docker compose logs -f api | cat
docker compose logs -f bot | cat
docker compose logs -f db | cat

# Check status
docker compose ps
```

### Step 8: Initial Configuration

1. **Access Admin Panel**:
   - Start a conversation with your bot
   - Send `/admin`
   - Configure servers, categories, and plans

2. **Add Payment Cards**:
   - Go to admin panel
   - Add your payment card information
   - Set primary cards

3. **Configure Content**:
   - Set up FAQ content
   - Add tutorial materials
   - Configure referral text

## 🔧 Advanced Configuration

### SSL/HTTPS Setup (Production)

```bash
# Install nginx
sudo apt install nginx

# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com

# Configure nginx
sudo nano /etc/nginx/sites-available/vpn-bot
```

Nginx configuration:
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Backup Configuration

Create a backup script:

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup"
DB_NAME="vpn_bot"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
docker-compose exec -T db mysqldump -u vpn_user -pvpn_pass $DB_NAME > $BACKUP_DIR/db_$DATE.sql

# Application backup
tar -czf $BACKUP_DIR/app_$DATE.tar.gz app/

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

Add to crontab:
```bash
# Daily backup at 2 AM
0 2 * * * /path/to/backup.sh
```

### Monitoring Setup

Install monitoring tools:

```bash
# Install htop for system monitoring
sudo apt install htop

# Install docker monitoring
docker run -d \
  --name=cadvisor \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  --publish=8080:8080 \
  gcr.io/cadvisor/cadvisor:latest
```

## 🧪 Testing

### Test Bot Functionality

1. **User Registration**:
   - Send `/start` to the bot
   - Verify user is registered in database

2. **Admin Panel**:
   - Send `/admin`
   - Test dashboard functionality
   - Add a test server and plan

3. **Purchase Flow**:
   - Create a test purchase
   - Test payment processing
   - Verify service creation

4. **Wallet System**:
   - Test wallet top-up
   - Test balance transfer
   - Verify transaction history

### Load Testing

```bash
# Install artillery for load testing
npm install -g artillery

# Create test configuration
cat > load-test.yml << EOF
config:
  target: 'http://localhost:8000'
  phases:
    - duration: 60
      arrivalRate: 10
scenarios:
  - name: "API Health Check"
    requests:
      - get:
          url: "/health"
EOF

# Run load test
artillery run load-test.yml
```

## 🚨 Troubleshooting

### Common Issues

1. **Bot Not Responding**:
   ```bash
   # Check bot logs
   docker compose logs bot | cat
   
   # Verify bot token
   curl -X GET "https://api.telegram.org/bot<TOKEN>/getMe"
   ```

2. **Database Connection Issues**:
   ```bash
   # Check database status
   docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\\l" | cat
   
   # Restart database
   docker compose restart db
   ```

3. **Panel Integration Issues**:
   ```bash
   # Test panel connectivity
   curl -X GET "https://your-panel.com/api/status"
   
   # Check panel logs
   docker compose logs api | cat
   ```

### Performance Optimization

1. **Database Optimization**:
   ```sql
   -- Add indexes for better performance
   CREATE INDEX idx_user_telegram_id ON telegramuser(telegram_user_id);
   CREATE INDEX idx_transaction_user_id ON transaction(user_id);
   CREATE INDEX idx_service_user_id ON service(user_id);
   ```

2. **Application Optimization**:
   ```bash
   # Increase worker processes
   # In docker-compose.yml
   command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

## 📊 Maintenance

### Daily Tasks
- Check bot uptime
- Monitor transaction success rates
- Review fraud detection alerts
- Check server resources

### Weekly Tasks
- Review user statistics
- Update payment card information
- Check panel connectivity
- Review error logs

### Monthly Tasks
- Update dependencies
- Review security settings
- Analyze performance metrics
- Plan capacity upgrades

## 🔐 Security Checklist

- [ ] Change default database passwords
- [ ] Enable SSL/HTTPS
- [ ] Configure firewall rules
- [ ] Set up regular backups
- [ ] Enable fraud detection
- [ ] Configure admin access controls
- [ ] Monitor for suspicious activity
- [ ] Keep dependencies updated

## 📞 Support

If you encounter issues:

1. Check the logs: `docker-compose logs -f`
2. Review this documentation
3. Check GitHub issues
4. Contact support team

---

**Note**: This setup guide assumes a basic understanding of Linux, Docker, and Telegram bots. For production deployment, consider hiring a DevOps specialist.