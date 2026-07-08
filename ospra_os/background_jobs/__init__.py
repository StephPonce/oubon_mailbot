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

# T126: token_refresh_job is dead — the live token refresher is
# api/aliexpress_token_scheduler.py (main.py imports start_token_refresh_scheduler
# from there, not from here). Re-export removed so the file is fully orphaned
# and can be git rm'd. Nothing else imports these names from this package.

__all__ = [
    "AutoDiscoveryJob",
    "AutoDiscoveryError",
    "start_auto_discovery_scheduler",
]

__version__ = "1.0.0"
