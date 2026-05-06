"""Main application module for fileuploader-s3."""

import markdown
from flask import Flask, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv

# Import application modules
from .config import BASE_URL, ROUTE_PREFIX, FLASK_DEBUG, TESTING
from .logging_config import setup_logging
from .storage import initialize_s3_client
from .routes import file_uploader

# Load environment variables
load_dotenv()

# Cross-platform file content validation
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    print("Warning: python-magic not available. Using basic file validation.")
    print("To install magic on Windows: pip install python-magic-bin")

# Prometheus metrics (always initialize but only use if enabled)
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    prometheus_metrics = {
        'upload_requests_total': Counter('fileuploader_uploads_total', 'Total upload requests', ['method', 'status']),
        'upload_duration_seconds': Histogram('fileuploader_upload_duration_seconds', 'Upload duration in seconds'),
        'delete_requests_total': Counter('fileuploader_deletes_total', 'Total delete requests', ['method', 'status']),
        'file_serve_requests_total': Counter('fileuploader_serves_total', 'Total file serve requests', ['status']),
        'file_size_bytes': Histogram('fileuploader_file_size_bytes', 'Uploaded file size in bytes', ['file_type']),
        'active_uploads': Gauge('fileuploader_active_uploads', 'Number of active uploads'),
        'storage_used_bytes': Gauge('fileuploader_storage_used_bytes', 'Storage used in bytes'),
    }
except ImportError:
    print("Warning: Prometheus client not available. Install with: pip install prometheus-client")

# S3/MinIO support (mandatory for this application)
boto3 = None
Config = None
try:
    import boto3
    from botocore.client import Config
except ImportError as e:
    print(f"❌ ERROR: S3 dependencies not available: {e}")
    print("❌ ERROR: This application requires S3 storage. Please install boto3:")
    print("   pip install boto3")
    exit(1)

app = Flask(__name__)
CORS(app)

# ---- Security Headers ----
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; object-src 'self';"
    return response

# ---- Initial Setup ----
app_logger = setup_logging()

# Initialize S3 client
initialize_s3_client(boto3, Config)

# ---- Home Page ----
@app.route("/")
def initial_render():
    """Render home page with documentation."""
    with open("docs/documentation.md", "r", encoding="utf-8") as f:
        markdown_content = f.read()
    markdown_content = markdown_content.replace("{base}", BASE_URL)
    html_content = markdown.markdown(markdown_content)
    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Uploader API</title>
        </head>
        <body>
            {}
        </body>
        </html>
        """.format(html_content)
    )

# ---- Prometheus Metrics Endpoint ----
@app.route("/metrics")
def metrics():
    """Prometheus metrics endpoint - only available when enabled."""
    if not prometheus_metrics:
        return jsonify({"error": "Prometheus metrics disabled"}), 404
    
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
    except ImportError:
        return jsonify({"error": "Prometheus client not installed"}), 503
    except Exception as e:
        return jsonify({"error": f"Metrics generation failed: {str(e)}"}), 500

# ---- Health Check Endpoint ----
@app.route("/health")
def health_check():
    """Health check endpoint with observability status."""
    # Check environment variables dynamically to allow runtime changes
    from .config import USE_PROMETHEUS, USE_LOKI
    current_use_prometheus = os.getenv("USE_PROMETHEUS", "false").lower() == "true"
    current_use_loki = os.getenv("USE_LOKI", "false").lower() == "true"
    current_s3_enabled = True  # S3 is now mandatory
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "observability": {
            "prometheus_enabled": current_use_prometheus,
            "loki_enabled": current_use_loki,
            "s3_enabled": current_s3_enabled
        }
    }
    return jsonify(health_status)

# Register blueprint
app.register_blueprint(file_uploader, url_prefix=ROUTE_PREFIX)


def main():
    """Main application entry point."""
    # Only run in debug mode if explicitly requested
    debug_mode = FLASK_DEBUG
    app.run(host="0.0.0.0", port=2424, debug=debug_mode)


if __name__ == "__main__":
    main()
