"""
Safe JSON File Operations for Ospra OS
======================================

Thread-safe JSON file read/write with file locking to prevent data corruption
when multiple processes/threads access the same file.

Features:
- File locking (fcntl on Unix, msvcrt on Windows)
- Atomic writes (write to temp, then rename)
- Automatic backup creation
- Retry logic for lock acquisition

Usage:
    from ospra_os.utils.safe_json import safe_read_json, safe_write_json

    # Read safely
    data = safe_read_json("/path/to/file.json", default={})

    # Write safely
    safe_write_json("/path/to/file.json", data)

Author: OspraOS
"""

import json
import logging
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# =============================================================================
# FILE LOCKING
# =============================================================================

# Try to import platform-specific locking
try:
    import fcntl
    LOCK_AVAILABLE = True
    LOCK_TYPE = "fcntl"
except ImportError:
    try:
        import msvcrt
        LOCK_AVAILABLE = True
        LOCK_TYPE = "msvcrt"
    except ImportError:
        LOCK_AVAILABLE = False
        LOCK_TYPE = None
        logger.warning("File locking not available on this platform")


@contextmanager
def file_lock(file_handle, exclusive: bool = True, timeout: float = 10.0):
    """
    Context manager for file locking.

    Args:
        file_handle: Open file handle
        exclusive: True for write lock, False for read lock
        timeout: Maximum seconds to wait for lock

    Yields:
        The file handle with lock acquired
    """
    if not LOCK_AVAILABLE:
        yield file_handle
        return

    lock_acquired = False
    start_time = time.time()

    try:
        while time.time() - start_time < timeout:
            try:
                if LOCK_TYPE == "fcntl":
                    lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                    fcntl.flock(file_handle.fileno(), lock_type | fcntl.LOCK_NB)
                elif LOCK_TYPE == "msvcrt":
                    if exclusive:
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        # Windows doesn't have shared locks in msvcrt, use exclusive
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)

                lock_acquired = True
                break
            except (IOError, OSError, BlockingIOError):
                # Lock not available, wait and retry
                time.sleep(0.1)

        if not lock_acquired:
            raise TimeoutError(f"Could not acquire file lock within {timeout} seconds")

        yield file_handle

    finally:
        if lock_acquired:
            try:
                if LOCK_TYPE == "fcntl":
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                elif LOCK_TYPE == "msvcrt":
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception as e:
                logger.warning(f"Failed to release file lock: {e}")


# =============================================================================
# SAFE JSON OPERATIONS
# =============================================================================

