"""
Email Settings API Routes

Simple endpoint for storing and retrieving user email settings/preferences.
Settings are persisted to a JSON file to survive server restarts.

SECURITY: All endpoints require JWT authentication. User ID is extracted
from the verified token, NOT from query parameters.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Dict, Any
import json
from pathlib import Path

from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

router = APIRouter(tags=["Email Settings"])


# File-based storage for persistence across server restarts
SETTINGS_FILE = Path("data/email_settings.json")


def _load_settings_from_file() -> Dict[int, Dict[str, Any]]:
    """Load settings from JSON file"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load settings file: {e}")
            return {}
    return {}


def _save_settings_to_file(settings: Dict[int, Dict[str, Any]]) -> None:
    """Save settings to JSON file"""
    try:
        # Create data directory if it doesn't exist
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Convert int keys to strings for JSON serialization
        settings_for_json = {str(k): v for k, v in settings.items()}

        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings_for_json, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save settings file: {e}")


# Load settings from file on module import
_settings_store = _load_settings_from_file()
# Convert string keys back to ints
_settings_store = {int(k): v for k, v in _settings_store.items()}


class EmailSettingsRequest(BaseModel):
    """Email settings payload"""
    settings: Dict[str, Any]


@router.get("/api/email-settings")
def get_email_settings(current_user: User = Depends(get_current_user)):
    """
    Get email settings for the authenticated user.

    Returns default settings if none exist yet.

    SECURITY: User ID is extracted from JWT token, not query params.
    """
    user_id = current_user.id
    # Default settings
    default_settings = {
        # Auto-sync settings
        "auto_sync_enabled": True,
        "sync_interval_minutes": 5,

        # Automation settings
        "automation_enabled": True,
        "auto_label_enabled": True,
        "auto_reply_enabled": False,
        "auto_archive_enabled": False,
        "auto_delete_spam": False,

        # Sync to provider settings
        "sync_star_to_provider": True,
        "sync_archive_to_provider": True,
        "sync_delete_to_provider": True,
        "sync_labels_to_provider": True,
        "sync_read_status_to_provider": True,

        # Smart features
        "smart_categorization": True,
        "priority_inbox": True,
        "thread_grouping": True,

        # Notifications
        "notification_enabled": True,
        "notification_sound": False,
        "notification_desktop": True,
    }

    # Get user settings or return defaults
    settings = _settings_store.get(user_id, default_settings)

    return {
        'success': True,
        'settings': settings
    }


@router.post("/api/email-settings")
def save_email_settings(
    request: EmailSettingsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Save email settings for the authenticated user.

    SECURITY: User ID is extracted from JWT token, not query params.

    Body: {
        "settings": {
            "auto_sync_enabled": true,
            "sync_interval_minutes": 15,
            ...
        }
    }
    """
    user_id = current_user.id
    try:
        # Store settings in memory
        _settings_store[user_id] = request.settings

        # Persist to file
        _save_settings_to_file(_settings_store)

        return {
            'success': True,
            'message': 'Settings saved successfully'
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


@router.delete("/api/email-settings")
def reset_email_settings(current_user: User = Depends(get_current_user)):
    """
    Reset email settings to defaults for the authenticated user.

    SECURITY: User ID is extracted from JWT token, not query params.
    """
    user_id = current_user.id
    try:
        # Remove user settings (will fall back to defaults on next GET)
        if user_id in _settings_store:
            del _settings_store[user_id]

            # Persist changes to file
            _save_settings_to_file(_settings_store)

        return {
            'success': True,
            'message': 'Settings reset to defaults'
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {str(e)}")
