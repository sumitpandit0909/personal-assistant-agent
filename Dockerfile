# 1. Use the official full Python base image (has compiler & build-essential pre-installed)
FROM python:3.12

# 2. Install system dependencies for WeasyPrint, GObject, and Pandoc
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    shared-mime-info \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. Install uv for ultra-fast dependency installation
RUN pip install --no-cache-dir uv

# 4. Copy python dependency files and install
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system --no-cache -r pyproject.toml

# 5. Copy the entire repository into the container
COPY . .

# 6. Expose the port FastAPI runs on
EXPOSE 8000

# 7. Default start command (used by the Web Service)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
