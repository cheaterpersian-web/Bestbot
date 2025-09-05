import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.crm import (
    UserProfile, UserActivity, PersonalizedOffer, CRMCampaign, CampaignRecipient,
    UserInsight, CustomerJourney, UserSegment, ActivityType
)
from models.user import TelegramUser
from models.billing import Transaction
from models.service import Service


class CRMService:
    """Customer Relationship Management service"""
    
    @staticmethod
    async def track_user_activity(
        session: AsyncSession,
        user_id: int,
        activity_type: ActivityType,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Track user activity for CRM"""
        
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            description=description,
            metadata=json.dumps(metadata) if metadata else None,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        session.add(activity)
        
        # Update user profile
        await CRMService._update_user_profile(session, user_id, activity_type)
    
    @staticmethod
    async def _update_user_profile(
        session: AsyncSession,
        user_id: int,
        activity_type: ActivityType
    ):
        """Update user profile based on activity"""
        
        profile = await CRMService._get_or_create_user_profile(session, user_id)
        
        # Update last activity
        profile.last_activity_at = datetime.utcnow()
        profile.days_since_last_activity = 0
        
        # Update activity-specific metrics
        if activity_type == ActivityType.LOGIN:
            profile.login_frequency += 1
        elif activity_type == ActivityType.PURCHASE:
            profile.purchase_frequency += 1
        elif activity_type == ActivityType.SERVICE_EXPIRY:
            # Check for churn risk
            await CRMService._assess_churn_risk(session, profile)
        
        # Recalculate engagement score
        profile.engagement_score = await CRMService._calculate_engagement_score(session, user_id)
        
        # Update segmentation
        await CRMService._update_user_segmentation(session, profile)
        
        profile.last_updated = datetime.utcnow()
    
    @staticmethod
    async def _get_or_create_user_profile(session: AsyncSession, user_id: int) -> UserProfile:
        """Get or create user profile"""
        
        profile = (await session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )).scalar_one_or_none()
        
        if not profile:
            profile = UserProfile(user_id=user_id)
            session.add(profile)
            await session.flush()
        
        return profile
    
    @staticmethod
    async def _calculate_engagement_score(session: AsyncSession, user_id: int) -> float:
        """Calculate user engagement score (0-1)"""
        
        # Get recent activities (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        activities = (await session.execute(
            select(UserActivity)
            .where(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= thirty_days_ago
                )
            )
        )).scalars().all()
        
        if not activities:
            return 0.0
        
        # Calculate score based on activity types and frequency
        score = 0.0
        
        for activity in activities:
            if activity.activity_type == ActivityType.LOGIN:
                score += 0.1
            elif activity.activity_type == ActivityType.PURCHASE:
                score += 0.3
            elif activity.activity_type == ActivityType.WALLET_TOPUP:
                score += 0.2
            elif activity.activity_type == ActivityType.SERVICE_RENEWAL:
                score += 0.25
            elif activity.activity_type == ActivityType.REFERRAL:
                score += 0.15
        
        # Normalize to 0-1 range
        return min(score, 1.0)
    
    @staticmethod
    async def _update_user_segmentation(session: AsyncSession, profile: UserProfile):
        """Update user segmentation based on behavior"""
        
        # Get user data
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == profile.user_id)
        )).scalar_one()
        
        # Calculate segments
        segments = []
        
        # New user (less than 7 days)
        if user.created_at > datetime.utcnow() - timedelta(days=7):
            segments.append(UserSegment.NEW_USER)
        
        # Active user (high engagement)
        if profile.engagement_score > 0.7:
            segments.append(UserSegment.ACTIVE_USER)
        
        # VIP user (high spending)
        if user.total_spent > 1000000:  # 1M IRR
            segments.append(UserSegment.VIP_USER)
            segments.append(UserSegment.HIGH_VALUE)
        
        # High value user
        elif user.total_spent > 500000:  # 500K IRR
            segments.append(UserSegment.HIGH_VALUE)
        
        # Low value user
        elif user.total_spent < 100000:  # 100K IRR
            segments.append(UserSegment.LOW_VALUE)
        
        # Frequent buyer
        if profile.purchase_frequency > 2:  # More than 2 purchases per month
            segments.append(UserSegment.FREQUENT_BUYER)
        
        # Occasional buyer
        elif profile.purchase_frequency > 0 and profile.purchase_frequency <= 1:
            segments.append(UserSegment.OCCASIONAL_BUYER)
        
        # Churned user (no activity for 30+ days)
        if profile.days_since_last_activity > 30:
            segments.append(UserSegment.CHURNED_USER)
            profile.lifecycle_stage = "churned"
        
        # Update profile
        if segments:
            profile.primary_segment = segments[0]
            profile.secondary_segments = [s.value for s in segments[1:]]
        
        # Update lifecycle stage
        if not segments or UserSegment.CHURNED_USER not in segments:
            if profile.engagement_score > 0.8:
                profile.lifecycle_stage = "active"
            elif profile.engagement_score > 0.4:
                profile.lifecycle_stage = "at_risk"
            else:
                profile.lifecycle_stage = "new"
    
    @staticmethod
    async def _assess_churn_risk(session: AsyncSession, profile: UserProfile):
        """Assess user churn risk"""
        
        # Factors that increase churn risk
        risk_factors = 0
        
        # Days since last activity
        if profile.days_since_last_activity > 14:
            risk_factors += 0.3
        elif profile.days_since_last_activity > 7:
            risk_factors += 0.2
        
        # Low engagement
        if profile.engagement_score < 0.3:
            risk_factors += 0.4
        elif profile.engagement_score < 0.5:
            risk_factors += 0.2
        
        # Service expiry without renewal
        # This would need to be implemented based on service data
        
        # High risk score
        if profile.risk_score > 0.5:
            risk_factors += 0.2
        
        profile.churn_probability = min(risk_factors, 1.0)
    
    @staticmethod
    async def get_user_insights(session: AsyncSession, user_id: int) -> List[UserInsight]:
        """Get AI-generated user insights"""
        
        insights = (await session.execute(
            select(UserInsight)
            .where(
                and_(
                    UserInsight.user_id == user_id,
                    UserInsight.is_active == True,
                    or_(
                        UserInsight.expires_at.is_(None),
                        UserInsight.expires_at > datetime.utcnow()
                    )
                )
            )
            .order_by(desc(UserInsight.confidence_score))
        )).scalars().all()
        
        return insights
    
    @staticmethod
    async def generate_personalized_offers(
        session: AsyncSession,
        user_id: int
    ) -> List[PersonalizedOffer]:
        """Generate personalized offers for user"""
        
        profile = await CRMService._get_or_create_user_profile(session, user_id)
        
        # Get existing active offers
        existing_offers = (await session.execute(
            select(PersonalizedOffer)
            .where(
                and_(
                    PersonalizedOffer.user_id == user_id,
                    PersonalizedOffer.is_active == True,
                    PersonalizedOffer.valid_to > datetime.utcnow(),
                    PersonalizedOffer.is_used == False
                )
            )
        )).scalars().all()
        
        if existing_offers:
            return existing_offers
        
        # Generate new offers based on user profile
        offers = []
        
        # Churn prevention offer
        if profile.churn_probability > 0.7:
            offer = PersonalizedOffer(
                user_id=user_id,
                title="تخفیف ویژه برای بازگشت شما",
                description="ما شما را از دست نمی‌دهیم! از این تخفیف ویژه استفاده کنید.",
                offer_type="discount",
                discount_percent=20,
                valid_from=datetime.utcnow(),
                valid_to=datetime.utcnow() + timedelta(days=7),
                created_by="system",
                creation_reason="churn_prevention"
            )
            offers.append(offer)
        
        # VIP user offer
        elif profile.primary_segment == UserSegment.VIP_USER:
            offer = PersonalizedOffer(
                user_id=user_id,
                title="پیشنهاد ویژه VIP",
                description="به عنوان کاربر VIP، از این پیشنهاد ویژه استفاده کنید.",
                offer_type="bonus",
                bonus_amount=50000,
                valid_from=datetime.utcnow(),
                valid_to=datetime.utcnow() + timedelta(days=14),
                created_by="system",
                creation_reason="vip_reward"
            )
            offers.append(offer)
        
        # New user offer
        elif profile.primary_segment == UserSegment.NEW_USER:
            offer = PersonalizedOffer(
                user_id=user_id,
                title="خوش آمدید! تخفیف ویژه",
                description="به عنوان کاربر جدید، از این تخفیف خوش آمدگویی استفاده کنید.",
                offer_type="discount",
                discount_percent=15,
                valid_from=datetime.utcnow(),
                valid_to=datetime.utcnow() + timedelta(days=30),
                created_by="system",
                creation_reason="new_user_welcome"
            )
            offers.append(offer)
        
        # Add offers to database
        for offer in offers:
            session.add(offer)
        
        return offers
    
    @staticmethod
    async def get_user_analytics(session: AsyncSession, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user analytics"""
        
        profile = await CRMService._get_or_create_user_profile(session, user_id)
        
        # Get recent activities
        recent_activities = (await session.execute(
            select(UserActivity)
            .where(UserActivity.user_id == user_id)
            .order_by(desc(UserActivity.created_at))
            .limit(10)
        )).scalars().all()
        
        # Get transaction history
        transactions = (await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(desc(Transaction.created_at))
            .limit(5)
        )).scalars().all()
        
        # Get service history
        services = (await session.execute(
            select(Service)
            .where(Service.user_id == user_id)
            .order_by(desc(Service.purchased_at))
            .limit(5)
        )).scalars().all()
        
        # Get insights
        insights = await CRMService.get_user_insights(session, user_id)
        
        # Get personalized offers
        offers = await CRMService.generate_personalized_offers(session, user_id)
        
        return {
            "profile": profile,
            "recent_activities": recent_activities,
            "transactions": transactions,
            "services": services,
            "insights": insights,
            "offers": offers,
            "engagement_score": profile.engagement_score,
            "churn_probability": profile.churn_probability,
            "lifecycle_stage": profile.lifecycle_stage
        }
    
    @staticmethod
    async def create_campaign(
        session: AsyncSession,
        name: str,
        campaign_type: str,
        message_content: str,
        target_segments: Optional[List[str]] = None,
        scheduled_at: Optional[datetime] = None
    ) -> CRMCampaign:
        """Create a new marketing campaign"""
        
        campaign = CRMCampaign(
            name=name,
            campaign_type=campaign_type,
            message_content=message_content,
            target_segments=target_segments,
            scheduled_at=scheduled_at,
            is_scheduled=scheduled_at is not None
        )
        session.add(campaign)
        await session.flush()
        
        # Generate recipient list
        await CRMService._generate_campaign_recipients(session, campaign)
        
        return campaign
    
    @staticmethod
    async def _generate_campaign_recipients(session: AsyncSession, campaign: CRMCampaign):
        """Generate recipient list for campaign"""
        
        # Build query based on target segments
        query = select(TelegramUser.id)
        
        if campaign.target_segments:
            # This would need more complex logic based on segments
            # For now, we'll target all active users
            query = query.where(TelegramUser.is_blocked == False)
        
        users = (await session.execute(query)).scalars().all()
        
        # Create recipient records
        for user_id in users:
            recipient = CRMCampaignRecipient(
                campaign_id=campaign.id,
                user_id=user_id
            )
            session.add(recipient)
        
        campaign.total_recipients = len(users)
    
    @staticmethod
    async def get_campaign_analytics(session: AsyncSession, campaign_id: int) -> Dict[str, Any]:
        """Get campaign analytics"""
        
        campaign = (await session.execute(
            select(CRMCampaign).where(CRMCampaign.id == campaign_id)
        )).scalar_one_or_none()
        
        if not campaign:
            return {}
        
        # Get recipient statistics
        recipients = (await session.execute(
            select(CRMCampaignRecipient).where(CRMCampaignRecipient.campaign_id == campaign_id)
        )).scalars().all()
        
        delivered = len([r for r in recipients if r.status == "delivered"])
        opened = len([r for r in recipients if r.opened_at is not None])
        clicked = len([r for r in recipients if r.clicked_at is not None])
        converted = len([r for r in recipients if r.converted_at is not None])
        
        return {
            "campaign": campaign,
            "total_recipients": campaign.total_recipients,
            "delivered": delivered,
            "opened": opened,
            "clicked": clicked,
            "converted": converted,
            "delivery_rate": (delivered / campaign.total_recipients * 100) if campaign.total_recipients > 0 else 0,
            "open_rate": (opened / delivered * 100) if delivered > 0 else 0,
            "click_rate": (clicked / opened * 100) if opened > 0 else 0,
            "conversion_rate": (converted / campaign.total_recipients * 100) if campaign.total_recipients > 0 else 0
        }
    
    @staticmethod
    async def get_segment_analytics(session: AsyncSession) -> Dict[str, Any]:
        """Get user segment analytics"""
        
        # Get segment counts
        segment_counts = (await session.execute(
            select(UserProfile.primary_segment, func.count(UserProfile.id))
            .group_by(UserProfile.primary_segment)
        )).all()
        
        # Get lifecycle stage counts
        lifecycle_counts = (await session.execute(
            select(UserProfile.lifecycle_stage, func.count(UserProfile.id))
            .group_by(UserProfile.lifecycle_stage)
        )).all()
        
        # Get engagement distribution
        engagement_ranges = [
            ("high", 0.7, 1.0),
            ("medium", 0.4, 0.7),
            ("low", 0.0, 0.4)
        ]
        
        engagement_distribution = {}
        for label, min_score, max_score in engagement_ranges:
            count = (await session.execute(
                select(func.count(UserProfile.id))
                .where(
                    and_(
                        UserProfile.engagement_score >= min_score,
                        UserProfile.engagement_score < max_score
                    )
                )
            )).scalar()
            engagement_distribution[label] = count
        
        return {
            "segment_counts": dict(segment_counts),
            "lifecycle_counts": dict(lifecycle_counts),
            "engagement_distribution": engagement_distribution
        }
    
    @staticmethod
    async def update_daily_metrics(session: AsyncSession):
        """Update daily CRM metrics"""
        
        # Update days since last activity for all users
        profiles = (await session.execute(select(UserProfile))).scalars().all()
        
        for profile in profiles:
            if profile.last_activity_at:
                days_diff = (datetime.utcnow() - profile.last_activity_at).days
                profile.days_since_last_activity = days_diff
                
                # Update lifecycle stage based on inactivity
                if days_diff > 30 and profile.lifecycle_stage != "churned":
                    profile.lifecycle_stage = "churned"
                    profile.primary_segment = UserSegment.CHURNED_USER
                elif days_diff > 14 and profile.lifecycle_stage == "active":
                    profile.lifecycle_stage = "at_risk"
        
        # Reset weekly counters
        if datetime.utcnow().weekday() == 0:  # Monday
            for profile in profiles:
                profile.login_frequency = 0
                profile.purchase_frequency = 0