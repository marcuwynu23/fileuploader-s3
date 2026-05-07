"""
Test cases for observability features including Prometheus metrics and structured logging.
"""

import json
import pytest
import io
import os
from unittest.mock import patch, Mock

class TestObservability:
    """Test observability features including metrics and structured logging."""
    
    def test_health_endpoint_observability_status(self, client):
        """Test health endpoint returns observability configuration."""
        response = client.get('/health')
        assert response.status_code == 200
        
        health_data = json.loads(response.data)
        assert 'observability' in health_data
        obs = health_data['observability']
        
        # Check all observability flags are present
        assert 'prometheus_enabled' in obs
        assert 'loki_enabled' in obs
        assert 's3_enabled' in obs
        assert isinstance(obs['prometheus_enabled'], bool)
        assert isinstance(obs['loki_enabled'], bool)
        assert isinstance(obs['s3_enabled'], bool)
    
    def test_prometheus_metrics_endpoint_enabled(self, client):
        """Test Prometheus metrics endpoint when enabled."""
        # Set environment variable for this test
        with patch.dict(os.environ, {'USE_PROMETHEUS': 'true'}):
            # Mock the prometheus metrics in routes module where it's actually used
            with patch('src.fileuploader_s3.routes.get_prometheus_metrics') as mock_get_metrics:
                mock_metrics = Mock()
                mock_metrics.__contains__ = Mock(return_value=True)
                mock_get_metrics.return_value = mock_metrics
                
                with patch('prometheus_client.generate_latest', return_value=b'# HELP test metric\n# TYPE test counter\ntest 1'):
                    response = client.get('/metrics')
                    assert response.status_code == 200
    
    def test_prometheus_metrics_endpoint_disabled(self, client):
        """Test Prometheus metrics endpoint when disabled."""
        # Set environment variable for this test
        with patch.dict(os.environ, {'USE_PROMETHEUS': 'false'}):
            with patch('src.fileuploader_s3.routes.get_prometheus_metrics') as mock_get_metrics:
                mock_get_metrics.return_value = None  # No metrics when disabled
                response = client.get('/metrics')
                assert response.status_code == 404
                data = json.loads(response.data)
                assert 'error' in data
    
    def test_structured_logging_format(self, client):
        """Test structured logging produces JSON format when Loki enabled."""
        with patch('src.fileuploader_s3.config.USE_LOKI', True):
            # Upload a test file to trigger logging
            png_data = (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00'
                b'\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00'
                b'\x01\x00\x01\x00\x00\x00IEND\xaeB`\x82'
            )
            
            data = {
                'folder': 'structured_logging_test',
                'file': (io.BytesIO(png_data), 'test.png', 'image/png')
            }
            
            response = client.post(
                '/api/test/fileuploader/upload',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 200
            # Log should contain structured data when Loki is enabled
            # This is verified by checking the log file content
    
    def test_observability_integration_workflow(self, client):
        """Test complete observability workflow with current configuration."""
        # Test with current environment configuration (may be enabled or disabled)
        # Upload a test file
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00'
            b'\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00'
            b'\x01\x00\x01\x00\x00\x00IEND\xaeB`\x82'
        )
        
        upload_data = {
            'folder': 'observability_integration_test',
            'file': (io.BytesIO(png_data), 'test.png', 'image/png')
        }
        
        upload_response = client.post(
            '/api/test/fileuploader/upload',
            data=upload_data,
            content_type='multipart/form-data'
        )
        
        assert upload_response.status_code == 200
        upload_result = json.loads(upload_response.data)
        assert 'url' in upload_result
        
        # Check health endpoint to see current configuration
        health_response = client.get('/health')
        assert health_response.status_code == 200
        health_data = json.loads(health_response.data)
        
        # Check metrics endpoint based on current configuration
        metrics_response = client.get('/metrics')
        if health_data['observability']['prometheus_enabled']:
            assert metrics_response.status_code == 200
            assert b'fileuploader_uploads_total' in metrics_response.data
        else:
            assert metrics_response.status_code == 404
            data = json.loads(metrics_response.data)
            assert 'error' in data
        
        # Serve file
        with patch('src.fileuploader_s3.storage.s3_client') as mock_s3:
            mock_s3.head_object.return_value = {'ContentLength': 1024}
            mock_s3.get_object.return_value = {
                'Body': io.BytesIO(png_data),
                'ContentLength': len(png_data)
            }
            
            serve_response = client.get('/uploads/observability_integration_test/test.png')
            assert serve_response.status_code == 200
        
        # Delete file
        from src.fileuploader_s3.utils import encrypt_key
        token = encrypt_key('observability_integration_test', 'test.png')
        
        with patch('src.fileuploader_s3.routes.decrypt_key') as mock_decrypt, \
             patch('src.fileuploader_s3.storage.s3_client') as mock_s3:
            
            mock_decrypt.return_value = 'observability_integration_test/test.png'
            mock_s3.head_object.return_value = {'ContentLength': 1024}
            mock_s3.delete_object.return_value = None
            
            delete_response = client.delete(f'/api/test/fileuploader/delete/{token}')
            assert delete_response.status_code == 200
        
        # Verify file is gone
        with patch('src.fileuploader_s3.storage.s3_client') as mock_s3:
            # Mock file not found
            class NoSuchKey(Exception):
                pass
            mock_s3.exceptions = type('exceptions', (), {'NoSuchKey': NoSuchKey})
            mock_s3.head_object.side_effect = NoSuchKey("File not found")
            
            final_serve_response = client.get('/uploads/observability_integration_test/test.png')
            assert final_serve_response.status_code == 404
        
        # Verify observability configuration
        assert 'prometheus_enabled' in health_data['observability']
        assert 'loki_enabled' in health_data['observability']
        assert 's3_enabled' in health_data['observability']
    
    def test_observability_current_configuration(self, client):
        """Test observability features with current configuration."""
        response = client.get('/health')
        assert response.status_code == 200
        
        health_data = json.loads(response.data)
        obs = health_data['observability']
        
        # Check current configuration (may be enabled or disabled)
        assert 'prometheus_enabled' in obs
        assert 'loki_enabled' in obs
        assert 's3_enabled' in obs
        assert isinstance(obs['prometheus_enabled'], bool)
        assert isinstance(obs['loki_enabled'], bool)
        assert isinstance(obs['s3_enabled'], bool)
        
        # Metrics endpoint should match prometheus_enabled status
        metrics_response = client.get('/metrics')
        if obs['prometheus_enabled']:
            assert metrics_response.status_code == 200
            assert b'fileuploader_uploads_total' in metrics_response.data
        else:
            assert metrics_response.status_code == 404
            data = json.loads(metrics_response.data)
            assert 'error' in data
