from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, Text, Numeric, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RefundType(str, Enum):
    """Types of refunds"""
    FULL_REFUND = "full_refund"  # بازپرداخت کامل
    PARTIAL_REFUND = "partial_refund"  # بازپرداخت جزئی
    SERVICE_CREDIT = "service_credit"  # اعتبار سرویس
    WALLET_CREDIT = "wallet_credit"  # اعتبار کیف پول
    UPGRADE_CREDIT = "upgrade_credit"  # اعتبار ارتقا


class RefundStatus(str, Enum):
    """Refund status"""
    PENDING = "pending"  # در انتظار
    APPROVED = "approved"  # تایید شده
    PROCESSING = "processing"  # در حال پردازش
    COMPLETED = "completed"  # تکمیل شده
    REJECTED = "rejected"  # رد شده
    CANCELLED = "cancelled"  # لغو شده


class RefundReason(str, Enum):
    """Refund reasons"""
    USER_REQUEST = "user_request"  # درخواست کاربر
    SERVICE_ISSUE = "service_issue"  # مشکل سرویس
    TECHNICAL_PROBLEM = "technical_problem"  # مشکل فنی
    BILLING_ERROR = "billing_error"  # خطای صورتحساب
    FRAUD_DETECTION = "fraud_detection"  # تشخیص کلاهبرداری
    ADMIN_DECISION = "admin_decision"  # تصمیم ادمین
    SERVICE_DISCONTINUED = "service_discontinued"  # قطع سرویس
    QUALITY_ISSUE = "quality_issue"  # مشکل کیفیت


class RefundRequest(Base):
    """Refund request model"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("service.id"))
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transaction.id"))
    
    # Refund details
    refund_type: Mapped[RefundType] = mapped_column(SQLEnum(RefundType))
    refund_reason: Mapped[RefundReason] = mapped_column(SQLEnum(RefundReason))
    requested_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    approved_amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)
    
    # Status
    status: Mapped[RefundStatus] = mapped_column(SQLEnum(RefundStatus), default=RefundStatus.PENDING)
    
    # Request details
    request_description: Mapped[str] = mapped_column(Text)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Processing
    processed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Refund method
    refund_method: Mapped[str] = mapped_column(String(32), default="wallet")  # wallet, bank_transfer, original_method
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ServiceUpgrade(Base):
    """Service upgrade model"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    current_service_id: Mapped[int] = mapped_column(ForeignKey("service.id"))
    target_plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id"))
    
    # Upgrade details
    upgrade_type: Mapped[str] = mapped_column(String(32))  # plan_upgrade, volume_add, time_extend
    current_plan_price: Mapped[float] = mapped_column(Numeric(18, 2))
    target_plan_price: Mapped[float] = mapped_column(Numeric(18, 2))
    upgrade_cost: Mapped[float] = mapped_column(Numeric(18, 2))
    
    # Payment
    payment_method: Mapped[str] = mapped_column(String(32))  # wallet, card_to_card, etc.
    payment_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transaction.id"), nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, processing, completed, failed
    
    # Processing
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    new_service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service.id"), nullable=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WalletTransaction(Base):
    """Wallet transaction model"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Transaction details
    transaction_type: Mapped[str] = mapped_column(String(32))  # credit, debit, refund, upgrade
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    balance_before: Mapped[float] = mapped_column(Numeric(18, 2))
    balance_after: Mapped[float] = mapped_column(Numeric(18, 2))
    
    # Reference
    reference_type: Mapped[str] = mapped_column(String(32))  # transaction, refund, upgrade, gift
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Description
    description: Mapped[str] = mapped_column(String(256))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Admin info
    processed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RefundPolicy(Base):
    """Refund policy configuration"""
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Policy rules
    service_type: Mapped[str] = mapped_column(String(32))  # all, specific categories
    max_refund_percent: Mapped[int] = mapped_column(Integer, default=100)  # 0-100%
    max_refund_days: Mapped[int] = mapped_column(Integer, default=30)  # Days after purchase
    
    # Conditions
    conditions: Mapped[str] = mapped_column(JSON)  # JSON conditions
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UpgradeRule(Base):
    """Service upgrade rules"""
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Upgrade configuration
    from_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("plan.id"), nullable=True)
    to_plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id"))
    
    # Pricing
    upgrade_discount_percent: Mapped[int] = mapped_column(Integer, default=0)  # 0-100%
    prorated_refund: Mapped[bool] = mapped_column(Boolean, default=True)  # Prorate current service
    
    # Conditions
    min_service_age_days: Mapped[int] = mapped_column(Integer, default=0)
    max_service_age_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RefundAnalytics(Base):
    """Refund analytics and statistics"""
    date: Mapped[datetime] = mapped_column(DateTime)
    
    # Refund statistics
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    approved_requests: Mapped[int] = mapped_column(Integer, default=0)
    rejected_requests: Mapped[int] = mapped_column(Integer, default=0)
    total_refund_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    
    # Refund by type
    full_refunds: Mapped[int] = mapped_column(Integer, default=0)
    partial_refunds: Mapped[int] = mapped_column(Integer, default=0)
    wallet_credits: Mapped[int] = mapped_column(Integer, default=0)
    
    # Refund by reason
    user_requests: Mapped[int] = mapped_column(Integer, default=0)
    service_issues: Mapped[int] = mapped_column(Integer, default=0)
    technical_problems: Mapped[int] = mapped_column(Integer, default=0)
    billing_errors: Mapped[int] = mapped_column(Integer, default=0)
    
    # Upgrade statistics
    total_upgrades: Mapped[int] = mapped_column(Integer, default=0)
    successful_upgrades: Mapped[int] = mapped_column(Integer, default=0)
    total_upgrade_revenue: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)