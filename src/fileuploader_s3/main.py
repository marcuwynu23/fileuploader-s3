from flask import Flask, Blueprint, request, jsonify, render_template_string, Response, stream_with_context, send_from_directory
import os
from pathlib import Path
from dotenv import load_dotenv
from flask_cors import CORS
from werkzeug.utils import secure_filename
import markdown
import mimetypes
# Security functions now implemented inline to avoid OpenSSL dependencies
import re
import base64

# Optional S3/MinIO support (can be disabled to avoid OpenSSL dependencies)
USE_S3 = os.getenv("USE_S3", "false").lower() == "true"
boto3 = None
Config = None
if USE_S3:
    try:
        import boto3
        from botocore.client import Config
    except ImportError as e:
        print(f"Warning: S3 dependencies not available: {e}")
        print("Falling back to local storage only")
        USE_S3 = False

# Load environment variables before checking USE_S3
load_dotenv()

app = Flask(__name__)
CORS(app)
file_uploader = Blueprint("file_uploader", __name__)

# ---- Config ----
BASE_URL = os.getenv("BASE_URL", "http://localhost:2424")
ROUTE_PREFIX = os.getenv("ROUTE_PREFIX", "/api/bcloud/fileuploader")
BASE_FOLDER = os.getenv("BASE_FOLDER", "uploads")  # Local storage for static serving

# ---- Security Configuration ----
ALLOWED_MIME_TYPES = {
    # Images
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    # Documents
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    # Videos
    '.mp4': 'video/mp4',
    '.avi': 'video/x-msvideo',
    '.mov': 'video/quicktime',
    # Archives
    '.zip': 'application/zip',
    '.tar': 'application/x-tar',
    '.gz': 'application/gzip',
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

BLOCKED_PATTERNS = [
    r'\.\./',  # Parent directory traversal
    r'\.\.\\',  # Windows parent directory traversal
    r'^\.\./',  # Starting with parent directory
    r'^\.\.\\',  # Starting with Windows parent directory
    r'^/',  # Absolute paths
    r'^\\',  # Windows absolute paths
]

# ---- Security Functions ----
def validate_folder_name(folder: str) -> bool:
    """Validate folder name to prevent path traversal attacks."""
    if not folder or not isinstance(folder, str):
        return False
    if len(folder) > 255:
        return False
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, folder, re.IGNORECASE):
            return False
    if not re.match(r'^[a-zA-Z0-9._-]+$', folder):
        return False
    return True

def validate_filename(filename: str) -> bool:
    """Validate filename to prevent path traversal attacks."""
    if not filename or not isinstance(filename, str):
        return False
    if len(filename) > 255:
        return False
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return False
    invalid_chars = r'[<>:"|?*\x00-\x1f]'
    if re.search(invalid_chars, filename):
        return False
    return True

def get_safe_file_path(base_folder: str, folder: str, filename: str):
    """Create a safe file path preventing path traversal attacks."""
    if not validate_folder_name(folder) or not validate_filename(filename):
        return None
    try:
        base_path = Path(base_folder).resolve()
        folder_path = base_path / folder
        file_path = folder_path / filename
        file_path_resolved = file_path.resolve()
        base_path_resolved = base_path.resolve()
        try:
            file_path_resolved.relative_to(base_path_resolved)
            return file_path_resolved
        except ValueError:
            return None
    except (ValueError, OSError):
        return None

def get_mime_type(filename: str) -> str:
    """Get MIME type for a filename based on extension."""
    ext = Path(filename).suffix.lower()
    return ALLOWED_MIME_TYPES.get(ext, 'application/octet-stream')

def is_allowed_file_type(filename: str) -> bool:
    """Check if file type is allowed based on extension."""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_MIME_TYPES

def generate_public_url(base_url: str, folder: str, filename: str) -> str:
    """Generate a clean, Gmail-compatible public URL for a file."""
    clean_base_url = base_url.rstrip('/')
    return f"{clean_base_url}/uploads/{folder}/{filename}"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    sanitized = filename.replace(' ', '_')
    sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '', sanitized)
    if not sanitized or sanitized == '.' or sanitized == '..':
        sanitized = 'unnamed_file'
    return sanitized

def encrypt_key(folder: str, filename: str) -> str:
    """Simple XOR encryption for basic obfuscation."""
    SECRET_KEY = os.getenv("ENCRYPTION_KEY", "default_key")
    raw = f"{folder}/{filename}"
    result = []
    key_bytes = SECRET_KEY.encode()
    for i, char in enumerate(raw):
        result.append(chr(ord(char) ^ key_bytes[i % len(key_bytes)]))
    encrypted = ''.join(result)
    return base64.b64encode(encrypted.encode()).decode()

