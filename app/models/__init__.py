# Import all models to ensure they are registered with SQLAlchemy
from .base import Base
from .user import TelegramUser
from .service import Service
from .catalog import Server, Category, Plan
from .billing import PaymentCard, Transaction
from .orders import PurchaseIntent
from .discounts import DiscountCode
from .referrals import ReferralEvent
from .support import Ticket, TicketMessage
from .tutorials import Tutorial
from .content import ContentItem
from .admin import AdminUser, BotSettings, Gift, ResellerRequest, Reseller, Button
from .analytics import UserActivity, DailyStats, ServiceUsage
from .trial import TrialRequest, TrialConfig
from .smart_discounts import SmartDiscount, DiscountUsage, CashbackRule, CashbackTransaction, UserDiscountProfile
from .crm import UserProfile, UserActivity, PersonalizedOffer, Campaign, CampaignRecipient, UserInsight, CustomerJourney
from .notifications import Notification, NotificationTemplate, NotificationSettings, NotificationLog

__all__ = [
    "Base",
    "TelegramUser",
    "Service", 
    "Server",
    "Category",
    "Plan",
    "PaymentCard",
    "Transaction",
    "PurchaseIntent",
    "DiscountCode",
    "ReferralEvent",
    "Ticket",
    "TicketMessage",
    "Tutorial",
    "ContentItem",
    "AdminUser",
    "BotSettings",
    "Gift",
    "ResellerRequest",
    "Reseller",
    "Button",
    "UserActivity",
    "DailyStats",
    "ServiceUsage",
    "TrialRequest",
    "TrialConfig",
    "SmartDiscount",
    "DiscountUsage",
    "CashbackRule",
    "CashbackTransaction",
    "UserDiscountProfile",
    "UserProfile",
    "UserActivity",
    "PersonalizedOffer",
    "Campaign",
    "CampaignRecipient",
    "UserInsight",
    "CustomerJourney",
    "Notification",
    "NotificationTemplate",
    "NotificationSettings",
    "NotificationLog",
]