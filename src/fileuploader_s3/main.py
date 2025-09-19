from flask import Flask, Blueprint, request, jsonify, render_template_string, Response, stream_with_context
import os
from dotenv import load_dotenv
from flask_cors import CORS
from werkzeug.utils import secure_filename
import markdown
import boto3
from botocore.client import Config
import mimetypes
from fileuploader_s3.security import encrypt_key, decrypt_key

load_dotenv()

app = Flask(__name__)
CORS(app)
file_uploader = Blueprint("file_uploader", __name__)

# ---- Config ----
BASE_URL = os.getenv("BASE_URL", "http://localhost:2424")
ROUTE_PREFIX = os.getenv("ROUTE_PREFIX", "/api/bcloud/fileuploader")

STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT", "http://localhost:9000")
STORAGE_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "admin")
STORAGE_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "admin123")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "fileuploads")

# ---- Storage client ----
s3_client = boto3.client(
    "s3",
    endpoint_url=STORAGE_ENDPOINT,
    aws_access_key_id=STORAGE_ACCESS_KEY,
    aws_secret_access_key=STORAGE_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

# Ensure bucket exists
try:
    s3_client.head_bucket(Bucket=STORAGE_BUCKET)
except:
    s3_client.create_bucket(Bucket=STORAGE_BUCKET)


@app.route("/")
def initial_render():
    with open("docs/documentation.md", "r", encoding="utf-8") as f:
        markdown_content = f.read()
    markdown_content = markdown_content.replace("{base}", BASE_URL)
    html_content = markdown.markdown(markdown_content)
    return render_template_string(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Uploader API</title>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
    )


# ---- Upload Single ----
@file_uploader.route("/upload", methods=["POST"])
def upload_file():
    folder = request.form.get("folder")
    if not folder:
        return jsonify({"error": "No folder specified"}), 400

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file provided"}), 400

    filename = secure_filename(file.filename).replace(" ", "_")
    token = encrypt_key(folder, filename)

    try:
        s3_client.upload_fileobj(file, STORAGE_BUCKET, f"{folder}/{filename}")
        file_url = f"{BASE_URL}{ROUTE_PREFIX}/render/{token}"
        return jsonify({"message": "File uploaded", "url": file_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---- Upload Multiple ----
@file_uploader.route("/upload_multi", methods=["POST"])
def upload_multiple_files():
    folder = request.form.get("folder")
    if not folder:
        return jsonify({"error": "No folder specified"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    uploaded = []
    for file in files:
        if not file or file.filename == "":
            continue
        filename = secure_filename(file.filename).replace(" ", "_")
        key = f"{folder}/{filename}"
        token = encrypt_key(folder, filename)
        s3_client.upload_fileobj(file, STORAGE_BUCKET, key)
        file_url = f"{BASE_URL}{ROUTE_PREFIX}/render/{token}"
        uploaded.append({"filename": filename, "url": file_url})

    return jsonify({"message": f"{len(uploaded)} files uploaded", "files": uploaded}), 200


# ---- Render ----
@file_uploader.route("/render/<token>", methods=["GET"])
def render_file(token):
    key = decrypt_key(token)
    if not key:
        return jsonify({"error": "Invalid token"}), 400

    try:
        print(f"DEBUG -> Bucket={STORAGE_BUCKET}, Key={key}")
        s3_response = s3_client.get_object(Bucket=STORAGE_BUCKET, Key=key)

        filename = key.split("/")[-1]
        mime_type =mimetypes.guess_type(filename)[0]
          
        return Response(
            stream_with_context(s3_response["Body"].iter_chunks()),
            mimetype=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Accept-Ranges": "bytes",
            },
        )
    except Exception as e:
        print("ERROR fetching object:", e)
        return jsonify({"error": "File not found"}), 404


# ---- Delete ----
@file_uploader.route("/delete/<token>", methods=["DELETE"])
def delete_file(token):
    key = decrypt_key(token)
    if not key:
        return jsonify({"error": "Invalid token"}), 400

    filename = key.split("/")[-1]
    try:
        s3_client.delete_object(Bucket=STORAGE_BUCKET, Key=key)
        return jsonify({"message": f"{filename} deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Register blueprint
app.register_blueprint(file_uploader, url_prefix=ROUTE_PREFIX)


def main():
    app.run(host="0.0.0.0", port=2424, debug=True)


if __name__ == "__main__":
    main()
