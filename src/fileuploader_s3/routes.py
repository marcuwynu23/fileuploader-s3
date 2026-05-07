"""API routes module for fileuploader-s3 application."""

import os
import time
import traceback
from flask import Blueprint, request, jsonify, Response, redirect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from .config import (
    BASE_URL, MAX_FILE_SIZE, MAX_CHUNK_SIZE, 
    USE_PROMETHEUS, USE_LOKI
)
from .security import (
    validate_folder_name, validate_filename, is_allowed_file_type,
    sanitize_filename, validate_file_content, get_mime_type
)
from .utils import decrypt_key
from .storage import (
    upload_file_to_s3, serve_file_from_s3, delete_file_from_s3,
    upload_chunk_to_s3, combine_chunks_from_s3, get_s3_client
)

# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

file_uploader = Blueprint("file_uploader", __name__)


# Helper functions for routes
def get_app_logger():
    """Get the application logger instance."""
    from .logging_config import setup_logging
    return setup_logging()


# Global variable to store prometheus metrics once initialized
_prometheus_metrics = None

def get_prometheus_metrics():
    """Get prometheus metrics if available."""
    global _prometheus_metrics
    if _prometheus_metrics is not None:
        return _prometheus_metrics
        
    try:
        from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
        registry = CollectorRegistry(auto_describe=True)
        
        _prometheus_metrics = {
            'upload_requests_total': Counter('fileuploader_uploads_total', 'Total upload requests', ['method', 'status'], registry=registry),
            'upload_duration_seconds': Histogram('fileuploader_upload_duration_seconds', 'Upload duration in seconds', registry=registry),
            'delete_requests_total': Counter('fileuploader_deletes_total', 'Total delete requests', ['method', 'status'], registry=registry),
            'file_serve_requests_total': Counter('fileuploader_serves_total', 'Total file serve requests', ['status'], registry=registry),
            'file_size_bytes': Histogram('fileuploader_file_size_bytes', 'Uploaded file size in bytes', ['file_type'], registry=registry),
            'active_uploads': Gauge('fileuploader_active_uploads', 'Number of active uploads', registry=registry),
            'storage_used_bytes': Gauge('fileuploader_storage_used_bytes', 'Storage used in bytes', registry=registry),
            'registry': registry
        }
    except ImportError:
        pass
    return _prometheus_metrics


