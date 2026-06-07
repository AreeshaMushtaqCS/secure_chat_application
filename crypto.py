import hashlib
import base64
from cryptography.fernet import Fernet

def derive_key_from_password(password: str) -> bytes:
    """Derive a Fernet key from a password using SHA-256"""
    # Use SHA-256 to derive a key from the password
    # In production, use PBKDF2 or Argon2 for better security
    h = hashlib.sha256(password.encode()).digest()
    return base64.urlsafe_b64encode(h)

def encrypt(password: str, plaintext: str) -> str:
    """Encrypt plaintext using password-derived key"""
    key = derive_key_from_password(password)
    f = Fernet(key)
    token = f.encrypt(plaintext.encode())
    return token.decode()

def decrypt(password: str, token: str) -> str:
    """Decrypt ciphertext using password-derived key"""
    key = derive_key_from_password(password)
    f = Fernet(key)
    return f.decrypt(token.encode()).decode()