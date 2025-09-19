import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("ENCRYPTION_KEY")
if not SECRET_KEY:
    raise RuntimeError("ENCRYPTION_KEY not set in environment!")

fernet = Fernet(SECRET_KEY.encode())

def encrypt_key(folder: str, filename: str) -> str:
    raw = f"{folder}/{filename}"
    return fernet.encrypt(raw.encode()).decode()

def decrypt_key(token: str) -> str | None:
    try:
        return fernet.decrypt(token.encode()).decode()
    except Exception:
        return None
