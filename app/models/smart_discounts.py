from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, Text, Numeric, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DiscountType(str, Enum):
    """Types of smart discounts"""
    HOURLY = "hourly"  # تخفیف ساعتی
    FIRST_PURCHASE = "first_purchase"  # تخفیف خرید اول
    CASHBACK = "cashback"  # کش‌بک
    BULK_PURCHASE = "bulk_purchase"  # تخفیف خرید عمده
    LOYALTY = "loyalty"  # تخفیف وفاداری
    SEASONAL = "seasonal"  # تخفیف فصلی
    BIRTHDAY = "birthday"  # تخفیف تولد


class SmartDiscount(Base):
    """Smart discount system with automatic triggers"""
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discount_type: Mapped[DiscountType] = mapped_column(SQLEnum(DiscountType))
    
    # Discount configuration
    percent_off: Mapped[int] = mapped_column(Integer, default=0)
    fixed_off: Mapped[int] = mapped_column(Integer, default=0)
    min_purchase_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_discount_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Trigger conditions
    trigger_conditions: Mapped[str] = mapped_column(Text)  # JSON conditions
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Time restrictions
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    daily_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Usage tracking
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    daily_used_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reset_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Priority and stacking
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Higher number = higher priority
    can_stack: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Target criteria
    target_user_groups: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON criteria
    target_plans: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON plan IDs
    target_servers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON server IDs


class DiscountUsage(Base):
    """Track individual discount usage"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    smart_discount_id: Mapped[int] = mapped_column(ForeignKey("smartdiscount.id"))
    transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transaction.id"), nullable=True)
    
    # Usage details
    original_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    discount_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    final_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    
    # Context
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    context_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON context


class CashbackRule(Base):
    """Cashback rules for different scenarios"""
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Cashback configuration
    percent_cashback: Mapped[float] = mapped_column(Numeric(5, 2), default=0)  # 0-100%
    fixed_cashback: Mapped[int] = mapped_column(Integer, default=0)
    min_purchase_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_cashback_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Trigger conditions
    trigger_type: Mapped[str] = mapped_column(String(32))  # purchase_amount, plan_type, server, etc.
    trigger_value: Mapped[str] = mapped_column(String(128))  # Specific trigger value
    
    # Time restrictions
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Usage limits
    daily_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Target criteria
    target_user_groups: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_plans: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CashbackTransaction(Base):
    """Individual cashback transactions"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    cashback_rule_id: Mapped[int] = mapped_column(ForeignKey("cashbackrule.id"))
    original_transaction_id: Mapped[int] = mapped_column(ForeignKey("transaction.id"))
    
    # Cashback details
    original_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    cashback_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    
    # Status
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, approved, paid
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class UserDiscountProfile(Base):
    """User-specific discount profile and history"""
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    
    # Purchase history
    total_purchases: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    first_purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Discount eligibility
    is_first_time_buyer: Mapped[bool] = mapped_column(Boolean, default=True)
    loyalty_level: Mapped[int] = mapped_column(Integer, default=0)  # 0-5 levels
    birthday_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-12
    
    # Usage tracking
    total_discounts_used: Mapped[int] = mapped_column(Integer, default=0)
    total_discount_savings: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_cashback_earned: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    
    # Preferences
    preferred_discount_types: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    notification_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    
    # Last updated
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)