def decrypt_key(token: str):
    """Decrypt token using XOR and base64 decoding."""
    try:
        SECRET_KEY = os.getenv("ENCRYPTION_KEY", "default_key")
        decoded = base64.b64decode(token.encode()).decode()
        result = []
        key_bytes = SECRET_KEY.encode()
        for i, char in enumerate(decoded):
            result.append(chr(ord(char) ^ key_bytes[i % len(key_bytes)]))
        return ''.join(result)
    except Exception:
        return None

# S3/MinIO Configuration
STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT", "http://localhost:9000")
STORAGE_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "admin")
STORAGE_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "admin123")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "fileuploads")

# Ensure base uploads folder exists
Path(BASE_FOLDER).mkdir(parents=True, exist_ok=True)

# ---- Storage clients ----
s3_client = None
if USE_S3:
    # S3/MinIO client for cloud storage
    s3_client = boto3.client(
        "s3",
        endpoint_url=STORAGE_ENDPOINT,
        aws_access_key_id=STORAGE_ACCESS_KEY,
        aws_secret_access_key=STORAGE_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    
    # Ensure S3 bucket exists
    try:
        s3_client.head_bucket(Bucket=STORAGE_BUCKET)
    except:
        s3_client.create_bucket(Bucket=STORAGE_BUCKET)

# ---- Helper Functions ----
def create_folder_if_not_exists(folder_path: Path) -> bool:
    """Create folder if it doesn't exist."""
    try:
        folder_path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False

def save_file_locally(file, folder: str, filename: str, base_folder: str = None) -> tuple[bool, str]:
    """Save file to local storage for static serving."""
    try:
        if base_folder is None:
            base_folder = BASE_FOLDER
        folder_path = Path(base_folder) / folder
        if not create_folder_if_not_exists(folder_path):
            return False, "Failed to create folder"
            
        file_path = folder_path / filename
        file.save(str(file_path))
        return True, str(file_path)
    except Exception as e:
        return False, str(e)


@app.route("/")
def initial_render():
    with open("docs/documentation.md", "r", encoding="utf-8") as f:
        markdown_content = f.read()
    markdown_content = markdown_content.replace("{base}", BASE_URL)
    html_content = markdown.markdown(markdown_content)
    return render_template_string(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Uploader API</title>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
    )


# ---- Upload Single ----
@file_uploader.route("/upload", methods=["POST"])
def upload_file():
    """Upload a single file and return Gmail-compatible static URL."""
    folder = request.form.get("folder")
    if not folder or not validate_folder_name(folder):
        return jsonify({"error": "Invalid or missing folder name"}), 400

    file = request.files.get("file")
    if not file or not hasattr(file, 'filename') or file.filename == "":
        return jsonify({"error": "No file provided"}), 400

    # Validate and sanitize filename
    original_filename = file.filename
    if not validate_filename(original_filename):
        return jsonify({"error": "Invalid filename"}), 400
        
    if not is_allowed_file_type(original_filename):
        return jsonify({"error": f"File type not allowed. Allowed types: {list(ALLOWED_MIME_TYPES.keys())}"}), 400

    filename = sanitize_filename(original_filename)
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({"error": f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"}), 400

    try:
        # Save to local storage for static serving
        base_folder = os.getenv('BASE_FOLDER', BASE_FOLDER)
        success, result = save_file_locally(file, folder, filename, base_folder)
        if not success:
            return jsonify({"error": f"Failed to save file: {result}"}), 500
        
        # Also save to S3 for backup (if enabled)
        if USE_S3 and s3_client:
            file.seek(0)  # Reset file pointer for S3 upload
            s3_client.upload_fileobj(file, STORAGE_BUCKET, f"{folder}/{filename}")
        
        # Generate Gmail-compatible static URL
        public_url = generate_public_url(BASE_URL, folder, filename)
        
        return jsonify({
            "message": f"File successfully uploaded to /uploads/{folder}/{filename}",
            "url": public_url,
            "filename": filename,
            "folder": folder,
            "size": file_size,
            "mime_type": get_mime_type(filename)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


# ---- Upload Multiple ----
@file_uploader.route("/upload_multi", methods=["POST"])
def upload_multiple_files():
    """Upload multiple files and return Gmail-compatible static URLs."""
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
        
        try:
            # Save to local storage
            success, result = save_file_locally(file, folder, filename)
            if not success:
                errors.append(f"Failed to save {original_filename}: {result}")
                continue
            
            # Also save to S3 (if enabled)
            if USE_S3 and s3_client:
                file.seek(0)
                s3_client.upload_fileobj(file, STORAGE_BUCKET, f"{folder}/{filename}")
            
            # Generate public URL
            public_url = generate_public_url(BASE_URL, folder, filename)
            
            uploaded.append({
                "filename": filename,
                "original_filename": original_filename,
                "url": public_url,
                "size": file_size,
                "mime_type": get_mime_type(filename)
            })
            
        except Exception as e:
            errors.append(f"Failed to upload {original_filename}: {str(e)}")

    response_data = {
        "message": f"{len(uploaded)} files uploaded successfully.",
        "uploaded": uploaded,
        "total_uploaded": len(uploaded)
    }
    
    if errors:
        response_data["errors"] = errors
        response_data["total_errors"] = len(errors)
    
    return jsonify(response_data), 200


# ---- Upload Single File in Chunks ----
@file_uploader.route("/upload_chunk", methods=["POST"])
def upload_chunk():
    """Upload a file in chunks and return Gmail-compatible static URL."""
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
        return jsonify({"error": f"File type not allowed. Allowed types: {list(ALLOWED_MIME_TYPES.keys())}"}), 400

    filename = sanitize_filename(original_filename)
    
    try:
        # Create temporary folder for chunks
        base_folder = os.getenv('BASE_FOLDER', BASE_FOLDER)
        temp_folder = Path(base_folder) / "temp" / folder
        temp_folder.mkdir(parents=True, exist_ok=True)
        
        # Save chunk
        chunk_path = temp_folder / f"{filename}.part{chunk_index}"
        file.save(str(chunk_path))
        
        # Check if this is the last chunk
        if chunk_index == total_chunks - 1:
            # Combine all chunks
            final_folder = Path(base_folder) / folder
            final_folder.mkdir(parents=True, exist_ok=True)
            final_path = final_folder / filename
            
            # Combine chunks into final file
            with open(final_path, 'wb') as outfile:
                for i in range(total_chunks):
                    chunk_file = temp_folder / f"{filename}.part{i}"
                    if chunk_file.exists():
                        with open(chunk_file, 'rb') as infile:
                            outfile.write(infile.read())
                        chunk_file.unlink()  # Remove chunk
            
            # Remove temp folder if empty
            try:
                temp_folder.rmdir()
                Path(BASE_FOLDER) / "temp" / folder
                Path(BASE_FOLDER) / "temp"
                # Try to remove folders if they're empty
                try:
                    (Path(BASE_FOLDER) / "temp" / folder).rmdir()
                    (Path(BASE_FOLDER) / "temp").rmdir()
                except OSError:
                    pass
            except OSError:
                pass
            
            # Upload to S3 (if enabled)
            if USE_S3 and s3_client:
                with open(final_path, 'rb') as final_file:
                    s3_client.upload_fileobj(final_file, STORAGE_BUCKET, f"{folder}/{filename}")
            
            # Generate Gmail-compatible static URL
            public_url = generate_public_url(BASE_URL, folder, filename)
            file_size = final_path.stat().st_size
            
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
        return jsonify({"error": f"Chunk upload failed: {str(e)}"}), 500


# ---- Upload Multiple Files in Chunks ----
@file_uploader.route("/upload_multi_chunk", methods=["POST"])
def upload_multiple_chunks():
    """Upload multiple files in chunks and return Gmail-compatible static URLs."""
    folder = request.form.get("folder")
    if not folder or not validate_folder_name(folder):
        return jsonify({"error": "Invalid or missing folder name"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided"}), 400

    chunk_index = int(request.form.get("dzchunkindex", 0))
    total_chunks = int(request.form.get("dztotalchunkcount", 1))
    
    uploaded_files = []
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
        
        try:
            # Create temporary folder for chunks
            base_folder = os.getenv('BASE_FOLDER', BASE_FOLDER)
            temp_folder = Path(base_folder) / "temp" / folder
            temp_folder.mkdir(parents=True, exist_ok=True)
            
            # Save chunk
            chunk_path = temp_folder / f"{filename}.part{chunk_index}"
            file.save(str(chunk_path))
            
            # Check if this is the last chunk for this file
            if chunk_index == total_chunks - 1:
                # Combine all chunks
                final_folder = Path(base_folder) / folder
                final_folder.mkdir(parents=True, exist_ok=True)
                final_path = final_folder / filename
                
                # Combine chunks into final file
                with open(final_path, 'wb') as outfile:
                    for i in range(total_chunks):
                        chunk_file = temp_folder / f"{filename}.part{i}"
                        if chunk_file.exists():
                            with open(chunk_file, 'rb') as infile:
                                outfile.write(infile.read())
                            chunk_file.unlink()  # Remove chunk
                
                # Upload to S3 (if enabled)
                if USE_S3 and s3_client:
                    with open(final_path, 'rb') as final_file:
                        s3_client.upload_fileobj(final_file, STORAGE_BUCKET, f"{folder}/{filename}")
                
                # Generate Gmail-compatible static URL
                public_url = generate_public_url(BASE_URL, folder, filename)
                file_size = final_path.stat().st_size
                
                uploaded_files.append({
                    "filename": filename,
                    "original_filename": original_filename,
                    "url": public_url,
                    "size": file_size,
                    "mime_type": get_mime_type(filename)
                })
            
        except Exception as e:
            errors.append(f"Failed to process {original_filename}: {str(e)}")
    
    # Clean up temp folders if all files are complete
    if uploaded_files:
        try:
            temp_folder = Path(base_folder) / "temp" / folder
            if temp_folder.exists() and not any(temp_folder.iterdir()):
                temp_folder.rmdir()
                temp_base = Path(base_folder) / "temp"
                if temp_base.exists():
                    temp_base.rmdir()
        except OSError:
            pass
    
    if uploaded_files:
        response_data = {
            "message": f"{len(uploaded_files)} file(s) uploaded successfully.",
            "files": uploaded_files,
            "total_uploaded": len(uploaded_files)
        }
    else:
        response_data = {"message": f"Chunk {chunk_index + 1} uploaded successfully."}
    
    if errors:
        response_data["errors"] = errors
        response_data["total_errors"] = len(errors)
    
    return jsonify(response_data), 200


# ---- Static File Serving (Gmail Compatible) ----
@app.route("/uploads/<path:filepath>", methods=["GET"])
def serve_static_file(filepath):
    """Serve files directly from local storage with proper MIME types.
    
    This endpoint provides Gmail-compatible static URLs like:
    /uploads/folder/filename.ext
    """
    try:
        # Split filepath into folder and filename
        path_parts = filepath.split('/', 1)
        if len(path_parts) != 2:
            return jsonify({"error": "Invalid file path"}), 400
            
        folder, filename = path_parts
        
        # Validate folder and filename
        if not validate_folder_name(folder) or not validate_filename(filename):
            return jsonify({"error": "Invalid folder or filename"}), 400
        
        # Get safe file path
        base_folder = os.getenv('BASE_FOLDER', BASE_FOLDER)
        file_path = get_safe_file_path(base_folder, folder, filename)
        if not file_path:
            return jsonify({"error": "Invalid folder or filename"}), 400
        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404
        
        # Get MIME type
        mime_type = get_mime_type(filename)
        
        # Serve file with proper headers for Gmail compatibility
        response = send_from_directory(
            str(file_path.parent),
            file_path.name,
            mimetype=mime_type,
            as_attachment=False
        )
        
        # Add Gmail-friendly headers
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 year cache
        
        return response
        
    except Exception as e:
        return jsonify({"error": f"Error serving file: {str(e)}"}), 500

# ---- Legacy Render Endpoint (Backward Compatibility) ----
@file_uploader.route("/render/<token>", methods=["GET"])
def render_file(token):
    """Legacy render endpoint for backward compatibility.
    
    Returns redirect to the new static URL.
    """
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
        static_url = generate_public_url(BASE_URL, folder, filename)
        
        # Redirect to new static URL
        from flask import redirect
        return redirect(static_url, code=301)
        
    except Exception as e:
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500


# ---- Delete ----
@file_uploader.route("/delete/<token>", methods=["DELETE"])
def delete_file(token):
    """Delete a file from both local storage and S3."""
    key = decrypt_key(token)
    if not key:
        return jsonify({"error": "Invalid token"}), 400

    try:
        # Extract folder and filename
        path_parts = key.split('/', 1)
        if len(path_parts) != 2:
            return jsonify({"error": "Invalid file key"}), 400
            
        folder, filename = path_parts
        
        # Validate folder and filename for security
        if not validate_folder_name(folder) or not validate_filename(filename):
            return jsonify({"error": "Invalid folder or filename"}), 400
        
        # Check for nested folders (not supported)
        if '/' in folder or '\\' in folder:
            return jsonify({"error": "Nested folders not supported"}), 400
        
        # Delete from local storage
        base_folder = os.getenv('BASE_FOLDER', BASE_FOLDER)
        file_path = get_safe_file_path(base_folder, folder, filename)
        if file_path and file_path.exists():
            file_path.unlink()
            
            # Try to remove folder if empty
            try:
                folder_path = file_path.parent
                if folder_path.exists() and not any(folder_path.iterdir()):
                    folder_path.rmdir()
            except OSError:
                pass  # Folder not empty or other error
        
        # Delete from S3 (if enabled)
        if USE_S3 and s3_client:
            s3_client.delete_object(Bucket=STORAGE_BUCKET, Key=key)
        
        return jsonify({
            "message": f"File {filename} deleted successfully",
            "filename": filename,
            "folder": folder
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Delete failed: {str(e)}"}), 500


# Register blueprint
app.register_blueprint(file_uploader, url_prefix=ROUTE_PREFIX)


def main():
    app.run(host="0.0.0.0", port=2424, debug=True)


if __name__ == "__main__":
    main()
