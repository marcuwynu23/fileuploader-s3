# File Uploader API

The File Uploader API is up and running. Below are the available endpoints and their functionality:

## Endpoints

### 1. Upload a File

- **Method**: `POST`
- **Endpoint**: `/api/bcloud/fileuploader/upload`
- **Description**: Upload a single file to a specified folder.
- **Parameters**:

  - `folder` (form-data, required): Target folder name.
  - `file` (form-data, required): File to upload.

- **Returns**:

  ```
  {
  "message": "File successfully uploaded to /uploads/test/sample.pdf",
  "url": "{base}/api/bcloud/fileuploader/render?filename=sample.pdf&folder=test"
  }
  ```

---

### 2. Upload Multiple Files

- **Method**: `POST`
- **Endpoint**: `/api/bcloud/fileuploader/upload_multi`
- **Description**: Upload multiple files to a specified folder in a single request.
- **Parameters**:
  - `folder` (form-data, required): Target folder name.
  - `files` (form-data, required, multiple): Files to upload (repeat key `files` for each file).
- **Returns**:

  ```
  {
  "message": "3 files uploaded successfully.",
  "files": [
      {
      "filename": "image1.jpg",
      "url": "{base}/api/bcloud/fileuploader/render?filename=image1.jpg&folder=test"
      },
      {
      "filename": "image2.png",
      "url": "{base}/api/bcloud/fileuploader/render?filename=image2.png&folder=test"
      },
      {
      "filename": "report.pdf",
      "url": "{base}/api/bcloud/fileuploader/render?filename=report.pdf&folder=test"
      }
  ]
  }
  ```

---

### 3. Upload a File in Chunks

- **Method**: `POST`
- **Endpoint**: `/api/bcloud/fileuploader/upload_chunk`
- **Description**: Upload a file in multiple chunks (useful for large files).
- **Parameters**:
  - `folder` (form-data, required): Target folder name.
  - `file` (form-data, required): File chunk.
  - `dzchunkindex` (form-data, required): Index of the current chunk (starting from 0).
  - `dztotalchunkcount` (form-data, required): Total number of chunks.
- **Returns (when all chunks uploaded)**:

  ```
  {
  "message": "File successfully uploaded to /uploads/test/bigfile.mp4",
  "url": "{base}/api/bcloud/fileuploader/render?filename=bigfile.mp4&folder=test"
  }
  ```

  - **Returns (when partial chunk uploaded)**:

  ```
  {
  "message": "Chunk 2 uploaded successfully."
  }
  ```

---

### 4. Upload Multiple Files in Chunks

- **Method**: `POST`
- **Endpoint**: `/api/bcloud/fileuploader/upload_multi_chunk`
- **Description**: Upload multiple files in chunks (each file is divided into chunks).
- **Parameters**:
  - `folder` (form-data, required): Target folder name.
  - `files` (form-data, required, multiple): File chunks (one or more per request).
  - `dzchunkindex` (form-data, required): Index of the current chunk (starting from 0).
  - `dztotalchunkcount` (form-data, required): Total number of chunks for each file.
- **Returns (when all chunks uploaded for a file)**:

  ```
  {
  "message": "1 file(s) uploaded successfully.",
  "files": [
      {
      "filename": "video.mp4",
      "url": "{base}/api/bcloud/fileuploader/render?filename=video.mp4&folder=test"
      }
  ]
  }
  ```

  - **Returns (when partial chunk uploaded)**:

  ```
  {
  "message": "Chunk 3 uploaded successfully."
  }
  ```

---

### 5. Retrieve a File

- **Method**: `GET`
- **Endpoint**: `/api/bcloud/fileuploader/render/<token>`
- **Description**: Retrieve a file from a specified folder.
- **Query Parameters**:
  - `token` (string, required): generate token.
- **Returns**:  
  The raw file content (image, pdf, docx, etc.) with correct MIME type.  
  Example: opening the URL in browser shows the image or downloads the file.

---

### 6. Delete a File

- **Method**: `DELETE`
- **Endpoint**: `/api/bcloud/fileuploader/delete/<token>`
- **Description**: Delete a file. If the folder is empty afterward, it will also be deleted.
- **Query Parameters**:
  - `token` (string, required): generate token.
- **Returns**:

  ```
   { "message": "File sample.pdf deleted" }
  ```

  or (if folder not empty):

  ```
  {"message": "File sample.pdf successfully deleted, but folder test is not empty"}
  ```
