# Release Notes - v0.0.2-beta

**Release Date:** May 7, 2026

This release focuses on Docker support and Windows compatibility improvements.

---

## What's New

### Docker Support
- **Docker Compose Configuration** - Added `docker-compose.yml` for easy local development
- **Development Setup** - New development-focused Docker Compose configuration
- **Containerized Deployment** - Run the entire stack (FileUploader + MinIO) with a single command

### Windows Compatibility
- **OpenSSL Fix** - Disabled S3 client initialization on Windows by default to prevent OpenSSL errors
  - Set `FORCE_S3=true` environment variable if you need S3 on Windows
  - Prevents the common `OPENSSL_Uplink` runtime error

---

## Quick Start with Docker

```bash
# Start services
docker compose up -d

# Access points:
# - FileUploader API: http://localhost:2424
# - MinIO Console: http://localhost:9001 (admin / admin123)
```

---

## Improvements

- Easier local development with Docker
- Better Windows developer experience
- Ready-to-use containerized stack

---

## Known Issues

- Windows requires `FORCE_S3=true` for S3 functionality (may cause OpenSSL warnings)
- No built-in monitoring or logging aggregation yet

---

## Contributors

Thanks to everyone who contributed to this release:
- @marcuwynu23

---

## Links

- [Full Changelog](../../../CHANGELOG.md)
- [GitHub Release](https://github.com/marcuwynu23/bucket-fileuploader/releases/tag/v0.0.2-beta)
