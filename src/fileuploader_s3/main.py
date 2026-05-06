from flask import Flask, Blueprint, request, jsonify, render_template_string, Response, stream_with_context, send_from_directory
import os
import logging
import json
import time
import hashlib
import secrets
import re
from pathlib import Path
from dotenv import load_dotenv
from flask_cors import CORS
from werkzeug.utils import secure_filename
import markdown
import mimetypes
import traceback
from collections import defaultdict, deque
from threading import Lock
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import portalocker
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Cross-platform file content validation
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    print("Warning: python-magic not available. Using basic file validation.")
    print("To install magic on Windows: pip install python-magic-bin")

# Prometheus metrics (always initialize but only use if enabled)
prometheus_metrics = None
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    prometheus_metrics = {
        'upload_requests_total': Counter('fileuploader_uploads_total', 'Total upload requests', ['method', 'status']),
        'upload_duration_seconds': Histogram('fileuploader_upload_duration_seconds', 'Upload duration in seconds'),
        'delete_requests_total': Counter('fileuploader_deletes_total', 'Total delete requests', ['method', 'status']),
        'file_serve_requests_total': Counter('fileuploader_serves_total', 'Total file serve requests', ['status']),
        'file_size_bytes': Histogram('fileuploader_file_size_bytes', 'Uploaded file size in bytes', ['file_type']),
        'active_uploads': Gauge('fileuploader_active_uploads', 'Number of active uploads'),
        'storage_used_bytes': Gauge('fileuploader_storage_used_bytes', 'Storage used in bytes'),
    }
except ImportError:
    print("Warning: Prometheus client not available. Install with: pip install prometheus-client")

# Load environment variables before checking USE_BUCKET_STORAGE
load_dotenv()

# Optional observability support
USE_PROMETHEUS = os.getenv("USE_PROMETHEUS", "false").lower() == "true"
USE_LOKI = os.getenv("USE_LOKI", "false").lower() == "true"

# S3/MinIO support (mandatory for this application)
boto3 = None
Config = None
try:
    import boto3
    from botocore.client import Config
except ImportError as e:
    print(f"❌ ERROR: S3 dependencies not available: {e}")
    print("❌ ERROR: This application requires S3 storage. Please install boto3:")
    print("   pip install boto3")
    exit(1)

app = Flask(__name__)
CORS(app)
file_uploader = Blueprint("file_uploader", __name__)

# ---- Security Headers ----
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'none';"
    return response

# ---- Rate Limiting Configuration ----
def get_rate_limits():
    """Get rate limits based on environment."""
    # Bypass rate limiting in development mode
    if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
        return ["10000 per minute", "100000 per hour"]  # Very high limits for development
    
    if os.getenv('TESTING', 'false').lower() == 'true':
        return ["1000 per minute", "10000 per hour"]  # Much higher limits for testing
    else:
        return ["100 per minute", "1000 per hour"]

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=get_rate_limits()
)

# ---- Encryption Setup ----
def get_encryption_key():
    """Generate or retrieve encryption key using PBKDF2."""
    secret_key = os.getenv("ENCRYPTION_KEY")
    if not secret_key:
        # Generate a random key if none provided
        secret_key = secrets.token_urlsafe(32)
        print(f"Warning: No ENCRYPTION_KEY provided. Generated key: {secret_key}")
    
    # Use PBKDF2 to derive a proper encryption key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'fileuploader_salt',  # In production, use a random salt per deployment
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
    return key

# Initialize encryption
try:
    encryption_key = get_encryption_key()
    cipher_suite = Fernet(encryption_key)
except Exception as e:
    print(f"Warning: Failed to initialize encryption: {e}")
    cipher_suite = None

# ---- Observability Configuration ----
class StructuredLogger:
    """Structured logger for Loki/Promtail compatibility."""
    
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.use_loki = USE_LOKI
        
    def _log_structured(self, level, message, **kwargs):
        """Log with structured data for Loki compatibility."""
        timestamp = time.time()
        log_data = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'service': 'fileuploader-s3',
            **kwargs
        }
        
        # Traditional log format
        if level == 'ERROR':
            self.logger.error(f"{message} | {json.dumps(kwargs)}")
        elif level == 'WARNING':
            self.logger.warning(f"{message} | {json.dumps(kwargs)}")
        elif level == 'INFO':
            self.logger.info(f"{message} | {json.dumps(kwargs)}")
        else:
            self.logger.debug(f"{message} | {json.dumps(kwargs)}")
        
        # If Loki enabled, you could send to Loki endpoint here
        # For now, structured logs are written in JSON format for Promtail to parse
        
    def info(self, message, **kwargs):
        self._log_structured('INFO', message, **kwargs)
        
    def warning(self, message, **kwargs):
        self._log_structured('WARNING', message, **kwargs)
        
    def error(self, message, **kwargs):
        self._log_structured('ERROR', message, **kwargs)
        
    def debug(self, message, **kwargs):
        self._log_structured('DEBUG', message, **kwargs)

