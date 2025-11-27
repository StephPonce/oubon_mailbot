"""
Report Scheduler - Automated report generation

Handles:
- Loading schedules from database
- Calculating next run times
- Running scheduled reports in background
- Updating schedule statistics
- Delivering reports to recipients
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from zoneinfo import ZoneInfo
import json

logger = logging.getLogger(__name__)


class ReportScheduler:
    """Manages automated report generation schedules"""

    def __init__(self, db_session=None):
        """
        Initialize scheduler

        Args:
            db_session: Database session for loading/updating schedules
        """
        self.db = db_session
        self.running = False
        self.schedules = {}  # In-memory cache of active schedules

    async def start(self):
        """Start the scheduler background task"""
        logger.info("🚀 Starting report scheduler...")
        self.running = True

        # Load schedules from database
        await self.load_schedules()

        # Start scheduler loop
        asyncio.create_task(self._scheduler_loop())

        logger.info("✅ Report scheduler started")

    async def stop(self):
        """Stop the scheduler"""
        logger.info("⏸️  Stopping report scheduler...")
        self.running = False

    async def load_schedules(self):
        """Load active schedules from database"""
        logger.info("📋 Loading report schedules...")

        # TODO: Load from database
        # For now, use mock data
        self.schedules = {
            'sched_weekly': {
                'schedule_id': 'sched_weekly',
                'name': 'Weekly Business Summary',
                'frequency': 'weekly',
                'day_of_week': 1,  # Monday
                'time': '08:00',
                'timezone': 'America/Los_Angeles',
                'report_config': {
                    'name': 'Weekly Business Summary',
                    'report_type': 'full',
                    'sections': ['executive_summary', 'revenue', 'products', 'ads'],
                    'filters': {
                        'date_range': {
                            'type': 'relative',
                            'value': 'last_7_days'
                        }
                    }
                },
                'recipients': {
                    'email': ['admin@oubon.com'],
                    'slack': '#reports'
                },
                'is_active': True,
                'next_run': None
            }
        }

        # Calculate next run times
        for schedule_id, schedule in self.schedules.items():
            schedule['next_run'] = self._calculate_next_run(schedule)

        logger.info(f"✅ Loaded {len(self.schedules)} active schedules")

    async def _scheduler_loop(self):
        """Main scheduler loop - checks every minute"""
        while self.running:
            try:
                await self._check_and_run_schedules()
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}")

            # Wait 1 minute before next check
            await asyncio.sleep(60)

    async def _check_and_run_schedules(self):
        """Check if any schedules need to run"""
        now = datetime.now(ZoneInfo('UTC'))

        for schedule_id, schedule in self.schedules.items():
            if not schedule.get('is_active'):
                continue

            next_run = schedule.get('next_run')
            if not next_run:
                continue

            # Check if it's time to run
            if now >= next_run:
                logger.info(f"⏰ Running scheduled report: {schedule['name']}")
                await self._run_scheduled_report(schedule)

                # Calculate next run time
                schedule['next_run'] = self._calculate_next_run(schedule)
                logger.info(f"📅 Next run scheduled for: {schedule['next_run']}")

    async def _run_scheduled_report(self, schedule: Dict):
        """
        Run a scheduled report

        Args:
            schedule: Schedule configuration
        """
        try:
            # Import here to avoid circular dependencies
            from ospra_os.reports.report_engine import get_report_engine
            from ospra_os.reports.renderers.pdf_renderer import create_pdf_renderer

            # Generate report
            engine = get_report_engine()
            report_config = schedule['report_config']

            logger.info(f"📊 Generating report: {report_config['name']}")
            report_data = await engine.generate_report(report_config)

            # Render as PDF
            logger.info("📄 Rendering PDF...")
            branding = report_config.get('branding')
            pdf_renderer = create_pdf_renderer(branding)
            pdf_bytes = pdf_renderer.render(report_data)

            # Save to disk
            import os
            import uuid
            report_id = f"rpt_{uuid.uuid4().hex[:12]}"
            os.makedirs('data/reports', exist_ok=True)
            pdf_path = f"data/reports/{report_id}.pdf"

            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)

            logger.info(f"✅ Report saved: {pdf_path}")

            # Deliver to recipients
            recipients = schedule.get('recipients', {})
            if recipients:
                await self._deliver_report(
                    report_id=report_id,
                    report_name=report_config['name'],
                    pdf_path=pdf_path,
                    pdf_bytes=pdf_bytes,
                    recipients=recipients
                )

            # Update schedule statistics
            # TODO: Update in database
            logger.info(f"✅ Scheduled report completed: {report_config['name']}")

        except Exception as e:
            logger.error(f"❌ Failed to run scheduled report: {e}")
            # TODO: Update failed_runs count in database

    async def _deliver_report(
        self,
        report_id: str,
        report_name: str,
        pdf_path: str,
        pdf_bytes: bytes,
        recipients: Dict
    ):
        """
        Deliver report to recipients

        Args:
            report_id: Unique report ID
            report_name: Report name
            pdf_path: Path to saved PDF
            pdf_bytes: PDF file bytes
            recipients: Dict with email, slack, webhook destinations
        """
        logger.info(f"📤 Delivering report: {report_name}")

        # Email delivery
        if 'email' in recipients and recipients['email']:
            logger.info(f"📧 Sending to email: {recipients['email']}")
            # TODO: Integrate with email service
            logger.info("⏸️  Email delivery not yet implemented")

        # Slack delivery
        if 'slack' in recipients and recipients['slack']:
            logger.info(f"📱 Sending to Slack: {recipients['slack']}")
            # TODO: Integrate with Slack
            logger.info("⏸️  Slack delivery not yet implemented")

        # Webhook delivery
        if 'webhook' in recipients and recipients['webhook']:
            logger.info(f"🔗 Sending to webhook: {recipients['webhook']}")
            # TODO: POST to webhook
            logger.info("⏸️  Webhook delivery not yet implemented")

        logger.info("✅ Report delivery completed")

    def _calculate_next_run(self, schedule: Dict) -> datetime:
        """
        Calculate next run time for a schedule

        Args:
            schedule: Schedule configuration

        Returns:
            Next run datetime in UTC
        """
        frequency = schedule.get('frequency')
        time_str = schedule.get('time', '08:00')  # HH:MM format
        timezone = schedule.get('timezone', 'UTC')

        # Parse time
        hour, minute = map(int, time_str.split(':'))

        # Get current time in schedule's timezone
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)

        if frequency == 'daily':
            # Next occurrence at specified time
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If time has passed today, schedule for tomorrow
            if next_run <= now:
                next_run += timedelta(days=1)

        elif frequency == 'weekly':
            day_of_week = schedule.get('day_of_week', 1)  # 0=Monday, 6=Sunday

            # Find next occurrence of specified weekday
            days_ahead = day_of_week - now.weekday()
            if days_ahead < 0:  # Target day already happened this week
                days_ahead += 7
            elif days_ahead == 0:  # Today is the target day
                # Check if time has passed
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target_time <= now:
                    days_ahead = 7

            next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)

        elif frequency == 'monthly':
            day_of_month = schedule.get('day_of_month', 1)

            # Try current month first
            try:
                next_run = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    # Move to next month
                    if now.month == 12:
                        next_run = next_run.replace(year=now.year + 1, month=1)
                    else:
                        next_run = next_run.replace(month=now.month + 1)
            except ValueError:
                # Day doesn't exist in this month (e.g., Feb 30)
                # Use last day of month
                if now.month == 12:
                    next_run = datetime(now.year + 1, 1, 1, hour, minute, tzinfo=tz)
                else:
                    next_run = datetime(now.year, now.month + 1, 1, hour, minute, tzinfo=tz)
                next_run -= timedelta(days=1)

        else:
            # Unknown frequency, default to daily
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)

        # Convert to UTC for storage
        next_run_utc = next_run.astimezone(ZoneInfo('UTC'))

        logger.info(f"📅 Next run for '{schedule.get('name')}': {next_run_utc} UTC ({next_run} {timezone})")

        return next_run_utc

    async def add_schedule(self, schedule: Dict) -> str:
        """
        Add a new schedule

        Args:
            schedule: Schedule configuration

        Returns:
            Schedule ID
        """
        import uuid
        schedule_id = f"sched_{uuid.uuid4().hex[:12]}"

        schedule['schedule_id'] = schedule_id
        schedule['next_run'] = self._calculate_next_run(schedule)

        self.schedules[schedule_id] = schedule

        # TODO: Save to database

        logger.info(f"✅ Schedule added: {schedule_id} - {schedule.get('name')}")

        return schedule_id

    async def remove_schedule(self, schedule_id: str):
        """Remove a schedule"""
        if schedule_id in self.schedules:
            del self.schedules[schedule_id]
            # TODO: Delete from database
            logger.info(f"✅ Schedule removed: {schedule_id}")
        else:
            logger.warning(f"⚠️  Schedule not found: {schedule_id}")

    async def update_schedule(self, schedule_id: str, updates: Dict):
        """Update an existing schedule"""
        if schedule_id in self.schedules:
            self.schedules[schedule_id].update(updates)

            # Recalculate next run if time/frequency changed
            if any(k in updates for k in ['frequency', 'time', 'day_of_week', 'day_of_month', 'timezone']):
                self.schedules[schedule_id]['next_run'] = self._calculate_next_run(
                    self.schedules[schedule_id]
                )

            # TODO: Update in database

            logger.info(f"✅ Schedule updated: {schedule_id}")
        else:
            logger.warning(f"⚠️  Schedule not found: {schedule_id}")

    def get_schedules(self) -> List[Dict]:
        """Get all active schedules"""
        return list(self.schedules.values())

    def get_schedule(self, schedule_id: str) -> Optional[Dict]:
        """Get a specific schedule"""
        return self.schedules.get(schedule_id)


# Export singleton instance
_scheduler = None

def get_scheduler(db_session=None) -> ReportScheduler:
    """Get or create scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = ReportScheduler(db_session)
    return _scheduler