# ---- Upload Single ----
@file_uploader.route("/upload", methods=["POST"])
@limiter.limit(limit_value="10 per minute")
def upload_file():
    """Upload a single file and return Gmail-compatible static URL."""
    app_logger = get_app_logger()
    prometheus_metrics = get_prometheus_metrics()
    
    start_time = time.time()
    
    folder = request.form.get("folder")
    if not folder or not validate_folder_name(folder):
        if prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='400').inc()
        return jsonify({"error": "Invalid or missing folder name"}), 400

    file = request.files.get("file")
    if not file or not hasattr(file, 'filename') or file.filename == "":
        if prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='400').inc()
        return jsonify({"error": "No file provided"}), 400

    # Validate and sanitize filename
    original_filename = file.filename
    if not validate_filename(original_filename):
        if prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='400').inc()
        return jsonify({"error": "Invalid filename"}), 400
        
    if not is_allowed_file_type(original_filename):
        if prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='400').inc()
        from .config import ALLOWED_MIME_TYPES
        return jsonify({"error": f"File type not allowed. Allowed types: {list(ALLOWED_MIME_TYPES.keys())}"}), 400

    filename = sanitize_filename(original_filename)
    file_type = os.path.splitext(filename)[1].lower()
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_size > MAX_FILE_SIZE:
        if prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='400').inc()
        return jsonify({"error": f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"}), 400

    try:
        # Track active uploads
        if prometheus_metrics:
            prometheus_metrics['active_uploads'].inc()
        
        # S3 storage is mandatory - if we reach here, S3 client should be available
        s3_client = get_s3_client()
        if not s3_client:
            app_logger.error("S3 client not available", 
                          folder=folder, file_name=filename, 
                          client_ip=request.remote_addr)
            if prometheus_metrics:
                prometheus_metrics['upload_requests_total'].labels(method='POST', status='500').inc()
                prometheus_metrics['active_uploads'].dec()
            return jsonify({"error": "S3 client not available - check configuration"}), 500
        
        # Read file content before any processing to avoid file handle issues
        file.seek(0)
        file_content = file.read()
        
        # Upload to S3 storage
        app_logger.info(f"Uploading to S3 storage")
        success, error_msg = upload_file_to_s3(file_content, folder, filename, app_logger)
        
        if not success:
            if prometheus_metrics:
                prometheus_metrics['upload_requests_total'].labels(method='POST', status='500').inc()
                prometheus_metrics['active_uploads'].dec()
            return jsonify({"error": error_msg}), 500
        
        # Generate Gmail-compatible static URL
        from .utils import generate_public_url
        public_url = generate_public_url(BASE_URL, folder, filename)
        duration = time.time() - start_time
        
        # Log success with structured data
        app_logger.info("File uploaded successfully", 
                      folder=folder, file_name=filename, 
                      file_size=file_size, duration=duration,
                      url=public_url, backend='s3',
                      client_ip=request.remote_addr)
        
        # Update Prometheus metrics
        if prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='200').inc()
            prometheus_metrics['upload_duration_seconds'].observe(duration)
            prometheus_metrics['file_size_bytes'].labels(file_type=file_type).observe(file_size)
            prometheus_metrics['active_uploads'].dec()
            prometheus_metrics['storage_used_bytes'].inc(file_size)
        
        return jsonify({
            "message": f"File successfully uploaded to /uploads/{folder}/{filename}",
            "url": public_url,
            "filename": filename,
            "folder": folder,
            "size": file_size,
            "mime_type": get_mime_type(filename)
        }), 200
        
    except Exception as e:
        app_logger.error("Upload failed", 
                      folder=folder, file_name=filename,
                      error=str(e), traceback=traceback.format_exc(),
                      client_ip=request.remote_addr)
        if prometheus_metrics:
            prometheus_metrics['upload_requests_total'].labels(method='POST', status='500').inc()
            prometheus_metrics['active_uploads'].dec()
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


# ---- Upload Multiple ----
@file_uploader.route("/upload_multi", methods=["POST"])
@limiter.limit(limit_value="20 per minute")
def upload_multiple_files():
    """Upload multiple files and return Gmail-compatible static URLs."""
    app_logger = get_app_logger()
    prometheus_metrics = get_prometheus_metrics()
    
    folder = request.form.get("folder")
    if not folder or not validate_folder_name(folder):
        return jsonify({"error": "Invalid or missing folder name"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    uploaded = []
    errors = []
    
    for file in files:
        if not file or file.filename == "":
            continue
            
        original_filename = file.filename
        if not validate_filename(original_filename):
            errors.append(f"Invalid filename: {original_filename}")
            continue
            
        if not is_allowed_file_type(original_filename):
            errors.append(f"File type not allowed: {original_filename}")
            continue

        filename = sanitize_filename(original_filename)
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            errors.append(f"File too large: {original_filename}")
            continue
        
        s3_client = get_s3_client()
        if not s3_client:
            errors.append(f"S3 client not available: {original_filename}")
            continue
        
        # Read file content
        file.seek(0)
        file_content = file.read()
        
        # Upload to S3
        success, error_msg = upload_file_to_s3(file_content, folder, filename, app_logger)
        
        if success:
            from .utils import generate_public_url
            public_url = generate_public_url(BASE_URL, folder, filename)
            uploaded.append({
                "filename": filename,
                "original_filename": original_filename,
                "url": public_url,
                "size": file_size,
                "mime_type": get_mime_type(filename)
            })
        else:
            errors.append(f"Failed to upload {original_filename}: {error_msg}")
    
    if uploaded:
        response_data = {
            "message": f"{len(uploaded)} file(s) uploaded successfully.",
            "files": uploaded,
            "uploaded": uploaded,  # Add for backward compatibility
            "total_uploaded": len(uploaded)
        }
    else:
        response_data = {"message": "No files uploaded successfully."}
    
    if errors:
        response_data["errors"] = errors
        response_data["total_errors"] = len(errors)  # Add total_errors for tests
    
    return jsonify(response_data)


# ---- Upload Multiple Chunk ----
@file_uploader.route("/upload_multi_chunk", methods=["POST"])
@limiter.limit(limit_value="20 per minute")
def upload_multiple_chunk():
    """Upload multiple files in chunks and return Gmail-compatible static URLs."""
    app_logger = get_app_logger()
    prometheus_metrics = get_prometheus_metrics()
    
    folder = request.form.get("folder")
    if not folder or not validate_folder_name(folder):
        return jsonify({"error": "Invalid or missing folder name"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    chunk_index = int(request.form.get("dzchunkindex", 0))
    total_chunks = int(request.form.get("dztotalchunkcount", 1))

    uploaded = []
    errors = []
    
    for file in files:
        if not file or file.filename == "":
            continue
            
        original_filename = file.filename
        if not validate_filename(original_filename):
            errors.append(f"Invalid filename: {original_filename}")
            continue
            
        if not is_allowed_file_type(original_filename):
            errors.append(f"File type not allowed: {original_filename}")
            continue

        filename = sanitize_filename(original_filename)
        
        # Check chunk size
        file.seek(0, os.SEEK_END)
        chunk_size = file.tell()
        file.seek(0)
        
        if chunk_size > MAX_CHUNK_SIZE:
            errors.append(f"Chunk too large: {original_filename}")
            continue
        
        # Read chunk content
        file_content = file.read()
        
        s3_client = get_s3_client()
        if not s3_client:
            errors.append(f"S3 client not available: {original_filename}")
            continue
        
        # Upload chunk to S3
        success, error_msg = upload_chunk_to_s3(file_content, folder, filename, chunk_index, app_logger)
        
        if not success:
            errors.append(f"Failed to upload chunk {original_filename}: {error_msg}")
            continue
        
        # If this is the last chunk, combine and upload final file
        if chunk_index == total_chunks - 1:
            combine_success, file_size, combine_error = combine_chunks_from_s3(folder, filename, total_chunks, app_logger)
            
            if combine_success:
                from .utils import generate_public_url
                public_url = generate_public_url(BASE_URL, folder, filename)
                uploaded.append({
                    "filename": filename,
                    "original_filename": original_filename,
                    "url": public_url,
                    "size": file_size,
                    "mime_type": get_mime_type(filename)
                })
            else:
                errors.append(f"Failed to combine chunks {original_filename}: {combine_error}")
    
    if uploaded:
        response_data = {
            "message": f"{len(uploaded)} file(s) uploaded successfully.",
            "files": uploaded,
            "uploaded": uploaded,  # Add for backward compatibility
            "total_uploaded": len(uploaded)
        }
    else:
        response_data = {"message": f"Chunk {chunk_index + 1} uploaded successfully."}
    
    if errors:
        response_data["errors"] = errors
        response_data["total_errors"] = len(errors)  # Add total_errors for tests
    
    return jsonify(response_data)




# ---- Upload Chunk ----
@file_uploader.route("/upload_chunk", methods=["POST"])
@limiter.limit(limit_value="20 per minute")
def upload_chunk():
    """Upload a file in chunks and return Gmail-compatible static URL."""
    app_logger = get_app_logger()
    prometheus_metrics = get_prometheus_metrics()
    
    folder = request.form.get("folder")
    if not folder or not validate_folder_name(folder):
        return jsonify({"error": "Invalid or missing folder name"}), 400

    file = request.files.get("file")
    if not file or not hasattr(file, 'filename') or file.filename == "":
        return jsonify({"error": "No file provided"}), 400

    chunk_index = int(request.form.get("dzchunkindex", 0))
    total_chunks = int(request.form.get("dztotalchunkcount", 1))

    # Validate and sanitize filename
    original_filename = file.filename
    if not validate_filename(original_filename):
        return jsonify({"error": "Invalid filename"}), 400
        
    if not is_allowed_file_type(original_filename):
        return jsonify({"error": f"File type not allowed. Allowed types: {list(get_allowed_mime_types().keys())}"}), 400

    filename = sanitize_filename(original_filename)
    
    try:
        # For S3-only storage, we need to handle chunk uploads differently
        # Store chunks in memory or temporary S3 location, then combine for final upload
        
        # Validate chunk size
        file.seek(0, os.SEEK_END)
        chunk_size = file.tell()
        file.seek(0)
        
        if chunk_size > MAX_CHUNK_SIZE:
            return jsonify({"error": f"Chunk too large. Maximum size: {MAX_CHUNK_SIZE // (1024*1024)}MB"}), 400
        
        # Read chunk content for validation
        file_content = file.read()
        
        # Validate chunk content (only first chunk)
        expected_mime = get_mime_type(filename)
        if chunk_index == 0 and not validate_file_content(file_content, expected_mime):
            return jsonify({"error": f"File content does not match expected type: {expected_mime}"}), 400
        
        s3_client = get_s3_client()
        if not s3_client:
            return jsonify({"error": "S3 client not available - check configuration"}), 500
        
        # For S3-only storage, we'll handle chunk uploads by storing in a temporary S3 location
        temp_key = f"temp/{folder}/{filename}.part{chunk_index}"
        
        success, error_msg = upload_chunk_to_s3(file_content, folder, filename, chunk_index, app_logger)
        
        if not success:
            return jsonify({"error": error_msg}), 500
        
        # Check if this is the last chunk
        if chunk_index == total_chunks - 1:
            # Combine all chunks from S3 temp location
            success, file_size, error_msg = combine_chunks_from_s3(folder, filename, total_chunks, app_logger)
            
            if not success:
                return jsonify({"error": error_msg}), 500
            
            # Generate Gmail-compatible static URL
            from .utils import generate_public_url
            public_url = generate_public_url(BASE_URL, folder, filename)
            
            return jsonify({
                "message": f"File successfully uploaded to /uploads/{folder}/{filename}",
                "url": public_url,
                "filename": filename,
                "folder": folder,
                "size": file_size,
                "mime_type": get_mime_type(filename)
            }), 200
        else:
            return jsonify({"message": f"Chunk {chunk_index + 1} uploaded successfully."}), 200
            
    except Exception as e:
        app_logger.error(f"Chunk upload failed for {folder}/{filename}: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Chunk upload failed: {str(e)}"}), 500


# ---- Static File Serving (S3) - will be registered directly on app ----
def serve_static_file(filepath):
    """Serve files directly from S3 storage with proper MIME types.
    
    This endpoint provides Gmail-compatible static URLs like:
    /uploads/folder/filename.ext
    """
    app_logger = get_app_logger()
    prometheus_metrics = get_prometheus_metrics()
    
    start_time = time.time()
    
    try:
        # S3 storage is mandatory - if we reach here, S3 client should be available
        s3_client = get_s3_client()
        if not s3_client:
            app_logger.error("S3 client not available for file serving", 
                          filepath=filepath, 
                          s3_client_available=s3_client is not None,
                          client_ip=request.remote_addr)
            if prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='500').inc()
            return jsonify({"error": "S3 client not available - check configuration"}), 500
        
        # Validate filepath structure and prevent path traversal
        if not filepath or '..' in filepath or '\\' in filepath:
            if prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='400').inc()
            return jsonify({"error": "Invalid file path"}), 400
        
        # Split filepath into components and validate each
        path_parts = filepath.split('/')
        if len(path_parts) < 2:
            if prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='400').inc()
            return jsonify({"error": "Invalid file path format"}), 400
        
        folder = '/'.join(path_parts[:-1])  # Support nested folders
        filename = path_parts[-1]
        
        # Validate folder and filename separately
        if not validate_folder_name(folder) or not validate_filename(filename):
            if prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='400').inc()
            return jsonify({"error": "Invalid folder or filename"}), 400
        
        # S3 object key
        s3_key = f"{folder}/{filename}"
        
        file_info = serve_file_from_s3(s3_key, app_logger)
        
        if not file_info['exists']:
            if prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='404').inc()
            return jsonify({"error": file_info['error']}), 404
        
        file_size = file_info['file_size']
        mime_type = get_mime_type(filename)
        
        # For small files, serve directly from S3
        if file_size <= 10 * 1024 * 1024:  # 10MB threshold
            s3_client = get_s3_client()
            s3_response = s3_client.get_object(Bucket=get_storage_bucket(), Key=s3_key)
            content = s3_response['Body'].read()
            
            response = Response(
                content,
                200,
                mimetype=mime_type,
                direct_passthrough=True
            )
            
            # Add Gmail-friendly headers
            response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 year cache
            response.headers['Content-Length'] = str(len(content))
            
            # Log successful file serving
            duration = time.time() - start_time
            app_logger.info("File served successfully from S3", 
                          folder=folder, file_name=filename,
                          file_size=file_size, duration=duration,
                          backend='s3', client_ip=request.remote_addr)
            
            if prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='200').inc()
            
            return response
        else:
            # For large files, redirect to presigned URL
            response = Response(
                redirect(file_info['presigned_url'], code=302),
                302
            )
            
            # Log redirect
            duration = time.time() - start_time
            app_logger.info("File redirect to S3 presigned URL", 
                          folder=folder, file_name=filename,
                          file_size=file_size, duration=duration,
                          backend='s3', client_ip=request.remote_addr)
            
            if prometheus_metrics:
                prometheus_metrics['file_serve_requests_total'].labels(status='302').inc()
            
            return response
            
    except Exception as e:
        app_logger.error("File serving failed", 
                      filepath=filepath, error=str(e), 
                      traceback=traceback.format_exc(),
                      client_ip=request.remote_addr)
        if prometheus_metrics:
            prometheus_metrics['file_serve_requests_total'].labels(status='500').inc()
        return jsonify({"error": "Internal server error"}), 500


