"""
Fixed pytest configuration that avoids collection hanging.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import io
import sys

# Set environment variables to bypass OpenSSL issues
os.environ['OPENSSL_CONF'] = ''

# Set test environment variables BEFORE any imports
os.environ.update({
    'ENCRYPTION_KEY': 'SZOnm/8TvkYACNXn/MM/agc/M+seIlnI4+MLR2/Xr78=',
    'BASE_URL': 'http://test.example.com',
    'ROUTE_PREFIX': '/api/test/fileuploader',
    'BASE_FOLDER': 'test_uploads',
    'STORAGE_ENDPOINT': 'http://test-s3.example.com',
    'STORAGE_ACCESS_KEY': 'test-access-key',
    'STORAGE_SECRET_KEY': 'test-secret-key',
    'STORAGE_BUCKET': 'test-bucket',
    'USE_S3': 'false',
    'USE_PROMETHEUS': 'True',
    'TESTING': 'true'
})

# Mock boto3 and related modules BEFORE any imports from the project!
mock_boto3 = Mock()
mock_client = Mock()
mock_client.head_bucket.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
mock_client.upload_fileobj.return_value = None
mock_client.delete_object.return_value = None
mock_client.get_object.return_value = {
    'Body': Mock(),
    'ContentLength': 1024
}
mock_boto3.client.return_value = mock_client

mock_magic = Mock()
mock_magic.from_buffer.return_value = 'image/png'

# Apply patches globally before any project imports
sys.modules['boto3'] = mock_boto3
sys.modules['botocore'] = Mock()
sys.modules['botocore.client'] = Mock()
sys.modules['urllib3'] = Mock()
sys.modules['magic'] = mock_magic

@pytest.fixture
def mock_s3_dependencies():
    """Mock S3 dependencies to avoid OpenSSL issues."""
    yield mock_boto3

@pytest.fixture
def client(mock_s3_dependencies):
    """Create a test client for the Flask application."""
    # Import after mocking (environment variables already set above)
    from src.fileuploader_s3.main import app, limiter
    
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Reset rate limiter for test isolation
    limiter.reset()
    
    with app.test_client() as client:
        with app.app_context():
            yield client

@pytest.fixture
def temp_upload_dir():
    """Create a temporary directory for file uploads during testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def sample_image_file():
    """Create a sample image file for testing."""
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00'
        b'\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00'
        b'\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    # Create a fresh BytesIO object for each test
    file_obj = io.BytesIO(png_data)
    file_obj.seek(0)  # Ensure file pointer is at start
    return file_obj

@pytest.fixture
def sample_pdf_file():
    """Create a sample PDF file for testing."""
    pdf_data = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n'
    file_obj = io.BytesIO(pdf_data)
    file_obj.seek(0)  # Ensure file pointer is at start
    return file_obj

@pytest.fixture
def sample_text_file():
    """Create a sample text file for testing."""
    text_data = b'This is a test file content.\nLine 2 of the file.\n'
    file_obj = io.BytesIO(text_data)
    file_obj.seek(0)  # Ensure file pointer is at start
    return file_obj

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
def valid_nested_folder_names():
    """Return valid nested folder names for testing."""
    return [
        'hrms/freedom-wall',
        'documents/reports/2024',
        'images/profile/user123',
        'projects/webapp/src/components',
        'data/exports/csv/monthly'
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
    from src.fileuploader_s3.config import ALLOWED_MIME_TYPES
    return list(ALLOWED_MIME_TYPES.keys())

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
    test_upload_dir = Path('test_uploads')
    if test_upload_dir.exists():
        import shutil
        shutil.rmtree(test_upload_dir, ignore_errors=True)
