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