def setup_logging():
    """Configure application logging for better debugging."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # JSON format for Loki/Promtail compatibility
    if USE_LOKI:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    else:
        log_format = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Configure root logger
    handlers = []
    
    # Console handler - disable ANSI colors for cleaner logs
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(log_format)
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)
    
    # File handler - use JSON format for Loki if enabled
    if USE_LOKI:
        file_handler = logging.FileHandler('fileuploader.log', encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        handlers.append(file_handler)
    else:
        file_handler = logging.FileHandler('fileuploader.log', encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        handlers=handlers,
        force=True  # Force reconfiguration
    )
    
    # Suppress Werkzeug development server logs unless in debug mode
    if log_level != 'DEBUG':
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    # Create structured logger for the application
    return StructuredLogger(__name__)

app_logger = setup_logging()

# ---- Config ----
BASE_URL = os.getenv("BASE_URL", "http://localhost:2424")
ROUTE_PREFIX = os.getenv("ROUTE_PREFIX", "/api/fileuploader")

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

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB per chunk
MAX_CHUNKS_PER_FILE = 100  # Maximum chunks per file

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

# ---- Security Functions ----
def validate_folder_name(folder: str) -> bool:
    """Validate folder name to prevent path traversal attacks."""
    if not folder or not isinstance(folder, str):
        return False
    if len(folder) > 255:
        return False
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, folder, re.IGNORECASE):
            return False
    if not re.match(r'^[a-zA-Z0-9._-]+$', folder):
        return False
    return True

def validate_filename(filename: str) -> bool:
    """Validate filename to prevent path traversal attacks."""
    if not filename or not isinstance(filename, str):
        return False
    if len(filename) > 255:
        return False
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return False
    invalid_chars = r'[<>:"|?*\x00-\x1f]'
    if re.search(invalid_chars, filename):
        return False
    
    # Check for Windows reserved names
    name_without_ext = Path(filename).stem.upper()
    if name_without_ext in WINDOWS_RESERVED_NAMES:
        return False
    
    # Check for filenames ending with dots or spaces (Windows issue)
    if filename.endswith('.') or filename.endswith(' '):
        return False
    
    return True

def validate_file_content(file_data: bytes, expected_mime: str) -> bool:
    """Validate file content using magic numbers to prevent RCE."""
    try:
        if MAGIC_AVAILABLE:
            # Use python-magic for content validation
            detected_mime = magic.from_buffer(file_data, mime=True)
            
            # Allow exact match or common variations
            allowed_variants = {
                'image/jpeg': ['image/jpeg', 'image/pjpeg'],
                'image/png': ['image/png'],
                'image/gif': ['image/gif'],
                'application/pdf': ['application/pdf'],
                'application/zip': ['application/zip', 'application/x-zip-compressed'],
            }
            
            if expected_mime in allowed_variants:
                return detected_mime in allowed_variants[expected_mime]
            
            # For other types, check exact match
            return detected_mime == expected_mime
        else:
            # Fallback to basic signature check when magic is not available
            if expected_mime in MAGIC_SIGNATURES:
                signature = MAGIC_SIGNATURES[expected_mime]
                return file_data.startswith(signature)
            
            # Additional basic validation for common types
            if expected_mime.startswith('image/'):
                # Basic image validation - check for common image signatures
                image_signatures = [
                    b'\xff\xd8\xff',  # JPEG
                    b'\x89PNG\r\n\x1a\n',  # PNG
                    b'GIF87a',  # GIF87a
                    b'GIF89a',  # GIF89a
                    b'RIFF',  # WEBP/AVI
                    b'\x00\x00\x01\x00',  # ICO
                ]
                return any(file_data.startswith(sig) for sig in image_signatures)
            
            elif expected_mime == 'application/pdf':
                return file_data.startswith(b'%PDF-')
            
            elif expected_mime in ['application/zip', 'application/x-zip-compressed']:
                return file_data.startswith(b'PK\x03\x04') or file_data.startswith(b'PK\x05\x06')
            
            # Allow unknown types if we can't validate
            return True
            
    except Exception:
        # If all validation fails, fall back to basic signature check
        if expected_mime in MAGIC_SIGNATURES:
            signature = MAGIC_SIGNATURES[expected_mime]
            return file_data.startswith(signature)
        return True  # Allow if we can't validate

def get_safe_file_path(base_folder: str, folder: str, filename: str):
    """Create a safe file path preventing path traversal attacks."""
    if not validate_folder_name(folder) or not validate_filename(filename):
        return None
    try:
        base_path = Path(base_folder).resolve()
        folder_path = base_path / folder
        file_path = folder_path / filename
        file_path_resolved = file_path.resolve()
        base_path_resolved = base_path.resolve()
        try:
            file_path_resolved.relative_to(base_path_resolved)
            return file_path_resolved
        except ValueError:
            return None
    except (ValueError, OSError):
        return None

def get_mime_type(filename: str) -> str:
    """Get MIME type for a filename based on extension."""
    ext = Path(filename).suffix.lower()
    return ALLOWED_MIME_TYPES.get(ext, 'application/octet-stream')

def is_allowed_file_type(filename: str) -> bool:
    """Check if file type is allowed based on extension."""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_MIME_TYPES

def generate_public_url(base_url: str, folder: str, filename: str) -> str:
    """Generate a clean, Gmail-compatible public URL for a file."""
    clean_base_url = base_url.rstrip('/')
    return f"{clean_base_url}/uploads/{folder}/{filename}"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    sanitized = filename.replace(' ', '_')
    sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '', sanitized)
    if not sanitized or sanitized == '.' or sanitized == '..':
        sanitized = 'unnamed_file'
    return sanitized

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

# S3/MinIO Configuration
STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT", "http://localhost:9000")
STORAGE_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "admin")
STORAGE_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "admin123")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "fileuploads")

# ---- Storage clients ----
print(f"🔍 Initializing S3 client...")
try:
    # S3/MinIO client for cloud storage (mandatory)
    s3_client = boto3.client(
        "s3",
        endpoint_url=STORAGE_ENDPOINT,
        aws_access_key_id=STORAGE_ACCESS_KEY,
        aws_secret_access_key=STORAGE_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    
    # Ensure S3 bucket exists
    try:
        s3_client.head_bucket(Bucket=STORAGE_BUCKET)
        print(f"✓ S3 bucket '{STORAGE_BUCKET}' is accessible at {STORAGE_ENDPOINT}")
    except:
        s3_client.create_bucket(Bucket=STORAGE_BUCKET)
        print(f"✓ Created S3 bucket '{STORAGE_BUCKET}' at {STORAGE_ENDPOINT}")
        
except Exception as s3_init_error:
    print(f"❌ Failed to initialize S3 client: {s3_init_error}")
    print(f"❌ ERROR: This application requires S3 storage to function")
    print(f"   Please check your S3 configuration:")
    print(f"   - STORAGE_ENDPOINT: {STORAGE_ENDPOINT}")
    print(f"   - STORAGE_ACCESS_KEY: {STORAGE_ACCESS_KEY}")
    print(f"   - STORAGE_BUCKET: {STORAGE_BUCKET}")
    print(f"   Make sure your S3 service is running and accessible")
    exit(1)

# ---- Helper Functions ----
def create_folder_if_not_exists(folder_path: Path) -> bool:
    """Create folder if it doesn't exist."""
    try:
        folder_path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False

