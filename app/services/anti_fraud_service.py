import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.anti_fraud import (
    FraudRule, FraudDetection, UserFraudProfile, FraudPattern,
    FraudAlert, FraudWhitelist, FraudBlacklist,
    FraudType, FraudSeverity, FraudAction
)
from models.user import TelegramUser
from models.billing import Transaction
from models.service import Service


class AntiFraudService:
    """Service for anti-fraud detection and prevention"""
    
    @staticmethod
    async def analyze_transaction(
        session: AsyncSession,
        transaction: Transaction,
        user: TelegramUser
    ) -> List[FraudDetection]:
        """Analyze transaction for fraud patterns"""
        
        detections = []
        
        # Get user fraud profile
        profile = await AntiFraudService._get_user_fraud_profile(session, user.id)
        
        # Check if user is whitelisted
        if await AntiFraudService._is_user_whitelisted(session, user):
            return detections
        
        # Check if user is blacklisted
        if await AntiFraudService._is_user_blacklisted(session, user):
            detection = await AntiFraudService._create_fraud_detection(
                session, user.id, FraudType.MULTIPLE_ACCOUNTS,
                FraudSeverity.CRITICAL, 1.0,
                "User is blacklisted", {"blacklist_reason": "blacklisted_user"}
            )
            detections.append(detection)
            return detections
        
        # Run fraud detection rules
        active_rules = (await session.execute(
            select(FraudRule).where(FraudRule.is_active == True)
        )).scalars().all()
        
        for rule in active_rules:
            detection = await AntiFraudService._check_fraud_rule(
                session, rule, transaction, user, profile
            )
            if detection:
                detections.append(detection)
        
        # Update user fraud profile
        await AntiFraudService._update_fraud_profile(session, user.id, transaction)
        
        return detections
    
    @staticmethod
    async def _check_fraud_rule(
        session: AsyncSession,
        rule: FraudRule,
        transaction: Transaction,
        user: TelegramUser,
        profile: UserFraudProfile
    ) -> Optional[FraudDetection]:
        """Check if transaction matches fraud rule"""
        
        try:
            criteria = json.loads(rule.criteria)
            confidence = 0.0
            evidence = {}
            
            if rule.fraud_type == FraudType.FAKE_RECEIPT:
                confidence, evidence = await AntiFraudService._check_fake_receipt(
                    session, transaction, criteria
                )
            
            elif rule.fraud_type == FraudType.DUPLICATE_PAYMENT:
                confidence, evidence = await AntiFraudService._check_duplicate_payment(
                    session, transaction, criteria
                )
            
            elif rule.fraud_type == FraudType.HIGH_FREQUENCY:
                confidence, evidence = await AntiFraudService._check_high_frequency(
                    session, user, criteria
                )
            
            elif rule.fraud_type == FraudType.UNUSUAL_AMOUNT:
                confidence, evidence = await AntiFraudService._check_unusual_amount(
                    session, user, transaction, criteria
                )
            
            elif rule.fraud_type == FraudType.SUSPICIOUS_PATTERN:
                confidence, evidence = await AntiFraudService._check_suspicious_pattern(
                    session, user, transaction, criteria
                )
            
            # Check if confidence meets threshold
            if confidence >= (rule.threshold or 0.7):
                detection = await AntiFraudService._create_fraud_detection(
                    session, user.id, rule.fraud_type, rule.severity,
                    confidence, f"Rule triggered: {rule.name}", evidence,
                    rule_id=rule.id, transaction_id=transaction.id
                )
                
                # Update rule statistics
                rule.triggered_count += 1
                rule.last_triggered_at = datetime.utcnow()
                
                # Take automatic action if enabled
                if rule.auto_action:
                    await AntiFraudService._execute_fraud_action(
                        session, detection, rule.action
                    )
                
                return detection
        
        except Exception as e:
            print(f"Error checking fraud rule {rule.name}: {e}")
        
        return None
    
    @staticmethod
    async def _check_fake_receipt(
        session: AsyncSession,
        transaction: Transaction,
        criteria: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """Check for fake receipt patterns"""
        
        confidence = 0.0
        evidence = {}
        
        # Check receipt image hash (if available)
        if hasattr(transaction, 'receipt_image_hash') and transaction.receipt_image_hash:
            # Check if this hash has been used before
            duplicate_count = (await session.execute(
                select(func.count(Transaction.id))
                .where(Transaction.receipt_image_hash == transaction.receipt_image_hash)
            )).scalar()
            
            if duplicate_count > 1:
                confidence += 0.8
                evidence["duplicate_receipt_hash"] = transaction.receipt_image_hash
                evidence["duplicate_count"] = duplicate_count
        
        # Check receipt amount vs transaction amount
        if hasattr(transaction, 'receipt_amount') and transaction.receipt_amount:
            if abs(transaction.receipt_amount - transaction.amount) > 1000:  # 1K IRR difference
                confidence += 0.6
                evidence["amount_mismatch"] = {
                    "receipt_amount": transaction.receipt_amount,
                    "transaction_amount": transaction.amount
                }
        
        # Check receipt date vs transaction date
        if hasattr(transaction, 'receipt_date') and transaction.receipt_date:
            time_diff = abs((transaction.created_at - transaction.receipt_date).total_seconds())
            if time_diff > 3600:  # More than 1 hour difference
                confidence += 0.4
                evidence["date_mismatch"] = {
                    "receipt_date": transaction.receipt_date.isoformat(),
                    "transaction_date": transaction.created_at.isoformat()
                }
        
        return min(confidence, 1.0), evidence
    
    @staticmethod
    async def _check_duplicate_payment(
        session: AsyncSession,
        transaction: Transaction,
        criteria: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """Check for duplicate payments"""
        
        confidence = 0.0
        evidence = {}
        
        # Check for same amount within time window
        time_window = timedelta(hours=criteria.get("time_window_hours", 1))
        start_time = transaction.created_at - time_window
        
        duplicate_transactions = (await session.execute(
            select(Transaction)
            .where(
                and_(
                    Transaction.user_id == transaction.user_id,
                    Transaction.amount == transaction.amount,
                    Transaction.created_at >= start_time,
                    Transaction.created_at <= transaction.created_at,
                    Transaction.id != transaction.id
                )
            )
        )).scalars().all()
        
        if duplicate_transactions:
            confidence = min(len(duplicate_transactions) * 0.3, 1.0)
            evidence["duplicate_transactions"] = [
                {"id": t.id, "amount": t.amount, "created_at": t.created_at.isoformat()}
                for t in duplicate_transactions
            ]
        
        return confidence, evidence
    
    @staticmethod
    async def _check_high_frequency(
        session: AsyncSession,
        user: TelegramUser,
        criteria: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """Check for high frequency transactions"""
        
        confidence = 0.0
        evidence = {}
        
        # Check transactions in last 24 hours
        time_window = timedelta(hours=criteria.get("time_window_hours", 24))
        start_time = datetime.utcnow() - time_window
        
        recent_transactions = (await session.execute(
            select(func.count(Transaction.id))
            .where(
                and_(
                    Transaction.user_id == user.id,
                    Transaction.created_at >= start_time
                )
            )
        )).scalar()
        
        max_transactions = criteria.get("max_transactions", 10)
        if recent_transactions > max_transactions:
            confidence = min((recent_transactions - max_transactions) / max_transactions, 1.0)
            evidence["high_frequency"] = {
                "transactions_count": recent_transactions,
                "max_allowed": max_transactions,
                "time_window_hours": criteria.get("time_window_hours", 24)
            }
        
        return confidence, evidence
    
    @staticmethod
    async def _check_unusual_amount(
        session: AsyncSession,
        user: TelegramUser,
        transaction: Transaction,
        criteria: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """Check for unusual transaction amounts"""
        
        confidence = 0.0
        evidence = {}
        
        # Get user's transaction history
        user_transactions = (await session.execute(
            select(Transaction.amount)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
            .limit(50)
        )).scalars().all()
        
        if len(user_transactions) >= 5:  # Need at least 5 transactions for analysis
            avg_amount = sum(user_transactions) / len(user_transactions)
            max_amount = max(user_transactions)
            
            # Check if current transaction is significantly higher than average
            if transaction.amount > avg_amount * criteria.get("multiplier", 3):
                confidence += 0.6
                evidence["unusual_amount"] = {
                    "current_amount": transaction.amount,
                    "average_amount": avg_amount,
                    "max_previous_amount": max_amount
                }
            
            # Check if amount is higher than previous maximum
            if transaction.amount > max_amount * 1.5:
                confidence += 0.4
                evidence["exceeds_maximum"] = {
                    "current_amount": transaction.amount,
                    "previous_maximum": max_amount
                }
        
        return min(confidence, 1.0), evidence
    
    @staticmethod
    async def _check_suspicious_pattern(
        session: AsyncSession,
        user: TelegramUser,
        transaction: Transaction,
        criteria: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """Check for suspicious behavioral patterns"""
        
        confidence = 0.0
        evidence = {}
        
        # Check for rapid successive transactions
        recent_transactions = (await session.execute(
            select(Transaction)
            .where(
                and_(
                    Transaction.user_id == user.id,
                    Transaction.created_at >= datetime.utcnow() - timedelta(hours=1)
                )
            )
            .order_by(Transaction.created_at.desc())
        )).scalars().all()
        
        if len(recent_transactions) >= 3:
            # Check if transactions are very close in time
            time_gaps = []
            for i in range(len(recent_transactions) - 1):
                gap = (recent_transactions[i].created_at - recent_transactions[i + 1].created_at).total_seconds()
                time_gaps.append(gap)
            
            avg_gap = sum(time_gaps) / len(time_gaps)
            if avg_gap < 300:  # Less than 5 minutes between transactions
                confidence += 0.7
                evidence["rapid_transactions"] = {
                    "transaction_count": len(recent_transactions),
                    "average_gap_seconds": avg_gap
                }
        
        # Check for round number amounts (potential fake transactions)
        if transaction.amount % 10000 == 0 and transaction.amount >= 100000:  # Round 10K amounts
            confidence += 0.3
            evidence["round_amount"] = transaction.amount
        
        return min(confidence, 1.0), evidence
    
    @staticmethod
    async def _create_fraud_detection(
        session: AsyncSession,
        user_id: int,
        fraud_type: FraudType,
        severity: FraudSeverity,
        confidence: float,
        description: str,
        evidence: Dict[str, Any],
        rule_id: Optional[int] = None,
        transaction_id: Optional[int] = None,
        service_id: Optional[int] = None
    ) -> FraudDetection:
        """Create fraud detection record"""
        
        detection = FraudDetection(
            user_id=user_id,
            rule_id=rule_id,
            fraud_type=fraud_type,
            severity=severity,
            confidence_score=confidence,
            description=description,
            evidence=json.dumps(evidence),
            related_transaction_id=transaction_id,
            related_service_id=service_id
        )
        session.add(detection)
        await session.flush()
        
        # Create alert if severity is high or critical
        if severity in [FraudSeverity.HIGH, FraudSeverity.CRITICAL]:
            await AntiFraudService._create_fraud_alert(session, detection)
        
        return detection
    
    @staticmethod
    async def _create_fraud_alert(
        session: AsyncSession,
        detection: FraudDetection
    ):
        """Create fraud alert for admins"""
        
        # Get admin users
        admin_users = (await session.execute(
            select(TelegramUser).where(TelegramUser.is_admin == True)
        )).scalars().all()
        
        if not admin_users:
            return
        
        alert = FraudAlert(
            detection_id=detection.id,
            user_id=detection.user_id,
            alert_type="immediate",
            severity=detection.severity,
            message=f"Fraud detected: {detection.fraud_type.value} - {detection.description}",
            admin_recipients=[admin.telegram_user_id for admin in admin_users]
        )
        session.add(alert)
    
    @staticmethod
    async def _execute_fraud_action(
        session: AsyncSession,
        detection: FraudDetection,
        action: FraudAction
    ):
        """Execute automatic fraud action"""
        
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == detection.user_id)
        )).scalar_one()
        
        if action == FraudAction.WARN:
            # Send warning message to user
            detection.action_taken = "warn"
            detection.action_details = "Warning sent to user"
        
        elif action == FraudAction.SUSPEND:
            # Suspend user account
            user.is_blocked = True
            detection.action_taken = "suspend"
            detection.action_details = "User account suspended"
        
        elif action == FraudAction.BLOCK:
            # Block user permanently
            user.is_blocked = True
            detection.action_taken = "block"
            detection.action_details = "User account blocked"
        
        elif action == FraudAction.DELETE_CONFIG:
            # Delete related service if exists
            if detection.related_service_id:
                service = (await session.execute(
                    select(Service).where(Service.id == detection.related_service_id)
                )).scalar_one_or_none()
                if service:
                    service.is_active = False
                    detection.action_taken = "delete_config"
                    detection.action_details = f"Service {service.id} deactivated"
        
        elif action == FraudAction.INVESTIGATE:
            # Mark for manual investigation
            detection.status = "investigating"
            detection.action_taken = "investigate"
            detection.action_details = "Marked for manual investigation"
    
    @staticmethod
    async def _get_user_fraud_profile(session: AsyncSession, user_id: int) -> UserFraudProfile:
        """Get or create user fraud profile"""
        
        profile = (await session.execute(
            select(UserFraudProfile).where(UserFraudProfile.user_id == user_id)
        )).scalar_one_or_none()
        
        if not profile:
            profile = UserFraudProfile(user_id=user_id)
            session.add(profile)
            await session.flush()
        
        return profile
    
    @staticmethod
    async def _update_fraud_profile(
        session: AsyncSession,
        user_id: int,
        transaction: Transaction
    ):
        """Update user fraud profile with new transaction"""
        
        profile = await AntiFraudService._get_user_fraud_profile(session, user_id)
        
        # Update transaction statistics
        profile.avg_transaction_amount = (
            (profile.avg_transaction_amount * profile.total_detections + transaction.amount) /
            (profile.total_detections + 1)
        )
        profile.max_transaction_amount = max(profile.max_transaction_amount, transaction.amount)
        
        # Update frequency (transactions per day)
        today = datetime.utcnow().date()
        if not hasattr(profile, 'last_transaction_date') or profile.last_transaction_date != today:
            profile.transaction_frequency = 1
        else:
            profile.transaction_frequency += 1
        
        profile.last_updated = datetime.utcnow()
    
    @staticmethod
    async def _is_user_whitelisted(session: AsyncSession, user: TelegramUser) -> bool:
        """Check if user is whitelisted"""
        
        whitelist = (await session.execute(
            select(FraudWhitelist)
            .where(
                and_(
                    FraudWhitelist.user_id == user.id,
                    FraudWhitelist.is_active == True,
                    or_(
                        FraudWhitelist.expires_at.is_(None),
                        FraudWhitelist.expires_at > datetime.utcnow()
                    )
                )
            )
        )).scalar_one_or_none()
        
        return whitelist is not None
    
    @staticmethod
    async def _is_user_blacklisted(session: AsyncSession, user: TelegramUser) -> bool:
        """Check if user is blacklisted"""
        
        blacklist = (await session.execute(
            select(FraudBlacklist)
            .where(
                and_(
                    FraudBlacklist.user_id == user.id,
                    FraudBlacklist.is_active == True
                )
            )
        )).scalar_one_or_none()
        
        return blacklist is not None
    
    @staticmethod
    async def get_fraud_analytics(session: AsyncSession) -> Dict[str, Any]:
        """Get fraud detection analytics"""
        
        # Overall statistics
        total_detections = (await session.execute(
            select(func.count(FraudDetection.id))
        )).scalar()
        
        high_severity_detections = (await session.execute(
            select(func.count(FraudDetection.id))
            .where(FraudDetection.severity.in_([FraudSeverity.HIGH, FraudSeverity.CRITICAL]))
        )).scalar()
        
        # Detections by type
        type_stats = (await session.execute(
            select(FraudDetection.fraud_type, func.count(FraudDetection.id))
            .group_by(FraudDetection.fraud_type)
        )).all()
        
        # Detections by severity
        severity_stats = (await session.execute(
            select(FraudDetection.severity, func.count(FraudDetection.id))
            .group_by(FraudDetection.severity)
        )).all()
        
        # Recent detections
        recent_detections = (await session.execute(
            select(FraudDetection)
            .order_by(desc(FraudDetection.detected_at))
            .limit(10)
        )).scalars().all()
        
        return {
            "total_detections": total_detections,
            "high_severity_detections": high_severity_detections,
            "type_stats": dict(type_stats),
            "severity_stats": dict(severity_stats),
            "recent_detections": recent_detections
        }
    
    @staticmethod
    async def add_to_blacklist(
        session: AsyncSession,
        user_id: int,
        fraud_type: FraudType,
        severity: FraudSeverity,
        reason: str,
        created_by: int,
        evidence: Optional[Dict[str, Any]] = None
    ) -> FraudBlacklist:
        """Add user to fraud blacklist"""
        
        blacklist_entry = FraudBlacklist(
            user_id=user_id,
            reason=reason,
            fraud_type=fraud_type,
            severity=severity,
            evidence=json.dumps(evidence) if evidence else None,
            created_by=created_by
        )
        session.add(blacklist_entry)
        
        # Block user if auto_block is enabled
        if blacklist_entry.auto_block:
            user = (await session.execute(
                select(TelegramUser).where(TelegramUser.id == user_id)
            )).scalar_one()
            user.is_blocked = True
        
        return blacklist_entry
    
    @staticmethod
    async def add_to_whitelist(
        session: AsyncSession,
        user_id: int,
        reason: str,
        created_by: int,
        expires_at: Optional[datetime] = None
    ) -> FraudWhitelist:
        """Add user to fraud whitelist"""
        
        whitelist_entry = FraudWhitelist(
            user_id=user_id,
            reason=reason,
            whitelist_type="user",
            created_by=created_by,
            expires_at=expires_at
        )
        session.add(whitelist_entry)
        
        return whitelist_entry