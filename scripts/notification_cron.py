#!/usr/bin/env python3
"""
Cron script for automatic notifications
This script should be run every 15 minutes to process notifications
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from services.notification_service import NotificationService


async def main():
    """Main function to process notifications"""
    try:
        print(f"Processing notifications at {asyncio.get_event_loop().time()}")
        
        from core.db import get_db_session
        async with get_db_session() as session:
            # Process pending notifications
            sent_count = await NotificationService.process_pending_notifications(session)
            print(f"Sent {sent_count} notifications")
            
            # Check service expiries
            await NotificationService.check_service_expiries(session)
            print("Checked service expiries")
            
            # Check low wallet balances
            await NotificationService.check_low_wallet_balances(session)
            print("Checked low wallet balances")
        
        print("Notification processing completed successfully")
    except Exception as e:
        print(f"Error processing notifications: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())