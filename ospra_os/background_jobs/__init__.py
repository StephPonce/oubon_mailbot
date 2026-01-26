"""
Background Jobs Package

Automated background tasks for OspraOS including:
- Product discovery automation
- Scheduled data syncing
- Periodic analytics updates
- Notification processing

Author: OspraOS
Date: November 2025
"""

from ospra_os.background_jobs.auto_discovery import (
    AutoDiscoveryJob,
    AutoDiscoveryError,
    start_auto_discovery_scheduler
)
from ospra_os.background_jobs.token_refresh_job import (
    TokenRefreshJob,
    start_token_refresh_scheduler
)

__all__ = [
    "AutoDiscoveryJob",
    "AutoDiscoveryError",
    "start_auto_discovery_scheduler",
    "TokenRefreshJob",
    "start_token_refresh_scheduler"
]

__version__ = "1.0.0"
