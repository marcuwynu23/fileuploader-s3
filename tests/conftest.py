"""
Pytest configuration and fixtures for file uploader tests.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import io

from src.fileuploader_s3.main import app
from src.fileuploader_s3.security_helpers import SecurityConfig


@pytest.fixture
def client():
    """Create a test client for the Flask application."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Set test environment variables
    os.environ.update({
        'ENCRYPTION_KEY': 'test-key-32-chars-long-for-testing-1234567890',
        'BASE_URL': 'http://test.example.com',
        'ROUTE_PREFIX': '/api/test/fileuploader',
        'BASE_FOLDER': 'test_uploads',
        'STORAGE_ENDPOINT': 'http://test-s3.example.com',
        'STORAGE_ACCESS_KEY': 'test-access-key',
        'STORAGE_SECRET_KEY': 'test-secret-key',
        'STORAGE_BUCKET': 'test-bucket'
    })
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_upload_dir():
    """Create a temporary directory for file uploads during testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['BASE_FOLDER'] = temp_dir
        yield temp_dir


@pytest.fixture
def sample_image_file():
    """Create a sample image file for testing."""
    # Create a simple PNG file (1x1 pixel)
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00'
        b'\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00'
        b'\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    return io.BytesIO(png_data)


@pytest.fixture
def sample_pdf_file():
    """Create a sample PDF file for testing."""
    pdf_data = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n'
    return io.BytesIO(pdf_data)


@pytest.fixture
def sample_text_file():
    """Create a sample text file for testing."""
    text_data = b'This is a test file content.\nLine 2 of the file.\n'
    return io.BytesIO(text_data)


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    mock_client = Mock()
    mock_client.head_bucket.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
    mock_client.upload_fileobj.return_value = None
    mock_client.delete_object.return_value = None
    mock_client.get_object.return_value = {
        'Body': Mock(),
        'ContentLength': 1024
    }
    return mock_client


@pytest.fixture
def valid_folder_names():
    """Return valid folder names for testing."""
    return [
        'test',
        'test_folder',
        'test-folder',
        'test123',
        'Test_Folder_123'
    ]


@pytest.fixture
def invalid_folder_names():
    """Return invalid folder names for testing."""
    return [
        '../test',
        '..\\test',
        '/test',
        '\\test',
        'test/..',
        'test\\..',
        'test/../folder',
        'test\\..\\folder',
        '',
        None,
        'test folder with spaces',
        'test@folder',
        'test#folder',
        'test$folder'
    ]


@pytest.fixture
def valid_filenames():
    """Return valid filenames for testing."""
    return [
        'image.png',
        'document.pdf',
        'video.mp4',
        'archive.zip',
        'file_with_underscores.docx',
        'file-with-dashes.jpg',
        'File123.jpeg',
        'test.webp',
        'animation.gif'
    ]


@pytest.fixture
def invalid_filenames():
    """Return invalid filenames for testing."""
    return [
        '../image.png',
        '..\\document.pdf',
        '/video.mp4',
        '\\archive.zip',
        'file<name>.docx',
        'file|name.jpg',
        'file"name.jpeg',
        'file:name.webp',
        'file*name.gif',
        'file?name.png',
        '',
        None
    ]


@pytest.fixture
def allowed_file_extensions():
    """Return list of allowed file extensions."""
    return list(SecurityConfig.ALLOWED_MIME_TYPES.keys())


@pytest.fixture
def disallowed_file_extensions():
    """Return list of disallowed file extensions."""
    return [
        '.exe',
        '.bat',
        '.sh',
        '.php',
        '.jsp',
        '.asp',
        '.cmd',
        '.scr',
        '.dll',
        '.msi'
    ]


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Automatically clean up temporary files after each test."""
    yield
    # Clean up test uploads directory if it exists
    test_upload_dir = Path('test_uploads')
    if test_upload_dir.exists():
        import shutil
        shutil.rmtree(test_upload_dir, ignore_errors=True)
