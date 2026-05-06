"""
Test cases for security helper functions.
"""

import pytest
from pathlib import Path
from src.fileuploader_s3.main import (
    ALLOWED_MIME_TYPES, MAX_FILE_SIZE, BLOCKED_PATTERNS,
    validate_folder_name, validate_filename,
    get_safe_file_path, get_mime_type, is_allowed_file_type,
    generate_public_url, sanitize_filename
)


class TestSecurityConfig:
    """Test SecurityConfig constants."""
    
    def test_allowed_mime_types_not_empty(self):
        """Test that allowed MIME types are defined."""
        assert ALLOWED_MIME_TYPES
        assert len(ALLOWED_MIME_TYPES) > 0
    
    def test_max_file_size_positive(self):
        """Test that max file size is positive."""
        assert MAX_FILE_SIZE > 0
    
    def test_blocked_patterns_defined(self):
        """Test that blocked patterns are defined."""
        assert BLOCKED_PATTERNS
        assert len(BLOCKED_PATTERNS) > 0


class TestValidateFolderName:
    """Test folder name validation."""
    
    def test_valid_folder_names(self, valid_folder_names):
        """Test that valid folder names are accepted."""
        for folder in valid_folder_names:
            assert validate_folder_name(folder), f"Folder '{folder}' should be valid"
    
    def test_invalid_folder_names(self, invalid_folder_names):
        """Test that invalid folder names are rejected."""
        for folder in invalid_folder_names:
            assert not validate_folder_name(folder), f"Folder '{folder}' should be invalid"
    
    def test_edge_cases(self):
        """Test edge cases for folder validation."""
        assert not validate_folder_name("")
        assert not validate_folder_name(None)
        assert not validate_folder_name(123)  # non-string
        assert not validate_folder_name("a" * 1000)  # very long


class TestValidateFilename:
    """Test filename validation."""
    
    def test_valid_filenames(self, valid_filenames):
        """Test that valid filenames are accepted."""
        for filename in valid_filenames:
            assert validate_filename(filename), f"Filename '{filename}' should be valid"
    
    def test_invalid_filenames(self, invalid_filenames):
        """Test that invalid filenames are rejected."""
        for filename in invalid_filenames:
            assert not validate_filename(filename), f"Filename '{filename}' should be invalid"
    
    def test_edge_cases(self):
        """Test edge cases for filename validation."""
        assert not validate_filename("")
        assert not validate_filename(None)
        assert not validate_filename(123)  # non-string
        assert not validate_filename("a" * 1000)  # very long


class TestGetSafeFilePath:
    """Test safe file path generation."""
    
    def test_safe_path_generation(self, temp_upload_dir):
        """Test that safe paths are generated correctly."""
        base_folder = temp_upload_dir
        folder = "test"
        filename = "image.png"
        
        safe_path = get_safe_file_path(base_folder, folder, filename)
        
        assert safe_path is not None
        assert safe_path.name == filename
        assert safe_path.parent.name == folder
        # Use resolved path comparison for Windows compatibility
        base_resolved = Path(base_folder).resolve()
        safe_resolved = safe_path.resolve()
        assert str(safe_resolved).startswith(str(base_resolved))
    
    def test_path_traversal_prevention(self, temp_upload_dir):
        """Test that path traversal attacks are prevented."""
        base_folder = temp_upload_dir
        
        # Test various path traversal attempts
        malicious_paths = [
            ("../test", "image.png"),
            ("test", "../../../image.png"),
            ("test", "..\\..\\image.png"),
            ("/etc/passwd", "image.png"),
            ("C:\\Windows\\System32", "image.png"),
        ]
        
        for folder, filename in malicious_paths:
            safe_path = get_safe_file_path(base_folder, folder, filename)
            assert safe_path is None, f"Path traversal should be blocked: {folder}/{filename}"
    
    def test_invalid_inputs(self, temp_upload_dir):
        """Test handling of invalid inputs."""
        base_folder = temp_upload_dir
        
        # Invalid folder
        assert get_safe_file_path(base_folder, "../test", "image.png") is None
        
        # Invalid filename
        assert get_safe_file_path(base_folder, "test", "../image.png") is None
        
        # None inputs
        assert get_safe_file_path(base_folder, None, "image.png") is None
        assert get_safe_file_path(base_folder, "test", None) is None


