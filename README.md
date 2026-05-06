<div align="center">

# Bucket Storage File Uploader API

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg) ![License](https://img.shields.io/badge/license-MIT-green.svg) ![Version](https://img.shields.io/badge/version-0.1.0-orange.svg) ![Flask](https://img.shields.io/badge/Flask-3.1.2-000000?style=flat&logo=flask) ![Bucket Storage](https://img.shields.io/badge/Bucket-Storage-FF9900?style=flat) ![Docker](https://img.shields.io/badge/Docker-Available-2496ED?style=flat&logo=docker)

</div>

A secure web service for uploading files to bucket storage (MinIO, AWS S3, Cloudflare R2, etc.).

---

## Features

- **Security First**: Path traversal protection, magic number validation, and encrypted tokens
- **Bucket Storage Compatible**: Works with any bucket storage backend
- **Multiple Upload Methods**: Single file, multi-file, and chunked uploads for large files
- **Static URLs**: Direct file access with clean URLs
- **Observability**: Prometheus metrics and structured logging
- **Performance**: Optimized caching, presigned URLs for large files, and rate limiting
- **Delete Functionality**: Secure file deletion with encrypted tokens
- **Legacy Support**: Backward compatibility with old token-based render endpoints
- **Docker Ready**: Docker and Docker Compose support out of the box

---

## Documentation Guides

For complete documentation, please refer to the following guides:

- [API Documentation](docs/documentation.md) - Complete API endpoints, configuration, and examples
- [Contributing Guide](CONTRIBUTING.md) - Development setup, testing, and contribution guidelines
- [Release Notes](RELEASE-NOTES.md) - Project release history and changelog
- [Security Policy](SECURITY.md) - Security vulnerability reporting
- [Code of Conduct](CODE_OF_CONDUCT.md) - Community guidelines


### GitHub Templates

- [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md)
- [Issue Templates](.github/ISSUE_TEMPLATE/)

---

## License

- [License](LICENSE) - MIT License