def save_file_locally(file, folder: str, filename: str, base_folder: str = None) -> tuple[bool, str]:
    """DEPRECATED: Local storage disabled - use S3 storage only."""
    return False, "Local storage disabled - use S3 storage only"

def save_file_locally_with_content(file_content: bytes, folder: str, filename: str, base_folder: str = None) -> tuple[bool, str]:
    """DEPRECATED: Local storage disabled - use S3 storage only."""
    return False, "Local storage disabled - use S3 storage only"


@app.route("/")
def initial_render():
    with open("docs/documentation.md", "r", encoding="utf-8") as f:
        markdown_content = f.read()
    markdown_content = markdown_content.replace("{base}", BASE_URL)
    html_content = markdown.markdown(markdown_content)
    return render_template_string(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Uploader API</title>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
    )


# ---- Upload Single ----
@file_uploader.route("/upload", methods=["POST"])
@limiter.limit("10 per minute")
def upload_file():
    """Upload a single file and return Gmail-compatible static URL."""
    start_time = time.time()
    
    folder = request.form.get("folder")
    if not folder or not validate_folder_name(folder):
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='400').inc()
        return jsonify({"error": "Invalid or missing folder name"}), 400

    file = request.files.get("file")
    if not file or not hasattr(file, 'filename') or file.filename == "":
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='400').inc()
        return jsonify({"error": "No file provided"}), 400

    # Validate and sanitize filename
    original_filename = file.filename
    if not validate_filename(original_filename):
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='400').inc()
        return jsonify({"error": "Invalid filename"}), 400
        
    if not is_allowed_file_type(original_filename):
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='400').inc()
        return jsonify({"error": f"File type not allowed. Allowed types: {list(ALLOWED_MIME_TYPES.keys())}"}), 400

    filename = sanitize_filename(original_filename)
    file_type = Path(filename).suffix.lower()
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_size > MAX_FILE_SIZE:
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='400').inc()
        return jsonify({"error": f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"}), 400

    try:
        # Track active uploads
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['active_uploads'].inc()
        
        # S3 storage is mandatory - if we reach here, S3 client should be available
        if not s3_client:
            app_logger.error("S3 client not available", 
                          folder=folder, filename=filename, 
                          client_ip=request.remote_addr)
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['upload_requests_total'].labels(method='POST', status='500').inc()
                prometheus_metrics['active_uploads'].dec()
            return jsonify({"error": "S3 client not available - check configuration"}), 500
        
        # Read file content before any processing to avoid file handle issues
        file.seek(0)
        file_content = file.read()
        
        # Upload to S3 storage
        app_logger.info(f"Uploading to S3 storage - Bucket: {STORAGE_BUCKET}, Endpoint: {STORAGE_ENDPOINT}")
        try:
            # Use file content for S3 upload
            from io import BytesIO
            file_obj = BytesIO(file_content)
            s3_client.upload_fileobj(file_obj, STORAGE_BUCKET, f"{folder}/{filename}")
            app_logger.info("File successfully uploaded to S3", 
                         folder=folder, filename=filename, 
                         file_size=file_size, backend='s3')
        except Exception as s3_error:
            app_logger.error("S3 upload failed", 
                          folder=folder, filename=filename, 
                          error=str(s3_error), backend='s3',
                          client_ip=request.remote_addr)
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['upload_requests_total'].labels(method='POST', status='500').inc()
                prometheus_metrics['active_uploads'].dec()
            return jsonify({"error": f"Upload failed: {str(s3_error)}"}), 500
        
        # Generate Gmail-compatible static URL
        public_url = generate_public_url(BASE_URL, folder, filename)
        duration = time.time() - start_time
        
        # Log success with structured data
        app_logger.info("File uploaded successfully", 
                      folder=folder, filename=filename, 
                      file_size=file_size, duration=duration,
                      url=public_url, backend='s3',
                      client_ip=request.remote_addr)
        
        # Update Prometheus metrics
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='200').inc()
            prometheus_metrics['upload_duration_seconds'].observe(duration)
            prometheus_metrics['file_size_bytes'].labels(file_type=file_type).observe(file_size)
            prometheus_metrics['active_uploads'].dec()
            prometheus_metrics['storage_used_bytes'].inc(file_size)
        
        return jsonify({
            "message": f"File successfully uploaded to /uploads/{folder}/{filename}",
            "url": public_url,
            "filename": filename,
            "folder": folder,
            "size": file_size,
            "mime_type": get_mime_type(filename)
        }), 200
        
    except Exception as e:
        app_logger.error("Upload failed", 
                      folder=folder, filename=filename,
                      error=str(e), traceback=traceback.format_exc(),
                      client_ip=request.remote_addr)
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='500').inc()
            prometheus_metrics['active_uploads'].dec()
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


