from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, Text, Numeric, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ResellerLevel(str, Enum):
    """Reseller hierarchy levels"""
    BRONZE = "bronze"  # برنزی
    SILVER = "silver"  # نقره‌ای
    GOLD = "gold"  # طلایی
    PLATINUM = "platinum"  # پلاتینیوم
    DIAMOND = "diamond"  # الماس


class ResellerStatus(str, Enum):
    """Reseller status"""
    PENDING = "pending"  # در انتظار تایید
    ACTIVE = "active"  # فعال
    SUSPENDED = "suspended"  # معلق
    TERMINATED = "terminated"  # فسخ شده
    BLACKLISTED = "blacklisted"  # سیاه‌لیست


class CommissionType(str, Enum):
    """Commission calculation types"""
    PERCENTAGE = "percentage"  # درصدی
    FIXED = "fixed"  # ثابت
    TIERED = "tiered"  # پلکانی


class AdvancedReseller(Base):
    """Advanced reseller with multi-level support"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"), unique=True)
    
    # Hierarchy
    parent_reseller_id: Mapped[Optional[int]] = mapped_column(ForeignKey("advancedreseller.id"), nullable=True)
    level: Mapped[ResellerLevel] = mapped_column(SQLEnum(ResellerLevel), default=ResellerLevel.BRONZE)
    status: Mapped[ResellerStatus] = mapped_column(SQLEnum(ResellerStatus), default=ResellerStatus.PENDING)
    
    # Business info
    business_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    business_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # individual, company
    tax_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    business_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    
    # Commission settings
    commission_type: Mapped[CommissionType] = mapped_column(SQLEnum(CommissionType), default=CommissionType.PERCENTAGE)
    commission_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # 0-100%
    fixed_commission: Mapped[int] = mapped_column(Integer, default=0)  # Fixed amount in IRR
    tiered_rates: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Tiered commission rates
    
    # Performance tracking
    total_sales: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_commission_earned: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_customers: Mapped[int] = mapped_column(Integer, default=0)
    total_sub_resellers: Mapped[int] = mapped_column(Integer, default=0)
    
    # Monthly targets and performance
    monthly_target: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)
    monthly_sales: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    monthly_commission: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    
    # Limits and permissions
    max_sub_resellers: Mapped[int] = mapped_column(Integer, default=5)
    can_create_sub_resellers: Mapped[bool] = mapped_column(Boolean, default=True)
    can_set_commission: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_customers: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Financial
    wallet_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    pending_commission: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_paid: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    
    # Dates
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    level_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Notes and settings
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    custom_settings: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)


class SubReseller(Base):
    """Sub-reseller relationship tracking"""
    parent_reseller_id: Mapped[int] = mapped_column(ForeignKey("advancedreseller.id"))
    sub_reseller_id: Mapped[int] = mapped_column(ForeignKey("advancedreseller.id"))
    
    # Relationship settings
    commission_override: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    can_manage: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Performance tracking
    total_sales_generated: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_commission_earned: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    
    # Dates
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ResellerCommission(Base):
    """Commission tracking for resellers"""
    reseller_id: Mapped[int] = mapped_column(ForeignKey("advancedreseller.id"))
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transaction.id"))
    
    # Commission details
    commission_type: Mapped[CommissionType] = mapped_column(SQLEnum(CommissionType))
    commission_rate: Mapped[float] = mapped_column(Numeric(5, 2))
    base_amount: Mapped[float] = mapped_column(Numeric(18, 2))  # Original transaction amount
    commission_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    
    # Hierarchy tracking
    level: Mapped[int] = mapped_column(Integer, default=1)  # 1=direct, 2=sub-reseller, etc.
    parent_reseller_id: Mapped[Optional[int]] = mapped_column(ForeignKey("advancedreseller.id"), nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, approved, paid
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Context
    customer_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service.id"), nullable=True)
    
    # Dates
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResellerTarget(Base):
    """Monthly/quarterly targets for resellers"""
    reseller_id: Mapped[int] = mapped_column(ForeignKey("advancedreseller.id"))
    
    # Target period
    target_year: Mapped[int] = mapped_column(Integer)
    target_month: Mapped[int] = mapped_column(Integer)  # 1-12, 0 for quarterly
    target_quarter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-4
    
    # Target amounts
    sales_target: Mapped[float] = mapped_column(Numeric(18, 2))
    customer_target: Mapped[int] = mapped_column(Integer)
    sub_reseller_target: Mapped[int] = mapped_column(Integer, default=0)
    
    # Achievement tracking
    sales_achieved: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    customers_achieved: Mapped[int] = mapped_column(Integer, default=0)
    sub_resellers_achieved: Mapped[int] = mapped_column(Integer, default=0)
    
    # Bonus settings
    bonus_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # Bonus percentage
    bonus_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)  # Calculated bonus
    
    # Status
    is_achieved: Mapped[bool] = mapped_column(Boolean, default=False)
    bonus_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Dates
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ResellerActivity(Base):
    """Reseller activity tracking"""
    reseller_id: Mapped[int] = mapped_column(ForeignKey("advancedreseller.id"))
    
    # Activity details
    activity_type: Mapped[str] = mapped_column(String(32))  # sale, commission, target_achieved, etc.
    description: Mapped[str] = mapped_column(String(512))
    
    # Context data
    amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transaction.id"), nullable=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service.id"), nullable=True)
    
    # Metadata
    payment_metadata: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResellerPayment(Base):
    """Reseller commission payments"""
    reseller_id: Mapped[int] = mapped_column(ForeignKey("advancedreseller.id"))
    
    # Payment details
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    payment_method: Mapped[str] = mapped_column(String(32))  # bank_transfer, wallet, etc.
    payment_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    
    # Commission details
    commission_ids: Mapped[str] = mapped_column(JSON)  # List of commission IDs included
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    
    # Status
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, processing, completed, failed
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Admin info
    processed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResellerLevelRule(Base):
    """Rules for reseller level progression"""
    level: Mapped[ResellerLevel] = mapped_column(SQLEnum(ResellerLevel))
    
    # Requirements
    min_sales: Mapped[float] = mapped_column(Numeric(18, 2))
    min_customers: Mapped[int] = mapped_column(Integer)
    min_sub_resellers: Mapped[int] = mapped_column(Integer, default=0)
    min_months_active: Mapped[int] = mapped_column(Integer, default=0)
    
    # Benefits
    commission_rate: Mapped[float] = mapped_column(Numeric(5, 2))
    max_sub_resellers: Mapped[int] = mapped_column(Integer)
    can_set_commission: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_customers: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Bonus settings
    monthly_bonus_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    quarterly_bonus_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Date
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)