class TestGetMimeType:
    """Test MIME type detection."""
    
    def test_known_mime_types(self):
        """Test MIME type detection for known file types."""
        test_cases = {
            'image.png': 'image/png',
            'image.jpg': 'image/jpeg',
            'image.jpeg': 'image/jpeg',
            'image.webp': 'image/webp',
            'image.gif': 'image/gif',
            'document.pdf': 'application/pdf',
            'document.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'video.mp4': 'video/mp4',
            'archive.zip': 'application/zip',
        }
        
        for filename, expected_mime in test_cases.items():
            assert get_mime_type(filename) == expected_mime
    
    def test_unknown_file_type(self):
        """Test MIME type for unknown file types."""
        assert get_mime_type('unknown.xyz') == 'application/octet-stream'
        assert get_mime_type('no_extension') == 'application/octet-stream'
    
    def test_case_insensitive_extensions(self):
        """Test that MIME type detection is case insensitive."""
        assert get_mime_type('IMAGE.PNG') == 'image/png'
        assert get_mime_type('Document.PDF') == 'application/pdf'
        assert get_mime_type('Video.MP4') == 'video/mp4'


class TestIsAllowedFileType:
    """Test file type validation."""
    
    def test_allowed_file_types(self, allowed_file_extensions):
        """Test that allowed file types are accepted."""
        for ext in allowed_file_extensions:
            filename = f"test{ext}"
            assert is_allowed_file_type(filename), f"File type '{ext}' should be allowed"
    
    def test_disallowed_file_types(self, disallowed_file_extensions):
        """Test that disallowed file types are rejected."""
        for ext in disallowed_file_extensions:
            filename = f"test{ext}"
            assert not is_allowed_file_type(filename), f"File type '{ext}' should be disallowed"
    
    def test_case_insensitive_validation(self):
        """Test that file type validation is case insensitive."""
        assert is_allowed_file_type('IMAGE.PNG')
        assert is_allowed_file_type('Document.PDF')
        assert is_allowed_file_type('Video.MP4')


class TestGeneratePublicUrl:
    """Test public URL generation."""
    
    def test_url_generation(self):
        """Test basic URL generation."""
        base_url = "https://example.com"
        folder = "test"
        filename = "image.png"
        
        url = generate_public_url(base_url, folder, filename)
        expected = "https://example.com/uploads/test/image.png"
        
        assert url == expected
    
    def test_url_with_trailing_slash(self):
        """Test URL generation with trailing slash in base URL."""
        base_url = "https://example.com/"
        folder = "test"
        filename = "image.png"
        
        url = generate_public_url(base_url, folder, filename)
        expected = "https://example.com/uploads/test/image.png"
        
        assert url == expected
    
    def test_url_with_special_characters(self):
        """Test URL generation with special characters in folder/filename."""
        base_url = "https://example.com"
        folder = "test-folder_123"
        filename = "image_with_underscores.png"
        
        url = generate_public_url(base_url, folder, filename)
        expected = "https://example.com/uploads/test-folder_123/image_with_underscores.png"
        
        assert url == expected


class TestSanitizeFilename:
    """Test filename sanitization."""
    
    def test_space_replacement(self):
        """Test that spaces are replaced with underscores."""
        assert sanitize_filename("image with spaces.png") == "image_with_spaces.png"
        assert sanitize_filename("multiple   spaces.jpg") == "multiple___spaces.jpg"
    
    def test_special_character_removal(self):
        """Test that dangerous characters are removed."""
        test_cases = {
            'file<name>.png': 'filename.png',
            'file|name.jpg': 'filename.jpg',
            'file"name.jpeg': 'filename.jpeg',
            'file:name.webp': 'filename.webp',
            'file*name.gif': 'filename.gif',
            'file?name.png': 'filename.png',
            'file\x00name.png': 'filename.png',
        }
        
        for input_name, expected in test_cases.items():
            assert sanitize_filename(input_name) == expected
    
    def test_empty_filename(self):
        """Test handling of empty or dangerous filenames."""
        assert sanitize_filename("") == "unnamed_file"
        assert sanitize_filename(".") == "unnamed_file"
        assert sanitize_filename("..") == "unnamed_file"
    
    def test_safe_filenames_unchanged(self):
        """Test that safe filenames are not changed."""
        safe_names = [
            "image.png",
            "document.pdf",
            "file_with_underscores.jpg",
            "file-with-dashes.png"
        ]
        
        for name in safe_names:
            assert sanitize_filename(name) == name
