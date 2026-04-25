"""
Retry Logic and Idempotency for Ospra OS
========================================

Provides reliable retry mechanisms for external API calls and
idempotency support for preventing duplicate operations.

Features:
- Exponential backoff with jitter
- Configurable retry conditions
- Idempotency key generation and tracking
- Circuit breaker pattern for failing services

Author: OspraOS
"""

import asyncio
import hashlib
import logging
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

logger = logging.getLogger(__name__)


# =============================================================================
# RETRY DECORATOR
# =============================================================================

class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Optional[List[Type[Exception]]] = None,
    retry_if: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        jitter: Add random jitter to prevent thundering herd (default: True)
        retry_on: List of exception types to retry on (default: all exceptions)
        retry_if: Custom function to determine if should retry
        on_retry: Callback called on each retry with (exception, attempt_number)

    Usage:
        @retry_with_backoff(max_retries=3, retry_on=[ConnectionError, TimeoutError])
        async def call_external_api():
            ...

        @retry_with_backoff(retry_if=lambda e: "rate limit" in str(e).lower())
        async def call_rate_limited_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if we should retry this exception
                    should_retry = False
                    if retry_if is not None:
                        should_retry = retry_if(e)
                    elif retry_on is not None:
                        should_retry = isinstance(e, tuple(retry_on))
                    else:
                        # Retry on all exceptions by default
                        should_retry = True

                    if not should_retry or attempt >= max_retries:
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    # Add jitter
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    # Call retry callback
                    if on_retry:
                        on_retry(e, attempt + 1)

                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__}: "
                        f"{type(e).__name__}: {str(e)[:100]}. "
                        f"Waiting {delay:.2f}s"
                    )

                    await asyncio.sleep(delay)

            raise RetryError(
                f"All {max_retries} retry attempts exhausted for {func.__name__}",
                last_exception
            )

        return wrapper
    return decorator


