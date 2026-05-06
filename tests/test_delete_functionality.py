"""
Test cases for delete functionality.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch


class TestDeleteFunctionality:
    """Test file deletion endpoints."""
    
    def test_successful_delete(self, client, temp_upload_dir, sample_image_file):
        """Test successful file deletion."""
        # Create a file in the correct base folder
        base_folder = 'test_uploads'
        upload_dir = Path(base_folder) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / 'test.png'
        file_path.write_bytes(sample_image_file.read())

        # Delete the file with proper token
        from src.fileuploader_s3.main import encrypt_key
        token = encrypt_key('test', 'test.png')
        
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = 'test/test.png'

            response = client.delete(f'/api/test/fileuploader/delete/{token}')
            
            assert response.status_code == 200
            
            response_data = json.loads(response.data)
            assert 'message' in response_data
            assert 'test.png' in response_data['message']
            assert response_data['filename'] == 'test.png'
            assert response_data['folder'] == 'test'
            
            # Verify file is deleted
            assert not file_path.exists()
    
    def test_delete_nonexistent_file(self, client):
        """Test deleting a non-existent file."""
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = 'test/nonexistent.png'
            
            response = client.delete('/api/test/fileuploader/delete/fake_token')
            
            assert response.status_code == 200  # Still returns success
            response_data = json.loads(response.data)
            assert 'deleted successfully' in response_data['message']
    
    def test_delete_removes_empty_folder(self, client, temp_upload_dir, sample_image_file):
        """Test that empty folders are removed after file deletion."""
        # Create a file in the correct base folder
        base_folder = 'test_uploads'
        upload_dir = Path(base_folder) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'test.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Delete the file
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = 'test/test.png'
            
            response = client.delete('/api/test/fileuploader/delete/fake_token')
            
            assert response.status_code == 200
            
            # Verify folder is removed
            assert not upload_dir.exists()
    
    def test_delete_keeps_nonempty_folder(self, client, temp_upload_dir, sample_image_file):
        """Test that non-empty folders are not removed."""
        # Create a folder with multiple files
        base_folder = 'test_uploads'
        upload_dir = Path(base_folder) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)

        file1_path = upload_dir / 'test.png'
        file1_path.write_bytes(sample_image_file.read())

        file2_path = upload_dir / 'other.png'
        file2_path.write_bytes(b'other content')
        
        # Delete one file
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = 'test/test.png'
            
            response = client.delete('/api/test/fileuploader/delete/fake_token')
            
            assert response.status_code == 200
            
            # Verify deleted file is gone
            assert not file1_path.exists()
            # Verify other file still exists
            assert file2_path.exists()
            # Verify folder still exists
            assert upload_dir.exists()
    
    def test_delete_invalid_token(self, client):
        """Test delete with invalid token."""
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = None
            
            response = client.delete('/api/test/fileuploader/delete/invalid_token')
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert 'error' in response_data
            assert 'Invalid token' in response_data['error']
    
    def test_delete_malformed_key(self, client):
        """Test delete with malformed key."""
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = 'invalid_format'  # Missing folder/filename
            
            response = client.delete('/api/test/fileuploader/delete/fake_token')
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert 'error' in response_data
    
    def test_delete_s3_failure(self, client, temp_upload_dir, sample_image_file):
        """Test delete when S3 deletion fails."""
        # Create a file
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'test.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Delete with S3 failure
        # Enable S3 for this test
        with patch('src.fileuploader_s3.main.USE_S3', True), \
             patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt, \
             patch('src.fileuploader_s3.main.s3_client') as mock_s3:
            
            mock_decrypt.return_value = 'test/test.png'
            mock_s3.delete_object.side_effect = Exception("S3 connection failed")
            
            response = client.delete('/api/test/fileuploader/delete/fake_token')
            
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert 'error' in response_data
            assert 'Delete failed' in response_data['error']
    
    def test_delete_local_file_failure(self, client, temp_upload_dir):
        """Test delete when local file deletion fails."""
        # Don't create the file (simulate local deletion failure)
        
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt, \
             patch('src.fileuploader_s3.main.s3_client') as mock_s3, \
             patch('pathlib.Path.unlink') as mock_unlink:
            
            mock_decrypt.return_value = 'test/test.png'
            mock_s3.delete_object.return_value = None
            mock_unlink.side_effect = Exception("Permission denied")
            
            response = client.delete('/api/test/fileuploader/delete/fake_token')
            
            # Should still succeed (S3 deletion worked)
            assert response.status_code == 200
    
    def test_delete_nested_folder_file(self, client, temp_upload_dir, sample_image_file):
        """Test deleting file from nested folder."""
        # Create nested folder structure
        base_folder = 'test_uploads'
        nested_dir = Path(base_folder) / 'test' / 'nested'
        nested_dir.mkdir(parents=True, exist_ok=True)

        file_path = nested_dir / 'image.png'
        file_path.write_bytes(sample_image_file.read())
        
        # This should fail as we only support one level
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = 'test/nested/image.png'
            
            response = client.delete('/api/test/fileuploader/delete/fake_token')
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert 'error' in response_data
    
    def test_delete_path_traversal_attempt(self, client, temp_upload_dir, sample_image_file):
        """Test delete with path traversal attempt."""
        # Create a legitimate file
        base_folder = 'test_uploads'
        upload_dir = Path(base_folder) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'test.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Try path traversal
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = '../test/test.png'
            
            response = client.delete('/api/test/fileuploader/delete/fake_token')
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert 'error' in response_data
            
            # Verify legitimate file still exists
            assert file_path.exists()


class TestDeleteSecurity:
    """Test security aspects of delete functionality."""
    
    def test_delete_token_validation(self, client):
        """Test that delete validates tokens properly."""
        # Test with empty token
        response = client.delete('/api/test/fileuploader/delete/')
        assert response.status_code == 404  # Route not found
        
        # Test with None token
        response = client.delete('/api/test/fileuploader/delete/None')
        assert response.status_code in [400, 404]
    
    def test_delete_sanitization(self, client, temp_upload_dir):
        """Test that delete properly sanitizes paths."""
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
            # Test various malicious inputs
            malicious_inputs = [
                '/etc/passwd',
                '..\\..\\windows\\system32\\config\\system',
                'test/../../../etc/passwd',
                'test\\..\\..\\..\\windows\\system.ini',
                'test\x00.png',
                'test|.png',
                'test?.png',
                'test*.png',
                'test".png',
                'test<.png',
                'test>.png'
            ]
            
            for malicious_input in malicious_inputs:
                mock_decrypt.return_value = malicious_input
                
                response = client.delete('/api/test/fileuploader/delete/fake_token')
                
                # Should reject malicious paths
                assert response.status_code == 400
                response_data = json.loads(response.data)
                assert 'error' in response_data
    
    def test_delete_concurrent_access(self, client, temp_upload_dir, sample_image_file):
        """Test delete behavior with concurrent access."""
        # Create a file
        upload_dir = Path(temp_upload_dir) / 'test'
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / 'test.png'
        file_path.write_bytes(sample_image_file.read())
        
        # Simulate concurrent delete requests
        with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt, \
             patch('src.fileuploader_s3.main.s3_client') as mock_s3:
            
            mock_decrypt.return_value = 'test/test.png'
            mock_s3.delete_object.return_value = None
            
            # Send multiple delete requests
            response1 = client.delete('/api/test/fileuploader/delete/token1')
            response2 = client.delete('/api/test/fileuploader/delete/token2')
            
            # Both should succeed (idempotent operation)
            assert response1.status_code == 200
            assert response2.status_code == 200
