# PaddleOCR 测试服务

这个目录用于先独立验证 PaddleOCR 解析 PDF/图片，跑通后再接入 RuoYi 后端的 `OcrServiceImpl`。

## 1. 创建环境

建议使用 Python 3.10 或 3.11。

```powershell
cd "e:\work\Intelligent Film Evaluation Cloud\paddleocr-service"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

先安装 PaddlePaddle。CPU 版：

```powershell
python -m pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
```

再安装服务依赖：

```powershell
python -m pip install -r requirements.txt
```

GPU 机器需要按 CUDA 版本换成对应的 `paddlepaddle-gpu` 安装命令。

本机已验证可用的 GPU 版安装命令：

```powershell
.\.venv\Scripts\python.exe -m pip uninstall -y paddlepaddle
.\.venv\Scripts\python.exe -m pip install paddlepaddle-gpu==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
```

如果 C 盘空间不足，把 pip 临时目录切到当前项目目录：

```powershell
New-Item -ItemType Directory -Force -Path ".tmp", ".pip-cache" | Out-Null
$env:TEMP=(Resolve-Path ".tmp").Path
$env:TMP=$env:TEMP
$env:PIP_CACHE_DIR=(Resolve-Path ".pip-cache").Path
```

## 2. 启动服务

```powershell
uvicorn app:app --host 127.0.0.1 --port 8100
```

GPU 启动：

```powershell
$env:PADDLEOCR_DEVICE="gpu:0"
$env:PADDLEOCR_PIPELINE="ocr"
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="True"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8100
```

健康检查：

```powershell
curl http://127.0.0.1:8100/health
```

## 3. 测试 PDF/图片

```powershell
python test_client.py "D:\sample\report.pdf"
```

或者：

```powershell
curl -X POST "http://127.0.0.1:8100/ocr" -F "file=@D:\sample\report.pdf"
```

返回结构里重点看：

- `recognizedText`：纯文本，后端可以直接返回给前端
- `markdown`：保留版面的 Markdown，适合展示报告结构
- `fields`：按规则提取的检测日期、焊缝编号、底片号等字段
- `pages`：每页的 PaddleOCR 原始结构化结果

第一次请求会比较慢，PaddleOCR 可能需要下载模型。

## 4. 通用字段提取函数

`field_extractor.py` 提供了通用字段提取能力。传入 OCR blocks 或 PaddleOCR 原始 JSON，再传入字段名列表即可返回字段值、坐标和置信度。

```python
from field_extractor import extract_fields_by_names

fields = extract_fields_by_names(
    ocr_data,
    ["规格", "材质", "检测标准"],
    {
        "规格": {"pattern": r"\d+(?:\.\d+)?[xX×*]\d+(?:\.\d+)?\s*mm"},
        "材质": {"pattern": r"[A-Z0-9.]+"},
        "检测标准": {"pattern": r"[A-Z0-9._/-]+"},
    },
)
```

返回示例：

```json
{
  "field": "规格",
  "value": "168.3×3.4mm",
  "confidence": 0.96,
  "matchedText": "规格",
  "page": 1,
  "fieldBox": [100, 100, 150, 125],
  "valueBox": [220, 100, 340, 125],
  "needConfirm": false,
  "source": "ocr-neighbor"
}
```

## 5. 常用配置

可以用环境变量调整推理参数：

```powershell
$env:PADDLEOCR_DEVICE="cpu"
$env:PADDLEOCR_LANG="ch"
$env:PADDLEOCR_USE_ORIENTATION="false"
$env:PADDLEOCR_USE_UNWARPING="false"
$env:PADDLEOCR_USE_TEXTLINE_ORIENTATION="false"
uvicorn app:app --host 127.0.0.1 --port 8100
```

后续接入 Java 时，让 `OcrServiceImpl` 把上传文件转发到：

```text
POST http://127.0.0.1:8100/ocr
Content-Type: multipart/form-data
file=<PDF/图片>
```

## 6. CPU Docker 镜像

Docker 镜像运行 Linux amd64 容器，可部署到 Linux Docker Engine，也可在 Windows 10/11 的 Docker Desktop（Linux 容器模式）中运行。

构建 CPU 镜像：

```powershell
docker build --target cpu -t ifec-paddleocr-service:cpu .
```

如果 Docker Hub 在当前网络不可访问，可以通过 `BASE_IMAGE` 指定已同步到内网或国内镜像仓库的 Python 3.10 基础镜像：

```powershell
docker build --target cpu --build-arg BASE_IMAGE=<镜像仓库>/python:3.10-slim-bookworm `
  -t ifec-paddleocr-service:cpu .
```

直接启动：

```powershell
docker run --name ifec-paddleocr-service --rm -p 8100:8100 `
  -v ifec-paddleocr-models:/home/ocr/.paddlex `
  ifec-paddleocr-service:cpu
```

