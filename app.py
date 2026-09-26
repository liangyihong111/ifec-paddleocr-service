import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware

from field_extractor import extract_fields_by_names, normalize_text

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

REPORT_FIELDS = [
    {"key": "companyName", "label": "公司名称", "aliases": ["中国核工业第五建设有限公司"]},
    {"key": "branchName", "label": "分公司", "aliases": ["制造分公司"]},
    {"key": "reportTitle", "label": "报告标题", "aliases": ["射线检测报告"]},
    {"key": "reportNo", "label": "报告编号", "aliases": ["报告编号"], "pattern": r"[A-Za-z0-9._/-]+"},
    {"key": "pageNo", "label": "当前页", "aliases": ["第几页"]},
    {"key": "totalPages", "label": "总页数", "aliases": ["共几页"]},
    {"key": "entrustingUnit", "label": "委托单位", "aliases": ["委托单位"]},
    {"key": "entrustNo", "label": "委托编号", "aliases": ["委托编号"], "pattern": r"[A-Za-z0-9._/-]+"},
    {"key": "inspectionCompleteDate", "label": "检测完成日期", "aliases": ["检测完成日期", "检测日期"], "pattern": r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?"},
    {"key": "qualityPlanNo", "label": "质量计划编号", "aliases": ["质量计划编号"]},
    {"key": "drawingNo", "label": "图纸号", "aliases": ["图纸号"]},
    {"key": "partName", "label": "检件名称", "aliases": ["检件名称"]},
    {"key": "inspectionScope", "label": "检测范围", "aliases": ["检测范围"], "multiline": 3},
    {"key": "material", "label": "材质", "aliases": ["材质", "材 质"]},
    {"key": "specification", "label": "规格", "aliases": ["规格", "规 格"]},
    {"key": "unitNo", "label": "机组号", "aliases": ["机组号"]},
    {"key": "subItemCode", "label": "子项代号", "aliases": ["子项代号"]},
    {"key": "systemNo", "label": "系统号", "aliases": ["系统号"]},
    {"key": "nuclearClass", "label": "核级", "aliases": ["核级", "核 级"]},
    {"key": "weldingMethod", "label": "焊接方法", "aliases": ["焊接方法"], "multiline": 2},
    {"key": "jointType", "label": "接头形式", "aliases": ["接头形式"]},
    {"key": "inspectionTiming", "label": "检测时机", "aliases": ["检测时机"]},
    {"key": "inspectionRatio", "label": "检测比例", "aliases": ["检测比例"]},
    {"key": "surfaceCondition", "label": "表面状态", "aliases": ["表面状态"]},
    {"key": "inspectionStandard", "label": "检测标准", "aliases": ["检测标准", "执行标准"]},
    {"key": "acceptanceStandard", "label": "验收标准", "aliases": ["验收标准"]},
    {"key": "basisFileNo", "label": "依据文件编号", "aliases": ["依据文件编号"]},
    {"key": "basisVersion", "label": "版本", "aliases": ["版本", "版 本"]},
    {"key": "radiationSourceType", "label": "射线源类型", "aliases": ["射线源类型"], "options": ["X", "γ"]},
    {"key": "equipmentModel", "label": "设备型号", "aliases": ["设备型号"], "multiline": 2},
    {"key": "equipmentNo", "label": "设备编号", "aliases": ["设备编号"]},
    {"key": "sourceType", "label": "源种类", "aliases": ["源种类"], "options": ["Ir192", "Se75"]},
    {"key": "focalSpotSize", "label": "有效焦点尺寸", "aliases": ["有效焦点尺寸"]},
    {"key": "penetrationThicknessMm", "label": "透照厚度/mm", "aliases": ["透照厚度/mm", "透照厚度"]},
    {"key": "inspectionTechniqueLevel", "label": "检测技术等级", "aliases": ["检测技术等级"], "options": ["N/A", "A", "AB", "B"]},
    {"key": "exposureMethod", "label": "透照方式", "aliases": ["透照方式"]},
    {"key": "singleExposureLength", "label": "一次透照长度", "aliases": ["一次透照长度"]},
    {"key": "l3Mm", "label": "L3/mm", "aliases": ["L3/mm", "L3"]},
    {"key": "filmModelLevel", "label": "胶片型号/级别", "aliases": ["胶片型号/级别", "胶片型号"], "multiline": 2},
    {"key": "filmSizeMm", "label": "胶片规格/mm", "aliases": ["胶片规格/mm", "胶片规格"]},
    {"key": "shieldingBackScreen", "label": "遮挡板（背屏）", "aliases": ["遮挡板（背屏）", "遮挡板", "背屏"]},
    {"key": "singleDoubleFilmTechnique", "label": "单/双片技术", "aliases": ["单/双片技术"], "options": ["单", "双"]},
    {"key": "exposureCount", "label": "曝光次数", "aliases": ["曝光次数"], "pattern": r"\d+"},
    {"key": "tubeVoltageKv", "label": "管电压/kV", "aliases": ["管电压/kV", "管电压"]},
    {"key": "tubeCurrentOrActivity", "label": "管电流/活度", "aliases": ["管电流/活度", "管电流", "活度"]},
    {"key": "focusDistanceMm", "label": "焦距/mm", "aliases": ["焦距/mm", "焦距"]},
    {"key": "sourceToFilmDistanceMm", "label": "源侧工件至胶片距离/mm", "aliases": ["源侧工件至胶片距离/mm", "源侧工件至胶片距离", "片距离/mm"]},
    {"key": "intensifyingScreenMm", "label": "增感屏/mm", "aliases": ["增感屏/mm", "增感屏"]},
    {"key": "filterPlateMm", "label": "滤光板/mm", "aliases": ["滤光板/mm", "滤光板"]},
    {"key": "exposureTimeMin", "label": "曝光时间/min", "aliases": ["曝光时间/min", "曝光时间"]},
    {"key": "iqiPlacement", "label": "像质计放置", "aliases": ["像质计放置"], "options": ["源侧", "片侧"]},
    {"key": "iqiModelQuantity", "label": "像质计型号/数量", "aliases": ["像质计型号/数量", "像质计型号", "数量"], "multiline": 2},
    {"key": "geometricUnsharpnessUgMm", "label": "几何不清晰度Ug/mm", "aliases": ["几何不清晰度Ug/mm", "几何不清晰度", "Ug/mm"]},
    {"key": "darkroomProcessing", "label": "暗室处理", "aliases": ["暗室处理"], "options": ["自动", "手工"]},
    {"key": "developerModel", "label": "显影液型号", "aliases": ["显影液型号"], "multiline": 2},
    {"key": "minVisibleWireAndDiameterMm", "label": "最小可见丝号及丝径/mm", "aliases": ["最小可见丝号及丝径/mm", "最小可见丝号", "丝径/mm"], "multiline": 2},
    {"key": "filmProcessorModel", "label": "洗片机型号", "aliases": ["洗片机型号"]},
    {"key": "fixerModel", "label": "定影液型号", "aliases": ["定影液型号"], "multiline": 2},
    {"key": "developTempTime", "label": "显影温度/时间", "aliases": ["显影温度/时间"]},
    {"key": "autoProcessingParams", "label": "自动处理参数", "aliases": ["自动处理参数"]},
    {"key": "viewingMethod", "label": "观片方式", "aliases": ["观片方式"], "options": ["单片", "双片"]},
    {"key": "fixingTempTime", "label": "定影温度/时间", "aliases": ["定影温度/时间"]},
    {"key": "qualifiedFilmCount", "label": "合格片数", "aliases": ["合格片数"], "pattern": r"\d+"},
    {"key": "unqualifiedFilmCount", "label": "不合格片数", "aliases": ["不合格片数"], "pattern": r"\d+"},
    {"key": "operatorAndQualification", "label": "操作人/资格", "aliases": ["操作人/资格", "操作人"], "multiline": 3},
    {"key": "conclusion", "label": "结论", "aliases": ["结论"], "options": ["合格", "不合格"]},
    {"key": "inspector", "label": "检测人", "aliases": ["检测人"]},
    {"key": "reviewer", "label": "审核人", "aliases": ["审核人"]},
    {"key": "approver", "label": "批准人", "aliases": ["批准人"]},
    {"key": "inspectorQualificationDate", "label": "检测人资格/日期", "aliases": ["检测人资格/日期", "资格/日期"]},
    {"key": "reviewerQualificationDate", "label": "审核人资格/日期", "aliases": ["审核人资格/日期"]},
    {"key": "approvalDate", "label": "批准日期", "aliases": ["批准日期", "日期"]},
    {"key": "inspectionSeal", "label": "检验检测专用章", "aliases": ["检验检测专用章"]},
    {"key": "sealNo", "label": "章编号/页下注编号", "aliases": ["章编号", "页下注编号"]},
]

INTAKE_FIELDS = [
    {"key": "projectName", "label": "工程名称", "aliases": ["工程名称"], "multiline": 2},
    {"key": "equipmentModelNo", "label": "设备型号/编号", "aliases": ["设备型号/编号"], "multiline": 2},
    {"key": "acceptanceStandardLevel", "label": "验收标准/级别", "aliases": ["验收标准/级别"], "multiline": 2},
    {"key": "inspectionDate", "label": "检测日期", "aliases": ["检测日期", "日期"], "multiline": 2},
    {"key": "specification", "label": "规格mm", "aliases": ["规格mm"], "multiline": 2},
    {"key": "exposureMethod", "label": "透照方式", "aliases": ["透照方式"], "multiline": 2},
    {"key": "iqiPlacement", "label": "像质计位置", "aliases": ["像质计位置", "像质计放置"], "multiline": 3},
    {"key": "iqiModelQuantity", "label": "像质计型号", "aliases": ["像质计型号", "像质计类型"], "multiline": 2},
    {"key": "penetrationThicknessMm", "label": "透照厚度", "aliases": ["透照厚度", "透照厚度/mm"], "multiline": 2},
    {"key": "singleDoubleFilmTechnique", "label": "胶片透照技术", "aliases": ["胶片透照技术", "单/双片技术"], "multiline": 2},
    {"key": "inspector", "label": "检测人员", "aliases": ["操作者", "检测人"], "multiline": 2},
    {"key": "inspectionUnit", "label": "检测单位", "aliases": ["实施单位", "检测单位"], "multiline": 2},
]

REPORT_FIELD_BY_LABEL = {item["label"]: item for item in REPORT_FIELDS}
REPORT_FIELD_LABELS = [item["label"] for item in REPORT_FIELDS]
REPORT_FIELD_RULES = {
    item["label"]: {
        "aliases": item.get("aliases", []),
        "pattern": item.get("pattern"),
        "direction": item.get("direction", "auto"),
    }
    for item in REPORT_FIELDS
}

app = FastAPI(title="IFEC PaddleOCR Test Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup_preload_pipeline():
    """可选预热：避免首次 OCR 因模型加载过慢导致后端超时。"""
    preload = os.getenv("PADDLEOCR_PRELOAD", "1").strip().lower() in {"1", "true", "yes", "on"}
    if not preload:
        return
    try:
        get_pipeline()
        print("[IFEC-OCR] PaddleOCR pipeline preloaded.")
    except Exception as exc:
        # 不阻塞服务启动，让接口返回具体错误
        print(f"[IFEC-OCR] PaddleOCR preload failed: {exc}")

_pipeline = None
_pipeline_kind: Optional[str] = None
_pipeline_error: Optional[str] = None
_pipeline_lock = threading.Lock()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_pipeline():
    global _pipeline, _pipeline_error, _pipeline_kind
    if _pipeline is not None:
        return _pipeline
    if _pipeline_error is not None:
        raise RuntimeError(_pipeline_error)

    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline
        if _pipeline_error is not None:
            raise RuntimeError(_pipeline_error)
        return _initialize_pipeline()


def _initialize_pipeline():
    global _pipeline, _pipeline_error, _pipeline_kind
    try:
        pipeline_kind = os.getenv("PADDLEOCR_PIPELINE", "ocr").strip().lower()
        common_kwargs: Dict[str, Any] = {
            "use_doc_orientation_classify": _env_bool("PADDLEOCR_USE_ORIENTATION", False),
            "use_doc_unwarping": _env_bool("PADDLEOCR_USE_UNWARPING", False),
            "use_textline_orientation": _env_bool("PADDLEOCR_USE_TEXTLINE_ORIENTATION", False),
        }

        pipeline_env_args = {
            "device": "PADDLEOCR_DEVICE",
            "lang": "PADDLEOCR_LANG",
        }
        for arg_name, env_name in pipeline_env_args.items():
            env_value = os.getenv(env_name)
            if env_value:
                common_kwargs[arg_name] = env_value

        model_dir_args = {
            "text_detection_model_dir": (
                "PADDLEOCR_TEXT_DETECTION_MODEL_DIR",
                "/home/ocr/.paddlex/official_models/PP-OCRv5_server_det",
            ),
            "text_recognition_model_dir": (
                "PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR",
                "/home/ocr/.paddlex/official_models/PP-OCRv5_server_rec",
            ),
        }
        for arg_name, (env_name, default_dir) in model_dir_args.items():
            model_dir = os.getenv(env_name)
            if not model_dir and os.path.isdir(default_dir):
                model_dir = default_dir
            if model_dir:
                common_kwargs[arg_name] = model_dir

        if pipeline_kind == "structure":
            from paddleocr import PPStructureV3

            structure_kwargs = {
                **common_kwargs,
                "use_table_recognition": _env_bool("PADDLEOCR_USE_TABLE", True),
                "use_formula_recognition": _env_bool("PADDLEOCR_USE_FORMULA", False),
                "use_chart_recognition": _env_bool("PADDLEOCR_USE_CHART", False),
                "use_seal_recognition": _env_bool("PADDLEOCR_USE_SEAL", False),
                "use_region_detection": _env_bool("PADDLEOCR_USE_REGION", False),
            }
            _pipeline = PPStructureV3(**structure_kwargs)
            _pipeline_kind = "structure"
        else:
            from paddleocr import PaddleOCR

            _pipeline = PaddleOCR(**common_kwargs)
            _pipeline_kind = "ocr"

        return _pipeline
    except Exception as exc:
        _pipeline_error = str(exc)
        raise


def make_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        safe_dict = {}
        for key, item in value.items():
            if key == "markdown_images":
                continue
            safe_dict[str(key)] = make_json_safe(item)
        return safe_dict
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]

    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return make_json_safe(tolist())

    item = getattr(value, "item", None)
    if callable(item):
        try:
            return make_json_safe(item())
        except Exception:
            pass

    return str(value)


def collect_strings(value: Any) -> List[str]:
    texts: List[str] = []

    def walk(node: Any, parent_key: str = ""):
        if isinstance(node, dict):
            for key, item in node.items():
                walk(item, str(key))
            return
        if isinstance(node, (list, tuple, set)):
            if parent_key in {"rec_texts", "texts"}:
                texts.extend(str(item).strip() for item in node if str(item).strip())
            else:
                for item in node:
                    walk(item, parent_key)
            return
        if parent_key in {"text", "content", "text_content", "rec_text"}:
            text = str(node).strip()
            if text:
                texts.append(text)

    walk(value)
    return dedupe_keep_order(texts)


def dedupe_keep_order(items: Iterable[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output


def extract_markdown_text(markdown_items: List[Dict[str, Any]], pipeline) -> str:
    if not markdown_items:
        return ""
    try:
        return pipeline.concatenate_markdown_pages(markdown_items)
    except Exception:
        parts = []
        for item in markdown_items:
            for key in ("markdown_texts", "markdown", "text"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
        return "\n\n".join(parts)


def normalize_markdown_to_text(markdown: str) -> str:
    text = re.sub(r"!\[[^\]]*]\([^)]+\)", "", markdown)
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_`|]+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_field_value(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip(" ：:;,，。")


def field_aliases(field: Dict[str, Any]) -> List[str]:
    return [field["label"]] + list(field.get("aliases") or [])


def known_label_norms() -> List[str]:
    norms: List[str] = []
    for field in REPORT_FIELDS + INTAKE_FIELDS:
        aliases = [field["label"]]
        if field["key"] not in {"companyName", "branchName", "reportTitle"}:
            aliases.extend(field.get("aliases") or [])
        for alias in aliases:
            norm = normalize_text(alias)
            if norm:
                norms.append(norm)
    return sorted(set(norms), key=len, reverse=True)


KNOWN_LABEL_NORMS = known_label_norms()


def is_known_label_line(line: str) -> bool:
    norm = normalize_text(line)
    if not norm:
        return False
    return any(norm == label or norm.startswith(label) for label in KNOWN_LABEL_NORMS)


def inline_value_from_line(line: str, aliases: List[str]) -> str:
    stripped = line.strip()
    for alias in aliases:
        if alias not in stripped:
            continue
        value = stripped[stripped.find(alias) + len(alias):]
        value = clean_field_value(value)
        if value:
            return value
    return ""


def extract_value_from_lines(text: str, field: Dict[str, Any]) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    aliases = field_aliases(field)
    alias_norms = [normalize_text(alias) for alias in aliases]
    max_lines = int(field.get("multiline") or 1)

    for index, line in enumerate(lines):
        norm_line = normalize_text(line)
        if not any(norm_line == alias_norm or norm_line.startswith(alias_norm) for alias_norm in alias_norms):
            continue

        inline = inline_value_from_line(line, aliases)
        if inline:
            return inline

        values: List[str] = []
        for next_line in lines[index + 1:index + 1 + max_lines]:
            if is_known_label_line(next_line):
                break
            values.append(next_line)
        return clean_field_value("\n".join(values))

    return ""


def extract_header_value(text: str, field: Dict[str, Any]) -> str:
    key = field["key"]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined = "\n".join(lines)

    if key == "companyName":
        for line in lines:
            if "中国核工业第五建设有限公司" in line:
                return "中国核工业第五建设有限公司"
    if key == "branchName":
        for line in lines:
            if "制造分公司" in line:
                return "制造分公司"
    if key == "reportTitle":
        for line in lines:
            if "射线检测报告" in line:
                return "射线检测报告"
    if key in {"pageNo", "totalPages"}:
        match = re.search(r"第\s*(\d+)\s*页\s*[，,]\s*共\s*(\d+)\s*页", joined)
        if match:
            return match.group(1) if key == "pageNo" else match.group(2)
    if key == "inspectionSeal" and "检验检测专用章" in joined:
        return "检验检测专用章"
    if key == "sealNo":
        matches = re.findall(r"\((\d+)\)", joined)
        if matches:
            return f"({matches[-1]})"
    return ""


def normalize_checkbox_value(value: str, options: Optional[List[str]]) -> str:
    if not value or not options:
        return value

    compact = normalize_text(value).replace("□", " □").replace("■", " ■")
    for option in options:
        option_norm = normalize_text(option)
        if re.search(r"■\s*" + re.escape(option_norm), compact, flags=re.IGNORECASE):
            return option

    selected = re.search(r"■\s*([^□■\s]+)", compact)
    if selected:
        selected_text = selected.group(1)
        for option in options:
            if normalize_text(option) in selected_text or selected_text in normalize_text(option):
                return option

    return value


def extract_configured_fields(
    ocr_data: Any,
    text: str,
    definitions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    labels = [item["label"] for item in definitions]
    rules = {
        item["label"]: {
            "aliases": item.get("aliases", []),
            "pattern": item.get("pattern"),
            "direction": item.get("direction", "auto"),
        }
        for item in definitions
    }
    spatial_results = extract_fields_by_names(ocr_data, labels, rules)
    spatial_by_label = {item.get("field"): item for item in spatial_results}

    fields: List[Dict[str, Any]] = []
    for field in definitions:
        label = field["label"]
        result = spatial_by_label.get(label) or {}
        value = clean_field_value(result.get("value"))
        confidence = float(result.get("confidence") or 0.0)
        source = result.get("source") or "not-found"

        fallback_value = ""
        if not value:
            fallback_value = extract_header_value(text, field) or extract_value_from_lines(text, field)
            if fallback_value:
                value = fallback_value
                confidence = max(confidence, 0.65)
                source = "text-fallback"

        value = normalize_checkbox_value(value, field.get("options"))
        fields.append(
            {
                "field": label,
                "key": field["key"],
                "label": label,
                "value": value,
                "confidence": round(confidence, 4),
                "page": result.get("page"),
                "fieldBox": result.get("fieldBox"),
                "valueBox": result.get("valueBox"),
                "matchedText": result.get("matchedText") or "",
                "needConfirm": (not value) or confidence < 0.75,
                "source": source,
                "options": field.get("options"),
            }
        )
    return fields


def extract_report_fields(ocr_data: Any, text: str) -> List[Dict[str, Any]]:
    return extract_configured_fields(ocr_data, text, REPORT_FIELDS)


def first_date(value: str) -> str:
    match = re.search(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?", value or "")
    if not match:
        return clean_field_value(value)
    parts = re.findall(r"\d+", match.group(0))
    if len(parts) < 3:
        return clean_field_value(match.group(0))
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def first_value_line(value: str) -> str:
    for line in (value or "").splitlines():
        cleaned = clean_field_value(line)
        if cleaned:
            return cleaned
    return ""


def normalize_equipment_model_no(value: str) -> str:
    first_line = first_value_line(value)
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._/-]*", first_line)
    return match.group(0) if match else first_line


def first_decimal(value: str) -> str:
    match = re.search(r"\d+(?:\.\d+)?", value or "")
    return match.group(0) if match else first_value_line(value)


def normalize_iqi_placement(value: str) -> str:
    compact = re.sub(r"\s+", "", clean_field_value(value))
    checked_mark = r"[☑✓√■▣]"
    if re.search(checked_mark + r"片侧", compact):
        return "片侧"
    if re.search(checked_mark + r"源侧", compact):
        return "源侧"
    # 报告中的已选框有时会被 OCR 丢弃，而未选框仍识别为“□”。
    if "□源侧" in compact and "片侧" in compact and "□片侧" not in compact:
        return "片侧"
    if "□片侧" in compact and "源侧" in compact and "□源侧" not in compact:
        return "源侧"
    if "片侧" in compact and "源侧" not in compact:
        return "片侧"
    if "源侧" in compact and "片侧" not in compact:
        return "源侧"
    return first_value_line(value)


def normalize_specification(value: str) -> str:
    normalized = clean_field_value(value).replace("Φ", "φ")
    match = re.search(
        r"[φΦ∅]?\s*\d+(?:\.\d+)?\s*[×xX*]\s*\d+(?:\.\d+)?"
        r"(?:\s*/\s*[φΦ∅]?\s*\d+(?:\.\d+)?\s*[×xX*]\s*\d+(?:\.\d+)?)?",
        normalized,
    )
    if match:
        normalized = match.group(0)
    normalized = re.sub(r"^mm", "", normalized, flags=re.IGNORECASE).strip()
    if normalized and normalized[0].isdigit() and re.search(r"/φ", normalized, flags=re.IGNORECASE):
        normalized = "φ" + normalized
    normalized = re.sub(r"\s+", "", normalized)
    normalized = (
        normalized.replace("Φ", "φ")
        .replace("∅", "φ")
        .replace("x", "×")
        .replace("X", "×")
        .replace("*", "×")
    )
    return normalized


def split_acceptance_standard_level(value: str) -> tuple[str, str]:
    normalized = re.sub(r"\s+", "", clean_field_value(value))
    match = re.search(r"([A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9._-]+)*)/(\d{1,2})", normalized)
    if not match:
        return normalized, ""

    standard = match.group(1).rstrip("/")
    numeric_level = int(match.group(2))
    roman_levels = {1: "I级", 2: "II级", 3: "III级", 4: "IV级"}
    return standard, roman_levels.get(numeric_level, f"{numeric_level}级")


def derived_intake_field(
    source: Dict[str, Any],
    key: str,
    label: str,
    value: str,
) -> Dict[str, Any]:
    result = dict(source)
    result.update(
        {
            "field": label,
            "key": key,
            "label": label,
            "value": value,
            "needConfirm": not bool(value) or float(source.get("confidence") or 0.0) < 0.75,
        }
    )
    return result


def extract_intake_fields(ocr_data: Any, text: str) -> List[Dict[str, Any]]:
    extracted = extract_configured_fields(ocr_data, text, INTAKE_FIELDS)
    by_key = {item["key"]: item for item in extracted}

    by_key["projectName"]["value"] = first_value_line(by_key["projectName"].get("value") or "")
    by_key["equipmentModelNo"]["value"] = normalize_equipment_model_no(
        by_key["equipmentModelNo"].get("value") or ""
    )
    by_key["inspector"]["value"] = first_value_line(by_key["inspector"].get("value") or "")
    by_key["inspectionUnit"]["value"] = first_value_line(by_key["inspectionUnit"].get("value") or "")
    by_key["exposureMethod"]["value"] = first_value_line(by_key["exposureMethod"].get("value") or "")
    iqi_definition = next(field for field in INTAKE_FIELDS if field["key"] == "iqiPlacement")
    iqi_text_value = extract_value_from_lines(text, iqi_definition)
    by_key["iqiPlacement"]["value"] = normalize_iqi_placement(
        iqi_text_value or by_key["iqiPlacement"].get("value") or ""
    )
    if iqi_text_value:
        by_key["iqiPlacement"]["source"] = "text-checkbox"
        by_key["iqiPlacement"]["confidence"] = max(
            float(by_key["iqiPlacement"].get("confidence") or 0.0), 0.85
        )
        by_key["iqiPlacement"]["needConfirm"] = False
    by_key["iqiModelQuantity"]["value"] = first_value_line(
        by_key["iqiModelQuantity"].get("value") or ""
    )
    by_key["penetrationThicknessMm"]["value"] = first_decimal(
        by_key["penetrationThicknessMm"].get("value") or ""
    )
    by_key["singleDoubleFilmTechnique"]["value"] = first_value_line(
        by_key["singleDoubleFilmTechnique"].get("value") or ""
    )
    combined = by_key["acceptanceStandardLevel"]
    acceptance_standard, accept_level = split_acceptance_standard_level(combined.get("value") or "")
    by_key["inspectionDate"]["value"] = first_date(by_key["inspectionDate"].get("value") or "")
    by_key["inspectionDate"]["needConfirm"] = not bool(by_key["inspectionDate"]["value"])
    by_key["specification"]["value"] = normalize_specification(by_key["specification"].get("value") or "")
    by_key["specification"]["needConfirm"] = not bool(by_key["specification"]["value"])

    return [
        by_key["projectName"],
        by_key["equipmentModelNo"],
        derived_intake_field(combined, "acceptanceStandard", "验收标准", acceptance_standard),
        derived_intake_field(combined, "acceptLevel", "验收级别", accept_level),
        by_key["inspectionDate"],
        derived_intake_field(
            by_key["specification"],
            "specification",
            "厚度/规格",
            by_key["specification"]["value"],
        ),
        by_key["exposureMethod"],
        by_key["iqiPlacement"],
        derived_intake_field(
            by_key["iqiModelQuantity"],
            "iqiModelQuantity",
            "像质计类型",
            by_key["iqiModelQuantity"]["value"],
        ),
        by_key["penetrationThicknessMm"],
        by_key["singleDoubleFilmTechnique"],
        by_key["inspector"],
        by_key["inspectionUnit"],
    ]


def pdf_pages_to_images(pdf_path: Path, output_dir: Path) -> List[Path]:
    import pypdfium2 as pdfium

    image_paths: List[Path] = []
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            image = page.render(scale=2).to_pil()
            image_path = output_dir / f"page-{page_index + 1:03d}.png"
            image.save(image_path)
            image_paths.append(image_path)
    finally:
        pdf.close()
    return image_paths


def make_inputs(input_path: Path, pipeline_kind: str, temp_dir: Path) -> List[Path]:
    if input_path.suffix.lower() == ".pdf" and pipeline_kind == "ocr":
        return pdf_pages_to_images(input_path, temp_dir)
    return [input_path]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "pipelineLoaded": _pipeline is not None,
        "pipelineKind": _pipeline_kind or os.getenv("PADDLEOCR_PIPELINE", "ocr").strip().lower(),
        "pipelineError": _pipeline_error,
    }


@app.get("/ready")
def ready():
    """Readiness probe that verifies the OCR pipeline can be loaded."""
    try:
        get_pipeline()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not-ready",
                "pipelineKind": _pipeline_kind
                or os.getenv("PADDLEOCR_PIPELINE", "ocr").strip().lower(),
                "pipelineError": str(exc),
            },
        ) from exc

    return {
        "status": "ready",
        "pipelineLoaded": True,
        "pipelineKind": _pipeline_kind,
        "device": os.getenv("PADDLEOCR_DEVICE", "cpu"),
    }


@app.post("/ocr")
async def recognize(
    file: UploadFile = File(...),
    include_details: bool = Query(False, description="Whether to include raw PaddleOCR page JSON."),
):
    start = time.time()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    with tempfile.TemporaryDirectory(prefix="ifec-ocr-") as temp_dir:
        input_path = Path(temp_dir) / (file.filename or f"upload{suffix}")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty upload file")
        input_path.write_bytes(content)

        try:
            pipeline = get_pipeline()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"PaddleOCR failed: {exc}") from exc

        pipeline_kind = _pipeline_kind or os.getenv("PADDLEOCR_PIPELINE", "ocr").strip().lower()
        input_paths = make_inputs(input_path, pipeline_kind, Path(temp_dir))
        pages = []
        ocr_pages_for_fields = []
        markdown_items = []
        text_parts = []
        for page_index, page_input in enumerate(input_paths, start=1):
            try:
                output = pipeline.predict(input=str(page_input))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"PaddleOCR failed on page {page_index}: {exc}") from exc

            page_texts: List[str] = []
            page_json_list = []
            for result in output:
                result_json = make_json_safe(getattr(result, "json", {}))
                result_markdown = make_json_safe(getattr(result, "markdown", {}))

                if isinstance(result_markdown, dict):
                    markdown_items.append(result_markdown)

                page_result_texts = collect_strings(result_json)
                page_texts.extend(page_result_texts)
                page_json_list.append(result_json)

            page_texts = dedupe_keep_order(page_texts)
            text_parts.extend(page_texts)

            page_payload = {
                "page": page_index,
                "text": "\n".join(page_texts),
            }
            ocr_pages_for_fields.append({"page": page_index, "json": page_json_list})
            if include_details:
                page_payload["json"] = page_json_list
            pages.append(page_payload)

        markdown = extract_markdown_text(markdown_items, pipeline)
        recognized_text = "\n".join(dedupe_keep_order(text_parts))
        if not recognized_text and markdown:
            recognized_text = normalize_markdown_to_text(markdown)

        return {
            "status": "success",
            "fileName": file.filename,
            "fileType": "pdf" if suffix == ".pdf" else "image",
            "recognizedText": recognized_text,
            "markdown": markdown,
            "fields": extract_intake_fields(ocr_pages_for_fields, recognized_text),
            "pages": pages,
            "costTime": int((time.time() - start) * 1000),
        }
