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

__all__ = [
    "AutoDiscoveryJob",
    "AutoDiscoveryError",
    "start_auto_discovery_scheduler"
]

__version__ = "1.0.0"
