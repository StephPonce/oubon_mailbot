"""
Calendar view for scheduled ads
"""
from typing import Dict, List
from datetime import datetime, timedelta
from collections import defaultdict
from ospra_os.services.schedule_manager import ScheduleManager


class CalendarView:
    """Generate calendar view of scheduled ads"""

    def __init__(self, schedule_manager: ScheduleManager):
        self.manager = schedule_manager

    def get_week_view(
        self,
        start_date: datetime = None
    ) -> Dict:
        """
        Get schedules organized by day for a week

        Returns:
        {
            "2025-11-20": [schedules...],
            "2025-11-21": [schedules...],
            ...
        }
        """
        if not start_date:
            start_date = datetime.utcnow()

        # Get all active and pending schedules
        schedules = self.manager.list_schedules(limit=1000)

        # Group by date
        calendar = defaultdict(list)

        for schedule in schedules:
            scheduled_date = datetime.fromisoformat(
                schedule['scheduled_start']
            ).date()

            # Check if in this week
            if start_date.date() <= scheduled_date < (start_date + timedelta(days=7)).date():
                date_key = scheduled_date.isoformat()
                calendar[date_key].append(schedule)

        # Sort each day's schedules by time
        for date_key in calendar:
            calendar[date_key].sort(
                key=lambda s: s['scheduled_start']
            )

        return dict(calendar)

    def get_month_view(
        self,
        year: int = None,
        month: int = None
    ) -> Dict:
        """Get schedules organized by day for a month"""
        if not year:
            year = datetime.utcnow().year
        if not month:
            month = datetime.utcnow().month

        schedules = self.manager.list_schedules(limit=1000)

        calendar = defaultdict(list)

        for schedule in schedules:
            scheduled_date = datetime.fromisoformat(
                schedule['scheduled_start']
            )

            if scheduled_date.year == year and scheduled_date.month == month:
                date_key = scheduled_date.date().isoformat()
                calendar[date_key].append(schedule)

        # Sort
        for date_key in calendar:
            calendar[date_key].sort(
                key=lambda s: s['scheduled_start']
            )

        return dict(calendar)

    def get_daily_budget_forecast(
        self,
        days: int = 30
    ) -> List[Dict]:
        """
        Forecast daily ad spend for next N days

        Returns list of {date, total_budget}
        """
        start_date = datetime.utcnow().date()
        schedules = self.manager.list_schedules(limit=1000)

        forecast = []

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            total_budget = 0

            for schedule in schedules:
                sched_start = datetime.fromisoformat(
                    schedule['scheduled_start']
                ).date()

                sched_end = None
                if schedule.get('scheduled_end'):
                    sched_end = datetime.fromisoformat(
                        schedule['scheduled_end']
                    ).date()

                # Check if schedule is active on this date
                if sched_start <= current_date:
                    if sched_end is None or current_date <= sched_end:
                        total_budget += schedule['daily_budget']

            forecast.append({
                'date': current_date.isoformat(),
                'total_budget': total_budget,
                'active_campaigns': sum(
                    1 for s in schedules
                    if datetime.fromisoformat(s['scheduled_start']).date() <= current_date
                    and (not s.get('scheduled_end') or datetime.fromisoformat(s['scheduled_end']).date() >= current_date)
                )
            })

        return forecast
