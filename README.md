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

Linux 上使用相同的 `docker compose` 命令。默认端口为 `8100`，可以通过 `.env` 的 `OCR_PORT` 修改。

## 8. GitHub Actions

工作流 `.github/workflows/docker-image.yml` 会执行单元测试并构建 `linux/amd64` CPU 镜像：

- Pull Request：验证测试和镜像构建，不推送镜像。
- 推送到 `main`：推送 `cpu-latest` 和带 commit SHA 的 CPU 标签。
- 推送 `v*` Git tag：额外生成 `<tag>-cpu`，例如 `v1.0.0-cpu`。
- 手动运行：通过 `publish` 参数决定是否推送到 GitHub Container Registry。

默认镜像地址：

```text
ghcr.io/liangyihong111/ifec-paddleocr-service:cpu-latest
```

如果 GitHub Container Registry 包为私有，需要先在部署机器登录：

```powershell
docker login ghcr.io
docker compose pull
docker compose up -d
```

当前阶段只发布 CPU 镜像。GPU 镜像会使用独立的构建目标和 `gpu-cu126` 标签，避免 CPU/GPU PaddlePaddle 包混装。

Docker 依赖使用 `paddleocr[doc-parser]`，覆盖当前代码使用的通用 OCR 和 `PPStructureV3`。没有安装与本服务无关的信息抽取、翻译及 LLM/LangChain 扩展，避免 `all` 依赖组造成版本冲突和镜像体积膨胀。
