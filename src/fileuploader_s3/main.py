"""Main application module for fileuploader-s3."""

import os
import time
from flask import Flask, render_template_string, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv

# Import application modules
from .config import BASE_URL, ROUTE_PREFIX, FLASK_DEBUG, TESTING
from .logging_config import setup_logging
from .storage import initialize_s3_client
from .routes import file_uploader, serve_static_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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
prometheus_metrics = None

# S3/MinIO support (mandatory for this application)
boto3 = None
Config = None
try:
    import boto3
    from botocore.client import Config
except ImportError as e:
    print(f"ERROR: S3 dependencies not available: {e}")
    print("ERROR: This application requires S3 storage. Please install boto3:")
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
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; font-src https://cdnjs.cloudflare.com; img-src 'self' data:; connect-src 'self';"
    return response

# ---- Initial Setup ----
app_logger = setup_logging()

# Initialize S3 client
initialize_s3_client(boto3, Config)

# ---- Home Page ----
@app.route("/")
def initial_render():
    """Render beautiful home page."""
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            template_content = f.read()
        # Replace base URL in template
        template_content = template_content.replace("{base_url}", BASE_URL)
        return template_content
    except FileNotFoundError:
        # Fallback to simple page if template not found
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>File Uploader S3 API</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #333; }
                .endpoint { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }
                code { background: #e9ecef; padding: 2px 4px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>File Uploader S3 API</h1>
                <p>Modern file storage service with S3 backend.</p>
                <div class="endpoint">
                    <strong>API Base:</strong> <code>{base_url}/api/fileuploader</code>
                </div>
                <div class="endpoint">
                    <strong>Health Check:</strong> <code>{base_url}/health</code>
                </div>
                <div class="endpoint">
                    <strong>Documentation:</strong> <a href="/docs">View API Docs</a>
                </div>
            </div>
        </body>
        </html>
        """.replace("{base_url}", BASE_URL)

# ---- Prometheus Metrics Endpoint ----
@app.route("/metrics")
def metrics():
    """Prometheus metrics endpoint - only available when enabled."""
    from .routes import get_prometheus_metrics
    metrics_data = get_prometheus_metrics()
    
    if not metrics_data:
        return jsonify({"error": "Prometheus metrics disabled"}), 404
    
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        registry = metrics_data.get('registry')
        if registry:
            return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)
        else:
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

# Create limiter instance for static file route
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

# Register static file route directly on app (not on blueprint)
@app.route("/uploads/<path:filepath>", methods=["GET"])
@limiter.limit(limit_value="100 per minute")
def serve_static_file_route(filepath):
    return serve_static_file(filepath)

# Register blueprint
app.register_blueprint(file_uploader, url_prefix=ROUTE_PREFIX)


def main():
    """Main application entry point."""
    # Only run in debug mode if explicitly requested
    debug_mode = FLASK_DEBUG
    app.run(host="0.0.0.0", port=2424, debug=debug_mode)


if __name__ == "__main__":
    main()
