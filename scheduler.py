#!/usr/bin/env python3
"""
Task Scheduler
Runs scheduled tasks like Discord alerts
"""

import asyncio
import schedule
import time
from datetime import datetime
from discord_alert import DiscordAlertService
from logger import logger


class TaskScheduler:
    """Handles scheduled tasks"""
    
    def __init__(self):
        self.alert_service = None
        self.running = False
    
    def _initialize_alert_service(self):
        """Initialize the alert service with environment variables"""
        if not self.alert_service:
            try:
                self.alert_service = DiscordAlertService()  # Will load from environment
            except ValueError as e:
                logger.error(f"Failed to initialize Discord alert service: {e}")
                logger.error("Please set DISCORD_WEBHOOK_URL in your .env file")
                raise
    
    async def send_hourly_alert(self):
        """Send hourly database status alert"""
        try:
            if not self.alert_service:
                self._initialize_alert_service()
                
            logger.info("Executing scheduled database status alert...")
            success = await self.alert_service.send_status_alert()
            
            if success:
                logger.info("Scheduled alert completed successfully")
            else:
                logger.error("Scheduled alert failed")
                
        except Exception as e:
            logger.error(f"Error in scheduled alert: {e}")
    
    def schedule_tasks(self):
        """Set up scheduled tasks"""
        # Schedule hourly alerts
        schedule.every().hour.do(lambda: asyncio.create_task(self.send_hourly_alert()))
        
        # Optional: Schedule at specific times
        # schedule.every().day.at("09:00").do(lambda: asyncio.create_task(self.send_hourly_alert()))
        # schedule.every().day.at("17:00").do(lambda: asyncio.create_task(self.send_hourly_alert()))
        
        logger.info("Scheduled tasks configured:")
        logger.info("- Database status alert: Every hour")
    
    async def run_scheduler(self):
        """Run the task scheduler"""
        try:
            self._initialize_alert_service()
        except ValueError:
            return  # Error already logged
            
        self.schedule_tasks()
        self.running = True
        
        logger.info("Task scheduler started. Press Ctrl+C to stop.")
        
        # Send initial alert
        logger.info("Sending initial database status alert...")
        await self.send_hourly_alert()
        
        try:
            while self.running:
                # Run pending scheduled tasks
                schedule.run_pending()
                
                # Sleep for 1 minute before checking again
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            self.running = False
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            self.running = False
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        logger.info("Scheduler stop requested")


async def main():
    """Main function"""
    scheduler = TaskScheduler()
    
    try:
        await scheduler.run_scheduler()
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler...")
        scheduler.stop()


if __name__ == "__main__":
    # Install schedule if not available
    try:
        import schedule
    except ImportError:
        logger.error("Please install schedule: pip install schedule")
        exit(1)
    
    asyncio.run(main())