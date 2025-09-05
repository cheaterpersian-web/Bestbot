from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NotificationType(str, Enum):
    """Types of notifications"""
    SERVICE_EXPIRY = "service_expiry"  # انقضای سرویس
    SERVICE_EXPIRY_WARNING = "service_expiry_warning"  # هشدار انقضا
    WALLET_LOW = "wallet_low"  # موجودی کم کیف پول
    PAYMENT_RECEIVED = "payment_received"  # دریافت پرداخت
    PAYMENT_APPROVED = "payment_approved"  # تایید پرداخت
    PAYMENT_REJECTED = "payment_rejected"  # رد پرداخت
    NEW_SERVICE = "new_service"  # سرویس جدید
    SERVICE_RENEWED = "service_renewed"  # تمدید سرویس
    DISCOUNT_AVAILABLE = "discount_available"  # تخفیف موجود
    CASHBACK_EARNED = "cashback_earned"  # کسب کش‌بک
    REFERRAL_BONUS = "referral_bonus"  # پاداش معرفی
    TRIAL_APPROVED = "trial_approved"  # تایید تست
    TRIAL_EXPIRED = "trial_expired"  # انقضای تست
    RESELLER_APPROVED = "reseller_approved"  # تایید نمایندگی
    SYSTEM_MAINTENANCE = "system_maintenance"  # تعمیرات سیستم
    SECURITY_ALERT = "security_alert"  # هشدار امنیتی


class NotificationStatus(str, Enum):
    """Notification status"""
    PENDING = "pending"  # در انتظار
    SENT = "sent"  # ارسال شده
    DELIVERED = "delivered"  # تحویل داده شده
    FAILED = "failed"  # ناموفق
    READ = "read"  # خوانده شده


class NotificationTemplate(Base):
    """Notification templates"""
    name: Mapped[str] = mapped_column(String(128), unique=True)
    notification_type: Mapped[NotificationType] = mapped_column(String(32))
    
    # Template content
    title: Mapped[str] = mapped_column(String(256))
    message: Mapped[str] = mapped_column(Text)
    
    # Template variables (JSON format)
    variables: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # 0=normal, 1=high, 2=urgent
    
    # Timing
    send_immediately: Mapped[bool] = mapped_column(Boolean, default=True)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Conditions
    conditions: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # When to send


class Notification(Base):
    """Individual notifications"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    notification_type: Mapped[NotificationType] = mapped_column(String(32))
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("notificationtemplate.id"), nullable=True)
    
    # Content
    title: Mapped[str] = mapped_column(String(256))
    message: Mapped[str] = mapped_column(Text)
    
    # Status and timing
    status: Mapped[NotificationStatus] = mapped_column(String(16), default=NotificationStatus.PENDING)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    
    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Context
    context_data: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Related data
    related_service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service.id"), nullable=True)
    related_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transaction.id"), nullable=True)
    
    # Delivery tracking
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class NotificationSettings(Base):
    """User notification preferences"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"), unique=True)
    
    # General settings
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-23
    quiet_hours_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-23
    
    # Notification type preferences
    service_expiry_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    service_expiry_days_before: Mapped[int] = mapped_column(Integer, default=3)  # Days before expiry
    
    wallet_low_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    wallet_low_threshold: Mapped[int] = mapped_column(Integer, default=10000)  # IRR
    
    payment_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    discount_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    referral_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    system_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Frequency settings
    max_notifications_per_day: Mapped[int] = mapped_column(Integer, default=10)
    notification_cooldown_minutes: Mapped[int] = mapped_column(Integer, default=30)
    
    # Last notification tracking
    last_notification_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notifications_today: Mapped[int] = mapped_column(Integer, default=0)
    last_reset_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class NotificationLog(Base):
    """Notification delivery logs"""
    notification_id: Mapped[int] = mapped_column(ForeignKey("notification.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Delivery details
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[NotificationStatus] = mapped_column(String(16))
    
    # Timing
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    # Response data
    telegram_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_data: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)