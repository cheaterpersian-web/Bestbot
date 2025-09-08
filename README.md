# VPN Telegram Bot - Persian Edition

A comprehensive, production-ready Telegram bot for selling VPN services with Persian language support. This bot provides a complete solution for VPN service providers with advanced features including payment processing, user management, admin dashboard, and fraud detection.

## 🚀 Features

### ✅ Phase 1 - Core Features (Implemented)

#### User Side
- **🛒 Purchase Flow**: Server → Category → Plan → Payment
  - Card-to-card payment with receipt validation
  - Wallet deduction (automatic)
  - Admin approval system for receipts
  - Fraud detection and scoring
- **📱 My Configs**: View all services, details, renew/add volume, regenerate UUID, delete
- **💰 Wallet System**: 
  - Top-up with receipt approval
  - Admin-defined min/max limits
  - Automatic deduction on purchases
  - Balance transfer between users
- **👤 User Profile**: ID, username, wallet balance, config count, last online, transfer balance
- **🎁 Referral System**: 
  - Unique referral links
  - Bonus % + fixed amount to wallet
  - Admin reports and statistics
- **🎫 Ticket System**: Create/view tickets with admin responses
- **📚 Tutorials**: OS-specific tutorials (Android, iOS, Windows, macOS, Linux)
- **🔍 Config Lookup**: Search by UUID/link → show remaining volume/time → add to account
- **📋 Other Menu**: Price list, FAQ, service status, reseller requests, trial configs

#### Admin Panel
- **📊 Dashboard**: Comprehensive stats (users, configs, categories, plans, income)
- **👥 User Management**: Block/unblock, wallet adjustment, detailed user info
- **🖥️ Server Management**: Add/edit/delete servers, reordering
- **📁 Category Management**: Full CRUD operations
- **📦 Plan Management**: Price per GB/day/server configuration
- **🎁 Gift System**: Volume/time to users, wallet balance (individual/bulk)
- **💳 Payment Settings**: Multi-card, random card, gateway support
- **⚙️ Bot Settings**: Sales toggle, test accounts, join-channel lock, phone verification
- **📢 Broadcast**: Send text, image, forward messages
- **🎫 Ticket Management**: Handle user support tickets
- **🤝 Reseller System**: Request approval and management

### 🔧 Technical Features
- **🏗️ Modular Architecture**: Clean separation of concerns
- **🗄️ Database**: MySQL 8 (utf8mb4)
- **🔒 Security**: Receipt validation, anti-fraud detection
- **🐳 Dockerized**: Complete stack with Bot + DB + API
- **🔌 API Integrations**: x-ui, 3x-ui, Hiddify panel support
- **📊 Analytics**: User activity tracking, daily stats
- **🛡️ Fraud Detection**: Advanced scoring system

## 📋 Requirements

- Python 3.11+
- MySQL 8+
- Docker & Docker Compose (recommended)
- Telegram Bot Token
- VPN Panel API access (x-ui, 3x-ui, or Hiddify)

## 🚀 شروع سریع (فارسی)

### 1) پیش‌نیازها
- Docker و Docker Compose
- توکن ربات تلگرام (BotFather)

### 2) نصب خودکار (توصیه‌شده)
```bash
bash scripts/setup.sh
```
این اسکریپت فایل `.env` را می‌سازد، مقادیر را از شما می‌پرسد و در صورت تمایل کانتینرها را اجرا می‌کند.

### 3) اجرای دستی (جایگزین)
```bash
# نصب وابستگی‌ها (لوکال)
pip install -r app/requirements.txt

# اجرای استک داکر
docker compose up -d --build

# اجرای مایگریشن‌ها (داخل کانتینر)
docker compose exec api alembic upgrade head
```

## 🏗️ Project Structure

