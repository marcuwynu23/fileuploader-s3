# Contributing to Bucket Storage File Uploader API

Thanks for your interest in contributing to the fileuploader-s3 project!

We welcome contributions of all kinds: bug fixes, features, documentation, and suggestions.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Supported File Types](#supported-file-types)
- [Security Features](#security-features)
- [Backward Compatibility](#backward-compatibility)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Branching Strategy](#branching-strategy)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Production Deployment](#production-deployment)
- [Tech Stack](#tech-stack)
- [Reporting Issues](#reporting-issues)
- [Code of Conduct](#code-of-conduct)

---

## Requirements

- Python **3.10+**
- [UV](https://docs.astral.sh/uv/) (fast Python package manager)
- A **bucket storage** (e.g. MinIO, AWS S3, Ceph)

---

## Quick Start

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

### 2. Clone and install dependencies

```sh
git clone https://github.com/marcuwynu23/fileuploader-s3.git
cd fileuploader-s3
uv sync
```

### 3. Generate an encryption key

This key is used to encrypt and decrypt file paths for legacy endpoints. It must be generated **once** and stored in your `.env`.

```sh
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Example output:

```
GxA5FFbcS-N3SBFzy5ZKdATSZ6JGkQktC7ZS1wGKqv4=
```

### 4. Configure `.env`

Copy `.env.example` to `.env` and fill in your values:

```dotenv
# Encryption
ENCRYPTION_KEY=GxA5FFbcS-N3SBFzy5ZKdATSZ6JGkQktC7ZS1wGKqv4=

# App Config
BASE_URL=https://yourdomain.com              # Your domain
ROUTE_PREFIX=/api/bcloud/fileuploader        # API route prefix
BASE_FOLDER=uploads                          # Local storage folder

# Storage (Bucket Storage)
STORAGE_ENDPOINT=https://s3.amazonaws.com    # e.g. http://minio.example.com or https://s3.amazonaws.com
STORAGE_ACCESS_KEY=your_access_key           # your MinIO/S3 access key
STORAGE_SECRET_KEY=your_secret_key           # your MinIO/S3 secret key
STORAGE_BUCKET=your-bucket-name              # target bucket
```

### 5. Run app

#### Option 1: Using Docker Compose (Recommended)

```bash
docker-compose up -d
```

This will start both MinIO and the fileuploader service with hot-reloading enabled.

The app will be available at:

```
http://localhost:2424/
```

#### Option 2: Run locally

```sh
uv run app
```

The app will be available at:

```
http://localhost:2424/
```

You can also check the API guide here:

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

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a new branch
4. Install dependencies and set up the project

---

## Development Setup

### Prerequisites

- Python 3.10+
- UV package manager
- A bucket storage (e.g., MinIO for local development)

### Installation Steps

1. Clone your fork:

```bash
git clone https://github.com/[your-username]/fileuploader-s3.git
cd fileuploader-s3
```

2. Install dependencies:

```bash
uv sync
```

3. Set up environment:

```bash
cp .env.example .env
```

Edit `.env` with your configuration (use local MinIO for development):

```dotenv
BASE_URL=http://localhost:2424
ROUTE_PREFIX=/api/bcloud/fileuploader
FLASK_DEBUG=true

# Local MinIO (recommended for development)
STORAGE_ENDPOINT=http://localhost:9000
STORAGE_ACCESS_KEY=admin
STORAGE_SECRET_KEY=admin123
STORAGE_BUCKET=fileuploads

# Generate your own encryption key
ENCRYPTION_KEY=your-generated-key-here
```

4. (Optional) Run local services with Docker Compose:

```bash
docker-compose up -d
```

This will start both MinIO and the fileuploader development service with hot-reloading enabled.

Or run MinIO alone with Docker:

```bash
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=admin \
  -e MINIO_ROOT_PASSWORD=admin123 \
  minio/minio server /data --console-address ":9001"
```

5. Run the development server (if not using Docker Compose):

```bash
uv run app
```

The app will be available at http://localhost:2424

---

## Project Structure

```
fileuploader-s3/
├── src/
│   └── fileuploader_s3/
│       ├── __init__.py
│       ├── main.py          # Application entry point
│       ├── config.py        # Configuration management
│       ├── routes.py        # API routes definitions
│       ├── storage.py       # Bucket storage operations
│       ├── security.py      # Security utilities and validation
│       ├── utils.py         # Helper functions
│       └── logging_config.py # Logging configuration
├── templates/
│   └── index.html           # API documentation page
├── tests/
│   ├── conftest.py          # Test configuration
│   ├── test_upload_endpoints.py
│   ├── test_static_serving.py
│   ├── test_delete_functionality.py
│   ├── test_security_helpers.py
│   └── ...
├── docs/
│   └── documentation.md
├── pyproject.toml
├── .env.example
├── README.md
└── CONTRIBUTING.md
```

---

## Branching Strategy

We follow a structured branching approach:

### Main Branches

- `main` → Production-ready code
- `develop` → Integration branch for ongoing development

### Supporting Branches

Use the following naming conventions:

- `feature/<short-description>` → New features
- `fix/<short-description>` → Bug fixes
- `chore/<short-description>` → Maintenance tasks
- `docs/<short-description>` → Documentation updates
- `refactor/<short-description>` → Code improvements without behavior change
- `test/<short-description>` → Adding or updating tests

Examples:

```
feature/add-multi-file-upload
fix/path-traversal-validation
docs/update-api-endpoints
```

---

## Development Workflow

1. Create a branch from `develop` (unless it's a hotfix for production)
2. Make your changes in a focused branch
3. Follow the project's coding style and conventions
4. Add or update tests when applicable
5. Run local checks before submitting

### Code Style Guidelines

- Follow PEP 8 style guide
- Use type hints for function signatures
- Write docstrings for public functions and classes
- Keep functions focused and concise
- Use meaningful variable and function names

---

## Testing

### Install Test Dependencies

```bash
uv sync --dev
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_upload_endpoints.py -v

# Run with coverage
uv run pytest --cov=src/fileuploader_s3 --cov-report=html
```

### Writing Tests

- Place tests in the `tests/` directory
- Follow the existing test patterns
- Test both success and error cases
- Include security-related tests when applicable

---

## Commit Messages

We follow the **Conventional Commits** specification.

### Format

```
<type>(optional scope): <short description>
```

### Common Types

- `feat` → New feature
- `fix` → Bug fix
- `docs` → Documentation changes
- `style` → Formatting (no code logic changes)
- `refactor` → Code restructuring
- `test` → Adding/updating tests
- `chore` → Maintenance

### Examples

```
feat(upload): add chunked upload support
fix(security): improve path traversal validation
docs(readme): update installation instructions
refactor(storage): simplify bucket storage client initialization
```

---

## Pull Request Process

1. Ensure your branch is up to date with `develop`
2. Verify all tests and checks pass
3. Open a pull request targeting `develop` (or `main` for hotfixes)
4. Clearly describe:
   - What changed
   - Why it was needed
   - Any relevant context
5. Link to any related issues

Optional:

- Include screenshots, logs, or examples if applicable

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

---

## Tech Stack

- **Flask** (API framework)
- **UV** (fast Python package manager)
- **cryptography.Fernet** (AES-128 encryption for legacy tokens)
- **boto3** (Bucket storage client)
- **Waitress** (production WSGI server)

---

## Reporting Issues

When reporting bugs, please include:

- Description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Relevant logs or error messages

---

## Code of Conduct

Be respectful and constructive in all interactions.
Harassment or inappropriate behavior will not be tolerated.

---

## Notes

- Maintainers may request changes before merging
- Not all contributions may be accepted, but all will be reviewed

---

Thanks again for contributing to fileuploader-s3!
