"""SQLite-backed rate limiter for API endpoints.

This provides persistent rate limiting that survives server restarts
and works correctly across multiple threads.
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, delete

from app.models import RateLimitRecord

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    SQLite-backed rate limiter with configurable limits per endpoint.

    Features:
    - Persistent across restarts (SQLite-backed)
    - Thread-safe operations
    - Configurable per-endpoint limits
    - Automatic cleanup of old records
    - Sliding window rate limiting
    """

    # Default rate limits: (max_requests, window_seconds)
    DEFAULT_LIMITS: Dict[str, Tuple[int, int]] = {
        # Standard endpoints
        "default": (100, 60),  # 100 requests per minute
        # High-traffic read endpoints
        "get_jobs": (60, 60),  # 60 requests per minute
        "get_runs": (60, 60),
        "get_profile": (30, 60),
        # Write/mutation endpoints (more restrictive)
        "create_run": (10, 60),  # 10 per minute
        "update_job": (30, 60),
        "update_profile": (10, 60),
        # Resource-intensive endpoints (very restrictive)
        "run_pipeline": (5, 300),  # 5 per 5 minutes
        "validate_linkedin": (3, 60),  # 3 per minute
        "answer_question": (20, 60),  # 20 per minute
        "apply_to_job": (10, 60),  # 10 per minute
        # Config endpoints (moderate)
        "get_config": (20, 60),
        "update_config": (5, 60),
    }

    # Cleanup old records every N requests
    CLEANUP_INTERVAL = 100

    def __init__(
        self,
        db: Session,
        custom_limits: Optional[Dict[str, Tuple[int, int]]] = None,
    ):
        """
        Initialize the rate limiter.

        Args:
            db: Database session
            custom_limits: Optional custom limits to override defaults
        """
        self.db = db
        self.limits = {**self.DEFAULT_LIMITS}
        if custom_limits:
            self.limits.update(custom_limits)

        self._request_count = 0
        self._lock = threading.Lock()

    def _get_limit(self, endpoint: str) -> Tuple[int, int]:
        """Get rate limit for an endpoint."""
        return self.limits.get(endpoint, self.limits["default"])

    def _get_client_id(self, request) -> str:
        """
        Extract client identifier from request.

        Uses X-Forwarded-For header if behind proxy, otherwise client host.
        Falls back to API key if present.
        """
        # Check for API key first (more reliable identifier)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Use hash of API key to avoid storing it
            import hashlib
            return f"key:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"

        # Check X-Forwarded-For for clients behind proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return f"ip:{forwarded_for.split(',')[0].strip()}"

        # Fall back to direct client IP
        if hasattr(request, 'client') and request.client:
            return f"ip:{request.client.host}"

        return "ip:unknown"

    def check_rate_limit(
        self,
        client_id: str,
        endpoint: str,
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if a request is within rate limits.

        Args:
            client_id: Client identifier
            endpoint: Endpoint being accessed

        Returns:
            Tuple of (is_allowed, rate_limit_info)
            rate_limit_info contains: limit, remaining, reset_seconds
        """
        max_requests, window_seconds = self._get_limit(endpoint)
        window_start = datetime.utcnow() - timedelta(seconds=window_seconds)

        with self._lock:
            # Count requests in current window
            request_count = self.db.query(RateLimitRecord).filter(
                and_(
                    RateLimitRecord.client_id == client_id,
                    RateLimitRecord.endpoint == endpoint,
                    RateLimitRecord.timestamp >= window_start,
                )
            ).count()

            # Calculate remaining requests
            remaining = max(0, max_requests - request_count)

            # Calculate reset time (when oldest request in window expires)
            oldest_request = self.db.query(RateLimitRecord).filter(
                and_(
                    RateLimitRecord.client_id == client_id,
                    RateLimitRecord.endpoint == endpoint,
                    RateLimitRecord.timestamp >= window_start,
                )
            ).order_by(RateLimitRecord.timestamp.asc()).first()

            if oldest_request:
                reset_time = oldest_request.timestamp + timedelta(seconds=window_seconds)
                reset_seconds = max(0, int((reset_time - datetime.utcnow()).total_seconds()))
            else:
                reset_seconds = window_seconds

            rate_limit_info = {
                "limit": max_requests,
                "remaining": remaining,
                "reset_seconds": reset_seconds,
                "window_seconds": window_seconds,
            }

            is_allowed = request_count < max_requests

            if is_allowed:
                # Record this request
                record = RateLimitRecord(
                    client_id=client_id,
                    endpoint=endpoint,
                    timestamp=datetime.utcnow(),
                )
                self.db.add(record)
                self.db.commit()

                # Periodic cleanup
                self._request_count += 1
                if self._request_count >= self.CLEANUP_INTERVAL:
                    self._cleanup_old_records()
                    self._request_count = 0

            return is_allowed, rate_limit_info

    def _cleanup_old_records(self):
        """Remove expired rate limit records."""
        try:
            # Find the longest window we track
            max_window = max(limit[1] for limit in self.limits.values())
            cutoff = datetime.utcnow() - timedelta(seconds=max_window * 2)

            # Delete old records
            deleted = self.db.query(RateLimitRecord).filter(
                RateLimitRecord.timestamp < cutoff
            ).delete(synchronize_session=False)

            self.db.commit()

            if deleted > 0:
                logger.debug(f"Cleaned up {deleted} old rate limit records")

        except Exception as e:
            logger.error(f"Error cleaning up rate limit records: {e}")
            self.db.rollback()

    def reset_limit(self, client_id: str, endpoint: Optional[str] = None):
        """
        Reset rate limit for a client.

        Args:
            client_id: Client identifier
            endpoint: Optional specific endpoint (resets all if None)
        """
        with self._lock:
            try:
                query = self.db.query(RateLimitRecord).filter(
                    RateLimitRecord.client_id == client_id
                )
                if endpoint:
                    query = query.filter(RateLimitRecord.endpoint == endpoint)

                deleted = query.delete(synchronize_session=False)
                self.db.commit()
                logger.info(f"Reset rate limit for {client_id}: deleted {deleted} records")

            except Exception as e:
                logger.error(f"Error resetting rate limit: {e}")
                self.db.rollback()

    def get_status(self, client_id: str) -> Dict[str, Dict[str, int]]:
        """
        Get rate limit status for all endpoints for a client.

        Args:
            client_id: Client identifier

        Returns:
            Dict mapping endpoint to rate limit info
        """
        status = {}

        for endpoint, (max_requests, window_seconds) in self.limits.items():
            window_start = datetime.utcnow() - timedelta(seconds=window_seconds)

            request_count = self.db.query(RateLimitRecord).filter(
                and_(
                    RateLimitRecord.client_id == client_id,
                    RateLimitRecord.endpoint == endpoint,
                    RateLimitRecord.timestamp >= window_start,
                )
            ).count()

            status[endpoint] = {
                "limit": max_requests,
                "used": request_count,
                "remaining": max(0, max_requests - request_count),
                "window_seconds": window_seconds,
            }

        return status


def rate_limit_dependency(endpoint: str):
    """
    FastAPI dependency for rate limiting.

    Usage:
        @app.get("/endpoint")
        async def my_endpoint(
            rate_limited: bool = Depends(rate_limit_dependency("my_endpoint")),
            db: Session = Depends(get_db)
        ):
            ...
    """
    from fastapi import Request, HTTPException, Depends
    from app.db import get_db

    async def check_rate_limit(
        request: Request,
        db: Session = Depends(get_db),
    ) -> bool:
        limiter = RateLimiter(db)
        client_id = limiter._get_client_id(request)

        is_allowed, info = limiter.check_rate_limit(client_id, endpoint)

        if not is_allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": info["limit"],
                    "reset_seconds": info["reset_seconds"],
                    "message": f"Rate limit of {info['limit']} requests per {info['window_seconds']} seconds exceeded. Try again in {info['reset_seconds']} seconds.",
                },
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset_seconds"]),
                    "Retry-After": str(info["reset_seconds"]),
                },
            )

        return True

    return check_rate_limit
