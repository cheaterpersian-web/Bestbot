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
from .advanced_reseller import AdvancedReseller, SubReseller, ResellerCommission, ResellerTarget, ResellerActivity, ResellerPayment, ResellerLevelRule
from .anti_fraud import FraudRule, FraudDetection, UserFraudProfile, FraudPattern, FraudAlert, FraudWhitelist, FraudBlacklist
from .scheduled_messages import ScheduledMessage, Campaign, MessageRecipient, MessageTemplate, MessageSchedule, MessageAnalytics
from .refund_system import RefundRequest, ServiceUpgrade, WalletTransaction, RefundPolicy, UpgradeRule, RefundAnalytics

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
    "AdvancedReseller",
    "SubReseller",
    "ResellerCommission",
    "ResellerTarget",
    "ResellerActivity",
    "ResellerPayment",
    "ResellerLevelRule",
    "FraudRule",
    "FraudDetection",
    "UserFraudProfile",
    "FraudPattern",
    "FraudAlert",
    "FraudWhitelist",
    "FraudBlacklist",
    "ScheduledMessage",
    "Campaign",
    "MessageRecipient",
    "MessageTemplate",
    "MessageSchedule",
    "MessageAnalytics",
    "RefundRequest",
    "ServiceUpgrade",
    "WalletTransaction",
    "RefundPolicy",
    "UpgradeRule",
    "RefundAnalytics",
]