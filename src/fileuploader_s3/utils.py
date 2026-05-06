"""Utility functions for fileuploader-s3 application."""

import hashlib
import secrets
import base64
from pathlib import Path
from .config import ENCRYPTION_KEY


def create_folder_if_not_exists(folder_path: Path) -> bool:
    """Create folder if it doesn't exist."""
    try:
        folder_path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def generate_public_url(base_url: str, folder: str, filename: str) -> str:
    """Generate a clean, Gmail-compatible public URL for a file."""
    clean_base_url = base_url.rstrip('/')
    return f"{clean_base_url}/uploads/{folder}/{filename}"


# Initialize cipher suite for encryption
cipher_suite = None
if ENCRYPTION_KEY and ENCRYPTION_KEY != "your-secret-encryption-key-here":
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        # Derive key from password
        password = ENCRYPTION_KEY.encode()
        salt = b'salt_'  # In production, use a proper random salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password)
        cipher_suite = Fernet(base64.urlsafe_b64encode(key))
    except Exception:
        pass


def encrypt_key(folder: str, filename: str) -> str:
    """Encrypt file key using AES encryption."""
    if not cipher_suite:
        # Fallback to base64 encoding if encryption fails
        raw = f"{folder}/{filename}"
        return base64.urlsafe_b64encode(raw.encode()).decode()
    
    try:
        raw = f"{folder}/{filename}"
        encrypted = cipher_suite.encrypt(raw.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception:
        # Fallback to base64 encoding
        raw = f"{folder}/{filename}"
        return base64.urlsafe_b64encode(raw.encode()).decode()


def decrypt_key(token: str):
    """Decrypt token using AES encryption."""
    if not cipher_suite:
        # Fallback to base64 decoding if encryption fails
        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            return decoded
        except Exception:
            return None
    
    try:
        decoded = base64.urlsafe_b64decode(token.encode())
        decrypted = cipher_suite.decrypt(decoded).decode()
        return decrypted
    except Exception:
        # Try fallback to base64 decoding
        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            return decoded
        except Exception:
            return None


def save_file_locally(file, folder: str, filename: str, base_folder: str = None) -> tuple[bool, str]:
    """DEPRECATED: Local storage disabled - use S3 storage only."""
    return False, "Local storage disabled - use S3 storage only"


def save_file_locally_with_content(file_content: bytes, folder: str, filename: str, base_folder: str = None) -> tuple[bool, str]:
    """DEPRECATED: Local storage disabled - use S3 storage only."""
    return False, "Local storage disabled - use S3 storage only"