# ---- Upload Multiple ----
@file_uploader.route("/upload_multi", methods=["POST"])
@limiter.limit("20 per minute")
def upload_multiple_files():
    """Upload multiple files and return Gmail-compatible static URLs."""
    folder = request.form.get("folder")
    if not folder or not validate_folder_name(folder):
        return jsonify({"error": "Invalid or missing folder name"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    uploaded = []
    errors = []
    
    for file in files:
        if not file or file.filename == "":
            continue
            
        original_filename = file.filename
        if not validate_filename(original_filename):
            errors.append(f"Invalid filename: {original_filename}")
            continue
            
        if not is_allowed_file_type(original_filename):
            errors.append(f"File type not allowed: {original_filename}")
            continue
            
        filename = sanitize_filename(original_filename)
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            errors.append(f"File too large: {original_filename}")
            continue
        
        try:
            # Save to local storage
            success, result = save_file_locally(file, folder, filename)
            if not success:
                errors.append(f"Failed to save {original_filename}: {result}")
                continue
            
            # Also save to S3 (if enabled)
            if USE_BUCKET_STORAGE and s3_client:
                try:
                    file.seek(0)
                    s3_client.upload_fileobj(file, STORAGE_BUCKET, f"{folder}/{filename}")
                except Exception as s3_error:
                    # If S3 upload fails, still consider it a success if local upload worked
                    # but add to errors for debugging
                    errors.append(f"S3 upload failed for {original_filename}: {str(s3_error)}")
            
            # Generate public URL
            public_url = generate_public_url(BASE_URL, folder, filename)
            
            uploaded.append({
                "filename": filename,
                "original_filename": original_filename,
                "url": public_url,
                "size": file_size,
                "mime_type": get_mime_type(filename)
            })
            
        except Exception as e:
            errors.append(f"Failed to upload {original_filename}: {str(e)}")

    response_data = {
        "message": f"{len(uploaded)} files uploaded successfully.",
        "uploaded": uploaded,
        "total_uploaded": len(uploaded)
    }
    
    if errors:
        response_data["errors"] = errors
        response_data["total_errors"] = len(errors)
    
    return jsonify(response_data), 200


# ---- Upload Single File in Chunks ----
@file_uploader.route("/upload_chunk", methods=["POST"])
@limiter.limit("20 per minute")
def upload_chunk():
    """Upload a file in chunks and return Gmail-compatible static URL."""
    folder = request.form.get("folder")
    if not folder or not validate_folder_name(folder):
        return jsonify({"error": "Invalid or missing folder name"}), 400

    file = request.files.get("file")
    if not file or not hasattr(file, 'filename') or file.filename == "":
        return jsonify({"error": "No file provided"}), 400

    # Validate chunk parameters
    try:
        chunk_index = int(request.form.get("dzchunkindex", 0))
        total_chunks = int(request.form.get("dztotalchunkcount", 1))
    except ValueError:
        return jsonify({"error": "Invalid chunk parameters"}), 400
    
    # Validate chunk limits
    if chunk_index < 0 or total_chunks <= 0 or total_chunks > MAX_CHUNKS_PER_FILE:
        return jsonify({"error": "Invalid chunk count or index"}), 400
    
    # Validate and sanitize filename
    original_filename = file.filename
    if not validate_filename(original_filename):
        return jsonify({"error": "Invalid filename"}), 400
        
    if not is_allowed_file_type(original_filename):
        return jsonify({"error": f"File type not allowed. Allowed types: {list(ALLOWED_MIME_TYPES.keys())}"}), 400

    filename = sanitize_filename(original_filename)
    
    try:
        # For S3-only storage, we need to handle chunk uploads differently
        # Store chunks in memory or temporary S3 location, then combine for final upload
        
        # Validate chunk size
        file.seek(0, os.SEEK_END)
        chunk_size = file.tell()
        file.seek(0)
        
        if chunk_size > MAX_CHUNK_SIZE:
            return jsonify({"error": f"Chunk too large. Maximum size: {MAX_CHUNK_SIZE // (1024*1024)}MB"}), 400
        
        # Read chunk content for validation
        file_content = file.read()
        
        # Validate chunk content (only first chunk)
        expected_mime = get_mime_type(filename)
        if chunk_index == 0 and not validate_file_content(file_content, expected_mime):
            return jsonify({"error": f"File content does not match expected type: {expected_mime}"}), 400
        
        # For S3-only storage, we'll handle chunk uploads by storing in a temporary S3 location
        # This is a simplified version - in production, you might want a more sophisticated approach
        temp_key = f"temp/{folder}/{filename}.part{chunk_index}"
        
        try:
            s3_client.put_object(
                Bucket=STORAGE_BUCKET,
                Key=temp_key,
                Body=file_content
            )
        except Exception as s3_error:
            return jsonify({"error": f"Failed to store chunk: {str(s3_error)}"}), 500
        
        # Check if this is the last chunk
        if chunk_index == total_chunks - 1:
            # Combine all chunks from S3 temp location
            all_chunks_content = b''
            for i in range(total_chunks):
                chunk_key = f"temp/{folder}/{filename}.part{i}"
                try:
                    chunk_obj = s3_client.get_object(Bucket=STORAGE_BUCKET, Key=chunk_key)
                    all_chunks_content += chunk_obj['Body'].read()
                    # Delete temporary chunk
                    s3_client.delete_object(Bucket=STORAGE_BUCKET, Key=chunk_key)
                except s3_client.exceptions.NoSuchKey:
                    return jsonify({"error": f"Missing chunk {i}"}), 400
            
            # Upload combined file to final location
            final_key = f"{folder}/{filename}"
            s3_client.put_object(
                Bucket=STORAGE_BUCKET,
                Key=final_key,
                Body=all_chunks_content
            )
            
            # Generate Gmail-compatible static URL
            public_url = generate_public_url(BASE_URL, folder, filename)
            file_size = len(all_chunks_content)
            
            return jsonify({
                "message": f"File successfully uploaded to /uploads/{folder}/{filename}",
                "url": public_url,
                "filename": filename,
                "folder": folder,
                "size": file_size,
                "mime_type": get_mime_type(filename)
            }), 200
        else:
            return jsonify({"message": f"Chunk {chunk_index + 1} uploaded successfully."}), 200
            
    except Exception as e:
        app_logger.error(f"Chunk upload failed for {folder}/{filename}: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Chunk upload failed: {str(e)}"}), 500


# ---- Upload Multiple Files in Chunks ----
@file_uploader.route("/upload_multi_chunk", methods=["POST"])
@limiter.limit("30 per minute")
def upload_multiple_chunks():
    """Upload multiple files in chunks and return Gmail-compatible static URLs."""
    folder = request.form.get("folder")
    if not folder or not validate_folder_name(folder):
        return jsonify({"error": "Invalid or missing folder name"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided"}), 400

    chunk_index = int(request.form.get("dzchunkindex", 0))
    total_chunks = int(request.form.get("dztotalchunkcount", 1))
    
    uploaded_files = []
    errors = []
    
    for file in files:
        if not file or file.filename == "":
            continue
            
        original_filename = file.filename
        if not validate_filename(original_filename):
            errors.append(f"Invalid filename: {original_filename}")
            continue
            
        if not is_allowed_file_type(original_filename):
            errors.append(f"File type not allowed: {original_filename}")
            continue

        filename = sanitize_filename(original_filename)
        
        try:
            # For S3-only storage, handle chunk uploads similar to single chunk upload
            # Validate chunk size
            file.seek(0, os.SEEK_END)
            chunk_size = file.tell()
            file.seek(0)
            
            if chunk_size > MAX_CHUNK_SIZE:
                errors.append(f"Chunk too large: {original_filename}")
                continue
            
            # Read chunk content for validation
            file_content = file.read()
            
            # Validate chunk content (only first chunk)
            expected_mime = get_mime_type(filename)
            if chunk_index == 0 and not validate_file_content(file_content, expected_mime):
                errors.append(f"Invalid file content: {original_filename}")
                continue
            
            # Store chunk in S3 temp location
            temp_key = f"temp/{folder}/{filename}.part{chunk_index}"
            
            try:
                s3_client.put_object(
                    Bucket=STORAGE_BUCKET,
                    Key=temp_key,
                    Body=file_content
                )
            except Exception as s3_error:
                errors.append(f"Failed to store chunk {original_filename}: {str(s3_error)}")
                continue
            
            # Check if this is the last chunk for this file
            if chunk_index == total_chunks - 1:
                # Combine all chunks from S3 temp location
                all_chunks_content = b''
                for i in range(total_chunks):
                    chunk_key = f"temp/{folder}/{filename}.part{i}"
                    try:
                        chunk_obj = s3_client.get_object(Bucket=STORAGE_BUCKET, Key=chunk_key)
                        all_chunks_content += chunk_obj['Body'].read()
                        # Delete temporary chunk
                        s3_client.delete_object(Bucket=STORAGE_BUCKET, Key=chunk_key)
                    except s3_client.exceptions.NoSuchKey:
                        errors.append(f"Missing chunk {i} for {original_filename}")
                        continue
                
                # Upload combined file to final location
                final_key = f"{folder}/{filename}"
                s3_client.put_object(
                    Bucket=STORAGE_BUCKET,
                    Key=final_key,
                    Body=all_chunks_content
                )
                
                # Generate Gmail-compatible static URL
                public_url = generate_public_url(BASE_URL, folder, filename)
                file_size = len(all_chunks_content)
                
                uploaded_files.append({
                    "filename": filename,
                    "original_filename": original_filename,
                    "url": public_url,
                    "size": file_size,
                    "mime_type": get_mime_type(filename)
                })
            
        except Exception as e:
            errors.append(f"Failed to process {original_filename}: {str(e)}")
    
    if uploaded_files:
        response_data = {
            "message": f"{len(uploaded_files)} file(s) uploaded successfully.",
            "files": uploaded_files,
            "total_uploaded": len(uploaded_files)
        }
    else:
        response_data = {"message": f"Chunk {chunk_index + 1} uploaded successfully."}
    
    if errors:
        response_data["errors"] = errors
@app.route("/uploads/<path:filepath>", methods=["GET"])
@limiter.limit("100 per minute")
def serve_static_file(filepath):
    """Serve files directly from S3 storage with proper MIME types.
    
    This endpoint provides Gmail-compatible static URLs like:
    /uploads/folder/filename.ext
    """
    start_time = time.time()
    
    try:
        # S3 storage is mandatory - if we reach here, S3 client should be available
        if not s3_client:
            app_logger.error("S3 client not available for file serving", 
                          filepath=filepath, 
                          s3_client_available=s3_client is not None,
                          client_ip=request.remote_addr)
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='500').inc()
            return jsonify({"error": "S3 client not available - check configuration"}), 500
        
        # Validate filepath structure and prevent path traversal
        if not filepath or '..' in filepath or '\\' in filepath:
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='400').inc()
            return jsonify({"error": "Invalid file path"}), 400
        
        # Split filepath into components and validate each
        path_parts = filepath.split('/')
        if len(path_parts) < 2:
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='400').inc()
            return jsonify({"error": "Invalid file path format"}), 400
        
        folder = '/'.join(path_parts[:-1])  # Support nested folders
        filename = path_parts[-1]
        
        # Validate folder and filename separately
        if not validate_folder_name(folder) or not validate_filename(filename):
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='400').inc()
            return jsonify({"error": "Invalid folder or filename"}), 400
        
        # S3 object key
        s3_key = f"{folder}/{filename}"
        
        try:
            # Get object metadata from S3
            s3_object = s3_client.head_object(Bucket=STORAGE_BUCKET, Key=s3_key)
            file_size = s3_object['ContentLength']
            mime_type = get_mime_type(filename)
            
            # Generate presigned URL for direct S3 access
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': STORAGE_BUCKET, 'Key': s3_key},
                ExpiresIn=3600  # 1 hour
            )
            
            # For small files, serve directly from S3
            if file_size <= 10 * 1024 * 1024:  # 10MB threshold
                s3_response = s3_client.get_object(Bucket=STORAGE_BUCKET, Key=s3_key)
                content = s3_response['Body'].read()
                
                response = Response(
                    content,
                    200,
                    mimetype=mime_type,
                    direct_passthrough=True
                )
                
                # Add Gmail-friendly headers
                response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
                response.headers['Accept-Ranges'] = 'bytes'
                response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 year cache
                response.headers['Content-Length'] = str(len(content))
                
                # Log successful file serving
                duration = time.time() - start_time
                app_logger.info("File served successfully from S3", 
                              folder=folder, filename=filename,
                              file_size=file_size, duration=duration,
                              backend='s3', client_ip=request.remote_addr)
                
                if USE_PROMETHEUS and prometheus_metrics:
                    prometheus_metrics['file_serve_requests_total'].labels(status='200').inc()
                
                return response
            else:
                # For large files, redirect to presigned URL
                response = Response(
                    redirect(presigned_url, code=302),
                    302
                )
                
                # Log redirect
                duration = time.time() - start_time
                app_logger.info("File redirect to S3 presigned URL", 
                              folder=folder, filename=filename,
                              file_size=file_size, duration=duration,
                              backend='s3', client_ip=request.remote_addr)
                
                if USE_PROMETHEUS and prometheus_metrics:
                    prometheus_metrics['file_serve_requests_total'].labels(status='302').inc()
                
                return response
                
        except s3_client.exceptions.NoSuchKey:
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='404').inc()
            return jsonify({"error": "File not found"}), 404
        except Exception as s3_error:
            app_logger.error("S3 file serving failed", 
                          folder=folder, filename=filename,
                          error=str(s3_error), backend='s3',
                          client_ip=request.remote_addr)
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='500').inc()
            return jsonify({"error": f"Failed to serve file: {str(s3_error)}"}), 500
        
    except Exception as e:
        app_logger.error("File serving failed", 
                      filepath=filepath, error=str(e), 
                      traceback=traceback.format_exc(),
                      client_ip=request.remote_addr)
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['file_serve_requests_total'].labels(status='500').inc()
        return jsonify({"error": "Internal server error"}), 500

