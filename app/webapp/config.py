"""
Configuration for Telegram Mini App
"""

import os
from typing import Optional

class WebAppConfig:
    """Configuration for Telegram Mini App"""
    
    # Bot settings
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    WEBHOOK_URL: Optional[str] = os.getenv("WEBHOOK_URL")
    
    # WebApp settings
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "https://yourdomain.com")
    WEBAPP_SECRET: str = os.getenv("WEBAPP_SECRET", "your-secret-key")
    
    # API settings
    API_BASE_URL: str = os.getenv("API_BASE_URL", "https://yourdomain.com/api")
    
    # Security settings
    ALLOWED_ORIGINS: list = [
        "https://web.telegram.org",
        "https://telegram.org",
        "https://yourdomain.com"
    ]
    
    # Feature flags
    ENABLE_WEBAPP: bool = os.getenv("ENABLE_WEBAPP", "true").lower() == "true"
    ENABLE_PAYMENTS: bool = os.getenv("ENABLE_PAYMENTS", "true").lower() == "true"
    ENABLE_QR_CODES: bool = os.getenv("ENABLE_QR_CODES", "true").lower() == "true"
    
    # UI settings
    THEME_COLOR: str = os.getenv("THEME_COLOR", "#2481cc")
    PRIMARY_COLOR: str = os.getenv("PRIMARY_COLOR", "#2481cc")
    SECONDARY_COLOR: str = os.getenv("SECONDARY_COLOR", "#f1f1f1")
    
    # Cache settings
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 1 hour