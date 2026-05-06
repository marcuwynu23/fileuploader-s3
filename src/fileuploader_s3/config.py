"""Configuration module for fileuploader-s3 application."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---- App Configuration ----
BASE_URL = os.getenv("BASE_URL", "http://localhost:2424")
ROUTE_PREFIX = os.getenv("ROUTE_PREFIX", "/api/fileuploader")

# ---- S3/MinIO Configuration (MANDATORY) ----
STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT", "http://localhost:9000")
STORAGE_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "admin")
STORAGE_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "admin123")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "fileuploads")

# ---- Security Configuration ----
ALLOWED_MIME_TYPES = {
    # Images
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    # Documents
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    # Videos
    '.mp4': 'video/mp4',
    '.avi': 'video/x-msvideo',
    '.mov': 'video/quicktime',
    # Archives
    '.zip': 'application/zip',
    '.tar': 'application/x-tar',
    '.gz': 'application/gzip',
}

# Magic number signatures for content validation
MAGIC_SIGNATURES = {
    'image/png': b'\x89PNG\r\n\x1a\n',
    'image/jpeg': b'\xff\xd8\xff',
    'image/gif': b'GIF87a',
    'image/gif': b'GIF89a',
    'application/pdf': b'%PDF-',
    'application/zip': b'PK\x03\x04',
}

# ---- File Size Limits ----
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB per chunk
MAX_CHUNKS_PER_FILE = 100  # Maximum chunks per file

# ---- Security Patterns ----
BLOCKED_PATTERNS = [
    r'\.\./',  # Parent directory traversal
    r'\.\.\\',  # Windows parent directory traversal
    r'^\.\./',  # Starting with parent directory
    r'^\.\.\\',  # Starting with Windows parent directory
    r'^/',  # Absolute paths
    r'^\\',  # Windows absolute paths
]

# Windows reserved names
WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
}

# ---- Observability Configuration ----
USE_PROMETHEUS = os.getenv("USE_PROMETHEUS", "false").lower() == "true"
USE_LOKI = os.getenv("USE_LOKI", "false").lower() == "true"

# ---- Logging Configuration ----
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# ---- Development Configuration ----
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
TESTING = os.getenv("TESTING", "false").lower() == "true"

# ---- Security Configuration ----
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "your-secret-encryption-key-here")
