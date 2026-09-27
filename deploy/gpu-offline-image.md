# Build and transfer the GPU image for an offline server

The project has two runtime images:

- `Dockerfile` builds the CPU image with `paddlepaddle`.
- `Dockerfile.gpu` builds the CUDA 12.6 GPU image with `paddlepaddle-gpu` and
  bundles the PP-OCRv5 detection and recognition models during the same build.

The GPU Dockerfile uses a disposable CPU build stage to download the
device-independent model weights. The final image contains only
`paddlepaddle-gpu`; the CPU package and downloader environment are discarded.

## Build on a connected Linux host

If Docker Hub is unavailable, obtain the Python base image from a reachable
mirror first:

```bash
docker pull docker.m.daocloud.io/library/python:3.10-slim-bookworm
docker tag docker.m.daocloud.io/library/python:3.10-slim-bookworm python:3.10-slim-bookworm
```

Build the GPU image. The build automatically downloads both OCR models:

```bash
docker build --pull=false \
  -f Dockerfile.gpu \
  -t ifec-paddleocr-service:gpu .
```

The final model paths are:

```text
/opt/paddleocr-models/PP-OCRv5_server_det
/opt/paddleocr-models/PP-OCRv5_server_rec
```

## Verify without network access

On a GPU host:

```bash
docker run -d \
  --name ifec-ocr-offline-test \
  --network none \
  --gpus all \
  --shm-size 1g \
  ifec-paddleocr-service:gpu

docker logs -f ifec-ocr-offline-test
```

In another terminal:

```bash
docker exec ifec-ocr-offline-test python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8100/ready', timeout=60).read().decode())"
docker rm -f ifec-ocr-offline-test
```

## Export and import

```bash
docker save -o ifec-paddleocr-service-gpu.tar ifec-paddleocr-service:gpu
sha256sum ifec-paddleocr-service-gpu.tar > ifec-paddleocr-service-gpu.tar.sha256
```

Copy the TAR file, checksum, and `compose.gpu.yaml` to the offline server. Then:

```bash
sha256sum -c ifec-paddleocr-service-gpu.tar.sha256
docker load -i ifec-paddleocr-service-gpu.tar
docker compose -f compose.gpu.yaml up -d
docker compose -f compose.gpu.yaml logs -f ocr
curl http://127.0.0.1:8866/ready
```
