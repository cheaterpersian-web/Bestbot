from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MessageType(str, Enum):
    """Types of scheduled messages"""
    TEXT = "text"  # متن ساده
    IMAGE = "image"  # تصویر
    VIDEO = "video"  # ویدیو
    DOCUMENT = "document"  # سند
    AUDIO = "audio"  # صدا
    VOICE = "voice"  # پیام صوتی
    STICKER = "sticker"  # استیکر
    ANIMATION = "animation"  # گیف
    POLL = "poll"  # نظرسنجی
    FORWARD = "forward"  # فوروارد


class MessageStatus(str, Enum):
    """Message status"""
    DRAFT = "draft"  # پیش‌نویس
    SCHEDULED = "scheduled"  # زمان‌بندی شده
    SENDING = "sending"  # در حال ارسال
    SENT = "sent"  # ارسال شده
    FAILED = "failed"  # ناموفق
    CANCELLED = "cancelled"  # لغو شده


class CampaignType(str, Enum):
    """Campaign types"""
    BROADCAST = "broadcast"  # همگانی
    TARGETED = "targeted"  # هدفمند
    FOLLOW_UP = "follow_up"  # پیگیری
    PROMOTIONAL = "promotional"  # تبلیغاتی
    EDUCATIONAL = "educational"  # آموزشی
    REMINDER = "reminder"  # یادآوری


class ScheduledMessage(Base):
    """Scheduled message model"""
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Message content
    message_type: Mapped[MessageType] = mapped_column(SQLEnum(MessageType), default=MessageType.TEXT)
    content: Mapped[str] = mapped_column(Text)  # Message text or file ID
    
    # Media files
    media_file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    media_caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    timezone: Mapped[str] = mapped_column(String(32), default="Asia/Tehran")
    
    # Status
    status: Mapped[MessageStatus] = mapped_column(SQLEnum(MessageStatus), default=MessageStatus.DRAFT)
    
    # Targeting
    target_type: Mapped[str] = mapped_column(String(32), default="all")  # all, specific, segment
    target_users: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # List of user IDs
    target_segments: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # List of segments
    target_criteria: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Custom criteria
    
    # Campaign info
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaign.id"), nullable=True)
    campaign_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    # Creator
    created_by: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Execution
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Settings
    parse_mode: Mapped[str] = mapped_column(String(16), default="HTML")
    disable_web_page_preview: Mapped[bool] = mapped_column(Boolean, default=False)
    disable_notification: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Retry settings
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_delay_minutes: Mapped[int] = mapped_column(Integer, default=5)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Campaign(Base):
    """Campaign model for organizing messages"""
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Campaign type
    campaign_type: Mapped[CampaignType] = mapped_column(SQLEnum(CampaignType))
    
    # Status
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft, active, completed, paused
    
    # Targeting
    target_audience: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    target_criteria: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Scheduling
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Creator
    created_by: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Statistics
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    total_sent: Mapped[int] = mapped_column(Integer, default=0)
    total_failed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class MessageRecipient(Base):
    """Message recipient tracking"""
    message_id: Mapped[int] = mapped_column(ForeignKey("scheduledmessage.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Delivery status
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, sent, failed, blocked
    
    # Delivery details
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    telegram_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Engagement
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class MessageTemplate(Base):
    """Message templates for reuse"""
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Template content
    message_type: Mapped[MessageType] = mapped_column(SQLEnum(MessageType))
    content: Mapped[str] = mapped_column(Text)
    media_file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    media_caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Template variables
    variables: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Available variables
    
    # Settings
    parse_mode: Mapped[str] = mapped_column(String(16), default="HTML")
    disable_web_page_preview: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Usage tracking
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Creator
    created_by: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MessageSchedule(Base):
    """Recurring message schedules"""
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Schedule type
    schedule_type: Mapped[str] = mapped_column(String(32))  # daily, weekly, monthly, custom
    
    # Schedule configuration
    schedule_config: Mapped[str] = mapped_column(JSON)  # Cron-like configuration
    
    # Message template
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("messagetemplate.id"), nullable=True)
    message_content: Mapped[str] = mapped_column(Text)
    
    # Targeting
    target_type: Mapped[str] = mapped_column(String(32), default="all")
    target_users: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    target_segments: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Execution tracking
    last_executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_execution_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    execution_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Creator
    created_by: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MessageAnalytics(Base):
    """Message analytics and statistics"""
    message_id: Mapped[int] = mapped_column(ForeignKey("scheduledmessage.id"))
    
    # Delivery statistics
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    read_count: Mapped[int] = mapped_column(Integer, default=0)
    clicked_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Engagement rates
    delivery_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # 0-100%
    read_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # 0-100%
    click_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # 0-100%
    
    # Timing
    avg_delivery_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # seconds
    first_delivery_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_delivery_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)