"""
Security and utility helpers for the file uploader application.
Provides path validation, MIME type mapping, and secure file operations.
"""

import os
import mimetypes
from pathlib import Path
from typing import Optional, Tuple
import re


class SecurityConfig:
    """Security configuration constants."""
    
    # Allowed file extensions and their MIME types
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
    
    # Maximum file size (50MB default)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    # Blocked patterns for path traversal prevention
    BLOCKED_PATTERNS = [
        r'\.\./',  # Parent directory traversal
        r'\.\.\\',  # Windows parent directory traversal
        r'^\.\./',  # Starting with parent directory
        r'^\.\.\\',  # Starting with Windows parent directory
        r'^/',  # Absolute paths
        r'^\\',  # Windows absolute paths
    ]


def validate_folder_name(folder: str) -> bool:
    """
    Validate folder name to prevent path traversal attacks.
    
    Args:
        folder: Folder name to validate
        
    Returns:
        True if safe, False otherwise
    """
    if not folder or not isinstance(folder, str):
        return False
    
    # Check for blocked patterns
    for pattern in SecurityConfig.BLOCKED_PATTERNS:
        if re.search(pattern, folder, re.IGNORECASE):
            return False
    
    # Check for valid characters (alphanumeric, hyphens, underscores)
    if not re.match(r'^[a-zA-Z0-9._-]+$', folder):
        return False
    
    return True


def validate_filename(filename: str) -> bool:
    """
    Validate filename to prevent path traversal attacks.
    
    Args:
        filename: Filename to validate
        
    Returns:
        True if safe, False otherwise
    """
    if not filename or not isinstance(filename, str):
        return False
    
    # Check for blocked patterns
    for pattern in SecurityConfig.BLOCKED_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return False
    
    # Check for valid filename characters
    invalid_chars = r'[<>:"|?*\x00-\x1f]'
    if re.search(invalid_chars, filename):
        return False
    
    return True


def get_safe_file_path(base_folder: str, folder: str, filename: str) -> Optional[Path]:
    """
    Create a safe file path preventing path traversal attacks.
    
    Args:
        base_folder: Base storage folder
        folder: Subfolder name
        filename: Filename
        
    Returns:
        Safe Path object or None if validation fails
    """
    if not validate_folder_name(folder) or not validate_filename(filename):
        return None
    
    try:
        base_path = Path(base_folder).resolve()
        folder_path = base_path / folder
        file_path = folder_path / filename
        
        # Ensure the final path is within the base directory
        if not str(file_path.resolve()).startswith(str(base_path)):
            return None
            
        return file_path
    except (ValueError, OSError):
        return None


def get_mime_type(filename: str) -> str:
    """
    Get MIME type for a filename based on extension.
    
    Args:
        filename: Filename to get MIME type for
        
    Returns:
        MIME type string
    """
    ext = Path(filename).suffix.lower()
    return SecurityConfig.ALLOWED_MIME_TYPES.get(ext, 'application/octet-stream')


def is_allowed_file_type(filename: str) -> bool:
    """
    Check if file type is allowed based on extension.
    
    Args:
        filename: Filename to check
        
    Returns:
        True if allowed, False otherwise
    """
    ext = Path(filename).suffix.lower()
    return ext in SecurityConfig.ALLOWED_MIME_TYPES


def generate_public_url(base_url: str, folder: str, filename: str) -> str:
    """
    Generate a clean, Gmail-compatible public URL for a file.
    
    Args:
        base_url: Base URL of the application
        folder: Folder name
        filename: Filename
        
    Returns:
        Clean URL string like https://domain.com/uploads/folder/filename
    """
    # Ensure base_url doesn't end with slash
    clean_base_url = base_url.rstrip('/')
    return f"{clean_base_url}/uploads/{folder}/{filename}"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Replace spaces with underscores
    sanitized = filename.replace(' ', '_')
    
    # Remove any remaining unsafe characters
    sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '', sanitized)
    
    # Ensure filename is not empty
    if not sanitized or sanitized == '.' or sanitized == '..':
        sanitized = 'unnamed_file'
    
    return sanitized
