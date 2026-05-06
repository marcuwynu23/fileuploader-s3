"""Storage module for S3 operations."""

from io import BytesIO
import os
from .config import STORAGE_ENDPOINT, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY, STORAGE_BUCKET
from .security import validate_file_content, get_mime_type

# S3 client will be initialized in main.py
s3_client = None


def initialize_s3_client(boto3, Config):
    """Initialize S3 client and ensure bucket exists."""
    global s3_client
    
    # Check if we're in TESTING mode
    testing = os.getenv('TESTING', 'false').lower() == 'true'
    
    print("Initializing S3 client...")
    try:
        # S3/MinIO client for cloud storage (mandatory)
        s3_client = boto3.client(
            "s3",
            endpoint_url=STORAGE_ENDPOINT,
            aws_access_key_id=STORAGE_ACCESS_KEY,
            aws_secret_access_key=STORAGE_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        
        # Ensure S3 bucket exists - don't fail in TESTING mode
        try:
            s3_client.head_bucket(Bucket=STORAGE_BUCKET)
            print(f"S3 bucket '{STORAGE_BUCKET}' is accessible at {STORAGE_ENDPOINT}")
        except:
            if not testing:
                s3_client.create_bucket(Bucket=STORAGE_BUCKET)
                print(f"Created S3 bucket '{STORAGE_BUCKET}' at {STORAGE_ENDPOINT}")
            
    except Exception as s3_init_error:
        print(f"Failed to initialize S3 client: {s3_init_error}")
        if not testing:
            print(f"ERROR: This application requires S3 storage to function")
            print(f"   Please check your S3 configuration:")
            print(f"   - STORAGE_ENDPOINT: {STORAGE_ENDPOINT}")
            print(f"   - STORAGE_ACCESS_KEY: {STORAGE_ACCESS_KEY}")
            print(f"   - STORAGE_BUCKET: {STORAGE_BUCKET}")
            print(f"   Make sure your S3 service is running and accessible")
            exit(1)
    
    return s3_client


def upload_file_to_s3(file_content: bytes, folder: str, filename: str, app_logger):
    """Upload file content to S3."""
    if not s3_client:
        raise Exception("S3 client not initialized")
    
    s3_key = f"{folder}/{filename}"
    
    try:
        file_obj = BytesIO(file_content)
        s3_client.upload_fileobj(file_obj, STORAGE_BUCKET, s3_key)
        app_logger.info("File successfully uploaded to S3", 
                     folder=folder, filename=filename, 
                     file_size=len(file_content), backend='s3', bucket=STORAGE_BUCKET, s3_key=s3_key)
        
        # Verify object exists
        try:
            s3_client.head_object(Bucket=STORAGE_BUCKET, Key=s3_key)
            app_logger.info("Verified object exists in S3", 
                         bucket=STORAGE_BUCKET, s3_key=s3_key)
        except Exception as verify_error:
            app_logger.warning("Failed to verify object in S3", 
                            error=str(verify_error), bucket=STORAGE_BUCKET, s3_key=s3_key)
        
        return True, None
    except Exception as s3_error:
        error_msg = f"Upload failed: {str(s3_error)}"
        app_logger.error("S3 upload failed", 
                      folder=folder, filename=filename,
                      error=str(s3_error), backend='s3')
        return False, error_msg


def serve_file_from_s3(filepath: str, app_logger):
    """Serve file directly from S3 storage."""
    if not s3_client:
        raise Exception("S3 client not initialized")
    
    try:
        # Get object metadata from S3
        s3_object = s3_client.head_object(Bucket=STORAGE_BUCKET, Key=filepath)
        file_size = s3_object['ContentLength']
        
        # Generate presigned URL for direct S3 access
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': STORAGE_BUCKET, 'Key': filepath},
            ExpiresIn=3600  # 1 hour
        )
        
        return {
            'file_size': file_size,
            'presigned_url': presigned_url,
            'exists': True
        }
        
    except s3_client.exceptions.NoSuchKey:
        return {'exists': False, 'error': 'File not found'}
    except Exception as s3_error:
        error_msg = f"Failed to serve file: {str(s3_error)}"
        app_logger.error("S3 file serving failed", 
                      filepath=filepath, error=str(s3_error))
        return {'exists': False, 'error': error_msg}


def delete_file_from_s3(filepath: str, app_logger):
    """Delete file from S3 storage."""
    if not s3_client:
        raise Exception("S3 client not initialized")
    
    try:
        # Get file size from S3 before deletion
        s3_object = s3_client.head_object(Bucket=STORAGE_BUCKET, Key=filepath)
        file_size = s3_object['ContentLength']
        
        # Delete from S3
        s3_client.delete_object(Bucket=STORAGE_BUCKET, Key=filepath)
        app_logger.info("File deleted from S3", 
                     filepath=filepath, 
                     file_size=file_size, backend='s3')
        return True, file_size, None
        
    except s3_client.exceptions.NoSuchKey:
        return False, 0, 'File not found'
    except Exception as s3_error:
        error_msg = f"Delete failed: {str(s3_error)}"
        app_logger.error("S3 deletion failed", 
                      filepath=filepath, error=str(s3_error))
        return False, 0, error_msg


def upload_chunk_to_s3(file_content: bytes, folder: str, filename: str, chunk_index: int, app_logger):
    """Upload chunk to S3 temporary location."""
    if not s3_client:
        raise Exception("S3 client not initialized")
    
    temp_key = f"temp/{folder}/{filename}.part{chunk_index}"
    
    try:
        s3_client.put_object(
            Bucket=STORAGE_BUCKET,
            Key=temp_key,
            Body=file_content
        )
        return True, None
    except Exception as s3_error:
        error_msg = f"Failed to store chunk: {str(s3_error)}"
        app_logger.error("S3 chunk upload failed", 
                      folder=folder, filename=filename, chunk_index=chunk_index,
                      error=str(s3_error))
        return False, error_msg


def combine_chunks_from_s3(folder: str, filename: str, total_chunks: int, app_logger):
    """Combine chunks from S3 temp location and upload final file."""
    if not s3_client:
        raise Exception("S3 client not initialized")
    
    try:
        # Combine all chunks from S3 temp location
        all_chunks_content = b''
        for i in range(total_chunks):
            chunk_key = f"temp/{folder}/{filename}.part{i}"
            try:
                chunk_obj = s3_client.get_object(Bucket=STORAGE_BUCKET, Key=chunk_key)
                all_chunks_content += chunk_obj['Body'].read()
                # Delete temporary chunk
                s3_client.delete_object(Bucket=STORAGE_BUCKET, Key=chunk_key)
            except s3_client.exceptions.NoSuchKey:
                return False, f"Missing chunk {i}"
        
        # Upload combined file to final location
        final_key = f"{folder}/{filename}"
        s3_client.put_object(
            Bucket=STORAGE_BUCKET,
            Key=final_key,
            Body=all_chunks_content
        )
        
        file_size = len(all_chunks_content)
        app_logger.info("File chunks combined and uploaded to S3", 
                      folder=folder, filename=filename,
                      file_size=file_size, total_chunks=total_chunks)
        return True, file_size, None
        
    except Exception as s3_error:
        error_msg = f"Failed to combine chunks: {str(s3_error)}"
        app_logger.error("S3 chunk combination failed", 
                      folder=folder, filename=filename,
                      error=str(s3_error))
        return False, 0, error_msg


def get_s3_client():
    """Get the global S3 client instance."""
    return s3_client
