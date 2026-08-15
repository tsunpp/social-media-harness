from __future__ import annotations

import colorsys
import json
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps


LAYOUTS = (
    {"axis": "cropped_left", "x": -0.012, "y": 0.107, "tension_device": "intentional_crop"},
    {"axis": "left_editorial", "x": 0.067, "y": 0.099, "tension_device": "italic_offset"},
    {"axis": "right_counterweight", "x": 0.519, "y": 0.091, "tension_device": "opposed_axis"},
    {"axis": "left_editorial_low", "x": 0.061, "y": 0.096, "tension_device": "scale_contrast"},
    {"axis": "left_resolution", "x": 0.054, "y": 0.099, "tension_device": "single_accent"},
)


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, value)):02X}" for value in rgb)


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Invalid RGB color: {value}")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _relative_luminance(color: str) -> float:
    channels = []
    for value in _rgb(color):
        channel = value / 255
        channels.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first: str, second: str) -> float:
    high, low = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def derive_palette(image_paths: Iterable[Path]) -> dict[str, Any]:
    saturated: list[tuple[int, int, int]] = []
    all_pixels: list[tuple[int, int, int]] = []
    for path in image_paths:
        image = Image.open(path).convert("RGB")
        image.thumbnail((96, 96))
        pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
        for red, green, blue in pixels:
            all_pixels.append((red, green, blue))
            hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
            if saturation >= 0.28 and 0.18 <= value <= 0.95:
                saturated.append((red, green, blue))
    if not all_pixels:
        raise ValueError("Typography palette requires at least one readable evidence image")
    source = saturated or all_pixels
    red = sum(pixel[0] for pixel in source) / len(source)
    green = sum(pixel[1] for pixel in source) / len(source)
    blue = sum(pixel[2] for pixel in source) / len(source)
    hue, saturation, _ = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    ink = colorsys.hsv_to_rgb(hue, max(0.42, min(0.72, saturation)), 0.38)
    secondary = colorsys.hsv_to_rgb(hue, max(0.18, min(0.36, saturation * 0.55)), 0.52)
    # Warm mineral accent works as a controlled counterpoint to blue/cyan campaigns;
    # otherwise use the complementary hue at deliberately muted saturation.
    accent_hue = 0.095 if 0.48 <= hue <= 0.72 else (hue + 0.5) % 1.0
    accent = colorsys.hsv_to_rgb(accent_hue, 0.56, 0.58)
    to_byte = lambda values: tuple(round(channel * 255) for channel in values)
    background = _hex(tuple(round(sum(pixel[index] for pixel in all_pixels) / len(all_pixels)) for index in range(3)))
    return {
        "source": "campaign_evidence_pixels",
        "dominant_ink": _hex(to_byte(ink)),
        "secondary_ink": _hex(to_byte(secondary)),
        "accent": _hex(to_byte(accent)),
        "accent_limit": 1,
        "representative_background": background,
    }


def load_font_roles(root: Path) -> dict[str, Any]:
    value = json.loads((root / "config" / "typography" / "font_roles.json").read_text(encoding="utf-8-sig"))
    for role in value["roles"].values():
        candidates = [role["windows_font"], *role.get("fallbacks", [])]
        selected = next((path for path in candidates if Path(path).is_file()), None)
        if selected is None:
            raise FileNotFoundError(f"No installed font for typography role {role['category']}")
        role["resolved_font"] = selected
    return value


def create_contract(
    root: Path,
    campaign: str,
    segments: list[dict[str, Any]],
    evidence_images: Iterable[Path],
    width: int = 1080,
    height: int = 1920,
) -> dict[str, Any]:
    if not segments:
        raise ValueError("Typography Director requires at least one segment")
    palette = derive_palette(evidence_images)
    fonts = load_font_roles(root)
    directed = []
    for index, segment in enumerate(segments):
        layout = LAYOUTS[index % len(LAYOUTS)]
        is_resolution = segment.get("function") == "resolution" or index == len(segments) - 1
        lines = segment.get("display_lines") or segment.get("lines")
        if not isinstance(lines, list) or not lines or any(not str(line).strip() for line in lines):
            raise ValueError(f"Segment {segment.get('segment_id')} requires display_lines")
        directed.append({
            "segment_id": segment["segment_id"],
            "function": segment.get("function", "development"),
            "index_copy": segment.get("index_copy", f"{index + 1:02d} / EDITORIAL STUDY"),
            "display_lines": [str(line).upper() for line in lines],
            "display_role": "expressive_display_serif_italic",
            "index_role": "condensed_editorial_index",
            "display_color": palette["accent"] if is_resolution else palette["dominant_ink"],
            "index_color": palette["secondary_ink"],
            "uses_accent": is_resolution,
            "layout": layout,
            "display_size_px": int(segment.get("display_size_px", round(width * 0.126))),
            "index_size_px": int(segment.get("index_size_px", round(width * 0.025))),
            "solid_fill": True,
            "outline_width": 0,
            "shadow": False,
            "phone_legibility_check": "REQUIRED",
        })
    contract = {
        "schema_version": 1,
        "campaign": campaign,
        "style_profile": "vogue-derived-editorial",
        "canvas": {"width": width, "height": height},
        "palette": palette,
        "font_roles": fonts["roles"],
        "segments": directed,
        "shared_targets": ["video", "post", "cover"],
        "decision_logic": [
            "type serves shot hierarchy and narrative function",
            "display and index roles create scale tension",
            "dominant and secondary inks derive from campaign pixels",
            "one accent is reserved for reveal or resolution",
            "placement changes by shot while preserving one visual family",
        ],
        "validation": {},
        "publishing_authorized": False,
    }
    contract["validation"] = validate_contract(contract)
    return contract


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    failures = []
    segments = contract.get("segments", [])
    minimum = 64 if contract.get("canvas", {}).get("width", 0) >= 1080 else 36
    accents = 0
    axes = set()
    for segment in segments:
        if not segment.get("solid_fill") or segment.get("outline_width") != 0 or segment.get("shadow"):
            failures.append(f"{segment.get('segment_id')}: hollow/outlined/shadow display treatment prohibited")
        if int(segment.get("display_size_px", 0)) < minimum:
            failures.append(f"{segment.get('segment_id')}: display type below mobile minimum")
        if segment.get("uses_accent"):
            accents += 1
        axes.add(segment.get("layout", {}).get("axis"))
    if accents > contract.get("palette", {}).get("accent_limit", 1):
        failures.append("Accent color exceeds one purposeful use")
    if len(segments) >= 3 and len(axes) < 2:
        failures.append("Catalog-like uniform placement detected")
    result = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "checks": ["solid fill", "no outline", "no shadow", "mobile size", "single accent", "shot-specific axes", "shared video/post/cover roles"],
    }
    if failures:
        raise ValueError("Typography contract failed: " + "; ".join(failures))
    return result


