# Ubuntu 24.04 CPU OCR deployment

Target: OCR, training and inference share one server. This OCR container listens only on `127.0.0.1:8866`; the existing Nginx instance serves `http://OCR_SERVER_PRIVATE_IP/api/v1/ocr` on port 80. Nginx allows only the confirmed Java backend source IP. The Java backend runs on another server.

These commands are for a deployment account with `sudo` access. Do not add the `ifec` user to the Docker group. Run the commands in order and stop if a check fails. Replace the example PDF path with an actual or sanitized report on the server.

## 1. Verify the deployment prerequisites

The administrator must confirm the source IP of Java requests as seen by Nginx, that port 80 is reachable from that host, and that the existing Nginx port-80 server block can include one new `location`. Check the current Docker installation and port occupancy:

```bash
sudo docker version
sudo docker compose version
sudo ss -lntp | grep -E ':(80|8866)\b' || true
sudo docker pull python:3.10-slim-bookworm
```

Port 80 is already used by Nginx. Port 8866 must be free before starting the OCR container. The `docker pull` checks the full base-image download, which the earlier HTTP checks did not establish.

## 2. Clone and build the CPU image

```bash
sudo install -d -o ifec -g ifec /opt/ifec/paddleocr-service
sudo -u ifec git clone https://github.com/liangyihong111/ifec-paddleocr-service.git /opt/ifec/paddleocr-service
cd /opt/ifec/paddleocr-service
sudo docker build --target cpu -t ifec-paddleocr-service:cpu .
```

The clone command assumes the target directory is empty. If the repository is already present, inspect its changes and update it with `git pull --ff-only` instead. The build installs the CPU PaddlePaddle package inside the image; no host Python environment is required.

## 3. Set the container binding and start

```bash
sudo -u ifec cp .env.example .env
sudo -u ifec sed -i 's|^OCR_IMAGE=.*|OCR_IMAGE=ifec-paddleocr-service:cpu|' .env
sudo docker compose config
sudo docker compose up -d --no-deps ocr
sudo docker compose ps
```

The example `.env` binds `OCR_BIND_HOST=127.0.0.1` and `OCR_BIND_PORT=8866`. `OCR_BIND_PORT` can be changed before startup, but the Nginx upstream port must be changed to match. Keep `OCR_BIND_HOST=127.0.0.1` while Nginx is the only network entry point. Do not expose port 8866 in UFW.

Wait for model download and preload, then check readiness and one real OCR request:

```bash
curl -fsS http://127.0.0.1:8866/ready
curl -fsS -F 'file=@/path/to/sanitized-report.pdf' http://127.0.0.1:8866/ocr
sudo docker compose logs --tail=100 ocr
```

`/health` reports process health only. A successful `/ready` confirms that the OCR pipeline loaded. Check the returned text and extracted fields against the report; HTTP 200 alone does not verify recognition quality.

## 4. Connect the existing Nginx server

After confirming the Java source IP, install the Nginx location snippet:

```bash
sudo install -d /etc/nginx/snippets
sudo install -m 0644 deploy/nginx-ocr-location.conf.example /etc/nginx/snippets/ifec-ocr-location.conf
```

Replace `JAVA_BACKEND_SOURCE_IP` in that file with the confirmed address. If `OCR_BIND_PORT` differs from 8866, update the snippet's `proxy_pass` port as well. Add the following line **inside the existing server block** that serves the OCR server's private IP on port 80; do not create a competing server block on port 80. The exact server-block file must be identified by its administrator.

```nginx
include /etc/nginx/snippets/ifec-ocr-location.conf;
```

After editing the Nginx configuration:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

The administrator should confirm the UFW rule for port 80 permits the Java host. No rule for port 8866 is needed. From the Java backend server, test access with a report:

```bash
curl -fsS -F 'file=@/path/to/sanitized-report.pdf' http://OCR_SERVER_PRIVATE_IP/api/v1/ocr
```

The exact URL has **no trailing slash**. Nginx forwards it to the FastAPI endpoint `POST /ocr` without a redirect. The snippet's 110 MiB body limit covers the Java endpoint's 100 MiB file limit plus multipart overhead; its 660-second proxy timeout exceeds Java's 600-second OCR read timeout.

## 5. Switch the Java backend

Set these in the Java backend deployment environment and restart the backend after its production configuration has been released:

```text
IFEC_OCR_SERVICE_URL=http://OCR_SERVER_PRIVATE_IP/api/v1/ocr
IFEC_OCR_AUTO_START=false
```

Check a full upload from the application, including the saved OCR status and fields. This verifies the Java → Nginx → OCR route. Keep the old OCR endpoint available until that check passes.

## 6. Routine checks and updates

```bash
cd /opt/ifec/paddleocr-service
sudo docker compose ps
sudo docker compose logs --tail=100 ocr
curl -fsS http://127.0.0.1:8866/ready
```

For a later approved update, check that the working tree is clean, fast-forward the repository, build the new image and recreate the OCR container. The named volume `ocr-model-cache` keeps downloaded models across container recreation:

```bash
cd /opt/ifec/paddleocr-service
sudo -u ifec git status --short
sudo -u ifec git pull --ff-only
sudo docker build --target cpu -t ifec-paddleocr-service:cpu .
sudo docker compose up -d --no-deps --force-recreate ocr
curl -fsS http://127.0.0.1:8866/ready
```

Do not use `docker compose down -v` during updates; it would remove the model cache volume.
