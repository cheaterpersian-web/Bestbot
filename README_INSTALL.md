# Installation (v1.0.1)

Old one-script installer has been removed. Use Docker Compose with PostgreSQL.

## 📋 Prerequisites
- Linux/macOS/WSL2
- Docker & Docker Compose
- Telegram Bot Token

## 🚀 Steps
1) Create env file
```bash
cp .env.example .env
```

2) Start stack
```bash
docker compose up -d --build
```

3) Verify
```bash
docker compose ps
docker compose logs -f api | cat
curl http://localhost:8000/health
```

## 🔗 Services
- API: http://localhost:8000
- Bot: runs in background after migrations

## 🛠️ Common Commands
```bash
docker compose restart api
docker compose exec api alembic upgrade head
docker compose down -v
```

## 📚 Docs
- Quick start: QUICK_START.md
- Full guide: INSTALLATION_GUIDE_FA.md

Note: This project is for legitimate VPN service providers.