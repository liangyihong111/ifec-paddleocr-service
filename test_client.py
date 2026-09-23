import argparse
import json
from pathlib import Path

import requests


def main():
    parser = argparse.ArgumentParser(description="Call the local PaddleOCR test service.")
    parser.add_argument("file", help="PDF or image file path")
    parser.add_argument("--url", default="http://127.0.0.1:8100/ocr", help="OCR endpoint")
    parser.add_argument("--full", action="store_true", help="Print full JSON response, including all page details.")
    args = parser.parse_args()

    file_path = Path(args.file)
    print(f"Uploading {file_path} to {args.url} ...", flush=True)
    print("Waiting for OCR response. The first run may take several minutes while models download.", flush=True)
    with file_path.open("rb") as fp:
        response = requests.post(
            args.url,
            params={"include_details": "true" if args.full else "false"},
            files={"file": (file_path.name, fp)},
            timeout=900,
        )

    print("HTTP", response.status_code)
    try:
        payload = response.json()
        if args.full or response.status_code >= 400:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        text = payload.get("recognizedText") or ""
        print(json.dumps(
            {
                "status": payload.get("status"),
                "fileName": payload.get("fileName"),
                "fileType": payload.get("fileType"),
                "pageCount": len(payload.get("pages") or []),
                "costTime": payload.get("costTime"),
                "fields": payload.get("fields"),
            },
            ensure_ascii=False,
            indent=2,
        ))
        print("\n===== recognizedText =====")
        print(text)
    except Exception:
        print(response.text)


if __name__ == "__main__":
    main()