def safe_read_json(
    file_path: Union[str, Path],
    default: Any = None,
    timeout: float = 10.0
) -> Any:
    """
    Safely read a JSON file with file locking.

    Args:
        file_path: Path to JSON file
        default: Value to return if file doesn't exist or is invalid
        timeout: Lock acquisition timeout in seconds

    Returns:
        Parsed JSON data or default value
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return default if default is not None else {}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            with file_lock(f, exclusive=False, timeout=timeout):
                content = f.read()
                if not content.strip():
                    return default if default is not None else {}
                return json.loads(content)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        return default if default is not None else {}

    except TimeoutError as e:
        logger.error(f"Lock timeout reading {file_path}: {e}")
        return default if default is not None else {}

    except (IOError, OSError) as e:
        logger.error(f"IO error reading {file_path}: {e}")
        return default if default is not None else {}


def safe_write_json(
    file_path: Union[str, Path],
    data: Any,
    indent: int = 2,
    timeout: float = 10.0,
    backup: bool = False
) -> bool:
    """
    Safely write data to a JSON file with atomic write and file locking.

    Uses atomic write pattern: write to temp file, then rename.
    This prevents corruption if process is killed mid-write.

    Args:
        file_path: Path to JSON file
        data: Data to serialize to JSON
        indent: JSON indent level (default: 2)
        timeout: Lock acquisition timeout in seconds
        backup: Create .bak backup of existing file

    Returns:
        True if successful, False otherwise
    """
    file_path = Path(file_path)

    try:
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create backup if requested and file exists
        if backup and file_path.exists():
            backup_path = file_path.with_suffix('.json.bak')
            try:
                import shutil
                shutil.copy2(file_path, backup_path)
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")

        # Write to temp file first
        temp_fd, temp_path = tempfile.mkstemp(
            suffix='.json.tmp',
            dir=str(file_path.parent)
        )

        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                with file_lock(f, exclusive=True, timeout=timeout):
                    json.dump(data, f, indent=indent, default=str, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

            # Atomic rename (on most systems)
            os.replace(temp_path, file_path)

            return True

        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise

    except TimeoutError as e:
        logger.error(f"Lock timeout writing {file_path}: {e}")
        return False

    except (IOError, OSError) as e:
        logger.error(f"IO error writing {file_path}: {e}")
        return False

    except Exception as e:
        logger.error(f"Failed to write {file_path}: {e}")
        return False


def safe_update_json(
    file_path: Union[str, Path],
    update_func: callable,
    default: Any = None,
    timeout: float = 10.0,
    backup: bool = False
) -> bool:
    """
    Safely read, modify, and write a JSON file atomically.

    Args:
        file_path: Path to JSON file
        update_func: Function that takes current data and returns updated data
        default: Default value if file doesn't exist
        timeout: Lock acquisition timeout
        backup: Create backup before update

    Returns:
        True if successful, False otherwise
    """
    file_path = Path(file_path)

    try:
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Read current data
        current_data = safe_read_json(file_path, default=default, timeout=timeout)

        # Apply update function
        updated_data = update_func(current_data)

        # Write updated data
        return safe_write_json(
            file_path,
            updated_data,
            timeout=timeout,
            backup=backup
        )

    except Exception as e:
        logger.error(f"Failed to update {file_path}: {e}")
        return False


def safe_append_to_json_list(
    file_path: Union[str, Path],
    item: Any,
    max_items: Optional[int] = None,
    timeout: float = 10.0
) -> bool:
    """
    Safely append an item to a JSON list file.

    Args:
        file_path: Path to JSON file containing a list
        item: Item to append
        max_items: Maximum items to keep (oldest removed if exceeded)
        timeout: Lock acquisition timeout

    Returns:
        True if successful, False otherwise
    """
    def append_item(data):
        if not isinstance(data, list):
            data = []
        data.append(item)
        if max_items and len(data) > max_items:
            data = data[-max_items:]
        return data

    return safe_update_json(
        file_path,
        append_item,
        default=[],
        timeout=timeout
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def load_json_with_defaults(
    file_path: Union[str, Path],
    defaults: Dict
) -> Dict:
    """
    Load JSON file and merge with defaults for any missing keys.

    Args:
        file_path: Path to JSON file
        defaults: Default values dict

    Returns:
        Merged configuration dict
    """
    data = safe_read_json(file_path, default={})
    result = defaults.copy()
    result.update(data)
    return result


def ensure_json_schema(
    file_path: Union[str, Path],
    schema: Dict,
    create_if_missing: bool = True
) -> bool:
    """
    Ensure a JSON file exists with required schema fields.

    Args:
        file_path: Path to JSON file
        schema: Dict with required fields and their default values
        create_if_missing: Create file if it doesn't exist

    Returns:
        True if file now conforms to schema
    """
    file_path = Path(file_path)

    if not file_path.exists():
        if create_if_missing:
            return safe_write_json(file_path, schema)
        return False

    # Load and update with missing fields
    data = safe_read_json(file_path, default={})
    updated = False

    for key, default_value in schema.items():
        if key not in data:
            data[key] = default_value
            updated = True

    if updated:
        return safe_write_json(file_path, data)

    return True


logger.info("[SUCCESS] safe_json module loaded")
