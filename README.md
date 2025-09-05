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
- **🗄️ Database**: PostgreSQL with optimized queries
- **🔒 Security**: Receipt validation, anti-fraud detection
- **🐳 Dockerized**: Complete stack with Bot + DB + API
- **🔌 API Integrations**: x-ui, 3x-ui, Hiddify panel support
- **📊 Analytics**: User activity tracking, daily stats
- **🛡️ Fraud Detection**: Advanced scoring system

## 📋 Requirements

- Python 3.11+
- PostgreSQL 13+
- Docker & Docker Compose (recommended)
- Telegram Bot Token
- VPN Panel API access (x-ui, 3x-ui, or Hiddify)

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd vpn-telegram-bot
```

### 2. Environment Configuration
Create a `.env` file in the root directory:

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_IDS=[123456789,987654321]
BOT_USERNAME=your_bot_username

# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://vpn_user:vpn_pass@db:5432/vpn_bot

# Sales/Payments
SALES_ENABLED=true
AUTO_APPROVE_RECEIPTS=false
MIN_TOPUP_AMOUNT=50000
MAX_TOPUP_AMOUNT=50000000

# Security
ENABLE_FRAUD_DETECTION=true
MAX_DAILY_TRANSACTIONS=10
MAX_DAILY_AMOUNT=1000000

# Referrals
REFERRAL_PERCENT=10
REFERRAL_FIXED=0

# Payment Gateways
ENABLE_STARS=false
ENABLE_ZARINPAL=false
ZARINPAL_MERCHANT_ID=

# Misc
STATUS_URL=https://your-status-page.com
UPTIME_ROBOT_API_KEY=
SUPPORT_CHANNEL=@your_support_channel
```

### 3. Start with Docker (v1.0.1)
```bash
cp .env.example .env
docker compose up -d --build
```

### 4. Notes on v1.0.1 Installer
- Old "easy install" and MySQL/Redis stack have been removed.
- New stack uses Docker Compose with PostgreSQL and Alembic migrations.
- Configure your env via `.env` (see `.env.example`).

### 5. Manual Setup (Alternative)
```bash
# Install dependencies
pip install -r app/requirements.txt

# Initialize database (inside container)
docker compose exec api alembic upgrade head

# Start the bot
python -m bot.main

# Start API server (optional)
uvicorn api.main:app --host 0.0.0.0 --port 8000
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

## 🚀 Deployment

### Production Deployment
1. Set up a VPS with Docker support
2. Configure environment variables
3. Set up SSL certificates
4. Configure reverse proxy (nginx)
5. Set up monitoring and logging
6. Configure backup strategy

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