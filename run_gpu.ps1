$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$env:PADDLEOCR_DEVICE = "gpu:0"
$env:PADDLEOCR_PIPELINE = "ocr"
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"

& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8100
