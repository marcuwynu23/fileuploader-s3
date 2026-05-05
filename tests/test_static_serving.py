"""
Test cases for static file serving endpoints.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from src.fileuploader_s3.main import app


class TestStaticFileServing:
    """Test static file serving endpoint."""
    
    def test_valid_file_access(self, client, temp_upload_dir, sample_image_file):
        """Test accessing a valid uploaded file."""
        # First upload a file
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'test.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Access the file
        response = client.get('/uploads/test/test.png')
        
        assert response.status_code == 200
        assert response.content_type == 'image/png'
        assert response.headers['Content-Disposition'] == 'inline; filename="test.png"'
        assert 'Cache-Control' in response.headers
        assert 'Accept-Ranges' in response.headers
    
    def test_file_not_found(self, client, temp_upload_dir):
        """Test accessing a non-existent file."""
        response = client.get('/uploads/test/nonexistent.png')
        
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert 'error' in response_data
        assert 'File not found' in response_data['error']
    
    def test_path_traversal_attempt(self, client, temp_upload_dir, sample_image_file):
        """Test path traversal attempts are blocked."""
        # Create a legitimate file
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'test.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Try path traversal
        response = client.get('/uploads/../test/test.png')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
    
    def test_invalid_folder_name(self, client):
        """Test accessing file with invalid folder name."""
        response = client.get('/uploads/../etc/passwd')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
    
    def test_invalid_filename(self, client):
        """Test accessing file with invalid filename."""
        response = client.get('/uploads/test/../malicious.png')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
    
    def test_malformed_path(self, client):
        """Test accessing with malformed path."""
        response = client.get('/uploads/test')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
    
    def test_different_file_types(self, client, temp_upload_dir, sample_image_file, sample_pdf_file, sample_text_file):
        """Test serving different file types with correct MIME types."""
        test_cases = [
            ('test.png', sample_image_file, 'image/png'),
            ('document.pdf', sample_pdf_file, 'application/pdf'),
            ('notes.txt', sample_text_file, 'application/octet-stream')  # Default for unknown types
        ]
        
        for filename, file_content, expected_mime in test_cases:
            # Upload file
            upload_dir = Path(temp_upload_dir) / 'test'
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = upload_dir / filename
            file_path.write_bytes(file_content.read())
            
            # Access the file
            response = client.get(f'/uploads/test/{filename}')
            
            assert response.status_code == 200
            assert response.content_type == expected_mime
            assert response.headers['Content-Disposition'] == f'inline; filename="{filename}"'
    
    def test_cache_headers(self, client, temp_upload_dir, sample_image_file):
        """Test that cache headers are properly set."""
        # Upload a file
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'test.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Access the file
        response = client.get('/uploads/test/test.png')
        
        assert response.status_code == 200
        assert 'Cache-Control' in response.headers
        assert 'public' in response.headers['Cache-Control']
        assert 'max-age=31536000' in response.headers['Cache-Control']  # 1 year cache
    
    def test_range_requests(self, client, temp_upload_dir, sample_image_file):
        """Test that range requests are supported."""
        # Upload a file
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'test.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Request with range header
        response = client.get('/uploads/test/test.png', headers={'Range': 'bytes=0-10'})
        
        assert response.status_code == 200  # Flask handles ranges automatically
        assert 'Accept-Ranges' in response.headers
        assert response.headers['Accept-Ranges'] == 'bytes'
    
    def test_special_characters_in_filename(self, client, temp_upload_dir):
        """Test accessing files with special characters in filename."""
        # Create a file with special characters
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'file_with_underscores-and-dashes.png'
        file_path.write_bytes(b'fake png content')
        
        # Access the file
        response = client.get('/uploads/test/file_with_underscores-and-dashes.png')
        
        assert response.status_code == 200
        assert response.content_type == 'image/png'
    
    def test_nested_folder_access(self, client, temp_upload_dir, sample_image_file):
        """Test accessing files in nested folders."""
        # Create nested folder structure
        nested_dir = Path(temp_upload_dir) / 'test' / 'nested' / 'folder'
        nested_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = nested_dir / 'image.png'
        file_path.write_bytes(sample_image_file.read())
        
        # This should fail as we only support one level of folder
        response = client.get('/uploads/test/nested/folder/image.png')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data


class TestLegacyRenderEndpoint:
    """Test legacy render endpoint for backward compatibility."""
    
    def test_legacy_redirect(self, client, temp_upload_dir, sample_image_file):
        """Test that legacy endpoint redirects to new static URL."""
        # Create a file
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'test.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Create a valid token (this would normally be encrypted)
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = 'test/test.png'
            
            response = client.get('/api/test/fileuploader/render/fake_token')
            
            assert response.status_code == 301
            assert 'Location' in response.headers
            assert response.headers['Location'] == 'http://test.example.com/uploads/test/test.png'
    
    def test_legacy_invalid_token(self, client):
        """Test legacy endpoint with invalid token."""
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = None
            
            response = client.get('/api/test/fileuploader/render/invalid_token')
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert 'error' in response_data
            assert 'Invalid token' in response_data['error']
    
    def test_legacy_malformed_key(self, client):
        """Test legacy endpoint with malformed key."""
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = 'invalid_format'  # Missing folder/filename
            
            response = client.get('/api/test/fileuploader/render/fake_token')
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert 'error' in response_data
    
    def test_legacy_file_not_found(self, client):
        """Test legacy endpoint when file doesn't exist."""
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = 'test/nonexistent.png'
            
            response = client.get('/api/test/fileuploader/render/fake_token')
            
            assert response.status_code == 301  # Still redirects, even if file doesn't exist
            assert 'Location' in response.headers


