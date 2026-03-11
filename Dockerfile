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
    && python -m pip install -r /app/requirements.txt

COPY . /app

CMD ["gunicorn", "app:app"]
