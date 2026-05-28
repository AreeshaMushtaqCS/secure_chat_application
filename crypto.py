import hashlib
import base64
from cryptography.fernet import Fernet


def derive_key_from_room(room_id: str) -> bytes:
    """Derive a Fernet key from the room_id. This is a simple demo KDF and
    should be replaced with a proper passphrase-based key derivation when
    used in production."""
    h = hashlib.sha256(room_id.encode()).digest()
    return base64.urlsafe_b64encode(h)


def encrypt(room_id: str, plaintext: str) -> str:
    key = derive_key_from_room(room_id)
    f = Fernet(key)
    token = f.encrypt(plaintext.encode())
    return token.decode()


def decrypt(room_id: str, token: str) -> str:
    key = derive_key_from_room(room_id)
    f = Fernet(key)
    return f.decrypt(token.encode()).decode()
