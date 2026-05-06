# Bucket Storage File Uploader API Documentation

A modern, secure, and scalable file storage API built with Flask and S3/MinIO backend.

## Quick Start

```bash
# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your S3 configuration

# Run the application
uv run app
```

## Table of Contents

- [API Overview](#api-overview)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
- [File Types](#supported-file-types)
- [Security Features](#security-features)
- [Configuration](#configuration)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Production Deployment](#production-deployment)
- [Examples](#examples)

---

## API Overview

The File Uploader S3 API provides RESTful endpoints for file management with the following features:

- S3/MinIO Storage: Scalable cloud storage with automatic bucket management
- Multiple Upload Methods: Single file, multiple files, and chunked uploads
- Static URLs: Direct file access with Gmail-compatible URLs
- Security: Path traversal protection, file validation, and encryption
- Observability: Prometheus metrics and structured logging
- Performance: Optimized for speed with caching and CDN support

Base URL: `{base_url}/api/fileuploader`

---

## Authentication

The API uses token-based authentication for delete operations. Upload operations are open by design but can be protected by reverse proxy.

### Token Generation

Files are automatically assigned encrypted tokens for secure deletion:

```json
{
  "token": "gASVBHFhYmFjZXN5ZGF0aW9uL2RvY3VtZW50cy9zYW1wbGUucGRm"
}
```

### Token Usage

Include the token in delete requests:

```bash
curl -X DELETE {base_url}/api/fileuploader/delete/{token}
```

---

## Endpoints

### 1. Upload Single File

**Endpoint**: `POST /api/fileuploader/upload`

**Description**: Upload a single file to a specified folder.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `folder` | form-data | Yes | Target folder name |
| `file` | form-data | Yes | File to upload |

**Request Example**:
```bash
curl -X POST {base_url}/api/fileuploader/upload \
  -F "folder=documents" \
  -F "file=@example.pdf"
```

**Response (200 OK)**:
```json
{
  "message": "File successfully uploaded to /uploads/documents/example.pdf",
  "url": "{base_url}/uploads/documents/example.pdf",
  "filename": "example.pdf",
  "folder": "documents",
  "size": 1024000,
  "mime_type": "application/pdf"
}
```

**Error Responses**:
```json
{"error": "Invalid or missing folder name"}  // 400 Bad Request
{"error": "No file provided"}                 // 400 Bad Request
{"error": "File too large"}                    // 400 Bad Request
{"error": "S3 client not available"}           // 500 Internal Server Error
```

---

### 2. Upload Multiple Files

**Endpoint**: `POST /api/fileuploader/upload_multi`

**Description**: Upload multiple files to a specified folder in a single request.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `folder` | form-data | Yes | Target folder name |
| `files` | form-data | Yes | Files to upload (repeat key for each file) |

**Request Example**:
```bash
curl -X POST {base_url}/api/fileuploader/upload_multi \
  -F "folder=images" \
  -F "files=@image1.jpg" \
  -F "files=@image2.png" \
  -F "files=@logo.gif"
```

**Response (200 OK)**:
```json
{
  "message": "3 file(s) uploaded successfully.",
  "files": [
    {
      "filename": "image1.jpg",
      "original_filename": "image1.jpg",
      "url": "{base_url}/uploads/images/image1.jpg",
      "size": 512000,
      "mime_type": "image/jpeg"
    },
    {
      "filename": "image2.png",
      "original_filename": "image2.png",
      "url": "{base_url}/uploads/images/image2.png",
      "size": 256000,
      "mime_type": "image/png"
    },
    {
      "filename": "logo.gif",
      "original_filename": "logo.gif",
      "url": "{base_url}/uploads/images/logo.gif",
      "size": 128000,
      "mime_type": "image/gif"
    }
  ],
  "total_uploaded": 3
}
```

---

### 3. Upload File in Chunks

**Endpoint**: `POST /api/fileuploader/upload_chunk`

**Description**: Upload large files in chunks for better reliability and resume capability.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `folder` | form-data | Yes | Target folder name |
| `file` | form-data | Yes | File chunk |
| `dzchunkindex` | form-data | Yes | Index of current chunk (0-based) |
| `dztotalchunkcount` | form-data | Yes | Total number of chunks |

**Request Example**:
```bash
# Upload first chunk
curl -X POST {base_url}/api/fileuploader/upload_chunk \
  -F "folder=videos" \
  -F "file=@bigfile.mp4.part0" \
  -F "dzchunkindex=0" \
  -F "dztotalchunkcount=3"

# Upload second chunk
curl -X POST {base_url}/api/fileuploader/upload_chunk \
  -F "folder=videos" \
  -F "file=@bigfile.mp4.part1" \
  -F "dzchunkindex=1" \
  -F "dztotalchunkcount=3"

# Upload final chunk
curl -X POST {base_url}/api/fileuploader/upload_chunk \
  -F "folder=videos" \
  -F "file=@bigfile.mp4.part2" \
  -F "dzchunkindex=2" \
  -F "dztotalchunkcount=3"
```

**Response (Final Chunk - 200 OK)**:
```json
{
  "message": "File successfully uploaded to /uploads/videos/bigfile.mp4",
  "url": "{base_url}/uploads/videos/bigfile.mp4",
  "filename": "bigfile.mp4",
  "folder": "videos",
  "size": 52428800,
  "mime_type": "video/mp4"
}
```

**Response (Intermediate Chunk - 200 OK)**:
```json
{
  "message": "Chunk 2 uploaded successfully."
}
```

---

### 4. Static File Access

**Endpoint**: `GET /uploads/<path:filepath>`

**Description**: Direct file access with static URLs and proper MIME types.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filepath` | path | Yes | Relative path in format `folder/filename.ext` |

**URL Examples**:
```
{base_url}/uploads/documents/report.pdf
{base_url}/uploads/images/photo.jpg
{base_url}/uploads/videos/presentation.mp4
```

**Response**: Raw file content with headers:
- `Content-Type`: Correct MIME type
- `Content-Disposition`: `inline; filename="filename.ext"`
- `Cache-Control`: `public, max-age=31536000`
- `Accept-Ranges`: `bytes`

Large Files: Files >10MB are redirected to presigned S3 URLs for optimal performance.

---

### 5. Legacy File Render

**Endpoint**: `GET /api/fileuploader/render/<token>`

**Description**: Legacy endpoint - redirects to new static URL format.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `token` | string | Yes | Encrypted file token |

**Response**: HTTP 301 redirect to static URL

---

### 6. Delete File

**Endpoint**: `DELETE /api/fileuploader/delete/<token>`

**Description**: Delete a file from S3 storage using encrypted token.

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `token` | string | Yes | Encrypted file token |

**Request Example**:
```bash
curl -X DELETE {base_url}/api/fileuploader/delete/gASVBHFhYmFjZXN5ZGF0aW9uL2RvY3VtZW50cy9zYW1wbGUucGRm
```

**Response (200 OK)**:
```json
{
  "message": "File example.pdf deleted successfully",
  "filename": "example.pdf",
  "folder": "documents"
}
```

**Error Responses**:
```json
{"error": "Invalid token"}        // 400 Bad Request
{"error": "File not found"}       // 404 Not Found
{"error": "Delete failed"}         // 500 Internal Server Error
```

---

### 7. Health Check

**Endpoint**: `GET /health`

**Description**: Check system health and observability status.

**Response (200 OK)**:
```json
{
  "status": "healthy",
  "timestamp": 1715064000,
  "observability": {
    "prometheus_enabled": true,
    "loki_enabled": false,
    "s3_enabled": true
  }
}
```

---

### 8. Prometheus Metrics

**Endpoint**: `GET /metrics`

**Description**: Prometheus metrics endpoint (when enabled).

**Response**: Prometheus metrics format (text/plain)

Available Metrics:
- `fileuploader_uploads_total` - Total upload requests
- `fileuploader_upload_duration_seconds` - Upload duration histogram
- `fileuploader_deletes_total` - Total delete requests
- `fileuploader_serves_total` - Total file serve requests
- `fileuploader_file_size_bytes` - File size histogram
- `fileuploader_active_uploads` - Active uploads gauge
- `fileuploader_storage_used_bytes` - Storage used gauge

---

## Supported File Types

| Extension | MIME Type | Description | Max Size |
|-----------|-----------|-------------|-----------|
| `.png` | `image/png` | PNG Images | 50MB |
| `.jpg`, `.jpeg` | `image/jpeg` | JPEG Images | 50MB |
| `.webp` | `image/webp` | WebP Images | 50MB |
| `.gif` | `image/gif` | GIF Images | 50MB |
| `.pdf` | `application/pdf` | PDF Documents | 50MB |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Word Documents | 50MB |
| `.doc` | `application/msword` | Legacy Word Documents | 50MB |
| `.mp4` | `video/mp4` | MP4 Videos | 50MB |
| `.avi` | `video/x-msvideo` | AVI Videos | 50MB |
| `.mov` | `video/quicktime` | QuickTime Videos | 50MB |
| `.zip` | `application/zip` | ZIP Archives | 50MB |
| `.tar` | `application/x-tar` | TAR Archives | 50MB |
| `.gz` | `application/gzip` | GZIP Archives | 50MB |

---

## Security Features

### Protection Mechanisms

- Path Traversal Prevention: Robust validation against `../`, `..\`, and other path attacks
- Filename Sanitization: Removes dangerous characters and spaces
- File Type Validation: Magic number validation against MIME type spoofing
- Size Limits: Configurable maximum file size (default: 50MB)
- Input Validation: All inputs validated before processing
- Encryption: AES-256 encryption for delete tokens
- Security Headers: XSS, CSRF, and content type protection

### Content Validation

Files are validated using:
- Magic Numbers: File signature detection
- Python-Magic: Advanced content analysis (when available)
- Fallback Validation: Basic signature checks

### Blocked Patterns

```
../           # Parent directory traversal
..\           # Windows parent directory
/absolute     # Absolute paths
\windows      # Windows absolute paths
<>:"|?*      # Dangerous characters
CON/PRN/AUX   # Windows reserved names
```

---

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Application Configuration
BASE_URL=http://localhost:2424
ROUTE_PREFIX=/api/fileuploader
FLASK_DEBUG=false
TESTING=false

# S3 Storage Configuration (MANDATORY)
STORAGE_ENDPOINT=http://localhost:9000
STORAGE_ACCESS_KEY=admin
STORAGE_SECRET_KEY=admin123
STORAGE_BUCKET=fileuploads

# Security Configuration
ENCRYPTION_KEY=your-secret-encryption-key-here

# Observability Configuration
USE_PROMETHEUS=false
USE_LOKI=false
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### Required Dependencies

```bash
# Core dependencies (already included in pyproject.toml)
uv sync

# Optional dependencies (already included in pyproject.toml)
# prometheus-client - For metrics
# python-magic (or python-magic-bin on Windows) - For advanced file validation
```

---

## Error Handling

### Standard Error Format

All errors return JSON with consistent format:

```json
{
  "error": "Human-readable error message"
}
```

### HTTP Status Codes

| Code | Meaning | Example Scenarios |
|-------|---------|-------------------|
| 200 | Success | File uploaded, deleted, or served |
| 301 | Redirect | Legacy render endpoint |
| 302 | Redirect | Large file presigned URL |
| 400 | Bad Request | Invalid parameters, file too large |
| 404 | Not Found | File doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Error | S3 failure, system error |

### Common Error Messages

```json
{"error": "Invalid or missing folder name"}
{"error": "No file provided"}
{"error": "File too large. Maximum size: 50MB"}
{"error": "File type not allowed"}
{"error": "Invalid filename"}
{"error": "S3 client not available"}
{"error": "Upload failed: S3 connection timeout"}
{"error": "File not found"}
{"error": "Invalid token"}
{"error": "Delete failed"}
```

---

## Rate Limiting

### Default Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| Upload endpoints | 10 requests/minute | Per IP |
| Multiple uploads | 20 requests/minute | Per IP |
| Chunk uploads | 20 requests/minute | Per IP |
| File serving | 100 requests/minute | Per IP |
| Delete operations | 50 requests/minute | Per IP |

### Rate Limit Response

```json
{
  "error": "Rate limit exceeded. Try again later."
}
```

HTTP Status: `429 Too Many Requests`

---

## Production Deployment

### Nginx Reverse Proxy (Recommended)

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    # SSL Configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Security Headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    
    # API Routes
    location /api/ {
        proxy_pass http://127.0.0.1:2424;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Upload Limits
        client_max_body_size 100M;
        proxy_request_buffering off;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
        proxy_send_timeout 300s;
    }
    
    # Static File Serving
    location /uploads/ {
        # Proxy to app for S3 integration
        proxy_pass http://127.0.0.1:2424;
        proxy_set_header Host $host;
        
        # Caching
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff;
        
        # Security
        location ~* \.(php|jsp|asp|sh|py|pl|rb)$ {
            deny all;
        }
    }
    
    # Health Check
    location /health {
        proxy_pass http://127.0.0.1:2424;
        access_log off;
    }
    
    # Metrics (restrict access)
    location /metrics {
        allow 127.0.0.1;
        allow 10.0.0.0/8;
        deny all;
        proxy_pass http://127.0.0.1:2424;
    }
}
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Expose port
EXPOSE 2424

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:2424/health || exit 1

# Run application
CMD ["python", "-m", "fileuploader_s3.main"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  fileuploader:
    build: .
    ports:
      - "2424:2424"
    environment:
      - STORAGE_ENDPOINT=${STORAGE_ENDPOINT}
      - STORAGE_ACCESS_KEY=${STORAGE_ACCESS_KEY}
      - STORAGE_SECRET_KEY=${STORAGE_SECRET_KEY}
      - STORAGE_BUCKET=${STORAGE_BUCKET}
      - BASE_URL=${BASE_URL}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - USE_PROMETHEUS=${USE_PROMETHEUS:-false}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:2424/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Production Server

```bash
# Install production WSGI server (already included in pyproject.toml)
uv sync

# Run with Waitress
uv run waitress-serve \
  --host=0.0.0.0 \
  --port=2424 \
  --call fileuploader_s3.main:app
```

---

## Examples

### JavaScript/React Example

```javascript
// Upload file with fetch
async function uploadFile(file, folder) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('folder', folder);

  try {
    const response = await fetch('{base_url}/api/fileuploader/upload', {
      method: 'POST',
      body: formData
    });
    
    const result = await response.json();
    
    if (response.ok) {
      console.log('Upload successful:', result);
      return result.url;
    } else {
      console.error('Upload failed:', result.error);
      throw new Error(result.error);
    }
  } catch (error) {
    console.error('Network error:', error);
    throw error;
  }
}

// Usage
const fileInput = document.getElementById('file');
const file = fileInput.files[0];
const url = await uploadFile(file, 'documents');
```
