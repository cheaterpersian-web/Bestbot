import shutil
import asyncio
import gzip
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
import aiofiles

from core.config import settings
from core.db import get_db_session


class BackupService:
    """Service for automatic database backup and restore"""
    
    def __init__(self):
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.backup_dir / "daily").mkdir(exist_ok=True)
        (self.backup_dir / "weekly").mkdir(exist_ok=True)
        (self.backup_dir / "monthly").mkdir(exist_ok=True)
        (self.backup_dir / "manual").mkdir(exist_ok=True)
    
    async def create_database_backup(
        self,
        backup_type: str = "manual",
        compress: bool = True
    ) -> str:
        """Create database backup"""
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"vpn_bot_backup_{timestamp}.sql"
        
        if backup_type == "daily":
            backup_path = self.backup_dir / "daily" / backup_filename
        elif backup_type == "weekly":
            backup_path = self.backup_dir / "weekly" / backup_filename
        elif backup_type == "monthly":
            backup_path = self.backup_dir / "monthly" / backup_filename
        else:
            backup_path = self.backup_dir / "manual" / backup_filename
        
        # Parse database URL
        db_url = settings.database_url
        if db_url.startswith("mysql"):
            await self._create_mysql_backup(backup_path, db_url)
        else:
            raise ValueError(f"Unsupported database type (MySQL only supported): {db_url}")
        
        # Compress if requested
        if compress:
            compressed_path = f"{backup_path}.gz"
            await self._compress_file(backup_path, compressed_path)
            backup_path = Path(compressed_path)
        
        # Create backup metadata
        metadata = {
            "backup_type": backup_type,
            "created_at": datetime.utcnow().isoformat(),
            "database_url": db_url,
            "file_size": backup_path.stat().st_size,
            "compressed": compress
        }
        
        metadata_path = backup_path.with_suffix(".json")
        async with aiofiles.open(metadata_path, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))
        
        return str(backup_path)
    
    async def _create_mysql_backup(self, backup_path: Path, db_url: str):
        """Create MySQL backup using mysqldump"""
        
        # Parse connection details
        # Format: mysql+aiomysql://user:pass@host:port/db
        url_parts = db_url.replace("mysql+aiomysql://", "").split("@")
        if len(url_parts) != 2:
            raise ValueError("Invalid MySQL URL format")
        
        user_pass = url_parts[0].split(":")
        if len(user_pass) != 2:
            raise ValueError("Invalid MySQL credentials format")
        
        user, password = user_pass
        host_db = url_parts[1].split("/")
        if len(host_db) != 2:
            raise ValueError("Invalid MySQL host/database format")
        
        host_port = host_db[0].split(":")
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else "3306"
        database = host_db[1].split("?")[0]  # Remove query parameters
        
        # Build mysqldump command
        cmd = [
            "mysqldump",
            f"--host={host}",
            f"--port={port}",
            f"--user={user}",
            f"--password={password}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            "--hex-blob",
            "--default-character-set=utf8mb4",
            database
        ]
        
        # Execute backup
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"MySQL backup failed: {stderr.decode()}")
        
        # Write backup to file
        async with aiofiles.open(backup_path, 'wb') as f:
            await f.write(stdout)
    
    # Non-MySQL backup paths are intentionally removed to enforce MySQL-only usage
    
    async def _compress_file(self, source_path: Path, target_path: str):
        """Compress file using gzip"""
        
        async with aiofiles.open(source_path, 'rb') as f_in:
            async with aiofiles.open(target_path, 'wb') as f_out:
                # Use gzip compression
                with gzip.open(f_out, 'wt') as gz_file:
                    content = await f_in.read()
                    gz_file.write(content.decode('utf-8'))
        
        # Remove original file
        source_path.unlink()
    
    async def restore_database_backup(self, backup_path: str) -> bool:
        """Restore database from backup"""
        
        backup_path = Path(backup_path)
        
        # Check if backup exists
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        # Check for metadata file
        metadata_path = backup_path.with_suffix(".json")
        if metadata_path.exists():
            async with aiofiles.open(metadata_path, 'r') as f:
                metadata = json.loads(await f.read())
        else:
            metadata = {"compressed": False}
        
        # Decompress if needed
        if metadata.get("compressed", False) or backup_path.suffix == ".gz":
            decompressed_path = backup_path.with_suffix("")
            await self._decompress_file(backup_path, decompressed_path)
            backup_path = decompressed_path
        
        # Restore based on database type (MySQL only)
        db_url = settings.database_url
        if db_url.startswith("mysql"):
            await self._restore_mysql_backup(backup_path, db_url)
        else:
            raise ValueError(f"Unsupported database type (MySQL only supported): {db_url}")
        
        return True
    
    async def _decompress_file(self, source_path: Path, target_path: Path):
        """Decompress gzip file"""
        
        async with aiofiles.open(source_path, 'rb') as f_in:
            with gzip.open(f_in, 'rt') as gz_file:
                content = gz_file.read()
                async with aiofiles.open(target_path, 'w') as f_out:
                    await f_out.write(content)
    
    async def _restore_mysql_backup(self, backup_path: Path, db_url: str):
        """Restore MySQL backup"""
        
        # Parse connection details (same as backup)
        url_parts = db_url.replace("mysql+aiomysql://", "").split("@")
        user_pass = url_parts[0].split(":")
        user, password = user_pass
        host_db = url_parts[1].split("/")
        host_port = host_db[0].split(":")
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else "3306"
        database = host_db[1].split("?")[0]
        
        # Build mysql command
        cmd = [
            "mysql",
            f"--host={host}",
            f"--port={port}",
            f"--user={user}",
            f"--password={password}",
            database
        ]
        
        # Execute restore
        async with aiofiles.open(backup_path, 'rb') as f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate(input=await f.read())
            
            if process.returncode != 0:
                raise Exception(f"MySQL restore failed: {stderr.decode()}")
    
    # Non-MySQL restore paths are intentionally removed to enforce MySQL-only usage
    
    async def list_backups(self, backup_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available backups"""
        
        backups = []
        
        if backup_type:
            backup_types = [backup_type]
        else:
            backup_types = ["daily", "weekly", "monthly", "manual"]
        
        for btype in backup_types:
            backup_dir = self.backup_dir / btype
            if not backup_dir.exists():
                continue
            
            for backup_file in backup_dir.glob("*.sql*"):
                metadata_file = backup_file.with_suffix(".json")
                
                if metadata_file.exists():
                    async with aiofiles.open(metadata_file, 'r') as f:
                        metadata = json.loads(await f.read())
                else:
                    metadata = {
                        "backup_type": btype,
                        "created_at": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat(),
                        "compressed": backup_file.suffix == ".gz"
                    }
                
                backups.append({
                    "file_path": str(backup_file),
                    "file_name": backup_file.name,
                    "backup_type": btype,
                    "created_at": metadata["created_at"],
                    "file_size": backup_file.stat().st_size,
                    "compressed": metadata.get("compressed", False)
                })
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        
        return backups
    
    async def cleanup_old_backups(self, retention_days: Dict[str, int]):
        """Clean up old backups based on retention policy"""
        
        retention_policies = {
            "daily": retention_days.get("daily", 7),
            "weekly": retention_days.get("weekly", 4),
            "monthly": retention_days.get("monthly", 12),
            "manual": retention_days.get("manual", 30)
        }
        
        for backup_type, days in retention_policies.items():
            backup_dir = self.backup_dir / backup_type
            if not backup_dir.exists():
                continue
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            for backup_file in backup_dir.glob("*.sql*"):
                file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_time < cutoff_date:
                    backup_file.unlink()
                    
                    # Also remove metadata file
                    metadata_file = backup_file.with_suffix(".json")
                    if metadata_file.exists():
                        metadata_file.unlink()
    
    async def get_backup_status(self) -> Dict[str, Any]:
        """Get backup system status"""
        
        backups = await self.list_backups()
        
        # Count backups by type
        backup_counts = {}
        total_size = 0
        
        for backup in backups:
            backup_type = backup["backup_type"]
            backup_counts[backup_type] = backup_counts.get(backup_type, 0) + 1
            total_size += backup["file_size"]
        
        # Find latest backup
        latest_backup = backups[0] if backups else None
        
        return {
            "total_backups": len(backups),
            "backup_counts": backup_counts,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "latest_backup": latest_backup,
            "backup_directory": str(self.backup_dir)
        }
    
    async def schedule_automatic_backups(self):
        """Schedule automatic backups (to be called by cron or scheduler)"""
        
        now = datetime.utcnow()
        
        # Daily backup (every day at 2 AM)
        if now.hour == 2 and now.minute < 5:
            try:
                await self.create_database_backup("daily", compress=True)
                print(f"Daily backup created at {now}")
            except Exception as e:
                print(f"Daily backup failed: {e}")
        
        # Weekly backup (every Sunday at 3 AM)
        elif now.weekday() == 6 and now.hour == 3 and now.minute < 5:
            try:
                await self.create_database_backup("weekly", compress=True)
                print(f"Weekly backup created at {now}")
            except Exception as e:
                print(f"Weekly backup failed: {e}")
        
        # Monthly backup (first day of month at 4 AM)
        elif now.day == 1 and now.hour == 4 and now.minute < 5:
            try:
                await self.create_database_backup("monthly", compress=True)
                print(f"Monthly backup created at {now}")
            except Exception as e:
                print(f"Monthly backup failed: {e}")
        
        # Cleanup old backups (every day at 5 AM)
        if now.hour == 5 and now.minute < 5:
            try:
                await self.cleanup_old_backups({
                    "daily": 7,
                    "weekly": 4,
                    "monthly": 12,
                    "manual": 30
                })
                print(f"Backup cleanup completed at {now}")
            except Exception as e:
                print(f"Backup cleanup failed: {e}")


# Global backup service instance
backup_service = BackupService()