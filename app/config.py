import os
import sys
import secrets
import logging
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# Load existing .env if present
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)

def get_or_create_secret_key() -> str:
    """
    Retrieve SECRET_KEY from environment, or generate a cryptographically
    secure 64-byte key and persist it securely to .env.
    """
    secret = os.getenv("SECRET_KEY")
    if secret and len(secret) >= 32:
        return secret

    # Generate cryptographically secure token
    new_secret = secrets.token_urlsafe(64)
    try:
        # Append or update .env file
        if ENV_FILE.exists():
            content = ENV_FILE.read_text(encoding="utf-8")
            if "SECRET_KEY=" in content:
                content = re.sub(r"SECRET_KEY=.*", f"SECRET_KEY={new_secret}", content)
            else:
                content += f"\nSECRET_KEY={new_secret}\n"
        else:
            content = f"# Generated Environment Configuration\nSECRET_KEY={new_secret}\n"
        
        ENV_FILE.write_text(content, encoding="utf-8")
    except Exception as e:
        # In environments where writing to disk might fail, still return the generated secret
        pass
    
    os.environ["SECRET_KEY"] = new_secret
    return new_secret

class SensitiveDataFilter(logging.Filter):
    """
    Prevents passwords, session tokens, hashes, and secrets from appearing in log streams.
    """
    SENSITIVE_PATTERNS = [
        (re.compile(r'(password|passwd|pwd|secret|token|csrf|hash|authorization)=([^\s&]+)', re.IGNORECASE), r'\1=***REDACTED***'),
        (re.compile(r'("(?:password|hashed_password|secret_key|session_token|token)":\s*)"[^"]+"', re.IGNORECASE), r'\1"***REDACTED***"'),
        (re.compile(r'(Bearer\s+)[A-Za-z0-9_\-\.]+', re.IGNORECASE), r'\1***REDACTED***'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True

def setup_logging():
    """Configure secure application logging with sensitive data filtering."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SensitiveDataFilter())
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger("teachersystem")
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [handler]
    root_logger.propagate = False
    return root_logger

# Configuration Constants
SECRET_KEY = get_or_create_secret_key()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_PATH = DATA_DIR / "teachersystem.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")

SESSION_COOKIE_NAME = "ts_session"
CSRF_COOKIE_NAME = "ts_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
SESSION_EXPIRE_HOURS = int(os.getenv("SESSION_EXPIRE_HOURS", "24"))
ENABLE_TEST_ENDPOINTS = os.getenv("ENABLE_TEST_ENDPOINTS", "false").lower() in ("true", "1", "yes")

# Authentication Security & Rate Limiting Configuration
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5"))
LOGIN_RATE_LIMIT_LOCKOUT_SECONDS = int(os.getenv("LOGIN_RATE_LIMIT_LOCKOUT_SECONDS", "300"))

logger = setup_logging()