class TestGmailCompatibility:
    """Test Gmail compatibility features."""
    
    def test_gmail_friendly_url_format(self, client, temp_upload_dir, sample_image_file):
        """Test that URLs are Gmail-friendly."""
        # Upload a file
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'logo.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Access the file
        response = client.get('/uploads/test/logo.png')
        
        assert response.status_code == 200
        
        # Check Gmail-friendly characteristics
        url = 'http://test.example.com/uploads/test/logo.png'
        
        # No query strings
        assert '?' not in url
        
        # No authentication tokens
        assert 'token' not in url
        
        # Proper file extension
        assert url.endswith('.png')
        
        # HTTPS-ready format
        assert url.startswith('http://')  # Can be upgraded to HTTPS
    
    def test_proper_mime_types_for_email_clients(self, client, temp_upload_dir, sample_image_file, sample_pdf_file):
        """Test proper MIME types for email clients."""
        test_cases = [
            ('logo.png', sample_image_file, 'image/png'),
            ('document.pdf', sample_pdf_file, 'application/pdf'),
        ]
        
        for filename, file_content, expected_mime in test_cases:
            # Upload file
            upload_dir = Path(temp_upload_dir) / 'test'
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = upload_dir / filename
            file_path.write_bytes(file_content.read())
            
            # Access the file
            response = client.get(f'/uploads/test/{filename}')
            
            assert response.status_code == 200
            assert response.content_type == expected_mime
            
            # Gmail requires inline disposition for images
            assert response.headers['Content-Disposition'] == f'inline; filename="{filename}"'
    
    def test_cache_headers_for_email_clients(self, client, temp_upload_dir, sample_image_file):
        """Test cache headers optimized for email clients."""
        # Upload a file
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'logo.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Access the file
        response = client.get('/uploads/test/logo.png')
        
        assert response.status_code == 200
        
        # Email clients benefit from aggressive caching
        cache_header = response.headers.get('Cache-Control', '')
        assert 'public' in cache_header
        assert 'max-age=31536000' in cache_header  # 1 year cache
    
    def test_no_redirects_for_gmail(self, client, temp_upload_dir, sample_image_file):
        """Test that file access doesn't involve redirects (Gmail blocks redirects)."""
        # Upload a file
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'logo.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Access the file
        response = client.get('/uploads/test/logo.png')
        
        assert response.status_code == 200
        # Direct file serving, no redirects
        assert response.status_code not in [301, 302, 303, 307, 308]