@file_uploader.route("/render/<token>", methods=["GET"])
@limiter.limit("20 per minute")
def render_file(token):
    """Returns redirect to new static URL.
    """
    key = decrypt_key(token)
    if not key:
        return jsonify({"error": "Invalid token"}), 400

    try:
        # Extract folder and filename from key
        path_parts = key.split('/', 1)
        if len(path_parts) != 2:
            return jsonify({"error": "Invalid file key"}), 400
            
        folder, filename = path_parts
        
        # Generate new static URL
        static_url = generate_public_url(BASE_URL, folder, filename)
        
        # Redirect to new static URL
        from flask import redirect
        return redirect(static_url, code=301)
        
    except Exception as e:
        app_logger.error(f"Error processing legacy render token {token}: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500

@file_uploader.route("/delete/<token>", methods=["DELETE"])
@limiter.limit("50 per minute")
def delete_file(token):
    """Delete a file from S3 storage."""
    start_time = time.time()
    
    # S3 storage is mandatory - if we reach here, S3 client should be available
    if not s3_client:
        app_logger.error("S3 client not available for file deletion", 
                        s3_client_available=s3_client is not None,
                        client_ip=request.remote_addr)
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='500').inc()
        return jsonify({"error": "S3 client not available - check configuration"}), 500
    
    key = decrypt_key(token)
    if not key:
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='400').inc()
        return jsonify({"error": "Invalid token"}), 400

    try:
        # Extract folder and filename
        path_parts = key.split('/', 1)
        if len(path_parts) != 2:
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='400').inc()
            return jsonify({"error": "Invalid file key"}), 400
            
        folder, filename = path_parts
        
        # Validate folder and filename for security
        if not validate_folder_name(folder) or not validate_filename(filename):
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='400').inc()
            return jsonify({"error": "Invalid folder or filename"}), 400
        
        # Check for nested folders (not supported)
        if '/' in filename or '\\' in filename:
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='400').inc()
            return jsonify({"error": "Nested folders not supported"}), 400
        
        # Get file size from S3 before deletion
        file_size = 0
        try:
            s3_object = s3_client.head_object(Bucket=STORAGE_BUCKET, Key=key)
            file_size = s3_object['ContentLength']
        except s3_client.exceptions.NoSuchKey:
            if USE_PROMETHEUS and prometheus_metrics:
                prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='404').inc()
            return jsonify({"error": "File not found"}), 404
        
        # Delete from S3
        s3_client.delete_object(Bucket=STORAGE_BUCKET, Key=key)
        app_logger.info("File deleted from S3", 
                     folder=folder, filename=filename, 
                     backend='s3', client_ip=request.remote_addr)
        
        duration = time.time() - start_time
        
        # Log successful deletion
        app_logger.info("File deleted successfully", 
                      folder=folder, filename=filename,
                      file_size=file_size, duration=duration,
                      backend='s3', client_ip=request.remote_addr)
        
        # Update Prometheus metrics
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='200').inc()
            prometheus_metrics['storage_used_bytes'].dec(file_size)
        
        return jsonify({
            "message": f"File {filename} deleted successfully",
            "filename": filename,
            "folder": folder
        }), 200
        
    except Exception as e:
        app_logger.error("Delete failed", 
                      folder=folder if 'folder' in locals() else 'unknown',
                      filename=filename if 'filename' in locals() else 'unknown',
                      error=str(e), traceback=traceback.format_exc(),
                      client_ip=request.remote_addr)
        if USE_PROMETHEUS and prometheus_metrics:
            prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='500').inc()
        return jsonify({"error": f"Delete failed: {str(e)}"}), 500


