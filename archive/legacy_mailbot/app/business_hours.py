"""Business hours and quiet hours checker for auto-reply system."""
from datetime import datetime, time
from typing import Optional
import pytz


class BusinessHours:
    """Check if current time is within operating hours or quiet hours."""

    def __init__(
        self,
        weekday_start: time = time(7, 0),   # Mon-Fri: 7 AM
        weekday_end: time = time(21, 0),    # Mon-Fri: 9 PM
        weekend_start: time = time(10, 0),  # Sat-Sun: 10 AM
        weekend_end: time = time(19, 0),    # Sat-Sun: 7 PM
        timezone: str = "America/New_York",  # EST/EDT
    ):
        self.weekday_start = weekday_start
        self.weekday_end = weekday_end
        self.weekend_start = weekend_start
        self.weekend_end = weekend_end
        self.timezone = pytz.timezone(timezone)

    def is_operating_hours(self, dt: Optional[datetime] = None) -> bool:
        """Check if current time is during operating hours (AI + full service)."""
        if dt is None:
            dt = datetime.now(self.timezone)
        else:
            dt = dt.astimezone(self.timezone)

        current_time = dt.time()
        day_of_week = dt.weekday()  # 0=Monday, 6=Sunday

        # Weekday (Mon-Fri): 0-4
        if day_of_week <= 4:
            return self.weekday_start <= current_time < self.weekday_end

        # Weekend (Sat-Sun): 5-6
        else:
            return self.weekend_start <= current_time < self.weekend_end

    def is_quiet_hours(self, dt: Optional[datetime] = None) -> bool:
        """Check if current time is during quiet hours (no AI, templates only)."""
        return not self.is_operating_hours(dt)

    def get_response_mode(self, dt: Optional[datetime] = None) -> str:
        """
        Get the appropriate response mode.

        Returns:
            "ai" - Use AI for personalized responses (operating hours)
            "template" - Use templates only (quiet hours or weekends)
        """
        return "ai" if self.is_operating_hours(dt) else "template"
