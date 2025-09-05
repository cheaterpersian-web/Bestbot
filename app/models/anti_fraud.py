from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, Text, Numeric, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FraudType(str, Enum):
    """Types of fraud detection"""
    FAKE_RECEIPT = "fake_receipt"  # رسید جعلی
    DUPLICATE_PAYMENT = "duplicate_payment"  # پرداخت تکراری
    SUSPICIOUS_PATTERN = "suspicious_pattern"  # الگوی مشکوک
    HIGH_FREQUENCY = "high_frequency"  # فرکانس بالا
    UNUSUAL_AMOUNT = "unusual_amount"  # مبلغ غیرعادی
    MULTIPLE_ACCOUNTS = "multiple_accounts"  # چندین حساب
    CHARGEBACK = "chargeback"  # برگشت وجه
    REFUND_ABUSE = "refund_abuse"  # سوء استفاده از بازپرداخت
    ACCOUNT_TAKEOVER = "account_takeover"  # تصاحب حساب
    BOT_ACTIVITY = "bot_activity"  # فعالیت ربات


class FraudSeverity(str, Enum):
    """Fraud severity levels"""
    LOW = "low"  # کم
    MEDIUM = "medium"  # متوسط
    HIGH = "high"  # بالا
    CRITICAL = "critical"  # بحرانی


class FraudAction(str, Enum):
    """Actions to take for fraud"""
    WARN = "warn"  # هشدار
    SUSPEND = "suspend"  # تعلیق
    BLOCK = "block"  # مسدود
    DELETE_CONFIG = "delete_config"  # حذف کانفیگ
    REFUND = "refund"  # بازپرداخت
    INVESTIGATE = "investigate"  # بررسی


class FraudRule(Base):
    """Fraud detection rules"""
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Rule configuration
    fraud_type: Mapped[FraudType] = mapped_column(SQLEnum(FraudType))
    severity: Mapped[FraudSeverity] = mapped_column(SQLEnum(FraudSeverity))
    action: Mapped[FraudAction] = mapped_column(SQLEnum(FraudAction))
    
    # Detection criteria
    criteria: Mapped[str] = mapped_column(JSON)  # JSON criteria for detection
    threshold: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)
    time_window_hours: Mapped[int] = mapped_column(Integer, default=24)
    
    # Rule settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_action: Mapped[bool] = mapped_column(Boolean, default=False)  # Auto-trigger action
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Performance tracking
    triggered_count: Mapped[int] = mapped_column(Integer, default=0)
    false_positive_count: Mapped[int] = mapped_column(Integer, default=0)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FraudDetection(Base):
    """Individual fraud detection records"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    rule_id: Mapped[int] = mapped_column(ForeignKey("fraudrule.id"))
    
    # Detection details
    fraud_type: Mapped[FraudType] = mapped_column(SQLEnum(FraudType))
    severity: Mapped[FraudSeverity] = mapped_column(SQLEnum(FraudSeverity))
    confidence_score: Mapped[float] = mapped_column(Numeric(3, 2))  # 0-1 confidence
    
    # Context
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(JSON)  # Evidence data
    related_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transaction.id"), nullable=True)
    related_service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service.id"), nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(16), default="detected")  # detected, investigating, resolved, false_positive
    action_taken: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    action_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Admin handling
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Date
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserFraudProfile(Base):
    """User fraud risk profile"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"), unique=True)
    
    # Risk assessment
    risk_score: Mapped[float] = mapped_column(Numeric(3, 2), default=0)  # 0-1 risk score
    risk_level: Mapped[str] = mapped_column(String(16), default="low")  # low, medium, high, critical
    
    # Fraud history
    total_detections: Mapped[int] = mapped_column(Integer, default=0)
    high_severity_detections: Mapped[int] = mapped_column(Integer, default=0)
    false_positive_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Behavioral patterns
    transaction_frequency: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # Transactions per day
    avg_transaction_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    max_transaction_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    unusual_patterns: Mapped[int] = mapped_column(Integer, default=0)
    
    # Account security
    account_age_days: Mapped[int] = mapped_column(Integer, default=0)
    last_password_change: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    suspicious_logins: Mapped[int] = mapped_column(Integer, default=0)
    
    # Restrictions
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    restriction_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    restriction_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Monitoring
    is_monitored: Mapped[bool] = mapped_column(Boolean, default=False)
    monitoring_level: Mapped[str] = mapped_column(String(16), default="normal")  # normal, enhanced, strict
    
    # Last updated
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FraudPattern(Base):
    """Known fraud patterns for detection"""
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Pattern details
    pattern_type: Mapped[FraudType] = mapped_column(SQLEnum(FraudType))
    pattern_data: Mapped[str] = mapped_column(JSON)  # Pattern matching data
    
    # Detection settings
    confidence_threshold: Mapped[float] = mapped_column(Numeric(3, 2), default=0.7)
    severity: Mapped[FraudSeverity] = mapped_column(SQLEnum(FraudSeverity))
    
    # Performance
    detection_count: Mapped[int] = mapped_column(Integer, default=0)
    accuracy_rate: Mapped[float] = mapped_column(Numeric(3, 2), default=0)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FraudAlert(Base):
    """Real-time fraud alerts"""
    detection_id: Mapped[int] = mapped_column(ForeignKey("frauddetection.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Alert details
    alert_type: Mapped[str] = mapped_column(String(32))  # immediate, batch, summary
    severity: Mapped[FraudSeverity] = mapped_column(SQLEnum(FraudSeverity))
    message: Mapped[str] = mapped_column(Text)
    
    # Recipients
    admin_recipients: Mapped[str] = mapped_column(JSON)  # List of admin user IDs
    
    # Status
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, sent, acknowledged, resolved
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FraudWhitelist(Base):
    """Whitelist for trusted users/patterns"""
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    # Whitelist details
    reason: Mapped[str] = mapped_column(String(256))
    whitelist_type: Mapped[str] = mapped_column(String(32))  # user, ip, phone, pattern
    
    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Admin info
    created_by: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FraudBlacklist(Base):
    """Blacklist for known fraudsters"""
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    
    # Blacklist details
    reason: Mapped[str] = mapped_column(String(256))
    fraud_type: Mapped[FraudType] = mapped_column(SQLEnum(FraudType))
    severity: Mapped[FraudSeverity] = mapped_column(SQLEnum(FraudSeverity))
    
    # Evidence
    evidence: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    related_detection_id: Mapped[Optional[int]] = mapped_column(ForeignKey("frauddetection.id"), nullable=True)
    
    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_block: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Admin info
    created_by: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)