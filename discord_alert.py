#!/usr/bin/env python3
"""
Discord Alert Service
Sends hourly database status alerts to Discord webhook
"""

import asyncio
import aiohttp
import json
import os
import glob
from datetime import datetime, timedelta
from typing import Dict, Any, List
from dotenv import load_dotenv
from database_manager import DatabaseManager
from logger import logger

# Load environment variables
load_dotenv()


class DiscordAlertService:
    """Handles Discord webhook alerts for database status"""
    
    def __init__(self, webhook_url: str = None, username: str = "Kevin-J"):
        # Load webhook URL from environment if not provided
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("Discord webhook URL not provided. Set DISCORD_WEBHOOK_URL environment variable or pass webhook_url parameter.")
        
        self.username = username
        self.db_manager = DatabaseManager()
        
    async def get_recent_errors(self, hours: int = 1) -> List[str]:
        """Get recent errors from error log files within the specified hours"""
        try:
            errors = []
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # Look specifically for error log files in logs directory
            error_log_pattern = "logs/error_*.log"
            error_log_files = glob.glob(error_log_pattern)
            
            if not error_log_files:
                logger.warning("No error log files found in logs/error_*.log pattern")
                return ["No error log files found"]
            
            # Sort by modification time (newest first)
            error_log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            logger.info(f"Analyzing {len(error_log_files)} error log files for recent errors...")
            
            for log_file in error_log_files:
                try:
                    # Check if file was modified recently (within last 2 hours to be safe)
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
                    if file_mtime < cutoff_time - timedelta(hours=1):  # Skip files older than 2 hours
                        logger.debug(f"Skipping old log file: {log_file} (modified: {file_mtime})")
                        continue
                    
                    logger.info(f"Analyzing error log: {log_file}")
                    
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    # Process lines from newest to oldest (reverse order)
                    for line in reversed(lines[-2000:]):  # Check last 2000 lines
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            # Try to extract timestamp from log line
                            # Expected format: "[2026-01-27 19:09:33] [ERROR] [component] message"
                            if line.startswith('[') and '] [' in line:
                                # Extract timestamp between first [ and ]
                                timestamp_end = line.find(']')
                                if timestamp_end > 0:
                                    timestamp_part = line[1:timestamp_end]  # Remove the opening [
                                    
                                    # Try different timestamp formats
                                    timestamp_formats = [
                                        "%Y-%m-%d %H:%M:%S",  # 2026-01-27 19:09:33
                                        "%Y-%m-%d %H:%M:%S.%f",  # with microseconds
                                    ]
                                    
                                    line_time = None
                                    for fmt in timestamp_formats:
                                        try:
                                            line_time = datetime.strptime(timestamp_part, fmt)
                                            break
                                        except ValueError:
                                            continue
                                    
                                    # If we found a timestamp and it's recent, include the error
                                    if line_time and line_time >= cutoff_time:
                                        # Clean up the error line
                                        clean_line = line.replace('\n', '').replace('\r', '')
                                        if len(clean_line) > 150:
                                            clean_line = clean_line[:147] + "..."
                                        
                                        # Extract just the error part (remove timestamp but keep level and component)
                                        # Format: [timestamp] [LEVEL] [component] message -> [LEVEL] [component] message
                                        parts = clean_line.split('] ', 1)
                                        if len(parts) > 1:
                                            error_part = parts[1]  # Everything after first ]
                                            # Keep timestamp for context but make it shorter
                                            short_timestamp = line_time.strftime("%H:%M:%S")
                                            formatted_error = f"`{short_timestamp}` {error_part}"
                                            errors.append(formatted_error)
                                        else:
                                            errors.append(clean_line)
                                    elif line_time and line_time < cutoff_time:
                                        # Stop processing this file if we've gone too far back
                                        logger.debug(f"Reached old timestamp: {line_time}, stopping analysis of {log_file}")
                                        break
                            else:
                                # If no proper timestamp format, check if it's a recent line anyway
                                # (for continuation lines of stack traces, etc.)
                                if len(errors) > 0 and len(errors) < 10:  # Only if we already have recent errors
                                    clean_line = line.replace('\n', '').replace('\r', '')
                                    if len(clean_line) > 100:
                                        clean_line = clean_line[:97] + "..."
                                    if clean_line.strip() and not clean_line.startswith('['):  # Don't add old timestamped lines
                                        errors.append(f"    {clean_line}")  # Indent continuation lines
                                        
                        except Exception as e:
                            logger.debug(f"Error parsing log line: {e}")
                            continue
                        
                        # Limit to prevent too many errors
                        if len(errors) >= 15:
                            break
                    
                    # If we found errors in this file, we might not need to check older files
                    if len(errors) >= 5:
                        break
                        
                except Exception as e:
                    logger.error(f"Error reading error log file {log_file}: {e}")
                    continue
            
            # Remove duplicates while preserving order
            seen = set()
            unique_errors = []
            for error in errors:
                if error not in seen:
                    seen.add(error)
                    unique_errors.append(error)
            
            if not unique_errors:
                return ["✅ No errors found in the last hour"]
            
            logger.info(f"Found {len(unique_errors)} unique recent errors")
            return unique_errors[:8]  # Limit to 8 most recent errors
            
        except Exception as e:
            logger.error(f"Error analyzing error log files: {e}")
            return [f"❌ Error analyzing error logs: {str(e)}"]
        """Get current database status information"""
        try:
            current_db = await self.db_manager.get_current_database()
            
            # Get database size in GB
            size_mb = await self.db_manager.check_database_size(current_db)
            size_gb = round(size_mb / 1024, 2)
            
            # Get tweet count
            tweet_count = await self.db_manager.get_table_count(current_db, "tweets")
            
            return {
                "database_name": current_db['name'],
                "tweet_count": tweet_count,
                "size_gb": size_gb,
                "size_mb": round(size_mb, 2),
                "capacity_used_percent": round((size_mb / self.db_manager.db_size_limit_mb) * 100, 2),
                "size_limit_mb": self.db_manager.db_size_limit_mb
            }
        except Exception as e:
            logger.error(f"Error getting database status: {e}")
            return {
                "database_name": "unknown",
                "tweet_count": 0,
                "size_gb": 0.0,
                "size_mb": 0.0,
                "capacity_used_percent": 0.0,
                "size_limit_mb": 0
            }
    
    async def get_database_status(self) -> Dict[str, Any]:
        """Get current database status information"""
        try:
            current_db = await self.db_manager.get_current_database()
            
            # Get database size in GB
            size_mb = await self.db_manager.check_database_size(current_db)
            size_gb = round(size_mb / 1024, 2)
            
            # Get tweet count
            tweet_count = await self.db_manager.get_table_count(current_db, "tweets")
            
            return {
                "database_name": current_db['name'],
                "tweet_count": tweet_count,
                "size_gb": size_gb,
                "size_mb": round(size_mb, 2),
                "capacity_used_percent": round((size_mb / self.db_manager.db_size_limit_mb) * 100, 2),
                "size_limit_mb": self.db_manager.db_size_limit_mb
            }
        except Exception as e:
            logger.error(f"Error getting database status: {e}")
            return {
                "database_name": "unknown",
                "tweet_count": 0,
                "size_gb": 0.0,
                "size_mb": 0.0,
                "capacity_used_percent": 0.0,
                "size_limit_mb": 0
            }
    
    def format_discord_message(self, db_status: Dict[str, Any], recent_errors: List[str]) -> Dict[str, Any]:
        """Format database status and recent errors into Discord webhook message"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format content with recent errors
        if len(recent_errors) == 1 and "No errors found" in recent_errors[0]:
            content = "✅ **Server Status: Healthy**\n🔍 No errors detected in the last hour"
        elif len(recent_errors) == 1 and "Error analyzing logs" in recent_errors[0]:
            content = f"⚠️ **Server Status: Log Analysis Failed**\n{recent_errors[0]}"
        else:
            content = f"🚨 **Recent Server Errors (Last Hour)**\n"
            for i, error in enumerate(recent_errors[:5], 1):
                content += f"`{i}.` {error}\n"
        
        # Determine color based on capacity usage
        if db_status['capacity_used_percent'] >= 90:
            color = 15158332  # Red
            status_emoji = "🔴"
        elif db_status['capacity_used_percent'] >= 75:
            color = 16776960  # Yellow
            status_emoji = "🟡"
        else:
            color = 5814783   # Green
            status_emoji = "🟢"
        
        return {
            "username": self.username,
            "content": content,
            "embeds": [
                {
                    "title": f"{status_emoji} Database Status - {current_time}",
                    "color": color,
                    "fields": [
                        {
                            "name": "Database Info",
                            "value": f"**Name:** {db_status['database_name']}\n**Tweet Count:** {db_status['tweet_count']:,}",
                            "inline": True
                        },
                        {
                            "name": "Storage Info",
                            "value": f"**Size:** {db_status['size_gb']} GB\n**Used:** {db_status['capacity_used_percent']}%",
                            "inline": True
                        },
                        {
                            "name": "Capacity",
                            "value": f"**Limit:** {db_status['size_limit_mb']} MB\n**Available:** {round(db_status['size_limit_mb'] - db_status['size_mb'], 2)} MB",
                            "inline": True
                        }
                    ],
                    "timestamp": datetime.now().isoformat(),
                    "footer": {
                        "text": "Twitter Data API - Hourly Report"
                    }
                }
            ]
        }
    
    async def send_discord_alert(self, message: Dict[str, Any]) -> bool:
        """Send message to Discord webhook"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=message,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 204:
                        logger.info("Discord alert sent successfully")
                        return True
                    else:
                        logger.error(f"Discord webhook failed with status {response.status}: {await response.text()}")
                        return False
        except Exception as e:
            logger.error(f"Error sending Discord alert: {e}")
            return False
    
    async def send_status_alert(self) -> bool:
        """Get database status and recent errors, then send Discord alert"""
        try:
            logger.info("Generating database status alert...")
            
            # Initialize databases if needed
            await self.db_manager.initialize_all_databases()
            
            # Get current database status
            db_status = await self.get_database_status()
            
            # Get recent errors from logs
            recent_errors = await self.get_recent_errors(hours=1)
            
            # Format Discord message
            message = self.format_discord_message(db_status, recent_errors)
            
            # Send to Discord
            success = await self.send_discord_alert(message)
            
            if success:
                error_count = len([e for e in recent_errors if not ("No errors found" in e or "Error analyzing logs" in e)])
                logger.info(f"Status alert sent: {db_status['database_name']} - {db_status['tweet_count']:,} tweets, {db_status['size_gb']} GB, {error_count} recent errors")
            else:
                logger.error("Failed to send status alert")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in send_status_alert: {e}")
            return False


async def run_hourly_alerts():
    """Run hourly Discord alerts"""
    try:
        alert_service = DiscordAlertService()  # Will load from environment
        
        logger.info("Starting hourly Discord alert service...")
        
        while True:
            try:
                # Send status alert
                await alert_service.send_status_alert()
                
                # Wait 1 hour (3600 seconds)
                logger.info("Waiting 1 hour for next alert...")
                await asyncio.sleep(3600)
                
            except KeyboardInterrupt:
                logger.info("Discord alert service stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in hourly alert loop: {e}")
                # Wait 5 minutes before retrying on error
                await asyncio.sleep(300)
                
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please set DISCORD_WEBHOOK_URL in your .env file")
        return


async def send_test_alert():
    """Send a test alert immediately"""
    try:
        alert_service = DiscordAlertService()  # Will load from environment
        
        logger.info("Sending test Discord alert...")
        success = await alert_service.send_status_alert()
        
        if success:
            logger.info("Test alert sent successfully!")
        else:
            logger.error("Test alert failed!")
        
        return success
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please set DISCORD_WEBHOOK_URL in your .env file")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Send test alert
        asyncio.run(send_test_alert())
    else:
        # Run hourly alerts
        asyncio.run(run_hourly_alerts())