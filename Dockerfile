ARG BASE_IMAGE=python:3.10-slim-bookworm
FROM ${BASE_IMAGE} AS cpu

ARG PADDLE_VERSION=3.2.0
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="IFEC PaddleOCR Service" \
      org.opencontainers.image.description="CPU container for the IFEC PaddleOCR HTTP service" \
      org.opencontainers.image.source="https://github.com/liangyihong111/ifec-paddleocr-service" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PADDLEOCR_DEVICE=cpu \
    PADDLEOCR_PIPELINE=ocr \
    PADDLEOCR_PRELOAD=1 \
    PADDLEOCR_LANG=ch \
    PADDLEOCR_USE_ORIENTATION=false \
    PADDLEOCR_USE_UNWARPING=false \
    PADDLEOCR_USE_TEXTLINE_ORIENTATION=false \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install "paddlepaddle==${PADDLE_VERSION}" \
        --index-url https://www.paddlepaddle.org.cn/packages/stable/cpu/ \
    && python -m pip install -r requirements.txt \
    && python -m pip check \
    && python -c "import paddle, paddleocr; print('PaddlePaddle', paddle.__version__, 'PaddleOCR', paddleocr.__version__)"

COPY app.py field_extractor.py ./

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin ocr \
    && mkdir -p /home/ocr/.paddlex \
    && chown -R ocr:ocr /home/ocr

USER ocr

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=10s --start-period=5m --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/ready', timeout=8).read()"]

STOPSIGNAL SIGTERM

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "1"]
