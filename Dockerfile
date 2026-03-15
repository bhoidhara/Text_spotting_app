FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-guj \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libfreetype6-dev \
    libpng-dev \
    libtiff5-dev \
    libwebp-dev \
    libheif-dev \
    libde265-0 \
    poppler-utils \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.1.2 torchvision==0.16.2 \
    && python -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Single lightweight worker to avoid OOM on free tier; threads for a bit of concurrency.
CMD ["sh", "-c", "gunicorn -w 1 -k gthread --threads 1 --timeout 60 --bind 0.0.0.0:${PORT:-10000} app:app"]
