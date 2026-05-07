# Release Notes - v0.0.3-beta

**Release Date:** May 7, 2026

This release introduces a complete observability stack with Prometheus metrics, Grafana dashboards, and Loki log aggregation.

---

## What's New

### Observability Stack
Complete monitoring and logging solution with Docker Compose:

- **Prometheus** - Metrics collection and storage
  - Tracks upload/serve/delete request counts
  - Monitors upload duration with histogram buckets
  - File size tracking and storage usage
  - Error rate monitoring

- **Grafana** - Beautiful dashboards and visualization
  - Pre-configured dashboard with 19 panels
  - Health status, active uploads, throughput graphs
  - Latency percentiles (P50, P95, P99)
  - File size distribution heatmaps
  - Real-time logs streaming
  - [Dashboard Source](https://github.com/marcuwynu23/grafana-dashboard-collections/blob/main/bucket-storage-fileuploader-api-dashboard)

- **Loki & Promtail** - Log aggregation
  - Centralized log collection from FileUploader
  - Structured JSON log parsing
  - Searchable fields: client IP, folder, file name, backend

### Documentation
- **Docker Compose Guide** - Comprehensive README for observability setup
- **Service Configuration** - Detailed environment variable documentation
- **Usage Examples** - Curl commands and troubleshooting tips

### Rate Limiting Improvements
- **Exempted Endpoints** - `/metrics` and `/health` endpoints are now exempt from rate limiting
  - Fixes Prometheus scraping errors (HTTP 429)
  - Allows monitoring without triggering rate limits

---

## Quick Start with Observability

```bash
# Start with full observability stack
docker compose -f docker-compose.observability.yml up -d

# Access points:
# - FileUploader API: http://localhost:2424
# - Grafana: http://localhost:3000 (admin / admin)
# - Prometheus: http://localhost:9090
# - Loki: http://localhost:3100
```

---

## Dashboard Features

The pre-configured Grafana dashboard includes:

| Panel | Description |
|-------|-------------|
| Health Status | Service up/down indicator |
| Active Uploads | Current uploads in progress |
| Total Requests | Upload/serve/delete counters |
| Request Rates | Throughput over time |
| Upload Duration | P50/P95/P99 latency percentiles |
| Storage Metrics | Used bytes and file sizes |
| Success Rate | Upload reliability percentage |
| Heatmaps | File size and duration distributions |
| Live Logs | Real-time log streaming from Loki |

---

## Improvements

- Full visibility into API performance and health
- Centralized logging with searchable fields
- Production-ready monitoring out of the box
- Better troubleshooting with detailed logs

---

## Contributors

Thanks to everyone who contributed to this release:
- @marcuwynu23

---

## Links

- [Full Changelog](../../../CHANGELOG.md)
- [GitHub Release](https://github.com/marcuwynu23/bucket-fileuploader/releases/tag/v0.0.3-beta)
- [Grafana Dashboard](https://github.com/marcuwynu23/grafana-dashboard-collections/blob/main/bucket-storage-fileuploader-api-dashboard)
