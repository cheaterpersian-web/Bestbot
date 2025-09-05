#!/usr/bin/env python3
"""
Cron script for automatic database backups
This script should be run by cron every hour to check for scheduled backups
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from services.backup_service import backup_service


async def main():
    """Main function to run scheduled backups"""
    try:
        print(f"Running scheduled backups at {asyncio.get_event_loop().time()}")
        await backup_service.schedule_automatic_backups()
        print("Scheduled backups completed successfully")
    except Exception as e:
        print(f"Error running scheduled backups: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())