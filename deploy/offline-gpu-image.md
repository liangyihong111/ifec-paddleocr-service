# Build and transfer the CUDA 12.6 offline GPU image

This workflow builds only the GPU image. The connected build host must have an
NVIDIA GPU, a compatible driver, Docker, and NVIDIA Container Toolkit.

The CUDA 12.6 PaddlePaddle package index is:

```text
https://www.paddlepaddle.org.cn/packages/stable/cu126/
```

This is a Python package index, not an OCR model URL. The `online` image is run
once on the connected GPU host so PaddleOCR downloads the PP-OCRv5 detection
and recognition models. The `offline` image then copies those files into an
immutable image directory.

## 1. Build the online GPU image

If Docker Hub is not reachable, first pull and tag the Python base image from a
reachable mirror:

```bash
docker pull docker.m.daocloud.io/library/python:3.10-slim-bookworm
docker tag docker.m.daocloud.io/library/python:3.10-slim-bookworm python:3.10-slim-bookworm
```

Build only the `online` target:

```bash
docker build --pull=false \
  --target online \
  -f Dockerfile.gpu.offline \
  -t ifec-paddleocr-service:gpu-cu126-online .
```

## 2. Download models with the online image

Prepare a host directory writable by the image user (UID 10001):

```bash
mkdir -p paddleocr-models
chown -R 10001:10001 paddleocr-models
```

Run the image with GPU and network access:

```bash
docker run -d \
  --name ifec-ocr-model-download \
  --gpus all \
  --shm-size 1g \
  -p 127.0.0.1:8867:8100 \
  -v "$(pwd)/paddleocr-models:/home/ocr/.paddlex" \
  ifec-paddleocr-service:gpu-cu126-online

docker logs -f ifec-ocr-model-download
```

Wait for `/ready` to return HTTP 200:

```bash
curl http://127.0.0.1:8867/ready
```

Then stop and remove the download container:

```bash
docker rm -f ifec-ocr-model-download
```

Verify both model files:

```bash
test -f paddleocr-models/official_models/PP-OCRv5_server_det/inference.pdiparams
test -f paddleocr-models/official_models/PP-OCRv5_server_rec/inference.pdiparams
echo MODEL_FILES_OK
```

`paddleocr-models/` is ignored by Git but intentionally remains in the Docker
build context.

## 3. Build the final offline image

```bash
docker build --pull=false \
  --target offline \
  -f Dockerfile.gpu.offline \
  -t ifec-paddleocr-service:gpu-cu126-offline .
```

The models are stored under `/opt/paddleocr-models`, outside the writable
PaddleX runtime cache at `/home/ocr/.paddlex`.

## 4. Verify without network access

```bash
docker run -d \
  --name ifec-ocr-offline-test \
  --network none \
  --gpus all \
  --shm-size 1g \
  ifec-paddleocr-service:gpu-cu126-offline

docker logs -f ifec-ocr-offline-test
```

In another terminal:

```bash
docker exec ifec-ocr-offline-test python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8100/ready', timeout=60).read().decode())"
docker rm -f ifec-ocr-offline-test
```

## 5. Export and load on the offline server

```bash
docker save \
  -o ifec-paddleocr-service-gpu-cu126-offline.tar \
  ifec-paddleocr-service:gpu-cu126-offline

sha256sum ifec-paddleocr-service-gpu-cu126-offline.tar \
  > ifec-paddleocr-service-gpu-cu126-offline.tar.sha256
```

On the offline server:

```bash
sha256sum -c ifec-paddleocr-service-gpu-cu126-offline.tar.sha256
docker load -i ifec-paddleocr-service-gpu-cu126-offline.tar
docker compose -f compose.gpu.offline.yaml up -d
docker compose -f compose.gpu.offline.yaml logs -f ocr
curl http://127.0.0.1:8866/ready
```