# ---- Legacy Render Endpoint ----
@file_uploader.route("/render/<token>", methods=["GET"])
@limiter.limit(limit_value="20 per minute")
def render_file(token):
    """Returns redirect to new static URL."""
    app_logger = get_app_logger()
    
    key = decrypt_key(token)
    if not key:
        return jsonify({"error": "Invalid token"}), 400

    try:
        # Extract folder and filename from key
        path_parts = key.split('/', 1)
        if len(path_parts) != 2:
            return jsonify({"error": "Invalid file key"}), 400
            
        folder, filename = path_parts
        
        # Generate new static URL
        from .utils import generate_public_url
        static_url = generate_public_url(BASE_URL, folder, filename)
        
        # Redirect to new static URL
        return redirect(static_url, code=301)
        
    except Exception as e:
        app_logger.error(f"Error processing legacy render token {token}: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500


# ---- Delete Endpoint ----
@file_uploader.route("/delete/<token>", methods=["DELETE"])
@limiter.limit(limit_value="20 per minute")
def delete_file(token):
    """Delete a file from S3 storage."""
    app_logger = get_app_logger()
    prometheus_metrics = get_prometheus_metrics()
    
    start_time = time.time()
    
    key = decrypt_key(token)
    if not key:
        if prometheus_metrics:
            prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='400').inc()
        return jsonify({"error": "Invalid token"}), 400

    try:
        # Extract folder and filename
        path_parts = key.split('/', 1)
        if len(path_parts) != 2:
            if prometheus_metrics:
                prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='400').inc()
            return jsonify({"error": "Invalid file key"}), 400
            
        folder, filename = path_parts
        
        # Validate folder and filename for security
        if not validate_folder_name(folder) or not validate_filename(filename):
            if prometheus_metrics:
                prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='400').inc()
            return jsonify({"error": "Invalid folder or filename"}), 400
        
                
        # Delete from S3
        success, file_size, error_msg = delete_file_from_s3(key, app_logger)
        
        if not success:
            if prometheus_metrics:
                prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='500').inc()
            return jsonify({"error": error_msg}), 500
        
        duration = time.time() - start_time
        
        # Log successful deletion
        app_logger.info("File deleted successfully", 
                      folder=folder, file_name=filename,
                      file_size=file_size, duration=duration,
                      backend='s3', client_ip=request.remote_addr)
        
        # Update Prometheus metrics
        if prometheus_metrics:
            prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='200').inc()
            prometheus_metrics['storage_used_bytes'].dec(file_size)
        
        return jsonify({
            "message": f"File {filename} deleted successfully",
            "filename": filename,
            "folder": folder
        }), 200
        
    except Exception as e:
        app_logger.error("Delete failed", 
                      folder=folder if 'folder' in locals() else 'unknown',
                      file_name=filename if 'filename' in locals() else 'unknown',
                      error=str(e), traceback=traceback.format_exc(),
                      client_ip=request.remote_addr)
        if prometheus_metrics:
            prometheus_metrics['delete_requests_total'].labels(method='DELETE', status='500').inc()
        return jsonify({"error": f"Delete failed: {str(e)}"}), 500


def get_allowed_mime_types():
    """Get allowed MIME types from config."""
    from .config import ALLOWED_MIME_TYPES
    return ALLOWED_MIME_TYPES


def get_storage_bucket():
    """Get storage bucket name from config."""
    from .config import STORAGE_BUCKET
    return STORAGE_BUCKET
