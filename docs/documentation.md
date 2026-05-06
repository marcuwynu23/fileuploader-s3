# File Uploader API

The File Uploader API is up and running with static URLs. Below are the available endpoints and their functionality:

## Endpoints

### 1. Upload a File

- **Method**: `POST`
- **Endpoint**: `/api/fileuploader/upload`
- **Description**: Upload a single file to a specified folder.
- **Parameters**:

  - `folder` (form-data, required): Target folder name.
  - `file` (form-data, required): File to upload.

- **Returns**:

  ```json
  {
    "message": "File successfully uploaded to /uploads/test/sample.pdf",
    "url": "https://domain.com/uploads/test/sample.pdf",
    "filename": "sample.pdf",
    "folder": "test",
    "size": 1024000,
    "mime_type": "application/pdf"
  }
  ```

---

### 2. Upload Multiple Files

- **Method**: `POST`
- **Endpoint**: `/api/fileuploader/upload_multi`
- **Description**: Upload multiple files to a specified folder in a single request.
- **Parameters**:
  - `folder` (form-data, required): Target folder name.
  - `files` (form-data, required, multiple): Files to upload (repeat key `files` for each file).
- **Returns**:

  ```json
  {
    "message": "3 files uploaded successfully.",
    "uploaded": [
      {
        "filename": "image1.jpg",
        "original_filename": "image1.jpg",
        "url": "https://domain.com/uploads/test/image1.jpg",
        "size": 512000,
        "mime_type": "image/jpeg"
      },
      {
        "filename": "image2.png",
        "original_filename": "image2.png",
        "url": "https://domain.com/uploads/test/image2.png",
        "size": 256000,
        "mime_type": "image/png"
      },
      {
        "filename": "report.pdf",
        "original_filename": "report.pdf",
        "url": "https://domain.com/uploads/test/report.pdf",
        "size": 1024000,
        "mime_type": "application/pdf"
      }
    ],
    "total_uploaded": 3
  }
  ```

---

### 3. Upload a File in Chunks

- **Method**: `POST`
- **Endpoint**: `/api/fileuploader/upload_chunk`
- **Description**: Upload a file in multiple chunks (useful for large files).
- **Parameters**:
  - `folder` (form-data, required): Target folder name.
  - `file` (form-data, required): File chunk.
  - `dzchunkindex` (form-data, required): Index of the current chunk (starting from 0).
  - `dztotalchunkcount` (form-data, required): Total number of chunks.
- **Returns (when all chunks uploaded)**:

  ```json
  {
    "message": "File successfully uploaded to /uploads/test/bigfile.mp4",
    "url": "https://domain.com/uploads/test/bigfile.mp4",
    "filename": "bigfile.mp4",
    "folder": "test",
    "size": 52428800,
    "mime_type": "video/mp4"
  }
  ```

  - **Returns (when partial chunk uploaded)**:

  ```json
  {
    "message": "Chunk 2 uploaded successfully."
  }
  ```

---

### 4. Upload Multiple Files in Chunks

- **Method**: `POST`
- **Endpoint**: `/api/fileuploader/upload_multi_chunk`
- **Description**: Upload multiple files in chunks (each file is divided into chunks).
- **Parameters**:
  - `folder` (form-data, required): Target folder name.
  - `files` (form-data, required, multiple): File chunks (one or more per request).
  - `dzchunkindex` (form-data, required): Index of the current chunk (starting from 0).
  - `dztotalchunkcount` (form-data, required): Total number of chunks for each file.
- **Returns (when all chunks uploaded for a file)**:

  ```json
  {
    "message": "1 file(s) uploaded successfully.",
    "files": [
      {
        "filename": "video.mp4",
        "original_filename": "video.mp4",
        "url": "https://domain.com/uploads/test/video.mp4",
        "size": 52428800,
        "mime_type": "video/mp4"
      }
    ],
    "total_uploaded": 1
  }
  ```

  - **Returns (when partial chunk uploaded)**:

  ```json
  {
    "message": "Chunk 3 uploaded successfully."
  }
  ```