def _ffmpeg_color(value: str) -> str:
    return "0x" + value.lstrip("#")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def build_ffmpeg_filters(contract: dict[str, Any], segment_id: str, duration: float) -> list[str]:
    validate_contract(contract)
    segment = next((item for item in contract["segments"] if item["segment_id"] == segment_id), None)
    if segment is None:
        raise KeyError(segment_id)
    canvas = contract["canvas"]
    display_font = contract["font_roles"][segment["display_role"]]["resolved_font"].replace(":", "\\:")
    index_font = contract["font_roles"][segment["index_role"]]["resolved_font"].replace(":", "\\:")
    x = round(segment["layout"]["x"] * canvas["width"])
    y = round(segment["layout"]["y"] * canvas["height"])
    end = max(0.7, min(duration - 0.35, 2.85))
    filters = [
        f"drawbox=x={round(0.065 * canvas['width'])}:y={round(0.066 * canvas['height'])}:w=3:h=44:color={_ffmpeg_color(segment['index_color'])}:t=fill:enable='between(t,0.20,{end})'",
        f"drawtext=fontfile='{index_font}':text='{_escape(segment['index_copy'])}':fontcolor={_ffmpeg_color(segment['index_color'])}:fontsize={segment['index_size_px']}:x={round(0.0815 * canvas['width'])}:y={round(0.0677 * canvas['height'])}:borderw=0:shadowx=0:shadowy=0:enable='between(t,0.20,{end})'",
    ]
    for line_index, line in enumerate(segment["display_lines"]):
        size = segment["display_size_px"] if line_index == 0 else round(segment["display_size_px"] * 0.78)
        filters.append(
            f"drawtext=fontfile='{display_font}':text='{_escape(line)}':fontcolor={_ffmpeg_color(segment['display_color'])}:fontsize={size}:x={x}:y={y + line_index * round(canvas['height'] * 0.06875)}:borderw=0:shadowx=0:shadowy=0:enable='between(t,0.35,{end})'"
        )
    return filters


def render_static(
    source: Path,
    destination: Path,
    contract: dict[str, Any],
    segment_id: str,
    target: str = "post",
    size: tuple[int, int] | None = None,
) -> Path:
    """Apply the same normalized Typography Director contract to a POST or cover."""
    validate_contract(contract)
    if target not in {"post", "cover"} or target not in contract["shared_targets"]:
        raise ValueError(f"Unsupported typography target: {target}")
    segment = next((item for item in contract["segments"] if item["segment_id"] == segment_id), None)
    if segment is None:
        raise KeyError(segment_id)
    width, height = size or (contract["canvas"]["width"], contract["canvas"]["height"])
    image = ImageOps.fit(Image.open(source).convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    scale = width / contract["canvas"]["width"]
    display_font_path = contract["font_roles"][segment["display_role"]]["resolved_font"]
    index_font_path = contract["font_roles"][segment["index_role"]]["resolved_font"]
    display_font = ImageFont.truetype(display_font_path, max(1, round(segment["display_size_px"] * scale)))
    secondary_font = ImageFont.truetype(display_font_path, max(1, round(segment["display_size_px"] * 0.78 * scale)))
    index_font = ImageFont.truetype(index_font_path, max(1, round(segment["index_size_px"] * scale)))
    x = round(segment["layout"]["x"] * width)
    y = round(segment["layout"]["y"] * height)
    index_x, index_y = round(0.0815 * width), round(0.0677 * height)
    draw.rectangle((round(0.065 * width), round(0.066 * height), round(0.068 * width), round(0.089 * height)), fill=segment["index_color"])
    draw.text((index_x, index_y), segment["index_copy"], font=index_font, fill=segment["index_color"])
    line_gap = round(height * 0.06875)
    for line_index, line in enumerate(segment["display_lines"]):
        draw.text((x, y + line_index * line_gap), line, font=display_font if line_index == 0 else secondary_font, fill=segment["display_color"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, quality=94)
    return destination


def write_contract(path: Path, contract: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
