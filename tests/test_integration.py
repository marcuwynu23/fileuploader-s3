"""
Integration tests for Gmail compatibility and end-to-end workflows.
"""

import json
import pytest
import io
from pathlib import Path
from unittest.mock import patch


class TestGmailCompatibilityIntegration:
    """Test Gmail compatibility integration scenarios."""
    
    def test_complete_gmail_workflow(self, client, temp_upload_dir, sample_image_file):
        """Test complete workflow: upload -> get URL -> access file."""
        # Step 1: Upload a file
        data = {
            'folder': 'email_assets',
            'file': (sample_image_file, 'logo.png', 'image/png')
        }
        
        with patch('src.fileuploader_s3.main.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            upload_response = client.post(
                '/api/test/fileuploader/upload',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert upload_response.status_code == 200
            upload_data = json.loads(upload_response.data)
            
            # Step 2: Verify URL format is Gmail-compatible
            file_url = upload_data['url']
            assert file_url == 'http://test.example.com/uploads/email_assets/logo.png'
            assert '?' not in file_url  # No query strings
            assert 'token' not in file_url  # No tokens
            assert file_url.endswith('.png')  # Proper extension
            
            # Step 3: Access the file directly (as Gmail would)
            file_response = client.get('/uploads/email_assets/logo.png')
            assert file_response.status_code == 200
            assert file_response.content_type == 'image/png'
            assert file_response.headers['Content-Disposition'] == 'inline; filename="logo.png"'
            
            # Step 4: Verify Gmail-friendly headers
            assert 'Cache-Control' in file_response.headers
            assert 'public' in file_response.headers['Cache-Control']
            assert 'Accept-Ranges' in file_response.headers
    
    def test_email_html_generation(self, client, temp_upload_dir, sample_image_file):
        """Test generating HTML email with uploaded image."""
        # Upload multiple files for email
        files = [
            (sample_image_file, 'logo.png', 'image/png'),
            (sample_image_file, 'banner.jpg', 'image/jpeg')
        ]
        
        data = {
            'folder': 'email_campaign',
            'files': files
        }
        
        with patch('src.fileuploader_s3.main.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            response = client.post(
                '/api/test/fileuploader/upload_multi',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 200
            upload_data = json.loads(response.data)
            
            # Generate HTML email template
            html_template = self._generate_email_html(upload_data['uploaded'])
            
            # Verify all URLs are Gmail-compatible
            for file_info in upload_data['uploaded']:
                url = file_info['url']
                assert url.startswith('http://test.example.com/uploads/')
                assert '?' not in url
                assert url in html_template
            
            # Verify HTML structure
            assert '<img' in html_template
            assert 'src=' in html_template
            assert 'alt=' in html_template
    
    def test_nodemailer_integration_example(self, client, temp_upload_dir, sample_image_file):
        """Test Nodemailer-style integration."""
        # Upload file
        data = {
            'folder': 'newsletter',
            'file': (sample_image_file, 'header.png', 'image/png')
        }
        
        with patch('src.fileuploader_s3.main.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            response = client.post(
                '/api/test/fileuploader/upload',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 200
            upload_data = json.loads(response.data)
            
            # Simulate Nodemailer configuration
            nodemailer_config = {
                'from': 'sender@example.com',
                'to': 'recipient@example.com',
                'subject': 'Newsletter with Images',
                'html': self._generate_newsletter_html(upload_data['url'])
            }
            
            # Verify configuration is valid
            assert nodemailer_config['html']
            assert upload_data['url'] in nodemailer_config['html']
            assert 'cid:' not in nodemailer_config['html']  # Using direct URLs
    
    def _generate_email_html(self, uploaded_files):
        """Generate HTML email template with uploaded files."""
        html = '<html><body>'
        html += '<h1>Check out these images!</h1>'
        
        for file_info in uploaded_files:
            if file_info['mime_type'].startswith('image/'):
                html += f'''
                <div style="margin: 20px 0;">
                    <img src="{file_info['url']}" 
                         alt="{file_info['filename']}" 
                         style="max-width: 600px; height: auto;">
                    <p>Image: {file_info['filename']} ({file_info['size']} bytes)</p>
                </div>
                '''
        
        html += '</body></html>'
        return html
    
    def _generate_newsletter_html(self, image_url):
        """Generate newsletter HTML with header image."""
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Newsletter</title>
        </head>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px;">
            <header style="text-align: center; margin-bottom: 30px;">
                <img src="{image_url}" 
                     alt="Newsletter Header" 
                     style="max-width: 100%; height: auto;">
            </header>
            <main>
                <h1>Our Latest Updates</h1>
                <p>This newsletter header image should display correctly in Gmail!</p>
            </main>
        </body>
        </html>
        '''


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    def test_upload_and_delete_workflow(self, client, temp_upload_dir, sample_image_file):
        """Test complete upload -> access -> delete workflow."""
        # Step 1: Upload file
        data = {
            'folder': 'workflow_test',
            'file': (sample_image_file, 'test.png', 'image/png')
        }
        
        with patch('src.fileuploader_s3.main.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            mock_s3.delete_object.return_value = None
            
            upload_response = client.post(
                '/api/test/fileuploader/upload',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert upload_response.status_code == 200
            upload_data = json.loads(upload_response.data)
            
            # Step 2: Access file
            file_response = client.get('/uploads/workflow_test/test.png')
            assert file_response.status_code == 200
            
            # Step 3: Delete file - use the actual token from upload response
            from src.fileuploader_s3.main import encrypt_key
            token = encrypt_key('workflow_test', 'test.png')
            
            # Reset file pointer to ensure it's closed
            sample_image_file.seek(0)
            
            delete_response = client.delete(f'/api/test/fileuploader/delete/{token}')
            assert delete_response.status_code == 200
            
            # Step 4: Verify file is gone
            file_response_after = client.get('/uploads/workflow_test/test.png')
            assert file_response_after.status_code == 404
    
    def test_chunk_upload_complete_workflow(self, client, temp_upload_dir, sample_image_file):
        """Test complete chunk upload workflow."""
        folder = 'chunk_test'
        filename = 'large_image.png'
        
        # Simulate chunk upload
        chunks = [
            (io.BytesIO(b'chunk1_data'), 'large_image.png', 'image/png'),
            (io.BytesIO(b'chunk2_data'), 'large_image.png', 'image/png'),
            (io.BytesIO(b'chunk3_data'), 'large_image.png', 'image/png')
        ]
        
        with patch('src.fileuploader_s3.main.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            # Upload chunks
            for i, chunk_data in enumerate(chunks):
                data = {
                    'folder': folder,
                    'file': chunk_data,
                    'dzchunkindex': str(i),
                    'dztotalchunkcount': str(len(chunks))
                }
                
                response = client.post(
                    '/api/test/fileuploader/upload_chunk',
                    data=data,
                    content_type='multipart/form-data'
                )
                
                if i < len(chunks) - 1:
                    # Partial chunk
                    assert response.status_code == 200
                    response_data = json.loads(response.data)
                    assert 'Chunk' in response_data['message']
                else:
                    # Final chunk
                    assert response.status_code == 200
                    response_data = json.loads(response.data)
                    assert 'url' in response_data
                    assert response_data['filename'] == filename
            
            # Verify final file is accessible
            file_response = client.get(f'/uploads/{folder}/{filename}')
            assert file_response.status_code == 200
    
    def test_multiple_files_email_campaign(self, client, temp_upload_dir, sample_image_file, sample_pdf_file):
        """Test email campaign with multiple file types."""
        # Upload various file types
        files = [
            (sample_image_file, 'logo.png', 'image/png'),
            (sample_pdf_file, 'brochure.pdf', 'application/pdf')
        ]
        
        data = {
            'folder': 'campaign_2024',
            'files': files
        }
        
        with patch('src.fileuploader_s3.main.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            response = client.post(
                '/api/test/fileuploader/upload_multi',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 200
            upload_data = json.loads(response.data)
            
            # Generate comprehensive email
            email_html = self._generate_campaign_html(upload_data['uploaded'])
            
            # Verify all files are accessible
            for file_info in upload_data['uploaded']:
                file_response = client.get(f"/uploads/campaign_2024/{file_info['filename']}")
                assert file_response.status_code == 200
                assert file_response.content_type == file_info['mime_type']
                
                # Verify URL is in email
                assert file_info['url'] in email_html
    
    def _generate_campaign_html(self, uploaded_files):
        """Generate email campaign HTML."""
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Marketing Campaign</title>
        </head>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px;">
        '''
        
        for file_info in uploaded_files:
            if file_info['mime_type'] == 'image/png':
                html += f'''
                <div style="text-align: center; margin: 30px 0;">
                    <img src="{file_info['url']}" 
                         alt="Campaign Image" 
                         style="max-width: 100%; height: auto; border-radius: 8px;">
                </div>
                '''
            elif file_info['mime_type'] == 'application/pdf':
                html += f'''
                <div style="margin: 30px 0; text-align: center;">
                    <a href="{file_info['url']}" 
                       style="background-color: #007bff; color: white; padding: 12px 24px; 
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Download Brochure (PDF)
                    </a>
                </div>
                '''
        
        html += '''
            </div>
        </body>
        </html>
        '''
        return html


class TestBackwardCompatibility:
    """Test backward compatibility scenarios."""
    
    def test_legacy_token_redirect_workflow(self, client, temp_upload_dir, sample_image_file):
        """Test that legacy tokens still work with redirect."""
        # Upload file
        data = {
            'folder': 'legacy_test',
            'file': (sample_image_file, 'legacy.png', 'image/png')
        }
        
        with patch('src.fileuploader_s3.main.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            upload_response = client.post(
                '/api/test/fileuploader/upload',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert upload_response.status_code == 200
            
            # Simulate legacy access with token
            with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
                mock_decrypt.return_value = 'legacy_test/legacy.png'
                
                legacy_response = client.get('/api/test/fileuploader/render/legacy_token')
                
                # Should redirect to new URL
                assert legacy_response.status_code == 301
                assert 'Location' in legacy_response.headers
                expected_location = 'http://test.example.com/uploads/legacy_test/legacy.png'
                assert legacy_response.headers['Location'] == expected_location
    
    def test_mixed_url_usage(self, client, temp_upload_dir, sample_image_file):
        """Test that both old and new URLs work simultaneously."""
        # Upload file
        data = {
            'folder': 'mixed_test',
            'file': (sample_image_file, 'mixed.png', 'image/png')
        }
        
        with patch('src.fileuploader_s3.main.s3_client') as mock_s3:
            mock_s3.upload_fileobj.return_value = None
            
            upload_response = client.post(
                '/api/test/fileuploader/upload',
                data=data,
                content_type='multipart/form-data'
            )
            
            assert upload_response.status_code == 200
            
            # New URL should work directly
            new_response = client.get('/uploads/mixed_test/mixed.png')
            assert new_response.status_code == 200
            
            # Legacy URL should redirect
            with patch('src.fileuploader_s3.main.decrypt_key') as mock_decrypt:
                mock_decrypt.return_value = 'mixed_test/mixed.png'
                
                legacy_response = client.get('/api/test/fileuploader/render/legacy_token')
                assert legacy_response.status_code == 301
                assert legacy_response.headers['Location'] == 'http://test.example.com/uploads/mixed_test/mixed.png'
