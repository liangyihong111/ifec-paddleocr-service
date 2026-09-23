import math
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


BBox = List[float]
Block = Dict[str, Any]
FieldRule = Dict[str, Any]


def normalize_text(text: Any) -> str:
    value = "" if text is None else str(text)
    value = re.sub(r"\s+", "", value)
    return value.strip(" :：;；,，。")


def bbox_from_points(points: Any) -> Optional[BBox]:
    if not points:
        return None

    if isinstance(points, (list, tuple)) and len(points) == 4 and all(is_number(v) for v in points):
        x1, y1, x2, y2 = [float(v) for v in points]
        return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]

    flat_points = []
    if isinstance(points, (list, tuple)):
        for point in points:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                flat_points.append((float(point[0]), float(point[1])))

    if not flat_points:
        return None

    xs = [point[0] for point in flat_points]
    ys = [point[1] for point in flat_points]
    return [min(xs), min(ys), max(xs), max(ys)]


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def block_center(block: Block) -> Tuple[float, float]:
    x1, y1, x2, y2 = block["bbox"]
    return (x1 + x2) / 2, (y1 + y2) / 2


def block_width(block: Block) -> float:
    x1, _, x2, _ = block["bbox"]
    return max(1.0, x2 - x1)


def block_height(block: Block) -> float:
    _, y1, _, y2 = block["bbox"]
    return max(1.0, y2 - y1)


def overlap_ratio(a1: float, a2: float, b1: float, b2: float) -> float:
    overlap = max(0.0, min(a2, b2) - max(a1, b1))
    base = max(1.0, min(a2 - a1, b2 - b1))
    return overlap / base


def normalize_block(block: Block, default_page: int = 1) -> Optional[Block]:
    text = str(block.get("text", "")).strip()
    bbox = bbox_from_points(block.get("bbox") or block.get("box") or block.get("poly"))
    if not text or not bbox:
        return None

    score = block.get("score", block.get("confidence", 1.0))
    try:
        score = float(score)
    except Exception:
        score = 1.0

    return {
        "page": int(block.get("page") or default_page),
        "text": text,
        "bbox": bbox,
        "score": max(0.0, min(1.0, score)),
    }


def flatten_ocr_blocks(ocr_data: Any) -> List[Block]:
    blocks: List[Block] = []
    append_blocks_from_node(ocr_data, blocks, default_page=1)
    blocks.sort(key=lambda item: (item["page"], item["bbox"][1], item["bbox"][0]))
    return blocks


def append_blocks_from_node(node: Any, blocks: List[Block], default_page: int) -> None:
    if node is None:
        return

    if isinstance(node, list):
        for item in node:
            append_blocks_from_node(item, blocks, default_page)
        return

    if not isinstance(node, dict):
        return

    if "page" in node:
        try:
            default_page = int(node["page"])
        except Exception:
            pass

    normalized = normalize_block(node, default_page)
    if normalized:
        blocks.append(normalized)
        return

    if "json" in node:
        append_blocks_from_node(node["json"], blocks, default_page)

    res = node.get("res")
    if isinstance(res, dict):
        page = default_page
        if isinstance(res.get("page_index"), int):
            page = int(res["page_index"]) + 1
        append_blocks_from_paddle_result(res, blocks, page)

    append_blocks_from_paddle_result(node, blocks, default_page)


def append_blocks_from_paddle_result(result: Dict[str, Any], blocks: List[Block], default_page: int) -> None:
    texts = result.get("rec_texts") or result.get("texts")
    if not isinstance(texts, list):
        return

    boxes = (
        result.get("rec_boxes")
        or result.get("rec_polys")
        or result.get("dt_polys")
        or result.get("dt_boxes")
        or result.get("boxes")
    )
    if not isinstance(boxes, list):
        return

    scores = result.get("rec_scores") or result.get("scores") or []
    for index, text in enumerate(texts):
        if index >= len(boxes):
            break
        score = scores[index] if index < len(scores) else 1.0
        block = normalize_block(
            {
                "page": default_page,
                "text": text,
                "bbox": boxes[index],
                "score": score,
            },
            default_page,
        )
        if block:
            blocks.append(block)


def extract_inline_value(text: str, aliases: Sequence[str], pattern: Optional[str]) -> Optional[str]:
    for alias in aliases:
        alias_index = text.find(alias)
        if alias_index < 0:
            continue
        value = text[alias_index + len(alias):].strip(" :：;；,，。")
        if not value:
            continue
        if pattern and not re.search(pattern, value, flags=re.IGNORECASE):
            continue
        return value
    return None


def build_label_norms(field_names: Iterable[str], rules: Optional[Dict[str, FieldRule]]) -> List[str]:
    norms = []
    for field in field_names:
        aliases = [field]
        if rules and field in rules:
            aliases.extend(rules[field].get("aliases") or [])
        norms.extend(normalize_text(alias) for alias in aliases)
    return [norm for norm in norms if norm]


def label_match_score(block_text: str, aliases: Sequence[str]) -> float:
    norm_text = normalize_text(block_text)
    best = 0.0
    for alias in aliases:
        norm_alias = normalize_text(alias)
        if not norm_alias:
            continue
        if norm_text == norm_alias:
            best = max(best, 1.0)
        elif norm_text.startswith(norm_alias):
            best = max(best, 0.9)
        elif norm_alias in norm_text:
            best = max(best, 0.7)
    return best


