from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Telegram
    bot_token: str = "your_telegram_bot_token_here"
    admin_ids: List[int] = []

    # Database
    database_url: str = "postgresql+asyncpg://vpn_user:vpn_pass@db:5432/vpn_bot"

    # Sales/Payments
    sales_enabled: bool = True
    auto_approve_receipts: bool = False
    min_topup_amount: int = 50_000
    max_topup_amount: int = 50_000_000

    # Panels
    default_panel_mode: str = "mock"  # mock | xui | 3xui | hiddify


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

