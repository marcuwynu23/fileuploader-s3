# Test Suite for File Uploader

This directory contains comprehensive test cases for the Gmail-compatible file uploader service.

## 🧪 Test Coverage

### Security Tests (`test_security_helpers.py`)
- **Path Traversal Prevention**: Tests against `../`, absolute paths, and directory traversal attacks
- **Filename Validation**: Validates safe filename patterns and character filtering
- **MIME Type Detection**: Ensures correct MIME type mapping for all supported formats
- **File Type Validation**: Verifies only allowed file types are accepted
- **URL Generation**: Tests Gmail-compatible URL format and sanitization
- **Input Sanitization**: Validates filename and folder name sanitization

### Upload Endpoint Tests (`test_upload_endpoints.py`)
- **Single File Upload**: Tests complete upload workflow with validation
- **Multiple File Upload**: Tests batch upload with error handling
- **Chunk Upload**: Tests large file upload in chunks
- **Multiple Chunk Upload**: Tests multi-file chunked uploads
- **Error Handling**: Tests invalid inputs, oversized files, disallowed types
- **S3 Integration**: Tests cloud storage backup functionality

### Static File Serving Tests (`test_static_serving.py`)
- **Direct File Access**: Tests Gmail-compatible static URL serving
- **MIME Type Headers**: Verifies correct content-type for all file types
- **Cache Headers**: Tests email-client-friendly caching
- **Path Security**: Prevents directory traversal attacks
- **Legacy Compatibility**: Tests backward compatibility with token-based URLs
- **Gmail Compatibility**: Validates email client requirements

### Delete Functionality Tests (`test_delete_functionality.py`)
- **File Deletion**: Tests complete file removal workflow
- **Folder Cleanup**: Tests empty folder removal
- **Security**: Tests path traversal prevention in delete operations
- **Error Handling**: Tests S3 failures and local deletion issues
- **Concurrent Access**: Tests idempotent delete operations

### Integration Tests (`test_integration.py`)
- **Gmail Workflow**: Complete upload → email → access workflow
- **Email HTML Generation**: Tests Nodemailer integration scenarios
- **End-to-End**: Complete application workflows
- **Backward Compatibility**: Legacy and new URL coexistence

## 🚀 Running Tests

### Install Test Dependencies

```bash
pip install -r tests/requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Security tests only
pytest tests/test_security_helpers.py -v

# Gmail compatibility tests
pytest tests/ -m gmail

# Integration tests
pytest tests/ -m integration

# Security tests
pytest tests/ -m security
```

### Run with Coverage

```bash
pytest --cov=src/fileuploader_s3 --cov-report=html
```

### Run Specific Test Files

```bash
pytest tests/test_upload_endpoints.py -v
pytest tests/test_static_serving.py -v
pytest tests/test_delete_functionality.py -v
pytest tests/test_integration.py -v
```

## 📋 Test Categories

### 🔒 Security Tests
- Path traversal prevention
- Input validation and sanitization
- File type restrictions
- Size limitations
- Malicious input handling

### 📧 Gmail Compatibility Tests
- Static URL format
- MIME type headers
- Cache optimization
- No redirects
- Direct file serving

### 🔄 Backward Compatibility Tests
- Legacy token redirects
- Old endpoint support
- Migration scenarios

### 🚀 Integration Tests
- End-to-end workflows
- Email campaign scenarios
- Nodemailer integration
- Multi-file operations

## 🎯 Key Test Scenarios

### Gmail Email Integration
```python
# Tests complete email workflow
1. Upload image → Get static URL
2. Generate HTML email with image URL
3. Verify Gmail can display image
4. Test caching and performance
```

### Security Validation
```python
# Tests security measures
1. Path traversal attempts: `../`, `/etc/passwd`
2. Malicious filenames: `file<name>.png`
3. Disallowed file types: `.exe`, `.bat`
4. Oversized files: > 50MB
5. Invalid folder names: special characters
```

### Performance Testing
```python
# Tests performance characteristics
1. Large file chunked uploads
2. Multiple concurrent uploads
3. Cache header effectiveness
4. Static file serving speed
```

## 🛠️ Test Fixtures

### Sample Files
- `sample_image_file`: 1x1 PNG image
- `sample_pdf_file`: Minimal PDF document
- `sample_text_file`: Plain text content

### Mock Services
- `mock_s3_client`: Mocked S3/MinIO client
- `temp_upload_dir`: Temporary upload directory

### Test Data
- `valid_folder_names`: Approved folder name patterns
- `invalid_folder_names`: Rejected folder name patterns
- `valid_filenames`: Approved filename patterns
- `invalid_filenames`: Rejected filename patterns

## 📊 Coverage Report

After running tests with coverage:

```bash
open htmlcov/index.html
```

The test suite aims for >90% coverage of:
- Security helper functions
- Upload endpoints
- Static file serving
- Delete functionality
- Error handling paths

## 🔧 Test Configuration

### Environment Variables
Tests automatically set required environment variables:
- `ENCRYPTION_KEY`: Test encryption key
- `BASE_URL`: Test domain URL
- `BASE_FOLDER`: Temporary upload directory
- `STORAGE_*`: Mock S3 configuration

### Cleanup
Tests automatically clean up:
- Temporary upload directories
- Mock S3 operations
- Test files and folders

## 🚨 Important Notes

1. **Isolation**: Each test runs in isolation with temporary directories
2. **Mocking**: S3 operations are mocked to avoid external dependencies
3. **Security**: Tests verify all security measures are working
4. **Gmail**: Tests specifically validate Gmail compatibility requirements
5. **Performance**: Tests include cache header validation for email clients

## 🎯 Test Goals

- ✅ **Security**: Prevent path traversal and malicious uploads
- ✅ **Gmail Compatibility**: Ensure images display in emails
- ✅ **Performance**: Validate static file serving efficiency
- ✅ **Reliability**: Test error handling and edge cases
- ✅ **Backward Compatibility**: Support legacy integrations
- ✅ **Integration**: Verify end-to-end workflows
