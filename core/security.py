import base64
import hashlib
import secrets
from datetime import timedelta

from cryptography.fernet import Fernet
from pwdlib import PasswordHash

from core.config import get_settings
from core.models import utcnow


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hash.verify(password, encoded)


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def session_expiry():
    return utcnow() + timedelta(days=get_settings().session_days)


def _fernet() -> Fernet:
    raw = hashlib.sha256(get_settings().app_encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
