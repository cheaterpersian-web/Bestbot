"""
Database migration script to add missing fields to existing tables.
This script should be run after the initial database setup.
"""

import asyncio
from sqlalchemy import text
from core.db import get_db_session


async def add_missing_fields():
    """Add missing fields to existing database tables"""
    
    async with get_db_session() as session:
        # Add missing fields to Server table
        try:
            await session.execute(text("""
                ALTER TABLE server 
                ADD COLUMN IF NOT EXISTS current_connections INT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS max_connections INT,
                ADD COLUMN IF NOT EXISTS last_sync_at DATETIME,
                ADD COLUMN IF NOT EXISTS sync_status VARCHAR(16) DEFAULT 'unknown',
                ADD COLUMN IF NOT EXISTS error_message TEXT
            """))
            print("✅ Added missing fields to Server table")
        except Exception as e:
            print(f"❌ Error adding fields to Server table: {e}")
        
        # Add missing fields to Category table
        try:
            await session.execute(text("""
                ALTER TABLE category 
                ADD COLUMN IF NOT EXISTS icon VARCHAR(64),
                ADD COLUMN IF NOT EXISTS color VARCHAR(16),
                ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT FALSE
            """))
            print("✅ Added missing fields to Category table")
        except Exception as e:
            print(f"❌ Error adding fields to Category table: {e}")
        
        # Add missing fields to Plan table
        try:
            await session.execute(text("""
                ALTER TABLE plan 
                ADD COLUMN IF NOT EXISTS is_popular BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS is_recommended BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS discount_percent INT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS original_price DECIMAL(18,2),
                ADD COLUMN IF NOT EXISTS sales_count INT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                ADD COLUMN IF NOT EXISTS updated_at DATETIME
            """))
            print("✅ Added missing fields to Plan table")
        except Exception as e:
            print(f"❌ Error adding fields to Plan table: {e}")
        
        # Add missing fields to TelegramUser table
        try:
            await session.execute(text("""
                ALTER TABLE telegramuser 
                ADD COLUMN IF NOT EXISTS phone_number VARCHAR(32),
                ADD COLUMN IF NOT EXISTS language_code VARCHAR(8),
                ADD COLUMN IF NOT EXISTS total_spent DECIMAL(18,2) DEFAULT 0,
                ADD COLUMN IF NOT EXISTS total_services INT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS verification_date DATETIME,
                ADD COLUMN IF NOT EXISTS notes TEXT,
                ADD COLUMN IF NOT EXISTS registration_source VARCHAR(32) DEFAULT 'bot',
                ADD COLUMN IF NOT EXISTS last_activity_at DATETIME
            """))
            print("✅ Added missing fields to TelegramUser table")
        except Exception as e:
            print(f"❌ Error adding fields to TelegramUser table: {e}")
        
        # Add missing fields to Service table
        try:
            await session.execute(text("""
                ALTER TABLE service 
                ADD COLUMN IF NOT EXISTS server_capacity_used INT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS connection_count INT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS last_connection_at DATETIME,
                ADD COLUMN IF NOT EXISTS auto_renewal BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS renewal_reminder_sent BOOLEAN DEFAULT FALSE
            """))
            print("✅ Added missing fields to Service table")
        except Exception as e:
            print(f"❌ Error adding fields to Service table: {e}")
        
        # Add missing fields to Transaction table
        try:
            await session.execute(text("""
                ALTER TABLE transaction 
                ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45),
                ADD COLUMN IF NOT EXISTS user_agent TEXT,
                ADD COLUMN IF NOT EXISTS payment_method VARCHAR(32),
                ADD COLUMN IF NOT EXISTS refund_amount DECIMAL(18,2) DEFAULT 0,
                ADD COLUMN IF NOT EXISTS refund_reason TEXT,
                ADD COLUMN IF NOT EXISTS refunded_at DATETIME
            """))
            print("✅ Added missing fields to Transaction table")
        except Exception as e:
            print(f"❌ Error adding fields to Transaction table: {e}")
        
        # Create indexes for better performance
        try:
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telegramuser_last_seen 
                ON telegramuser(last_seen_at);
                
                CREATE INDEX IF NOT EXISTS idx_telegramuser_wallet_balance 
                ON telegramuser(wallet_balance);
                
                CREATE INDEX IF NOT EXISTS idx_service_expires_at 
                ON service(expires_at);
                
                CREATE INDEX IF NOT EXISTS idx_service_is_active 
                ON service(is_active);
                
                CREATE INDEX IF NOT EXISTS idx_transaction_status 
                ON transaction(status);
                
                CREATE INDEX IF NOT EXISTS idx_transaction_created_at 
                ON transaction(created_at);
                
                CREATE INDEX IF NOT EXISTS idx_plan_is_active 
                ON plan(is_active);
                
                CREATE INDEX IF NOT EXISTS idx_server_is_active 
                ON server(is_active);
            """))
            print("✅ Created database indexes")
        except Exception as e:
            print(f"❌ Error creating indexes: {e}")
        
        await session.commit()
        print("🎉 Database migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(add_missing_fields())