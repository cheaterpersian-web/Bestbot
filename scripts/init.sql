-- VPN Telegram Bot - Database Initialization Script
-- اسکریپت مقداردهی اولیه پایگاه داده ربات تلگرام VPN

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS vpn_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Use the database
USE vpn_bot;

-- NOTE: User and password are created by official MySQL image using
-- MYSQL_USER / MYSQL_PASSWORD env vars. Avoid overriding here to prevent
-- password mismatches with the application .env.

-- Set timezone
SET time_zone = '+00:00';

-- Create initial tables (these will be managed by Alembic migrations)
-- But we can create some basic structure for better performance

-- Create indexes for better performance
-- These will be created after migrations run

-- Insert default admin user (will be created by the application)
-- This is just a placeholder

-- Set MySQL configuration for better performance
SET GLOBAL innodb_buffer_pool_size = 256M;
SET GLOBAL max_connections = 200;
-- Query cache has been removed in MySQL 8.x; skip deprecated settings.

-- Create backup user for automated backups
CREATE USER IF NOT EXISTS 'backup_user'@'%' IDENTIFIED BY 'backup_pass';
GRANT SELECT, LOCK TABLES, SHOW VIEW, EVENT, TRIGGER ON vpn_bot.* TO 'backup_user'@'%';
FLUSH PRIVILEGES;

-- Log initialization
SELECT 'VPN Telegram Bot database initialized successfully' as status;