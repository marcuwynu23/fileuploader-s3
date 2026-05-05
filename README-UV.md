# UV Migration Notes

## OpenSSL Issue on Windows

When running the application on Windows, you may encounter an OpenSSL error:
```
OPENSSL_Uplink(00007FFF209D9C60,08): no OPENSSL_Applink
```

This is a known issue with the `cryptography` package on Windows. Here are some workarounds:

### Option 1: Use PyOpenSSL
```bash
uv add pyopenssl
```

### Option 2: Set environment variable
```bash
set PYTHONHTTPSVERIFY=0
uv run app
```

### Option 3: Use conda environment (recommended for Windows)
```bash
conda create -n fileuploader-s3 python=3.12
conda activate fileuploader-s3
pip install uv
uv sync
uv run app
```

## UV Commands

- Install dependencies: `uv sync`
- Run the app: `uv run app`
- Add new dependencies: `uv add package_name`
- Remove dependencies: `uv remove package_name`
- Update dependencies: `uv sync --upgrade`

## Migration Summary

- ✅ Removed Poetry configuration (`poetry.lock`)
- ✅ Converted `pyproject.toml` to UV format
- ✅ Updated `.gitignore` for UV
- ✅ Removed outdated `requirements.txt`
- ✅ All dependencies successfully installed with UV
