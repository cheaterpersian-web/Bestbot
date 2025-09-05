from functools import lru_cache
from typing import List
import json

from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore unknown env keys like TZ
    )

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Telegram
    # Map env BOT_TOKEN -> bot_token; also accept BOT_TOKEN in .env
    bot_token: str = Field(default="your_telegram_bot_token_here", alias="BOT_TOKEN")
    admin_ids: List[int] = []
    bot_username: str = ""

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, int):
            return [int(v)]
        if isinstance(v, str):
            s = v.strip()
            # try JSON first
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [int(x) for x in parsed]
                if isinstance(parsed, int):
                    return [int(parsed)]
            except Exception:
                pass
            # fallback: CSV "1,2,3" or space/comma separated
            parts = [p for p in s.replace(" ", "").split(",") if p]
            try:
                return [int(p) for p in parts] if parts else []
            except Exception:
                return []
        return []

    # Database
    database_url: str = "postgresql+asyncpg://vpn_user:vpn_pass@db:5432/vpn_bot"

    # Sales/Payments
    sales_enabled: bool = True
    auto_approve_receipts: bool = False
    min_topup_amount: int = 50_000
    max_topup_amount: int = 50_000_000
    enable_test_accounts: bool = False
    require_phone_verification: bool = False
    join_channel_required: bool = False
    channel_username: str = ""

    # Panels
    default_panel_mode: str = "mock"  # mock | xui | 3xui | hiddify | sanaei

    # Referrals
    referral_percent: int = 10
    referral_fixed: int = 0

    # Security
    enable_fraud_detection: bool = True
    max_daily_transactions: int = 10
    max_daily_amount: int = 1_000_000

    # Payment Gateways
    enable_stars: bool = False
    enable_zarinpal: bool = False
    zarinpal_merchant_id: str = ""

    # Misc
    status_url: str = ""
    uptime_robot_api_key: str = ""
    support_channel: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

