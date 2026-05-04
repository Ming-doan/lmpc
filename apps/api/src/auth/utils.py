import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()

def hash_password(password: str) -> str:
    return _ph.hash(password)

def verify_password(password: str, hash: str) -> bool:
    try:
        return _ph.verify(hash, password)
    except VerifyMismatchError:
        return False

def generate_token() -> str:
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
