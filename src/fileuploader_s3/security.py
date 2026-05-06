import os
import base64
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("ENCRYPTION_KEY")
if not SECRET_KEY:
    raise RuntimeError("ENCRYPTION_KEY not set in environment!")

def _xor_encrypt(data: str, key: str) -> str:
    """Simple XOR encryption for basic obfuscation."""
    result = []
    key_bytes = key.encode()
    for i, char in enumerate(data):
        result.append(chr(ord(char) ^ key_bytes[i % len(key_bytes)]))
    return ''.join(result)

def encrypt_key(folder: str, filename: str) -> str:
    """Encrypt folder/filename using XOR and base64 encoding."""
    raw = f"{folder}/{filename}"
    encrypted = _xor_encrypt(raw, SECRET_KEY)
    return base64.b64encode(encrypted.encode()).decode()

def decrypt_key(token: str) -> str | None:
    """Decrypt token using XOR and base64 decoding."""
    try:
        decoded = base64.b64decode(token.encode()).decode()
        decrypted = _xor_encrypt(decoded, SECRET_KEY)  # XOR is symmetric
        return decrypted
    except Exception:
        return None
