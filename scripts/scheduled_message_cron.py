#!/usr/bin/env python3
"""
Cron script for processing scheduled messages
This script should be run every minute to process scheduled messages
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from services.scheduled_message_service import ScheduledMessageService


async def main():
    """Main function to process scheduled messages"""
    try:
        print(f"Processing scheduled messages at {asyncio.get_event_loop().time()}")
        
        from core.db import get_db_session
        async with get_db_session() as session:
            # Process scheduled messages
            sent_count = await ScheduledMessageService.process_scheduled_messages(session)
            print(f"Sent {sent_count} scheduled messages")
            
            # Process recurring schedules
            executed_count = await ScheduledMessageService.process_recurring_schedules(session)
            print(f"Executed {executed_count} recurring schedules")
        
        print("Scheduled message processing completed successfully")
    except Exception as e:
        print(f"Error processing scheduled messages: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())