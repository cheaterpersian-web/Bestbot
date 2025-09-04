import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import Transaction
from models.user import TelegramUser
from core.config import settings


class FraudDetectionService:
    """Service for detecting fraudulent transactions and validating receipts"""
    
    @staticmethod
    async def calculate_fraud_score(
        session: AsyncSession, 
        user_id: int, 
        amount: float, 
        receipt_file_id: str
    ) -> float:
        """Calculate fraud probability score (0-1) for a transaction"""
        score = 0.0
        
        # Check user transaction history
        recent_tx_count = await FraudDetectionService._get_recent_transaction_count(session, user_id)
        if recent_tx_count > settings.max_daily_transactions:
            score += 0.3
            
        # Check daily amount limit
        daily_amount = await FraudDetectionService._get_daily_amount(session, user_id)
        if daily_amount + amount > settings.max_daily_amount:
            score += 0.4
            
        # Check for duplicate receipts
        if await FraudDetectionService._is_duplicate_receipt(session, receipt_file_id):
            score += 0.5
            
        # Check for suspicious patterns
        if await FraudDetectionService._has_suspicious_patterns(session, user_id):
            score += 0.2
            
        return min(score, 1.0)
    
    @staticmethod
    async def _get_recent_transaction_count(session: AsyncSession, user_id: int) -> int:
        """Get transaction count in last 24 hours"""
        yesterday = datetime.utcnow() - timedelta(days=1)
        result = await session.execute(
            select(func.count(Transaction.id))
            .where(Transaction.user_id == user_id)
            .where(Transaction.created_at >= yesterday)
        )
        return result.scalar() or 0
    
    @staticmethod
    async def _get_daily_amount(session: AsyncSession, user_id: int) -> float:
        """Get total transaction amount in last 24 hours"""
        yesterday = datetime.utcnow() - timedelta(days=1)
        result = await session.execute(
            select(func.sum(Transaction.amount))
            .where(Transaction.user_id == user_id)
            .where(Transaction.created_at >= yesterday)
            .where(Transaction.status == "approved")
        )
        return float(result.scalar() or 0)
    
    @staticmethod
    async def _is_duplicate_receipt(session: AsyncSession, receipt_file_id: str) -> bool:
        """Check if receipt has been used before"""
        result = await session.execute(
            select(Transaction.id)
            .where(Transaction.receipt_image_file_id == receipt_file_id)
            .where(Transaction.status.in_(["approved", "pending"]))
        )
        return result.scalar_one_or_none() is not None
    
    @staticmethod
    async def _has_suspicious_patterns(session: AsyncSession, user_id: int) -> bool:
        """Check for suspicious transaction patterns"""
        # Check for rapid successive transactions
        recent_txs = await session.execute(
            select(Transaction.created_at)
            .where(Transaction.user_id == user_id)
            .where(Transaction.created_at >= datetime.utcnow() - timedelta(hours=1))
            .order_by(Transaction.created_at.desc())
            .limit(5)
        )
        
        tx_times = [tx[0] for tx in recent_txs.fetchall()]
        if len(tx_times) >= 3:
            # Check if transactions are too close together
            for i in range(len(tx_times) - 1):
                if (tx_times[i] - tx_times[i + 1]).total_seconds() < 60:  # Less than 1 minute apart
                    return True
        
        return False
    
    @staticmethod
    def validate_receipt_format(receipt_text: str) -> Dict[str, bool]:
        """Validate receipt format and extract information"""
        validation = {
            "has_amount": False,
            "has_card_number": False,
            "has_date": False,
            "has_time": False,
            "is_valid_format": False
        }
        
        if not receipt_text:
            return validation
            
        # Check for amount patterns (Persian/English numbers)
        amount_patterns = [
            r'[\d,]+\.?\d*\s*تومان',
            r'[\d,]+\.?\d*\s*ریال',
            r'مبلغ[\s:]*[\d,]+\.?\d*',
            r'amount[\s:]*[\d,]+\.?\d*'
        ]
        
        for pattern in amount_patterns:
            if re.search(pattern, receipt_text, re.IGNORECASE):
                validation["has_amount"] = True
                break
        
        # Check for card number patterns
        card_patterns = [
            r'\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}',
            r'کارت[\s:]*\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}',
            r'card[\s:]*\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}'
        ]
        
        for pattern in card_patterns:
            if re.search(pattern, receipt_text, re.IGNORECASE):
                validation["has_card_number"] = True
                break
        
        # Check for date patterns
        date_patterns = [
            r'\d{4}[/\-]\d{2}[/\-]\d{2}',
            r'\d{2}[/\-]\d{2}[/\-]\d{4}',
            r'\d{4}[\s\-]\d{2}[\s\-]\d{2}'
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, receipt_text):
                validation["has_date"] = True
                break
        
        # Check for time patterns
        time_patterns = [
            r'\d{2}:\d{2}:\d{2}',
            r'\d{2}:\d{2}',
            r'\d{1,2}:\d{2}\s*(AM|PM|ق\.ظ|ب\.ظ)'
        ]
        
        for pattern in time_patterns:
            if re.search(pattern, receipt_text, re.IGNORECASE):
                validation["has_time"] = True
                break
        
        # Overall validation
        validation["is_valid_format"] = (
            validation["has_amount"] and 
            validation["has_card_number"] and 
            validation["has_date"]
        )
        
        return validation
    
    @staticmethod
    def generate_receipt_hash(receipt_file_id: str, user_id: int) -> str:
        """Generate a hash for receipt tracking"""
        content = f"{receipt_file_id}_{user_id}_{datetime.utcnow().strftime('%Y%m%d')}"
        return hashlib.md5(content.encode()).hexdigest()