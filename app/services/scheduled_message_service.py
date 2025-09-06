import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.scheduled_messages import (
    ScheduledMessage, Campaign, MessageRecipient, MessageTemplate,
    MessageSchedule, MessageAnalytics, MessageType, MessageStatus, CampaignType
)
from models.user import TelegramUser
from models.crm import UserProfile, UserSegment
from core.config import settings


class ScheduledMessageService:
    """Service for managing scheduled messages and campaigns"""
    
    @staticmethod
    async def create_scheduled_message(
        session: AsyncSession,
        title: str,
        content: str,
        scheduled_at: datetime,
        message_type: MessageType = MessageType.TEXT,
        target_type: str = "all",
        target_users: Optional[List[int]] = None,
        target_segments: Optional[List[str]] = None,
        created_by: int = None,
        campaign_id: Optional[int] = None,
        media_file_id: Optional[str] = None,
        media_caption: Optional[str] = None
    ) -> ScheduledMessage:
        """Create a new scheduled message"""
        
        # Generate recipient list
        recipients = await ScheduledMessageService._generate_recipient_list(
            session, target_type, target_users, target_segments
        )
        
        # Create scheduled message
        message = ScheduledMessage(
            title=title,
            content=content,
            message_type=message_type,
            scheduled_at=scheduled_at,
            target_type=target_type,
            target_users=json.dumps(target_users) if target_users else None,
            target_segments=json.dumps(target_segments) if target_segments else None,
            created_by=created_by,
            campaign_id=campaign_id,
            media_file_id=media_file_id,
            media_caption=media_caption,
            total_recipients=len(recipients)
        )
        session.add(message)
        await session.flush()
        
        # Create recipient records
        for user_id in recipients:
            recipient = MessageRecipient(
                message_id=message.id,
                user_id=user_id
            )
            session.add(recipient)
        
        return message
    
    @staticmethod
    async def _generate_recipient_list(
        session: AsyncSession,
        target_type: str,
        target_users: Optional[List[int]] = None,
        target_segments: Optional[List[str]] = None
    ) -> List[int]:
        """Generate list of recipient user IDs"""
        
        if target_type == "all":
            # Get all active users
            users = (await session.execute(
                select(TelegramUser.id)
                .where(TelegramUser.is_blocked == False)
            )).scalars().all()
            return list(users)
        
        elif target_type == "specific" and target_users:
            return target_users
        
        elif target_type == "segment" and target_segments:
            # Get users by segments
            user_ids = []
            for segment in target_segments:
                if segment == "new_users":
                    # Users registered in last 7 days
                    cutoff_date = datetime.utcnow() - timedelta(days=7)
                    users = (await session.execute(
                        select(TelegramUser.id)
                        .where(
                            and_(
                                TelegramUser.is_blocked == False,
                                TelegramUser.created_at >= cutoff_date
                            )
                        )
                    )).scalars().all()
                    user_ids.extend(users)
                
                elif segment == "active_users":
                    # Users with high engagement
                    users = (await session.execute(
                        select(TelegramUser.id)
                        .join(UserProfile, TelegramUser.id == UserProfile.user_id)
                        .where(
                            and_(
                                TelegramUser.is_blocked == False,
                                UserProfile.engagement_score > 0.7
                            )
                        )
                    )).scalars().all()
                    user_ids.extend(users)
                
                elif segment == "vip_users":
                    # High-value users
                    users = (await session.execute(
                        select(TelegramUser.id)
                        .where(
                            and_(
                                TelegramUser.is_blocked == False,
                                TelegramUser.total_spent > 500000  # 500K IRR
                            )
                        )
                    )).scalars().all()
                    user_ids.extend(users)
                
                elif segment == "churned_users":
                    # Users who haven't been active
                    cutoff_date = datetime.utcnow() - timedelta(days=30)
                    users = (await session.execute(
                        select(TelegramUser.id)
                        .join(UserProfile, TelegramUser.id == UserProfile.user_id)
                        .where(
                            and_(
                                TelegramUser.is_blocked == False,
                                UserProfile.last_activity_at < cutoff_date
                            )
                        )
                    )).scalars().all()
                    user_ids.extend(users)
            
            return list(set(user_ids))  # Remove duplicates
        
        return []
    
    @staticmethod
    async def process_scheduled_messages(session: AsyncSession) -> int:
        """Process and send scheduled messages"""
        
        # Get messages ready to send
        now = datetime.utcnow()
        ready_messages = (await session.execute(
            select(ScheduledMessage)
            .where(
                and_(
                    ScheduledMessage.status == MessageStatus.SCHEDULED,
                    ScheduledMessage.scheduled_at <= now
                )
            )
            .order_by(ScheduledMessage.scheduled_at)
            .limit(10)  # Process in batches
        )).scalars().all()
        
        sent_count = 0
        
        for message in ready_messages:
            try:
                # Update status to sending
                message.status = MessageStatus.SENDING
                
                # Send message
                success = await ScheduledMessageService._send_message(session, message)
                
                if success:
                    message.status = MessageStatus.SENT
                    message.sent_at = now
                    sent_count += 1
                else:
                    message.status = MessageStatus.FAILED
                    message.retry_count += 1
                    
                    # Retry if under limit
                    if message.retry_count < message.max_retries:
                        retry_delay = timedelta(minutes=message.retry_delay_minutes)
                        message.scheduled_at = now + retry_delay
                        message.status = MessageStatus.SCHEDULED
            
            except Exception as e:
                message.status = MessageStatus.FAILED
                message.retry_count += 1
                print(f"Error sending message {message.id}: {e}")
        
        return sent_count
    
    @staticmethod
    async def _send_message(session: AsyncSession, message: ScheduledMessage) -> bool:
        """Send message to all recipients"""
        
        try:
            from aiogram import Bot
            bot = Bot(token=settings.bot_token)
            
            # Get recipients
            recipients = (await session.execute(
                select(MessageRecipient)
                .where(
                    and_(
                        MessageRecipient.message_id == message.id,
                        MessageRecipient.status == "pending"
                    )
                )
            )).scalars().all()
            
            sent_count = 0
            failed_count = 0
            
            for recipient in recipients:
                try:
                    # Get user
                    user = (await session.execute(
                        select(TelegramUser).where(TelegramUser.id == recipient.user_id)
                    )).scalar_one()
                    
                    # Send message based on type
                    if message.message_type == MessageType.TEXT:
                        sent_msg = await bot.send_message(
                            chat_id=user.telegram_user_id,
                            text=message.content,
                            parse_mode=message.parse_mode,
                            disable_web_page_preview=message.disable_web_page_preview,
                            disable_notification=message.disable_notification
                        )
                    
                    elif message.message_type == MessageType.IMAGE and message.media_file_id:
                        sent_msg = await bot.send_photo(
                            chat_id=user.telegram_user_id,
                            photo=message.media_file_id,
                            caption=message.media_caption or message.content,
                            parse_mode=message.parse_mode,
                            disable_notification=message.disable_notification
                        )
                    
                    elif message.message_type == MessageType.VIDEO and message.media_file_id:
                        sent_msg = await bot.send_video(
                            chat_id=user.telegram_user_id,
                            video=message.media_file_id,
                            caption=message.media_caption or message.content,
                            parse_mode=message.parse_mode,
                            disable_notification=message.disable_notification
                        )
                    
                    elif message.message_type == MessageType.DOCUMENT and message.media_file_id:
                        sent_msg = await bot.send_document(
                            chat_id=user.telegram_user_id,
                            document=message.media_file_id,
                            caption=message.media_caption or message.content,
                            parse_mode=message.parse_mode,
                            disable_notification=message.disable_notification
                        )

                    elif message.message_type == MessageType.FORWARD:
                        # content contains JSON {from_chat_id, message_id}
                        try:
                            ref = json.loads(message.content)
                            from_chat_id = ref.get("from_chat_id")
                            source_message_id = ref.get("message_id")
                            sent_msg = await bot.copy_message(
                                chat_id=user.telegram_user_id,
                                from_chat_id=from_chat_id,
                                message_id=source_message_id
                            )
                        except Exception as inner_e:
                            raise inner_e
                    
                    else:
                        # Fallback to text
                        sent_msg = await bot.send_message(
                            chat_id=user.telegram_user_id,
                            text=message.content,
                            parse_mode=message.parse_mode,
                            disable_notification=message.disable_notification
                        )
                    
                    # Update recipient status
                    recipient.status = "sent"
                    recipient.sent_at = datetime.utcnow()
                    recipient.telegram_message_id = sent_msg.message_id
                    sent_count += 1
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.1)
                
                except Exception as e:
                    recipient.status = "failed"
                    recipient.error_message = str(e)
                    recipient.retry_count += 1
                    failed_count += 1
            
            # Update message statistics
            message.sent_count = sent_count
            message.failed_count = failed_count
            
            # Create analytics record
            analytics = MessageAnalytics(
                message_id=message.id,
                total_recipients=len(recipients),
                sent_count=sent_count,
                failed_count=failed_count,
                delivery_rate=(sent_count / len(recipients) * 100) if recipients else 0
            )
            session.add(analytics)
            
            return sent_count > 0
        
        except Exception as e:
            print(f"Error in _send_message: {e}")
            return False
    
    @staticmethod
    async def create_campaign(
        session: AsyncSession,
        name: str,
        campaign_type: CampaignType,
        description: Optional[str] = None,
        target_audience: Optional[Dict[str, Any]] = None,
        created_by: int = None
    ) -> Campaign:
        """Create a new campaign"""
        
        campaign = Campaign(
            name=name,
            description=description,
            campaign_type=campaign_type,
            target_audience=json.dumps(target_audience) if target_audience else None,
            created_by=created_by
        )
        session.add(campaign)
        await session.flush()
        
        return campaign
    
    @staticmethod
    async def create_message_template(
        session: AsyncSession,
        name: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        variables: Optional[List[str]] = None,
        created_by: int = None,
        media_file_id: Optional[str] = None,
        media_caption: Optional[str] = None
    ) -> MessageTemplate:
        """Create a message template"""
        
        template = MessageTemplate(
            name=name,
            content=content,
            message_type=message_type,
            variables=json.dumps(variables) if variables else None,
            created_by=created_by,
            media_file_id=media_file_id,
            media_caption=media_caption
        )
        session.add(template)
        
        return template
    
    @staticmethod
    async def create_recurring_schedule(
        session: AsyncSession,
        name: str,
        schedule_type: str,
        schedule_config: Dict[str, Any],
        message_content: str,
        target_type: str = "all",
        created_by: int = None
    ) -> MessageSchedule:
        """Create a recurring message schedule"""
        
        # Calculate next execution time
        next_execution = ScheduledMessageService._calculate_next_execution(
            schedule_type, schedule_config
        )
        
        schedule = MessageSchedule(
            name=name,
            schedule_type=schedule_type,
            schedule_config=json.dumps(schedule_config),
            message_content=message_content,
            target_type=target_type,
            next_execution_at=next_execution,
            created_by=created_by
        )
        session.add(schedule)
        
        return schedule
    
    @staticmethod
    def _calculate_next_execution(schedule_type: str, config: Dict[str, Any]) -> datetime:
        """Calculate next execution time for recurring schedule"""
        
        now = datetime.utcnow()
        
        if schedule_type == "daily":
            hour = config.get("hour", 9)
            minute = config.get("minute", 0)
            next_execution = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_execution <= now:
                next_execution += timedelta(days=1)
            return next_execution
        
        elif schedule_type == "weekly":
            weekday = config.get("weekday", 0)  # 0 = Monday
            hour = config.get("hour", 9)
            minute = config.get("minute", 0)
            
            days_ahead = weekday - now.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            
            next_execution = now + timedelta(days=days_ahead)
            next_execution = next_execution.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_execution
        
        elif schedule_type == "monthly":
            day = config.get("day", 1)
            hour = config.get("hour", 9)
            minute = config.get("minute", 0)
            
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            else:
                next_month = now.replace(month=now.month + 1, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            
            return next_month
        
        return now + timedelta(hours=1)  # Default to 1 hour from now
    
    @staticmethod
    async def process_recurring_schedules(session: AsyncSession) -> int:
        """Process recurring message schedules"""
        
        now = datetime.utcnow()
        
        # Get schedules ready to execute
        ready_schedules = (await session.execute(
            select(MessageSchedule)
            .where(
                and_(
                    MessageSchedule.is_active == True,
                    MessageSchedule.next_execution_at <= now
                )
            )
        )).scalars().all()
        
        executed_count = 0
        
        for schedule in ready_schedules:
            try:
                # Create scheduled message from template
                message = await ScheduledMessageService.create_scheduled_message(
                    session=session,
                    title=f"Recurring: {schedule.name}",
                    content=schedule.message_content,
                    scheduled_at=now,
                    target_type=schedule.target_type,
                    target_users=json.loads(schedule.target_users) if schedule.target_users else None,
                    target_segments=json.loads(schedule.target_segments) if schedule.target_segments else None,
                    created_by=schedule.created_by
                )
                
                # Update schedule
                schedule.last_executed_at = now
                schedule.execution_count += 1
                schedule.next_execution_at = ScheduledMessageService._calculate_next_execution(
                    schedule.schedule_type,
                    json.loads(schedule.schedule_config)
                )
                
                executed_count += 1
            
            except Exception as e:
                print(f"Error processing recurring schedule {schedule.id}: {e}")
        
        return executed_count
    
    @staticmethod
    async def get_message_analytics(session: AsyncSession, message_id: int) -> Dict[str, Any]:
        """Get analytics for a specific message"""
        
        analytics = (await session.execute(
            select(MessageAnalytics)
            .where(MessageAnalytics.message_id == message_id)
        )).scalar_one_or_none()
        
        if not analytics:
            return {}
        
        # Get recipient details
        recipients = (await session.execute(
            select(MessageRecipient)
            .where(MessageRecipient.message_id == message_id)
        )).scalars().all()
        
        return {
            "analytics": analytics,
            "recipients": recipients,
            "delivery_rate": analytics.delivery_rate,
            "read_rate": analytics.read_rate,
            "click_rate": analytics.click_rate
        }
    
    @staticmethod
    async def get_campaign_analytics(session: AsyncSession, campaign_id: int) -> Dict[str, Any]:
        """Get analytics for a campaign"""
        
        campaign = (await session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )).scalar_one_or_none()
        
        if not campaign:
            return {}
        
        # Get campaign messages
        messages = (await session.execute(
            select(ScheduledMessage)
            .where(ScheduledMessage.campaign_id == campaign_id)
        )).scalars().all()
        
        # Calculate total analytics
        total_recipients = sum(m.total_recipients for m in messages)
        total_sent = sum(m.sent_count for m in messages)
        total_failed = sum(m.failed_count for m in messages)
        
        return {
            "campaign": campaign,
            "messages": messages,
            "total_recipients": total_recipients,
            "total_sent": total_sent,
            "total_failed": total_failed,
            "delivery_rate": (total_sent / total_recipients * 100) if total_recipients > 0 else 0
        }
    
    @staticmethod
    async def cancel_scheduled_message(session: AsyncSession, message_id: int) -> bool:
        """Cancel a scheduled message"""
        
        message = (await session.execute(
            select(ScheduledMessage).where(ScheduledMessage.id == message_id)
        )).scalar_one_or_none()
        
        if not message:
            return False
        
        if message.status in [MessageStatus.SENT, MessageStatus.FAILED]:
            return False  # Cannot cancel already sent/failed messages
        
        message.status = MessageStatus.CANCELLED
        return True
    
    @staticmethod
    async def reschedule_message(
        session: AsyncSession,
        message_id: int,
        new_scheduled_at: datetime
    ) -> bool:
        """Reschedule a message"""
        
        message = (await session.execute(
            select(ScheduledMessage).where(ScheduledMessage.id == message_id)
        )).scalar_one_or_none()
        
        if not message:
            return False
        
        if message.status in [MessageStatus.SENT, MessageStatus.FAILED]:
            return False  # Cannot reschedule already sent/failed messages
        
        message.scheduled_at = new_scheduled_at
        message.status = MessageStatus.SCHEDULED
        message.retry_count = 0  # Reset retry count
        
        return True