# ---- Prometheus Metrics Endpoint ----
@app.route("/metrics")
def metrics():
    """Prometheus metrics endpoint - only available when enabled."""
    if not USE_PROMETHEUS:
        return jsonify({"error": "Prometheus metrics disabled"}), 404
    
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
    except ImportError:
        return jsonify({"error": "Prometheus client not installed"}), 503
    except Exception as e:
        return jsonify({"error": f"Metrics generation failed: {str(e)}"}), 500

# ---- Health Check Endpoint ----
@app.route("/health")
def health_check():
    """Health check endpoint with observability status."""
    # Check environment variables dynamically to allow runtime changes
    # Force re-reading of environment variables
    current_use_prometheus = os.getenv("USE_PROMETHEUS", "false").lower() == "true"
    current_use_loki = os.getenv("USE_LOKI", "false").lower() == "true"
    current_s3_enabled = True  # S3 is now mandatory
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "observability": {
            "prometheus_enabled": current_use_prometheus,
            "loki_enabled": current_use_loki,
            "s3_enabled": current_s3_enabled
        }
    }
    return jsonify(health_status)

# Register blueprint
app.register_blueprint(file_uploader, url_prefix=ROUTE_PREFIX)


def main():
    # Only run in debug mode if explicitly requested
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=2424, debug=debug_mode)


if __name__ == "__main__":
    main()
