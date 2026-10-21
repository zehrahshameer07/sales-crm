"""Settings, read from environment variables.

Nothing secret is hard-coded here. In production (e.g. Render) set the values in the
host's dashboard. See .env.example for the full list.
"""
import os
import warnings
from dataclasses import dataclass, field

DEV_SECRET = "dev-only-insecure-secret-change-me-before-deploying"


def _text(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw and raw.strip() else default
    except ValueError:
        return default


def _detect_env() -> str:
    env = _text("APP_ENV").lower()
    if env:
        return env
    # Render sets RENDER=true automatically, so treat that as production
    return "production" if os.getenv("RENDER") else "development"


@dataclass
class Settings:
    app_env: str = field(default_factory=_detect_env)
    secret_key: str = field(default_factory=lambda: _text("SECRET_KEY"))
    access_token_minutes: int = field(default_factory=lambda: _int("ACCESS_TOKEN_MINUTES", 480))
    cookie_name: str = "crm_session"
    cookie_secure: bool = False
    timezone: str = field(default_factory=lambda: _text("APP_TIMEZONE", "Asia/Kolkata"))

    # login protection
    login_max_attempts: int = field(default_factory=lambda: _int("LOGIN_MAX_ATTEMPTS", 5))
    login_lock_minutes: int = field(default_factory=lambda: _int("LOGIN_LOCK_MINUTES", 15))
    login_ip_limit: int = field(default_factory=lambda: _int("LOGIN_IP_LIMIT", 20))  # per 5 minutes
    write_rate_limit: int = field(default_factory=lambda: _int("WRITE_RATE_LIMIT", 60))  # per minute, per user
    export_rate_limit: int = field(default_factory=lambda: _int("EXPORT_RATE_LIMIT", 10))  # per minute, per user
    trust_proxy: bool = False

    # password hashing cost (Argon2id). Defaults follow the library's recommended profile.
    argon2_time_cost: int = field(default_factory=lambda: _int("ARGON2_TIME_COST", 3))
    argon2_memory_kib: int = field(default_factory=lambda: _int("ARGON2_MEMORY_KIB", 65536))
    min_password_length: int = 10

    # startup behaviour
    auto_migrate: bool = field(default_factory=lambda: _bool("AUTO_MIGRATE", True))
    reset_legacy_schema: bool = field(default_factory=lambda: _bool("RESET_LEGACY_SCHEMA", False))
    admin_email: str = field(default_factory=lambda: _text("ADMIN_EMAIL"))
    admin_password: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", ""))
    admin_name: str = field(default_factory=lambda: _text("ADMIN_NAME", "Administrator"))
    seed_demo: bool = field(default_factory=lambda: _bool("SEED_DEMO", False))
    show_demo_logins: bool = False

    def __post_init__(self) -> None:
        self.cookie_secure = _bool("COOKIE_SECURE", self.is_production)
        self.trust_proxy = _bool("TRUST_PROXY", self.is_production)
        self.show_demo_logins = _bool("SHOW_DEMO_LOGINS", self.seed_demo)
        if not self.secret_key:
            if self.is_production:
                raise RuntimeError(
                    "SECRET_KEY is not set. Generate one with: "
                    "python -c \"import secrets; print(secrets.token_urlsafe(48))\" "
                    "and set it as an environment variable."
                )
            warnings.warn("SECRET_KEY not set: using an insecure development key.", stacklevel=2)
            self.secret_key = DEV_SECRET
        if self.is_production and len(self.secret_key) < 32:
            raise RuntimeError("SECRET_KEY is too short. Use at least 32 random characters.")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