第一次启动会下载 OCR 模型。模型保存在命名卷 `ifec-paddleocr-models` 中，后续重建容器可以复用。

检查服务存活状态和模型就绪状态：

```powershell
curl http://127.0.0.1:8100/health
curl http://127.0.0.1:8100/ready
```

`/health` 用于存活检查；`/ready` 会确认 OCR Pipeline 已成功加载，未就绪时返回 HTTP 503。

## 7. Docker Compose 部署

复制环境变量示例并按需修改：

```powershell
Copy-Item .env.example .env
```

如果使用本地构建的镜像，把 `.env` 中的 `OCR_IMAGE` 改为：

```text
OCR_IMAGE=ifec-paddleocr-service:cpu
```

启动服务：

```powershell
docker compose up -d
docker compose ps
```

查看日志或停止服务：

```powershell
docker compose logs -f ocr
docker compose down
```

Linux 上使用相同的 `docker compose` 命令。容器内端口为 `8100`；宿主机默认只监听 `127.0.0.1:8866`，可通过 `.env` 的 `OCR_BIND_HOST`、`OCR_BIND_PORT` 修改。Ubuntu 服务器的逐条部署命令和 Nginx 接入配置见 [`deploy/ubuntu-cpu.md`](deploy/ubuntu-cpu.md)。

## 8. GitHub Actions

两个工作流都会执行单元测试，并构建 `linux/amd64` 镜像：

- `.github/workflows/docker-image.yml`：CPU 镜像。
- `.github/workflows/docker-gpu-image.yml`：CUDA 11.8 GPU 镜像。

- Pull Request：验证测试和镜像构建，不推送镜像；仅在对应镜像的源码、依赖或工作流变更时运行。
- 推送到 `main`：分别推送 `cpu-latest`、`gpu-cu118-latest` 和带 commit SHA 的标签。
- 推送 `v*` Git tag：额外生成 `<tag>-cpu` 和 `<tag>-gpu-cu118`，例如 `v1.0.0-gpu-cu118`。
- 手动运行：在 GitHub Actions 中选择相应工作流，通过 `publish` 参数决定是否推送到 GitHub Container Registry。非默认分支手动发布时使用 SHA 标签。

默认镜像地址：

```text
ghcr.io/liangyihong111/ifec-paddleocr-service:cpu-latest
ghcr.io/liangyihong111/ifec-paddleocr-service:gpu-cu118-latest
```

如果 GitHub Container Registry 包为私有，需要先在部署机器登录：

```powershell
docker login ghcr.io
docker compose pull
docker compose up -d
```

GPU 镜像使用独立的 `Dockerfile.gpu`，从飞桨 CUDA 11.8 软件源安装 `paddlepaddle-gpu==3.2.0`；CPU 镜像继续使用 `Dockerfile` 和 CPU 软件源。两个工作流的构建缓存也互相隔离。GitHub Actions 的普通 runner 仅验证镜像构建，GPU 推理需要在配置好 NVIDIA 驱动与容器运行时的服务器上验证。

Docker 依赖使用 `paddleocr[doc-parser]`，覆盖当前代码使用的通用 OCR 和 `PPStructureV3`。没有安装与本服务无关的信息抽取、翻译及 LLM/LangChain 扩展，避免 `all` 依赖组造成版本冲突和镜像体积膨胀。

## 9. GPU Docker 镜像

在支持 CUDA 11.8 的 NVIDIA 驱动、NVIDIA Container Toolkit 和 CDI 已配置的 Linux 服务器上，可以本地构建：

```bash
docker build -f Dockerfile.gpu -t ifec-paddleocr-service:gpu-cu118 .
```

或在 GitHub Actions 发布后拉取：

```bash
docker pull ghcr.io/liangyihong111/ifec-paddleocr-service:gpu-cu118-latest
```

如果服务器已有 `compose.gpu.yaml`，把其中的 `OCR_GPU_IMAGE` 指向上述 GHCR 镜像，再运行：

```bash
OCR_GPU_IMAGE=ghcr.io/liangyihong111/ifec-paddleocr-service:gpu-cu118-latest \
  docker compose -f compose.gpu.yaml up -d --no-deps --force-recreate ocr
docker compose -f compose.gpu.yaml ps
curl http://127.0.0.1:8866/ready
```

Compose 服务需保留 `PADDLEOCR_DEVICE=gpu:0`、`devices: [nvidia.com/gpu=all]`、模型卷挂载和 `8866:8100` 端口映射。仅供本机访问时使用 `127.0.0.1:8866:8100`；向其他服务器开放时可绑定服务器内网 IP。容器内服务仍监听 `0.0.0.0:8100`。镜像不内置 OCR 模型，首次启动会下载到挂载的 `/home/ocr/.paddlex`。
