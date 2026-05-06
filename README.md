# File Uploader Web Service

This service provides a secure file uploader backed by **S3-compatible storage** (MinIO, AWS S3, etc.).  
Uploaded files are accessible through **static URLs** for direct file access.

---

## Requirements

- Python **3.10+**
- [UV](https://docs.astral.sh/uv/) (fast Python package manager)
- An **S3-compatible storage** (e.g. MinIO, AWS S3, Ceph)

---

## Setup

### 1. Install UV

If you don't already have UV, install it:

**Linux / macOS**

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify installation:

```sh
uv --version
```

---

### 2. Clone and install dependencies

```sh
git clone https://github.com/marcuwynu23/fileuploader-s3.git
cd fileuploader-s3
uv sync
```

---

### 3. Generate an encryption key

This key is used to encrypt and decrypt file paths for legacy endpoints. It must be generated **once** and stored in your `.env`.

```sh
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Example output:

```
GxA5FFbcS-N3SBFzy5ZKdATSZ6JGkQktC7ZS1wGKqv4=
```

---

### 4. Configure `.env`

Copy `.env.example` to `.env` and fill in your values:

```dotenv
# Encryption
ENCRYPTION_KEY=GxA5FFbcS-N3SBFzy5ZKdATSZ6JGkQktC7ZS1wGKqv4=

# App Config
BASE_URL=https://yourdomain.com              # Your domain
ROUTE_PREFIX=/api/bcloud/fileuploader        # API route prefix
BASE_FOLDER=uploads                          # Local storage folder

# Storage (S3 / MinIO / Compatible)
STORAGE_ENDPOINT=https://s3.amazonaws.com    # e.g. http://minio.example.com or https://s3.amazonaws.com
STORAGE_ACCESS_KEY=your_access_key           # your MinIO/S3 access key
STORAGE_SECRET_KEY=your_secret_key           # your MinIO/S3 secret key
STORAGE_BUCKET=your-bucket-name              # target bucket
```

---

### 5. Run app

```sh
uv run app
```

The app will be available at:

```
http://localhost:2424/
```

You can also check **API guide** here:

```
http://localhost:2424/api/bcloud/fileuploader
```

---

## Usage

### Upload a file

```http
POST /api/bcloud/fileuploader/upload
```

**Form Data**

- `folder`: destination folder inside bucket
- `file`: file to upload

**Response**

```json
{
  "message": "File successfully uploaded to /uploads/test/logo.png",
  "url": "https://yourdomain.com/uploads/test/logo.png",
  "filename": "logo.png",
  "folder": "test",
  "size": 1024000,
  "mime_type": "image/png"
}
```

---

### Direct file access

```http
GET /uploads/<path:filepath>
```

**Example URL**

```
https://yourdomain.com/uploads/test/logo.png
```

- Serves files directly with proper MIME types
- Clean URLs without query strings
- Optimized caching headers

---

### Email Integration Example

```javascript
const nodemailer = require('nodemailer');

const mailOptions = {
  from: 'sender@example.com',
  to: 'recipient@example.com',
  subject: 'Check out this image!',
  html: `
    <h1>Image from our server</h1>
    <img src="https://yourdomain.com/uploads/test/logo.png" 
         alt="Logo" style="max-width: 300px;">
    <p>This image displays correctly in Gmail!</p>
  `
};
```

---

## Supported File Types

| Extension | MIME Type | Description |
|-----------|-----------|-------------|
| `.png` | `image/png` | PNG Images |
| `.jpg`, `.jpeg` | `image/jpeg` | JPEG Images |
| `.webp` | `image/webp` | WebP Images |
| `.gif` | `image/gif` | GIF Images |
| `.pdf` | `application/pdf` | PDF Documents |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Word Documents |
| `.mp4` | `video/mp4` | MP4 Videos |
| `.zip` | `application/zip` | ZIP Archives |

---

## Security Features

- **Path Traversal Prevention**: Robust validation against `../` and other path attacks
- **Filename Sanitization**: Removes dangerous characters and spaces
- **File Type Validation**: Only allowed file types are accepted
- **Size Limits**: Configurable maximum file size (default: 50MB)
- **Input Validation**: All inputs are validated before processing

---

## Backward Compatibility

Legacy render endpoints still work and redirect to new static URLs:

```http
GET /api/bcloud/fileuploader/render/<token>
```

Returns HTTP 301 redirect to:
```
https://yourdomain.com/uploads/folder/filename.ext
```

---

## Production Deployment

### Nginx Reverse Proxy (Recommended)

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # API routes
    location /api/ {
        proxy_pass http://127.0.0.1:2424;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase upload limits
        client_max_body_size 100M;
        proxy_request_buffering off;
    }
    
    # Static file serving (optimized)
    location /uploads/ {
        alias /path/to/your/app/uploads/;
        
        # Cache static files
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff;
        
        # Security headers
        location ~* \.(php|jsp|asp|sh|py)$ {
            deny all;
        }
    }
}
```

### Running with Waitress

```bash
# Install waitress
uv add waitress

# Run production server
uv run waitress-serve --host=0.0.0.0 --port=2424 --call fileuploader_s3.main:app
```

## Testing

### Install Test Dependencies

```bash
pip install -r tests/requirements.txt
```

### Run Tests

```bash
# Run all tests
pytest

# Run specific test files
pytest tests/test_upload_endpoints.py -v
pytest tests/test_static_serving.py -v

# Run with coverage
pytest --cov=src/fileuploader_s3 --cov-report=html
```

### Migration from Old URLs

**Before**:
```
https://domain.com/api/bcloud/fileuploader/render?filename=logo.png&folder=test
```

**After**:
```
https://domain.com/uploads/test/logo.png
```

---

## Notes

- `ENCRYPTION_KEY` must be stable across deployments for legacy endpoint compatibility
- New static URLs don't require encryption tokens
- Files are stored locally for static serving + S3 for backup
- Large files are supported with chunked uploads
- All endpoints include comprehensive error handling and validation

---

## Tech Stack

- **Flask** (API framework)
- **UV** (fast Python package manager)
- **cryptography.Fernet** (AES-128 encryption for legacy tokens)
- **boto3** (S3/MinIO client)
- **Waitress** (production WSGI server)
