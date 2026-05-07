# Docker Compose Setup for Bucket FileUploader

This directory contains Docker Compose configurations for running the Bucket FileUploader service with optional observability stack.

## Quick Start

### Basic Setup (FileUploader + MinIO)

The `docker-compose.yml` provides the core services:
- **FileUploader** - The main Flask application
- **MinIO** - Local S3-compatible object storage

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f fileuploader

# Stop services
docker compose down
```

**Access Points:**
- FileUploader API: http://localhost:2424
- MinIO Console: http://localhost:9001 (admin / admin123)
- MinIO S3 API: http://localhost:9000

### Full Observability Stack

The `docker-compose.observability.yml` adds monitoring and logging:
- **Prometheus** - Metrics collection
- **Grafana** - Metrics visualization
- **Loki/Promtail** - Log aggregation (optional)

```bash
# Start with observability
docker compose -f docker-compose.observability.yml up -d

# View all logs
docker compose -f docker-compose.observability.yml logs -f

# Stop everything
docker compose -f docker-compose.observability.yml down
```

**Access Points:**
- FileUploader API: http://localhost:2424
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin / admin)
- MinIO Console: http://localhost:9001

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | http://localhost:2424 | Public URL for generated file links |
| `ROUTE_PREFIX` | /api/fileuploader | API base path |
| `STORAGE_ENDPOINT` | http://minio:9000 | S3/MinIO endpoint |
| `STORAGE_ACCESS_KEY` | admin | S3 access key |
| `STORAGE_SECRET_KEY` | admin123 | S3 secret key |
| `STORAGE_BUCKET` | fileuploads | S3 bucket name |
| `USE_PROMETHEUS` | true | Enable Prometheus metrics |
| `USE_LOKI` | true | Enable Loki logging |
| `FLASK_DEBUG` | false | Enable Flask debug mode |

### Custom Configuration

Create a `.env` file in this directory:

```env
# .env
BASE_URL=https://yourdomain.com
STORAGE_ACCESS_KEY=your-access-key
STORAGE_SECRET_KEY=your-secret-key
USE_PROMETHEUS=true
USE_LOKI=true
```

Then start services:
```bash
docker compose --env-file .env up -d
```

## Service Details

### FileUploader

- **Image:** `ghcr.io/marcuwynu23/bucket-fileuploader:latest`
- **Port:** 2424
- **Endpoints:**
  - `POST /api/fileuploader/upload` - Upload single file
  - `POST /api/fileuploader/upload_multi` - Upload multiple files
  - `POST /api/fileuploader/upload_chunk` - Upload file chunk
  - `DELETE /api/fileuploader/delete/{token}` - Delete file
  - `GET /uploads/{folder}/{filename}` - Serve file
  - `GET /health` - Health check
  - `GET /metrics` - Prometheus metrics (when enabled)

### MinIO

- **Image:** `minio/minio:latest`
- **Ports:** 9000 (S3 API), 9001 (Console)
- **Data:** Stored in `minio-data` volume

### Prometheus

- **Image:** `prom/prometheus:latest`
- **Port:** 9090
- **Config:** `./observability/prometheus/prometheus.yml`
- **Storage:** `prometheus_data` volume
- **Scrape Target:** `fileuploader:2424/metrics`

### Grafana

- **Image:** `grafana/grafana:latest`
- **Port:** 3000
- **Credentials:** admin / admin
- **Data Source:** Prometheus (auto-configured)
- **Storage:** `grafana_data` volume

## Usage Examples

### Upload a File

```bash
curl -X POST \
  http://localhost:2424/api/fileuploader/upload \
  -F "folder=myfolder" \
  -F "file=@/path/to/image.png"
```

Response:
```json
{
  "message": "File successfully uploaded to /uploads/myfolder/image.png",
  "url": "http://localhost:2424/uploads/myfolder/image.png",
  "filename": "image.png"
}
```

### Access Uploaded File

```bash
curl http://localhost:2424/uploads/myfolder/image.png
```

### Check Health

```bash
curl http://localhost:2424/health
```

### View Metrics

```bash
# Prometheus format
curl http://localhost:2424/metrics

# Or use Prometheus UI: http://localhost:9090
```

## Troubleshooting

### Services Not Starting

```bash
# Check logs
docker compose logs fileuploader
docker compose logs minio

# Restart services
docker compose restart
```

### Prometheus Target Down

If Prometheus shows `fileuploader` as down:
1. Check if fileuploader is running: `docker compose ps`
2. Verify metrics endpoint: `curl http://localhost:2424/metrics`
3. Check hostname in `prometheus.yml` matches service name (`fileuploader`)

### 429 Too Many Requests on /metrics

The rate limiter exempts `/metrics` and `/health` endpoints. If you see 429 errors:
1. Ensure you're using the latest image
2. Check `main.py` has `limiter.exempt(metrics)` and `limiter.exempt(health_check)`
3. Restart the fileuploader service

### File Upload Fails

1. Check MinIO is healthy: `docker compose ps`
2. Verify S3 credentials in environment
3. Check fileuploader logs: `docker compose logs -f fileuploader`

## Development

### Building Local Image

```bash
# From project root
docker build -t bucket-fileuploader:local .

# Update docker-compose.yml to use local image
# image: bucket-fileuploader:local
```

### Running Tests

```bash
# From project root
uv run pytest tests/
```

## Production Considerations

1. **Change default passwords** - Update `admin123` and `admin` credentials
2. **Use external S3** - Replace MinIO with AWS S3 or Cloudflare R2
3. **Enable HTTPS** - Use reverse proxy (nginx/traefik) with SSL
4. **Persistent storage** - Ensure volumes are backed up
5. **Resource limits** - Add CPU/memory limits to services

## Volumes

| Volume | Purpose |
|--------|---------|
| `minio-data` | MinIO object storage |
| `prometheus_data` | Prometheus time-series data |
| `grafana_data` | Grafana dashboards and settings |

## Networks

All services communicate on the default Docker network created by Compose.

## Commands Reference

```bash
# Start all services
docker compose up -d

# Start specific services
docker compose up -d fileuploader minio

# View logs
docker compose logs -f

# Scale (if supported)
docker compose up -d --scale fileuploader=2

# Update services
docker compose pull
docker compose up -d

# Clean up
docker compose down
docker compose down -v  # Also remove volumes
```
