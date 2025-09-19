# 📂 File Uploader Web Service

This service provides a secure file uploader backed by **S3-compatible storage** (MinIO, AWS S3, etc.).  
Uploaded files are accessible through **encrypted render URLs**, so real filenames and folders are never exposed.

---

## 📦 Requirements

- Python **3.10+**
- [Poetry](https://python-poetry.org/docs/#installation) (dependency manager)
- An **S3-compatible storage** (e.g. MinIO, AWS S3, Ceph)

---

## ⚙️ Setup

### 1. Install Poetry

If you don’t already have Poetry, install it:

**Linux / macOS**

```sh
curl -sSL https://install.python-poetry.org | python3 -
```

**Windows (PowerShell)**

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

Verify installation:

```sh
poetry --version
```

---

### 2. Clone and install dependencies

```sh
git clone https://github.com/your-org/filuploader-s3.git
cd filuploader-s3
poetry install
```

---

### 3. Generate an encryption key

This key is used to encrypt and decrypt file paths. It must be generated **once** and stored in your `.env`.

```sh
poetry run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Example output:

```
u73l7dvmTnDChikLR8o9uZcZ1lEusbr2FJkW_TcQOHI=
```

---

### 4. Configure `.env`

Copy `.env.example` to `.env` and fill in your values:

```dotenv
# 🔑 Encryption
ENCRYPTION_KEY=u73l7dvmTnDChikLR8o9uZcZ1lEusbr2FJkW_TcQOHI=

# 🌍 App Config
BASE_URL=http://localhost:2424                 # app base URL
ROUTE_PREFIX=/api/bcloud/fileuploader          # route prefix for uploader APIs

# 📦 Storage (S3 / MinIO / Compatible)
STORAGE_ENDPOINT=http://localhost:9000         # e.g. http://minio.example.com or https://s3.amazonaws.com
STORAGE_ACCESS_KEY=admin                       # your MinIO/S3 access key
STORAGE_SECRET_KEY=admin123                    # your MinIO/S3 secret key
STORAGE_BUCKET=fileuploads                     # target bucket
```

---

### 5. Run the app

```sh
poetry run app
```

The app will be available at:

```
http://localhost:2424/
```

You can also check the **API guide** here:

```
http://localhost:2424/api/bcloud/fileuploader
```

---

## 🚀 Usage

### Upload a file

```http
POST /api/bcloud/fileuploader/upload
```

**Form Data**

- `folder`: destination folder inside the bucket
- `file`: file to upload

**Response**

```json
{
  "message": "File uploaded",
  "url": "http://localhost:2424/api/bcloud/fileuploader/render/gAAAAABozN..."
}
```

---

### Render (secure access)

```http
GET /api/bcloud/fileuploader/render/<token>
```

- Streams the file directly (video, PDF, image, etc.)
- Browser plays inline (e.g. `video/mp4`, `application/pdf`)
- Real filename/folder are **never exposed**

---

## 🛡️ Notes

- `ENCRYPTION_KEY` must be stable across deployments, otherwise previously issued URLs will become invalid.
- Tokens never reveal the real storage path.
- Large files (videos) are streamed with proper headers for browser playback.

---

## 🧰 Tech Stack

- **Flask** (API framework)
- **Poetry** (dependency manager)
- **cryptography.Fernet** (AES-128 encryption for secure tokens)
- **boto3** (S3/MinIO client)