```
vpn-telegram-bot/
├── app/
│   ├── bot/                    # Telegram bot implementation
│   │   ├── routers/           # Bot command handlers
│   │   ├── middlewares/       # Bot middlewares
│   │   ├── keyboards.py       # Keyboard layouts
│   │   └── inline.py          # Inline keyboards
│   ├── models/                # Database models
│   ├── services/              # Business logic services
│   │   ├── panels/           # VPN panel integrations
│   │   ├── fraud_detection.py
│   │   ├── payment_processor.py
│   │   └── admin_dashboard.py
│   ├── core/                 # Core configuration
│   └── api/                  # REST API (optional)
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## 🔧 Configuration

### Database Models
The bot uses SQLAlchemy with the following main models:
- `TelegramUser`: User information and wallet
- `Service`: VPN service configurations
- `Transaction`: Payment and wallet transactions
- `Server`, `Category`, `Plan`: Service catalog
- `Ticket`, `TicketMessage`: Support system
- `ReferralEvent`: Referral tracking
- `AdminUser`, `BotSettings`: Admin management

### Panel Integration
The bot supports multiple VPN panel types:
- **x-ui**: Full API integration
- **3x-ui**: Full API integration  
- **Hiddify**: Full API integration
- **Mock**: For testing and development

### Payment Processing
- **Card-to-Card**: Receipt validation with fraud detection
- **Wallet**: Internal balance system
- **Stars**: Telegram Stars integration (configurable)
- **Zarinpal**: Iranian payment gateway (configurable)

## 📊 Admin Commands

### Basic Commands
- `/admin` - Access admin panel
- `/start` - User registration and main menu

### Admin Panel Features
- **📊 Dashboard**: Real-time statistics and analytics
- **👥 User Management**: Block/unblock users, adjust wallets
- **📋 Transaction Review**: Approve/reject payments
- **🖥️ Server Management**: Add/edit/delete servers
- **📁 Category Management**: Organize service categories
- **📦 Plan Management**: Configure pricing and limits
- **🎁 Gift System**: Send gifts to users
- **📢 Broadcast**: Send messages to all users
- **🎫 Ticket Management**: Handle support requests

## 🔒 Security Features

### Fraud Detection
- Receipt validation and scoring
- Duplicate receipt detection
- Suspicious pattern analysis
- Daily transaction limits
- User behavior monitoring

### Admin Security
- Role-based access control
- Admin activity logging
- Secure transaction approval
- User blocking/unblocking

## 🚀 استقرار (Production)
1. روی سرور با پشتیبانی Docker مستقر کنید
2. DNS دامنه را به سرور اشاره دهید (A/AAAA)
3. در `.env` مقدارهای `DOMAIN`, `EMAIL`, `BOT_TOKEN`, `WEBAPP_URL` را تنظیم کنید
4. سرویس‌ها را با `docker compose up -d --build` بالا بیاورید (سرویس `caddy` فعال است)
5. Caddy به صورت خودکار SSL را از Let's Encrypt دریافت و تمدید می‌کند

### Monitoring
- Health checks for all services
- Database performance monitoring
- Bot uptime monitoring
- Transaction success rates
- User activity analytics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Contact the development team
- Check the documentation

## 🔄 Updates

### Version 1.0.0
- Initial release with core features
- Persian language support
- Complete admin panel
- Fraud detection system
- Multi-panel support

### Future Roadmap
- Telegram Mini App interface (now included at `/`)
- Advanced analytics dashboard
- Automated backup system
- Multi-language support
- Advanced reseller features

---

**Note**: This bot is designed for legitimate VPN service providers. Please ensure compliance with local laws and regulations in your jurisdiction.

## 📱 Telegram Mini App (WebApp)

The project includes a Telegram Mini App that users can open inside Telegram to manage their VPN services.

- Entry route: `/` serves `app/webapp/static/index.html`
- Static assets: `/static/*` from `app/webapp/static`
- Backend API for WebApp: `app/webapp/api.py` under `/api/*`

### Activation Steps
1. Set environment variables in `.env`:
   - `BOT_TOKEN=...` from BotFather
   - `WEBAPP_URL=https://your.domain` (public HTTPS URL)
2. Deploy API to a public HTTPS domain and ensure it serves the root page.
3. Start the bot service. Users can type `/webapp` or `/app` to get a button that opens the Mini App (handled by `app/bot/routers/webapp_entry.py`).
4. Optional: In BotFather, set a persistent menu button with your WebApp URL.

The frontend sends `Authorization: Bearer <initData>` and the backend verifies it according to Telegram's HMAC rules in `verify_telegram_auth`.