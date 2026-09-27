# Build and transfer offline Docker images

The offline image bundles the PP-OCRv5 detection and recognition models under
`/opt/paddleocr-models`. The runtime cache remains at `/home/ocr/.paddlex`, so a
cache volume cannot hide the bundled models.

All commands in the build section run on a connected Linux amd64 host. No GPU
is required to build the images. A GPU and NVIDIA Container Toolkit are only
required when running the GPU image.

## Build the local base images

From the repository root:

```bash
docker build --pull -f Dockerfile -t ifec-paddleocr-service:cpu .
docker build --pull -f Dockerfile.gpu -t ifec-paddleocr-service:gpu .
```

## Build images with bundled models

GPU image:

```bash
docker build --pull=false \
  -f Dockerfile.offline \
  --build-arg MODEL_FETCHER_IMAGE=ifec-paddleocr-service:cpu \
  --build-arg RUNTIME_IMAGE=ifec-paddleocr-service:gpu \
  -t ifec-paddleocr-service:gpu-offline .
```

CPU image:

```bash
docker build --pull=false \
  -f Dockerfile.offline \
  --build-arg MODEL_FETCHER_IMAGE=ifec-paddleocr-service:cpu \
  --build-arg RUNTIME_IMAGE=ifec-paddleocr-service:cpu \
  -t ifec-paddleocr-service:cpu-offline .
```

The model download happens only in the `model-downloader` build stage. The
final GPU image never initializes PaddlePaddle on the build host.

## Verify that the models are embedded

```bash
docker run --rm \
  --entrypoint sh \
  ifec-paddleocr-service:gpu-offline \
  -c 'test -f /opt/paddleocr-models/PP-OCRv5_server_det/inference.pdiparams && test -f /opt/paddleocr-models/PP-OCRv5_server_rec/inference.pdiparams && echo MODEL_FILES_OK'
```

## Test without network access

On a GPU host:

```bash
docker run -d \
  --name ifec-ocr-offline-test \
  --network none \
  --gpus all \
  --shm-size 1g \
  ifec-paddleocr-service:gpu-offline

docker logs -f ifec-ocr-offline-test
```

In another terminal, call the readiness endpoint from inside the container:

```bash
docker exec ifec-ocr-offline-test python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8100/ready', timeout=30).read().decode())"
docker rm -f ifec-ocr-offline-test
```

`--network none` proves that startup does not download a model.

## Export and transfer

```bash
docker save \
  -o ifec-paddleocr-service-gpu-offline.tar \
  ifec-paddleocr-service:gpu-offline

sha256sum ifec-paddleocr-service-gpu-offline.tar \
  > ifec-paddleocr-service-gpu-offline.tar.sha256
```

Transfer the TAR file, checksum, `compose.gpu.offline.yaml`, and this document
to the offline server. Then run:

```bash
sha256sum -c ifec-paddleocr-service-gpu-offline.tar.sha256
docker load -i ifec-paddleocr-service-gpu-offline.tar
docker compose -f compose.gpu.offline.yaml up -d
docker compose -f compose.gpu.offline.yaml logs -f ocr
curl http://127.0.0.1:8866/ready
```

Set `OCR_GPU_DEVICE_ID`, `OCR_GPU_BIND_HOST`, or `OCR_GPU_BIND_PORT` in a local
`.env` file when their defaults are not suitable.
