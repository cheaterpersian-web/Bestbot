from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, Text, Numeric, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UserSegment(str, Enum):
    """User segmentation categories"""
    NEW_USER = "new_user"  # کاربر جدید
    ACTIVE_USER = "active_user"  # کاربر فعال
    VIP_USER = "vip_user"  # کاربر VIP
    CHURNED_USER = "churned_user"  # کاربر ترک کرده
    HIGH_VALUE = "high_value"  # کاربر با ارزش بالا
    LOW_VALUE = "low_value"  # کاربر با ارزش پایین
    FREQUENT_BUYER = "frequent_buyer"  # خریدار مکرر
    OCCASIONAL_BUYER = "occasional_buyer"  # خریدار گاه‌به‌گاه


class ActivityType(str, Enum):
    """Types of user activities"""
    LOGIN = "login"
    PURCHASE = "purchase"
    WALLET_TOPUP = "wallet_topup"
    SERVICE_RENEWAL = "service_renewal"
    SERVICE_EXPIRY = "service_expiry"
    TICKET_CREATED = "ticket_created"
    REFERRAL = "referral"
    DISCOUNT_USED = "discount_used"
    CASHBACK_EARNED = "cashback_earned"
    TRIAL_REQUESTED = "trial_requested"
    RESELLER_REQUESTED = "reseller_requested"


class UserProfile(Base):
    """Enhanced user profile for CRM"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"), unique=True)
    
    # Segmentation
    primary_segment: Mapped[UserSegment] = mapped_column(SQLEnum(UserSegment), default=UserSegment.NEW_USER)
    secondary_segments: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # List of segments
    
    # Behavioral data
    login_frequency: Mapped[int] = mapped_column(Integer, default=0)  # Logins per week
    purchase_frequency: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # Purchases per month
    avg_purchase_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    preferred_payment_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    preferred_plan_types: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    preferred_servers: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Engagement metrics
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    days_since_last_activity: Mapped[int] = mapped_column(Integer, default=0)
    engagement_score: Mapped[float] = mapped_column(Numeric(3, 2), default=0)  # 0-1 score
    
    # Risk assessment
    risk_score: Mapped[float] = mapped_column(Numeric(3, 2), default=0)  # 0-1 score
    fraud_attempts: Mapped[int] = mapped_column(Integer, default=0)
    chargeback_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Lifecycle stage
    lifecycle_stage: Mapped[str] = mapped_column(String(32), default="new")  # new, active, at_risk, churned
    churn_probability: Mapped[float] = mapped_column(Numeric(3, 2), default=0)  # 0-1 probability
    
    # Personalization
    interests: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    communication_preferences: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    language_preference: Mapped[str] = mapped_column(String(8), default="fa")
    
    # Campaign tracking
    last_campaign_contact: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    campaign_responses: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Last updated
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserActivity(Base):
    """Detailed user activity tracking"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    activity_type: Mapped[ActivityType] = mapped_column(SQLEnum(ActivityType))
    
    # Activity details
    description: Mapped[str] = mapped_column(String(512))
    metadata: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Additional context
    
    # Context
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PersonalizedOffer(Base):
    """Personalized offers for users"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Offer details
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    offer_type: Mapped[str] = mapped_column(String(32))  # discount, cashback, bonus, etc.
    
    # Offer value
    discount_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    discount_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bonus_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Targeting
    target_segments: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    target_plans: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    target_servers: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Validity
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_to: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Usage tracking
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Creation context
    created_by: Mapped[str] = mapped_column(String(32), default="system")  # system, admin, campaign
    creation_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class Campaign(Base):
    """Marketing campaigns"""
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Campaign type
    campaign_type: Mapped[str] = mapped_column(String(32))  # email, push, broadcast, etc.
    
    # Targeting
    target_segments: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    target_criteria: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Content
    subject: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    message_content: Mapped[str] = mapped_column(Text)
    media_file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    
    # Scheduling
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Status
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft, scheduled, sent, completed
    
    # Results
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    opened_count: Mapped[int] = mapped_column(Integer, default=0)
    clicked_count: Mapped[int] = mapped_column(Integer, default=0)
    converted_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class CampaignRecipient(Base):
    """Campaign recipients tracking"""
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Delivery status
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, delivered, failed, bounced
    
    # Engagement tracking
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    converted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)


class UserInsight(Base):
    """AI-generated user insights"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Insight details
    insight_type: Mapped[str] = mapped_column(String(32))  # behavior, preference, risk, opportunity
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Numeric(3, 2))  # 0-1 confidence
    
    # Recommendations
    recommendations: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    action_items: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Metadata
    data_sources: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class CustomerJourney(Base):
    """Customer journey mapping"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Journey stage
    current_stage: Mapped[str] = mapped_column(String(32))  # awareness, consideration, purchase, retention, advocacy
    stage_entry_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Journey data
    touchpoints: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # List of touchpoints
    conversion_events: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Key conversion events
    dropoff_points: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Where users drop off
    
    # Journey metrics
    time_in_stage: Mapped[int] = mapped_column(Integer, default=0)  # Days in current stage
    total_journey_time: Mapped[int] = mapped_column(Integer, default=0)  # Total days in journey
    conversion_probability: Mapped[float] = mapped_column(Numeric(3, 2), default=0)  # 0-1 probability
    
    # Next actions
    next_recommended_action: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    next_action_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)