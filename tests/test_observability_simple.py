"""
Simple observability test that demonstrates features work correctly.
"""

import json
import pytest
import io
from unittest.mock import patch

def test_observability_basic_functionality(client):
    """Test basic observability functionality without complex patching."""
    
    # Test 1: Health endpoint should work
    response = client.get('/health')
    assert response.status_code == 200
    
    health_data = json.loads(response.data)
    assert 'observability' in health_data
    obs = health_data['observability']
    
    # Check all observability flags are present
    assert 'prometheus_enabled' in obs
    assert 'loki_enabled' in obs
    assert 's3_enabled' in obs
    
    # Test 2: Upload a file (should work regardless of observability settings)
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00'
        b'\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00'
        b'\x01\x00\x01\x00\x00\x00IEND\xaeB`\x82'
    )
    
    data = {
        'folder': 'simple_observability_test',
        'file': (io.BytesIO(png_data), 'test.png', 'image/png')
    }
    
    with patch('src.fileuploader_s3.storage.s3_client') as mock_s3:
        # Mock for upload
        mock_s3.upload_fileobj.return_value = None
        mock_s3.head_object.return_value = {'ContentLength': 1024}
        
        upload_response = client.post(
            '/api/test/fileuploader/upload',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert upload_response.status_code == 200
        upload_result = json.loads(upload_response.data)
        assert 'url' in upload_result
        
        # Test 3: Serve the uploaded file with S3 mocking
        mock_s3.get_object.return_value = {
            'Body': io.BytesIO(png_data),
            'ContentLength': len(png_data)
        }
        
        serve_response = client.get('/uploads/simple_observability_test/test.png')
        assert serve_response.status_code == 200
        
        # Test 4: Delete the file
        from src.fileuploader_s3.utils import encrypt_key
        from src.fileuploader_s3.routes import decrypt_key
        token = encrypt_key('simple_observability_test', 'test.png')
        
        with patch('src.fileuploader_s3.routes.decrypt_key') as mock_decrypt:
            mock_decrypt.return_value = 'simple_observability_test/test.png'
            mock_s3.delete_object.return_value = None
            
            delete_response = client.delete(f'/api/test/fileuploader/delete/{token}')
            assert delete_response.status_code == 200
        
        # Test 5: Verify file is gone
        class NoSuchKey(Exception):
            pass
        mock_s3.exceptions = type('exceptions', (), {'NoSuchKey': NoSuchKey})
        mock_s3.head_object.side_effect = NoSuchKey("File not found")
        
        final_serve_response = client.get('/uploads/simple_observability_test/test.png')
        assert final_serve_response.status_code == 404
    
    print("✅ Basic observability workflow test passed!")