def retry_sync_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Optional[List[Type[Exception]]] = None,
):
    """
    Decorator for retrying synchronous functions with exponential backoff.

    Same as retry_with_backoff but for sync functions.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    should_retry = retry_on is None or isinstance(e, tuple(retry_on))

                    if not should_retry or attempt >= max_retries:
                        raise

                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__}: "
                        f"{type(e).__name__}. Waiting {delay:.2f}s"
                    )

                    time.sleep(delay)

            raise RetryError(
                f"All {max_retries} retry attempts exhausted for {func.__name__}",
                last_exception
            )

        return wrapper
    return decorator


# =============================================================================
# IDEMPOTENCY
# =============================================================================

class IdempotencyStore:
    """
    In-memory idempotency key store.

    For production, replace with Redis:
        redis_client.setex(key, ttl, value)
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl_seconds

    def _cleanup_expired(self):
        """Remove expired entries."""
        now = datetime.now(timezone.utc)
        expired = [
            key for key, data in self._store.items()
            if data.get("expires_at", now) < now
        ]
        for key in expired:
            del self._store[key]

    def exists(self, key: str) -> bool:
        """Check if an idempotency key exists and is not expired."""
        self._cleanup_expired()
        return key in self._store

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get stored result for an idempotency key."""
        self._cleanup_expired()
        data = self._store.get(key)
        if data:
            return data.get("result")
        return None

    def set(self, key: str, result: Any, status: str = "completed"):
        """Store result for an idempotency key."""
        self._store[key] = {
            "result": result,
            "status": status,
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=self._ttl)
        }

    def is_in_progress(self, key: str) -> bool:
        """Check if operation is currently in progress."""
        self._cleanup_expired()
        data = self._store.get(key)
        return data is not None and data.get("status") == "in_progress"

    def mark_in_progress(self, key: str):
        """Mark an operation as in progress."""
        self._store[key] = {
            "result": None,
            "status": "in_progress",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=300)  # 5 min timeout for in-progress
        }

    def clear(self, key: str):
        """Remove an idempotency key."""
        if key in self._store:
            del self._store[key]


# Global idempotency store (use Redis in production)
_idempotency_store = IdempotencyStore()


def generate_idempotency_key(*args, **kwargs) -> str:
    """
    Generate a deterministic idempotency key from arguments.

    The key is a hash of the arguments, so the same inputs always
    produce the same key.
    """
    key_data = f"{args}:{sorted(kwargs.items())}"
    return hashlib.sha256(key_data.encode()).hexdigest()[:32]


def idempotent(
    key_func: Optional[Callable[..., str]] = None,
    ttl_seconds: int = 3600,
    store: Optional[IdempotencyStore] = None
):
    """
    Decorator to make an async function idempotent.

    If the same operation (determined by idempotency key) is called multiple
    times, only the first call executes; subsequent calls return the cached result.

    Args:
        key_func: Function to generate idempotency key from args/kwargs.
                  Default: hash of all arguments.
        ttl_seconds: How long to cache results (default: 1 hour)
        store: Custom IdempotencyStore instance

    Usage:
        @idempotent()
        async def deploy_product(product_id: str, store_id: str):
            ...

        @idempotent(key_func=lambda product_id, **kw: f"deploy:{product_id}")
        async def deploy_product(product_id: str, store_id: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate idempotency key
            if key_func:
                idempotency_key = key_func(*args, **kwargs)
            else:
                idempotency_key = f"{func.__name__}:{generate_idempotency_key(*args, **kwargs)}"

            _store = store or _idempotency_store

            # Check if already completed
            cached_result = _store.get(idempotency_key)
            if cached_result is not None:
                logger.info(f"Idempotent hit for {func.__name__}: returning cached result")
                return cached_result

            # Check if in progress
            if _store.is_in_progress(idempotency_key):
                raise RetryError(
                    f"Operation {func.__name__} is already in progress. "
                    "Please wait and try again."
                )

            # Mark as in progress
            _store.mark_in_progress(idempotency_key)

            try:
                # Execute the function
                result = await func(*args, **kwargs)

                # Cache the result
                _store.set(idempotency_key, result)

                return result
            except Exception as e:
                # Clear the in-progress marker on failure
                _store.clear(idempotency_key)
                raise

        return wrapper
    return decorator


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected
    - HALF_OPEN: Testing if service has recovered

    Usage:
        external_api_breaker = CircuitBreaker(
            name="shopify_api",
            failure_threshold=5,
            recovery_timeout=60
        )

        @external_api_breaker
        async def call_shopify():
            ...
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Optional[Type[Exception]] = None
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception or Exception

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._success_count = 0

    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    logger.info(f"Circuit {self.name} entering half-open state")
        return self._state

    def record_success(self):
        """Record a successful call."""
        self._failure_count = 0
        if self._state == self.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= 3:  # Need 3 successes to fully close
                self._state = self.CLOSED
                self._success_count = 0
                logger.info(f"Circuit {self.name} closed after successful recovery")

    def record_failure(self, exception: Exception):
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        self._success_count = 0

        if self._failure_count >= self.failure_threshold:
            self._state = self.OPEN
            logger.warning(
                f"Circuit {self.name} opened after {self._failure_count} failures. "
                f"Last error: {type(exception).__name__}: {str(exception)[:100]}"
            )

    def __call__(self, func: Callable) -> Callable:
        """Use as decorator."""
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if self.state == self.OPEN:
                raise RetryError(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Service unavailable, please try again later."
                )

            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except self.expected_exception as e:
                self.record_failure(e)
                raise

        return wrapper


# =============================================================================
# COMMON RETRY CONDITIONS
# =============================================================================

def is_transient_error(exception: Exception) -> bool:
    """Check if an exception is likely transient and worth retrying."""
    transient_indicators = [
        "timeout",
        "connection",
        "rate limit",
        "429",
        "502",
        "503",
        "504",
        "temporary",
        "unavailable",
        "network",
    ]

    error_str = str(exception).lower()
    error_type = type(exception).__name__.lower()

    return any(
        indicator in error_str or indicator in error_type
        for indicator in transient_indicators
    )


def is_rate_limit_error(exception: Exception) -> bool:
    """Check if an exception is a rate limit error."""
    error_str = str(exception).lower()
    return (
        "rate limit" in error_str or
        "429" in error_str or
        "too many requests" in error_str
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

async def retry_operation(
    operation: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs
) -> Any:
    """
    Retry an operation with exponential backoff.

    Utility function for one-off retries without decorating.

    Usage:
        result = await retry_operation(
            call_api,
            endpoint="/products",
            max_retries=5
        )
    """
    @retry_with_backoff(max_retries=max_retries, base_delay=base_delay)
    async def wrapped():
        return await operation(*args, **kwargs)

    return await wrapped()
