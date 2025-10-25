"""Business hours and quiet hours checker for auto-reply system."""
from datetime import datetime, time
from typing import Optional
import pytz


class BusinessHours:
    """Check if current time is within operating hours or quiet hours."""

    def __init__(
        self,
        quiet_start: time = time(21, 0),  # 9 PM
        quiet_end: time = time(7, 0),     # 7 AM
        timezone: str = "America/New_York",  # EST/EDT
        operating_days: Optional[list] = None,  # Mon-Fri = [0,1,2,3,4]
    ):
        self.quiet_start = quiet_start
        self.quiet_end = quiet_end
        self.timezone = pytz.timezone(timezone)
        self.operating_days = operating_days or [0, 1, 2, 3, 4]  # Mon-Fri default

    def is_quiet_hours(self, dt: Optional[datetime] = None) -> bool:
        """Check if current time is during quiet hours (no AI, templates only)."""
        if dt is None:
            dt = datetime.now(self.timezone)
        else:
            dt = dt.astimezone(self.timezone)

        current_time = dt.time()

        # Handle quiet hours that span midnight
        if self.quiet_start > self.quiet_end:
            # e.g., 21:00 to 07:00 next day
            return current_time >= self.quiet_start or current_time < self.quiet_end
        else:
            # e.g., 01:00 to 05:00 same day
            return self.quiet_start <= current_time < self.quiet_end

    def is_operating_hours(self, dt: Optional[datetime] = None) -> bool:
        """Check if current time is during operating hours (AI + full service)."""
        if dt is None:
            dt = datetime.now(self.timezone)
        else:
            dt = dt.astimezone(self.timezone)

        # Check if it's an operating day (e.g., Mon-Fri)
        if dt.weekday() not in self.operating_days:
            return False

        # Not during quiet hours
        return not self.is_quiet_hours(dt)

    def get_response_mode(self, dt: Optional[datetime] = None) -> str:
        """
        Get the appropriate response mode.

        Returns:
            "ai" - Use AI for personalized responses (operating hours)
            "template" - Use templates only (quiet hours or weekends)
        """
        return "ai" if self.is_operating_hours(dt) else "template"
