"""
Test cases for upload endpoints.
"""

import json
import os
import io
import pytest
from unittest.mock import patch, Mock
from pathlib import Path


class TestSingleUpload:
    """Test single file upload endpoint."""
    
    def test_successful_upload(self, client, temp_upload_dir, sample_image_file):
        """Test successful file upload."""
        data = {
            'folder': 'test',
            'file': (sample_image_file, 'test.png', 'image/png')
        }
        
        with patch('src.fileuploader_s3.storage.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            response = client.post(
                '/api/test/fileuploader/upload',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 200
            
            response_data = json.loads(response.data)
            assert response_data['message'].startswith('File successfully uploaded')
            assert 'url' in response_data
            assert response_data['filename'] == 'test.png'
            assert response_data['folder'] == 'test'
            assert response_data['mime_type'] == 'image/png'
            assert 'size' in response_data
            assert response_data['url'] == 'http://test.example.com/uploads/test/test.png'
    
    def test_upload_without_folder(self, client, sample_image_file):
        """Test upload without folder parameter."""
        data = {
            'file': (sample_image_file, 'test.png', 'image/png')
        }
        
        response = client.post(
            '/api/test/fileuploader/upload',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
        assert 'folder' in response_data['error']
    
    def test_upload_without_file(self, client):
        """Test upload without file parameter."""
        data = {
            'folder': 'test'
        }
        
        response = client.post(
            '/api/test/fileuploader/upload',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
        assert 'file' in response_data['error']
    
    def test_upload_with_invalid_folder(self, client, sample_image_file):
        """Test upload with invalid folder name."""
        data = {
            'folder': '../test',  # Path traversal attempt
            'file': (sample_image_file, 'test.png', 'image/png')
        }
        
        response = client.post(
            '/api/test/fileuploader/upload',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
        assert 'folder' in response_data['error']
    
    def test_upload_with_invalid_filename(self, client, temp_upload_dir):
        """Test upload with invalid filename."""
        # Create a file with dangerous characters
        malicious_file = (b'fake content', '../malicious.png', 'image/png')
        
        data = {
            'folder': 'test',
            'file': malicious_file
        }
        
        response = client.post(
            '/api/test/fileuploader/upload',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
    
    def test_upload_disallowed_file_type(self, client, temp_upload_dir):
        """Test upload with disallowed file type."""
        # Create an executable file
        exe_file = (io.BytesIO(b'MZ\x90\x00'), 'malware.exe', 'application/x-executable')
        
        data = {
            'folder': 'test',
            'file': exe_file
        }
        
        response = client.post(
            '/api/test/fileuploader/upload',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
        assert 'File type not allowed' in response_data['error']
    
    @pytest.mark.skip(reason="Creates large file causing disk space issues")
    def test_upload_oversized_file(self, client, temp_upload_dir):
        """Test upload with file exceeding size limit."""
        # Create a large file (larger than default 50MB limit)
        large_content = b'x' * (60 * 1024 * 1024)  # 60MB
        large_file = (io.BytesIO(large_content), 'large.png', 'image/png')
        
        data = {
            'folder': 'test',
            'file': large_file
        }
        
        response = client.post(
            '/api/test/fileuploader/upload',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
        assert 'too large' in response_data['error']
    
    def test_upload_s3_failure(self, client, temp_upload_dir, sample_image_file):
        """Test upload when S3 upload fails."""
        data = {
            'folder': 'test',
            'file': (sample_image_file, 'test.png', 'image/png')
        }
        
        # Test S3 upload failure
        with patch('src.fileuploader_s3.storage.s3_client') as mock_s3:
            mock_s3.upload_fileobj.side_effect = Exception("S3 connection failed")
            
            response = client.post(
                '/api/test/fileuploader/upload',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert 'error' in response_data


class TestMultipleUpload:
    """Test multiple file upload endpoint."""
    
    def test_successful_multiple_upload(self, client, temp_upload_dir, sample_image_file, sample_pdf_file):
        """Test successful multiple file upload."""
        data = {
            'folder': 'test',
            'files': [
                (sample_image_file, 'image.png', 'image/png'),
                (sample_pdf_file, 'document.pdf', 'application/pdf')
            ]
        }
        
        with patch('src.fileuploader_s3.storage.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            response = client.post(
                '/api/test/fileuploader/upload_multi',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 200
            
            response_data = json.loads(response.data)
            assert 'uploaded' in response_data
            assert response_data['total_uploaded'] == 2
            assert len(response_data['uploaded']) == 2
            
            # Check first file
            first_file = response_data['uploaded'][0]
            assert first_file['filename'] in ['image.png', 'document.pdf']
            assert 'url' in first_file
            assert 'size' in first_file
            assert 'mime_type' in first_file
    
    def test_multiple_upload_no_files(self, client):
        """Test multiple upload with no files."""
        data = {
            'folder': 'test'
        }
        
        response = client.post(
            '/api/test/fileuploader/upload_multi',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data
    
    def test_multiple_upload_with_errors(self, client, temp_upload_dir, sample_image_file):
        """Test multiple upload with some invalid files."""
        # Mix valid and invalid files
        data = {
            'folder': 'test',
            'files': [
                (sample_image_file, 'image.png', 'image/png'),  # Valid
                (io.BytesIO(b'MZ\x90\x00'), 'malware.exe', 'application/x-executable'),  # Invalid
                (io.BytesIO(b'fake content'), '../malicious.png', 'image/png')  # Invalid filename
            ]
        }
        
        response = client.post(
            '/api/test/fileuploader/upload_multi',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        
        response_data = json.loads(response.data)
        assert response_data['total_uploaded'] == 1
        assert 'errors' in response_data
        assert response_data['total_errors'] == 2


class TestChunkUpload:
    """Test chunk upload endpoints."""
    
    def test_single_chunk_upload(self, client, temp_upload_dir, sample_image_file):
        """Test single chunk upload (complete file)."""
        data = {
            'folder': 'test',
            'file': (sample_image_file, 'image.png', 'image/png'),
            'dzchunkindex': '0',
            'dztotalchunkcount': '1'
        }
        
        with patch('src.fileuploader_s3.storage.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            response = client.post(
                '/api/test/fileuploader/upload_chunk',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 200
            
            response_data = json.loads(response.data)
            assert 'url' in response_data
            assert response_data['filename'] == 'image.png'
            assert response_data['folder'] == 'test'
    
    def test_partial_chunk_upload(self, client, temp_upload_dir, sample_image_file):
        """Test partial chunk upload."""
        data = {
            'folder': 'test',
            'file': (sample_image_file, 'image.png', 'image/png'),
            'dzchunkindex': '0',
            'dztotalchunkcount': '3'
        }
        
        response = client.post(
            '/api/test/fileuploader/upload_chunk',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        
        response_data = json.loads(response.data)
        assert 'Chunk 1 uploaded successfully' in response_data['message']
    
    @pytest.mark.skip(reason="Test checks local filesystem - not applicable with S3 backend")
    def test_final_chunk_upload(self, client, temp_upload_dir, sample_image_file):
        """Test final chunk upload that combines all chunks."""
        # This test simulates the final chunk after previous chunks were uploaded
        data = {
            'folder': 'test',
            'file': (sample_image_file, 'image.png', 'image/png'),
            'dzchunkindex': '2',  # Final chunk
            'dztotalchunkcount': '3'
        }

        # Mock existing chunks in the correct test_uploads directory
        base_folder = Path('test_uploads')
        temp_dir = base_folder / 'temp' / 'test'
        temp_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / 'image.png.part0').write_bytes(b'chunk1')
        (temp_dir / 'image.png.part1').write_bytes(b'chunk2')
        
        with patch('src.fileuploader_s3.storage.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            response = client.post(
                '/api/test/fileuploader/upload_chunk',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 200
            
            response_data = json.loads(response.data)
            assert 'url' in response_data
            assert response_data['filename'] == 'image.png'
            
            # Verify file was combined
            final_file = Path('test_uploads') / 'test' / 'image.png'
            assert final_file.exists()
    
    def test_chunk_upload_invalid_folder(self, client, sample_image_file):
        """Test chunk upload with invalid folder."""
        data = {
            'folder': '../test',
            'file': (sample_image_file, 'image.png', 'image/png'),
            'dzchunkindex': '0',
            'dztotalchunkcount': '1'
        }
        
        response = client.post(
            '/api/test/fileuploader/upload_chunk',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'folder' in response_data['error']
    
    def test_chunk_upload_invalid_filename(self, client, temp_upload_dir):
        """Test chunk upload with invalid filename."""
        malicious_file = (b'fake content', '../malicious.png', 'image/png')
        
        data = {
            'folder': 'test',
            'file': malicious_file,
            'dzchunkindex': '0',
            'dztotalchunkcount': '1'
        }
        
        response = client.post(
            '/api/test/fileuploader/upload_chunk',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'error' in response_data


class TestMultipleChunkUpload:
    """Test multiple file chunk upload endpoint."""
    
    def test_multiple_chunk_upload_success(self, client, temp_upload_dir, sample_image_file, sample_pdf_file):
        """Test successful multiple file chunk upload."""
        data = {
            'folder': 'test',
            'files': [
                (sample_image_file, 'image.png', 'image/png'),
                (sample_pdf_file, 'document.pdf', 'application/pdf')
            ],
            'dzchunkindex': '0',
            'dztotalchunkcount': '1'
        }
        
        with patch('src.fileuploader_s3.storage.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            response = client.post(
                '/api/test/fileuploader/upload_multi_chunk',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 200
            
            response_data = json.loads(response.data)
            assert 'files' in response_data
            assert response_data['total_uploaded'] == 2
    
    def test_multiple_chunk_upload_partial(self, client, temp_upload_dir, sample_image_file):
        """Test partial multiple file chunk upload."""
        data = {
            'folder': 'test',
            'files': [
                (sample_image_file, 'image.png', 'image/png')
            ],
            'dzchunkindex': '1',  # Middle chunk
            'dztotalchunkcount': '3'
        }
        
        response = client.post(
            '/api/test/fileuploader/upload_multi_chunk',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        
        response_data = json.loads(response.data)
        assert 'Chunk 2 uploaded successfully' in response_data['message']
