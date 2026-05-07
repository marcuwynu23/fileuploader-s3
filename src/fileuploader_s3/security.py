"""Security and validation module for fileuploader-s3 application."""

import re
from pathlib import Path
from .config import ALLOWED_MIME_TYPES, MAGIC_SIGNATURES, BLOCKED_PATTERNS, WINDOWS_RESERVED_NAMES

# Cross-platform file content validation
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False


def validate_folder_name(folder: str) -> bool:
    """Validate folder name to prevent path traversal attacks while allowing nested paths."""
    if not folder or not isinstance(folder, str):
        return False
    if len(folder) > 255:
        return False
    
    # Check for blocked patterns first
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, folder, re.IGNORECASE):
            return False
    
    # Split folder path and validate each component
    folder_components = folder.split('/')
    
    # Validate each folder component in the path
    for component in folder_components:
        # Skip empty components (allow trailing slashes)
        if not component:
            continue
        
        # Reject path traversal components explicitly
        if component == '..' or component == '.':
            return False
        
        # Each component must be valid
        if not re.match(r'^[a-zA-Z0-9._-]+$', component):
            return False
        
        # Check for Windows reserved names in each component
        if component.upper() in WINDOWS_RESERVED_NAMES:
            return False
    
    # Ensure we have at least one valid component
    return len([c for c in folder_components if c]) > 0


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


def get_mime_type(filename: str) -> str:
    """Get MIME type for a filename based on extension."""
    ext = Path(filename).suffix.lower()
    return ALLOWED_MIME_TYPES.get(ext, 'application/octet-stream')


def is_allowed_file_type(filename: str) -> bool:
    """Check if file type is allowed based on extension."""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_MIME_TYPES


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    sanitized = filename.replace(' ', '_')
    sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '', sanitized)
    if not sanitized or sanitized == '.' or sanitized == '..':
        sanitized = 'unnamed_file'
    return sanitized


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