---

### 5. Static File Access

- **Method**: `GET`
- **Endpoint**: `/uploads/<path:filepath>`
- **Description**: Direct file access with static URLs.
- **Parameters**:
  - `filepath` (path, required): Relative path in format `folder/filename.ext`
- **Returns**:  
  The raw file content with correct MIME type and headers.
- **Example URL**: `https://domain.com/uploads/test/logo.png`
- **Headers**:
  - `Content-Type`: Correct MIME type (e.g., `image/png`)
  - `Content-Disposition`: `inline; filename="logo.png"`
  - `Cache-Control`: `public, max-age=31536000`
  - `Accept-Ranges`: `bytes`

---

### 6. Retrieve a File (Legacy)

- **Method**: `GET`
- **Endpoint**: `/api/fileuploader/render/<token>`
- **Description**: **Legacy endpoint** - redirects to new static URL.
- **Query Parameters**:
  - `token` (string, required): Encrypted file token.
- **Returns**:  
  HTTP 301 redirect to the new static URL like `https://domain.com/uploads/folder/filename.ext`

---

### 7. Delete a File

- **Method**: `DELETE`
- **Endpoint**: `/api/fileuploader/delete/<token>`
- **Description**: Delete a file from both local storage and S3. If the folder is empty afterward, it will also be deleted.
- **Query Parameters**:
  - `token` (string, required): Encrypted file token.
- **Returns**:

  ```json
   {
    "message": "File sample.pdf deleted successfully",
    "filename": "sample.pdf",
    "folder": "test"
  }
  ```

  or (if folder not empty):

  ```json
  {"message": "File sample.pdf successfully deleted, but folder test is not empty"}
  ```

---

## 📁 Supported File Types

| Extension | MIME Type | Description |
|-----------|-----------|-------------|
| `.png` | `image/png` | PNG Images |
| `.jpg`, `.jpeg` | `image/jpeg` | JPEG Images |
| `.webp` | `image/webp` | WebP Images |
| `.gif` | `image/gif` | GIF Images |
| `.pdf` | `application/pdf` | PDF Documents |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Word Documents |
| `.doc` | `application/msword` | Legacy Word Documents |
| `.mp4` | `video/mp4` | MP4 Videos |
| `.avi` | `video/x-msvideo` | AVI Videos |
| `.mov` | `video/quicktime` | QuickTime Videos |
| `.zip` | `application/zip` | ZIP Archives |
| `.tar` | `application/x-tar` | TAR Archives |
| `.gz` | `application/gzip` | GZIP Archives |

---

## 🔒 Security Features

- **Path Traversal Prevention**: Robust validation against `../` and other path attacks
- **Filename Sanitization**: Removes dangerous characters and spaces
- **File Type Validation**: Only allowed file types are accepted
- **Size Limits**: Configurable maximum file size (default: 50MB)
- **Input Validation**: All inputs are validated before processing

---

## 🔧 Configuration

### Environment Variables

```bash
# App Configuration
BASE_URL=https://yourdomain.com              # Your domain
ROUTE_PREFIX=/api/fileuploader        # API route prefix
BASE_FOLDER=uploads                          # Local storage folder

# Storage (S3/MinIO)
STORAGE_ENDPOINT=https://s3.amazonaws.com    # S3 endpoint
STORAGE_ACCESS_KEY=your_access_key           # AWS access key
STORAGE_SECRET_KEY=your_secret_key           # AWS secret key
STORAGE_BUCKET=your-bucket-name              # S3 bucket name

# Security
ENCRYPTION_KEY=your-32-byte-key              # For legacy tokens
```

---

## 🚀 Production Deployment

### Nginx Reverse Proxy (Recommended)

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

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

---

## 📈 Performance Benefits

- **Direct File Serving**: No database queries for file access
- **Caching**: Browser and CDN-friendly URLs
- **Reduced Latency**: No token decryption for file access
- **Scalability**: Static files can be served by CDN or Nginx