def is_label_like(block: Block, label_norms: Sequence[str]) -> bool:
    norm = normalize_text(block.get("text", ""))
    return any(norm == label or norm.startswith(label) for label in label_norms)


def pattern_match_score(text: str, pattern: Optional[str]) -> float:
    if not pattern:
        return 0.0
    return 1.0 if re.search(pattern, text, flags=re.IGNORECASE) else -1.0


def spatial_score(label: Block, value: Block, direction: str) -> float:
    if label["page"] != value["page"]:
        return -math.inf

    lx1, ly1, lx2, ly2 = label["bbox"]
    vx1, vy1, vx2, vy2 = value["bbox"]
    lcx, lcy = block_center(label)
    vcx, vcy = block_center(value)
    label_h = block_height(label)

    right_score = -math.inf
    dx = vx1 - lx2
    y_overlap = overlap_ratio(ly1, ly2, vy1, vy2)
    row_gap = abs(lcy - vcy)
    if dx >= -label_h and y_overlap >= 0.25:
        right_score = 0.85 + 0.25 * y_overlap - min(max(dx, 0.0), 900.0) / 1200.0 - row_gap / 300.0

    below_score = -math.inf
    dy = vy1 - ly2
    x_overlap = overlap_ratio(lx1, lx2, vx1, vx2)
    x_gap = abs(lcx - vcx)
    if dy >= -label_h * 0.4 and dy <= label_h * 5:
        below_score = 0.55 + 0.25 * x_overlap - max(dy, 0.0) / 250.0 - x_gap / 700.0

    if direction == "right":
        return right_score
    if direction == "below":
        return below_score
    return max(right_score, below_score)


def pick_value_candidate(
    label: Block,
    blocks: Sequence[Block],
    field_names: Sequence[str],
    rules: Optional[Dict[str, FieldRule]],
    field: str,
) -> Optional[Tuple[Block, float]]:
    rule = (rules or {}).get(field, {})
    direction = rule.get("direction", "auto")
    pattern = rule.get("pattern")
    label_norms = build_label_norms(field_names, rules)

    scored: List[Tuple[float, Block]] = []
    for candidate in blocks:
        if candidate is label or candidate["page"] != label["page"]:
            continue
        if is_label_like(candidate, label_norms):
            continue

        score = spatial_score(label, candidate, direction)
        if score == -math.inf:
            continue

        pattern_score = pattern_match_score(candidate["text"], pattern)
        if pattern_score < 0:
            score -= 0.45
        elif pattern_score > 0:
            score += 0.35

        score += min(1.0, float(candidate.get("score", 1.0))) * 0.15
        scored.append((score, candidate))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_block = scored[0]
    if best_score < 0.15:
        return None
    return best_block, best_score


def build_result(
    field: str,
    label: Block,
    value: str,
    value_block: Optional[Block],
    label_score: float,
    spatial_or_inline_score: float,
) -> Dict[str, Any]:
    value_score = float(value_block.get("score", 1.0)) if value_block else 1.0
    confidence = max(0.0, min(1.0, (label_score * 0.35) + (value_score * 0.35) + (spatial_or_inline_score * 0.30)))
    return {
        "field": field,
        "value": value,
        "confidence": round(confidence, 4),
        "matchedText": label["text"],
        "page": label["page"],
        "fieldBox": label["bbox"],
        "valueBox": value_block["bbox"] if value_block else label["bbox"],
        "needConfirm": confidence < 0.75,
        "source": "ocr-neighbor" if value_block else "ocr-inline",
    }


def extract_fields_by_names(
    ocr_data: Any,
    field_names: Sequence[str],
    rules: Optional[Dict[str, FieldRule]] = None,
) -> List[Dict[str, Any]]:
    blocks = flatten_ocr_blocks(ocr_data)
    results: List[Dict[str, Any]] = []

    for field in field_names:
        rule = (rules or {}).get(field, {})
        aliases = [field] + list(rule.get("aliases") or [])
        pattern = rule.get("pattern")

        label_candidates = []
        for block in blocks:
            match_score = label_match_score(block["text"], aliases)
            if match_score > 0:
                label_candidates.append((match_score, block))

        label_candidates.sort(key=lambda item: item[0], reverse=True)
        field_result = None

        for label_score, label_block in label_candidates:
            inline_value = extract_inline_value(label_block["text"], aliases, pattern)
            if inline_value:
                field_result = build_result(field, label_block, inline_value, None, label_score, 1.0)
                break

            picked = pick_value_candidate(label_block, blocks, field_names, rules, field)
            if not picked:
                continue

            value_block, candidate_score = picked
            field_result = build_result(field, label_block, value_block["text"], value_block, label_score, candidate_score)
            break

        if field_result:
            results.append(field_result)
        else:
            results.append(
                {
                    "field": field,
                    "value": "",
                    "confidence": 0.0,
                    "matchedText": "",
                    "page": None,
                    "fieldBox": None,
                    "valueBox": None,
                    "needConfirm": True,
                    "source": "not-found",
                }
            )

    return results

