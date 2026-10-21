"""Password hashing, session tokens, password rules and rate limiting."""
import hashlib
import math
import re
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Request

from .config import settings
from .timeutil import utcnow

# ---------------------------------------------------------------- passwords
_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_kib,
    parallelism=1 if settings.argon2_memory_kib < 1024 else 4,
)
_dummy_hash: Optional[str] = None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def burn_password_check(password: str) -> None:
    """Do a real hash check on a fake hash, so unknown emails take as long as known ones."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    verify_password(_dummy_hash, password)


_COMMON_PASSWORDS = {
    "password", "password1", "password123", "1234567890", "12345678910", "qwertyuiop",
    "admin12345", "letmein123", "welcome123", "iloveyou123", "changeme123", "freebees123",
}


def password_problems(password: str, *, email: str = "", name: str = "") -> list[str]:
    problems = []
    if len(password) < settings.min_password_length:
        problems.append(f"Use at least {settings.min_password_length} characters.")
    if len(password) > 128:
        problems.append("Use at most 128 characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        problems.append("Include both letters and numbers.")
    lowered = password.lower()
    if lowered in _COMMON_PASSWORDS:
        problems.append("That password is too common.")
    local = email.split("@")[0].lower() if email else ""
    if local and len(local) >= 4 and local in lowered:
        problems.append("Don't include your email name in the password.")
    first = name.split()[0].lower() if name.strip() else ""
    if first and len(first) >= 4 and first in lowered:
        problems.append("Don't include your name in the password.")
    return problems


def password_version(password_hash: str) -> str:
    """Short fingerprint of the current password. Tokens carry it, so changing the password logs out everywhere."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


# ------------------------------------------------------------------ tokens
def create_access_token(user_id, password_hash: str) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "pwv": password_version(password_hash),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token, settings.secret_key, algorithms=["HS256"], options={"require": ["exp", "sub", "iat"]}
    )


# ------------------------------------------------------------ rate limiting
class SlidingWindowLimiter:
    """Allow `limit` events per `window` seconds per key. In memory, so per server instance.

    Good enough for one instance; with several instances use a shared store such as Redis.
    """

    def __init__(self, limit_getter, window_seconds: int) -> None:
        self._limit_getter = limit_getter
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _purge(self, key: str, now: float) -> deque:
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        return hits

    def retry_after(self, key: str) -> int:
        """Seconds to wait before another event is allowed (0 = allowed now)."""
        with self._lock:
            now = time.monotonic()
            hits = self._purge(key, now)
            if len(hits) < self._limit_getter():
                return 0
            return math.ceil(hits[0] + self.window - now)

    def record(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._purge(key, now).append(now)
            if len(self._hits) > 20000:  # keep memory bounded
                for stale in [k for k, v in self._hits.items() if not v][:5000]:
                    self._hits.pop(stale, None)

    def hit(self, key: str) -> int:
        """Record an event unless the limit is reached. Returns seconds to wait (0 = allowed)."""
        wait = self.retry_after(key)
        if wait == 0:
            self.record(key)
        return wait

    def reset(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


login_ip_limiter = SlidingWindowLimiter(lambda: settings.login_ip_limit, 300)
login_unknown_email_limiter = SlidingWindowLimiter(
    lambda: settings.login_max_attempts, settings.login_lock_minutes * 60
)
write_limiter = SlidingWindowLimiter(lambda: settings.write_rate_limit, 60)
export_limiter = SlidingWindowLimiter(lambda: settings.export_rate_limit, 60)


def reset_all_limiters() -> None:
    for limiter in (login_ip_limiter, login_unknown_email_limiter, write_limiter, export_limiter):
        limiter.reset()


def client_ip(request: Request) -> str:
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
