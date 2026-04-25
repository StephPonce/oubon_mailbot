"""
Error Tracker
Track and categorize system errors
"""

import uuid
import traceback
from functools import wraps
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from collections import defaultdict


class ErrorTracker:
    """Track and categorize system errors"""

    # Error categories
    INTEGRATION_ERROR = "INTEGRATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    JOB_ERROR = "JOB_ERROR"
    API_ERROR = "API_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"

    # Severity levels
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def __init__(self):
        self.errors = {}  # error_id -> error_data
        self.errors_by_category = defaultdict(list)

    async def log_error(
        self,
        category: str,
        message: str,
        source: str,
        severity: str = "ERROR",
        details: dict = None,
        stack_trace: str = None
    ) -> str:
        """
        Log an error
        Returns: error_id
        """
        error_id = str(uuid.uuid4())[:8]

        error_data = {
            "error_id": error_id,
            "category": category,
            "severity": severity,
            "source": source,
            "message": message,
            "details": details or {},
            "stack_trace": stack_trace,
            "acknowledged": False,
            "acknowledged_at": None,
            "acknowledged_by": None,
            "resolved": False,
            "resolved_at": None,
            "resolution": None,
            "occurred_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        }

        self.errors[error_id] = error_data
        self.errors_by_category[category].append(error_id)

        return error_id

    async def get_errors(
        self,
        category: str = None,
        severity: str = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[dict]:
        """Get recent errors with filters"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        filtered_errors = []
        for error in self.errors.values():
            # Time filter
            if error['occurred_at'] < cutoff:
                continue

            # Category filter
            if category and error['category'] != category:
                continue

            # Severity filter
            if severity and error['severity'] != severity:
                continue

            filtered_errors.append(error)

        # Sort by time (most recent first)
        filtered_errors.sort(key=lambda x: x['occurred_at'], reverse=True)

        return filtered_errors[:limit]

    async def get_error(self, error_id: str) -> Optional[dict]:
        """Get specific error details"""
        return self.errors.get(error_id)

    async def get_error_counts(self, hours: int = 24) -> dict:
        """Get error counts by category"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        recent_errors = [
            e for e in self.errors.values()
            if e['occurred_at'] > cutoff
        ]

        by_category = defaultdict(int)
        by_severity = defaultdict(int)

        for error in recent_errors:
            by_category[error['category']] += 1
            by_severity[error['severity']] += 1

        return {
            "total": len(recent_errors),
            "by_category": dict(by_category),
            "by_severity": dict(by_severity)
        }

    async def get_error_trends(self, days: int = 7) -> List[dict]:
        """Error counts over time"""
        daily_counts = []

        for day_offset in range(days):
            day_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=day_offset)
            day_end = day_start + timedelta(days=1)

            day_errors = [
                e for e in self.errors.values()
                if day_start <= e['occurred_at'] < day_end
            ]

            daily_counts.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "count": len(day_errors),
                "by_category": self._count_by_category(day_errors)
            })

        daily_counts.reverse()  # Oldest to newest
        return daily_counts

    async def acknowledge_error(self, error_id: str, notes: str = None, user: str = "system"):
        """Mark error as acknowledged"""
        if error_id in self.errors:
            self.errors[error_id]['acknowledged'] = True
            self.errors[error_id]['acknowledged_at'] = datetime.now(timezone.utc)
            self.errors[error_id]['acknowledged_by'] = user
            if notes:
                self.errors[error_id]['details']['ack_notes'] = notes

    async def resolve_error(self, error_id: str, resolution: str = None):
        """Mark error as resolved"""
        if error_id in self.errors:
            self.errors[error_id]['resolved'] = True
            self.errors[error_id]['resolved_at'] = datetime.now(timezone.utc)
            self.errors[error_id]['resolution'] = resolution

    async def get_recurring_errors(self, hours: int = 24, min_count: int = 3) -> List[dict]:
        """Find errors that occur repeatedly"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Group by message
        message_counts = defaultdict(list)
        for error in self.errors.values():
            if error['occurred_at'] > cutoff:
                key = f"{error['category']}:{error['message'][:100]}"
                message_counts[key].append(error)

        # Find recurring patterns
        recurring = []
        for key, error_list in message_counts.items():
            if len(error_list) >= min_count:
                recurring.append({
                    "pattern": key,
                    "count": len(error_list),
                    "first_occurred": min(e['occurred_at'] for e in error_list),
                    "last_occurred": max(e['occurred_at'] for e in error_list),
                    "category": error_list[0]['category'],
                    "message": error_list[0]['message']
                })

        recurring.sort(key=lambda x: x['count'], reverse=True)
        return recurring

    def _count_by_category(self, errors: List[dict]) -> dict:
        """Count errors by category"""
        counts = defaultdict(int)
        for error in errors:
            counts[error['category']] += 1
        return dict(counts)


# Global error tracker instance
error_tracker = ErrorTracker()


def track_errors(category: str, severity: str = "ERROR"):
    """Decorator to automatically track errors"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await error_tracker.log_error(
                    category=category,
                    message=str(e),
                    source=func.__name__,
                    severity=severity,
                    stack_trace=traceback.format_exc()
                )
                raise
        return wrapper
    return decorator
