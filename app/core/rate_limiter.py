import time
import threading
from typing import Dict, List
from fastapi import HTTPException, status
from app.config import (
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
    LOGIN_RATE_LIMIT_LOCKOUT_SECONDS,
    logger
)

class LoginRateLimiter:
    """
    In-memory rate limiter designed to mitigate brute-force password guessing
    and credential stuffing attacks against /api/auth/login.
    
    Architecture & Scope:
    - Thread-safe using threading.Lock.
    - Tracks failed login attempts per (client_ip, username) pair to prevent account lockouts
      across separate valid users behind the same school LAN gateway/NAT.
    - Zero external dependencies (no Redis required), perfectly tailored for local single-node SQLite deployment.
    - Deterministic testing support via configurable _time_provider.
    
    Limitations:
    - State is held in application process memory. Server restart resets the counters.
    - Does not synchronize state across multiple independent OS worker processes without a shared broker.
    """
    def __init__(
        self,
        max_attempts: int = LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
        lockout_seconds: int = LOGIN_RATE_LIMIT_LOCKOUT_SECONDS
    ):
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        # Maps key (f"{ip}:{username}") -> list of failure timestamps (floats)
        self._failures: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
        self._time_provider = time.time

    def _get_key(self, ip: str, username: str) -> str:
        clean_user = username.strip().lower() if username else ""
        return f"{ip}:{clean_user}"

    def check_rate_limit(self, ip: str, username: str) -> None:
        """
        Check if the (IP, username) has exceeded the max allowed failed attempts.
        Raises HTTPException(429) if locked out.
        """
        key = self._get_key(ip, username)
        now = self._time_provider()

        with self._lock:
            timestamps = self._failures.get(key, [])
            valid_timestamps = [t for t in timestamps if (now - t) < self.lockout_seconds]
            self._failures[key] = valid_timestamps

            if len(valid_timestamps) >= self.max_attempts:
                oldest_in_window = valid_timestamps[0]
                remaining_lockout = int(self.lockout_seconds - (now - oldest_in_window))
                remaining_lockout = max(1, remaining_lockout)

                logger.warning(
                    f"Rate limit exceeded for client IP [{ip}] attempting login on user [{username}]. Lockout active."
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Please try again after {remaining_lockout} seconds.",
                    headers={"Retry-After": str(remaining_lockout)}
                )

    def record_failure(self, ip: str, username: str) -> None:
        """Record a failed login attempt."""
        key = self._get_key(ip, username)
        now = self._time_provider()

        with self._lock:
            timestamps = self._failures.get(key, [])
            valid_timestamps = [t for t in timestamps if (now - t) < self.lockout_seconds]
            valid_timestamps.append(now)
            self._failures[key] = valid_timestamps

    def record_success(self, ip: str, username: str) -> None:
        """Reset failed attempts upon successful login."""
        key = self._get_key(ip, username)
        with self._lock:
            if key in self._failures:
                del self._failures[key]

    def reset(self) -> None:
        """Reset all rate limiter state (used in test fixtures)."""
        with self._lock:
            self._failures.clear()

login_rate_limiter = LoginRateLimiter()
