import secrets
import hashlib
import re
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from app.config import SESSION_EXPIRE_HOURS, logger

# Password Policy Configuration
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
COMMON_WEAK_PASSWORDS = {
    "password", "password123", "12345678", "admin123", "qwerty123", "teacher123"
}

def validate_password_strength(password: str) -> str:
    """
    Validates that a password satisfies the application security policy:
    1. Minimum 8 characters, maximum 128 characters.
    2. Contains at least one letter (a-z, A-Z).
    3. Contains at least one digit (0-9).
    4. Not in common weak passwords blacklist.

    Returns the validated password if compliant.
    Raises ValueError with a user-friendly explanation if non-compliant.
    """
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")

    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must not exceed {PASSWORD_MAX_LENGTH} characters.")

    if not re.search(r"[a-zA-Z]", password):
        raise ValueError("Password must contain at least one letter.")

    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one number.")

    if password.lower() in COMMON_WEAK_PASSWORDS:
        raise ValueError("Password is too common or easily guessed. Please choose a stronger password.")

    return password

# Initialize Argon2id password hasher with secure parameters
_ph = PasswordHasher(
    time_cost=3,        # 3 iterations
    memory_cost=65536,  # 64 MB memory
    parallelism=4,      # 4 threads
    hash_len=32,
    salt_len=16
)

def hash_password(password: str) -> str:
    """Hash a password using Argon2id after validating strength policy."""
    validate_password_strength(password)
    return _ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against an Argon2id hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as e:
        logger.error(f"Unexpected error during password verification: {e}")
        return False

def generate_session_token() -> str:
    """Generate a high-entropy 48-byte URL-safe session token."""
    return secrets.token_urlsafe(48)

def hash_token(token: str) -> str:
    """Compute SHA-256 hex digest of a session token for storage and lookup."""
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def generate_csrf_token() -> str:
    """Generate a 32-byte URL-safe CSRF token."""
    return secrets.token_urlsafe(32)

def calculate_session_expiry() -> datetime:
    """Calculate the expiration datetime for a new session."""
    return datetime.now(timezone.utc) + timedelta(hours=SESSION_EXPIRE_HOURS)
