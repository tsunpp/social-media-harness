from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import ExifTags, Image, ImageOps

from app.database import connect, initialize


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

DURATION_PATTERN = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
VIDEO_STREAM_PATTERN = re.compile(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b")
TILE_GRID_PATTERN = re.compile(r"Tile Grid:.*?\b(\d{2,5})x(\d{2,5})\b")
ROTATION_PATTERN = re.compile(r"rotation of\s+(-?\d+(?:\.\d+)?)")
CREATION_PATTERN = re.compile(r"creation_time\s*:\s*([^\r\n]+)")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_type_for(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    return None


def orientation_for(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    if width == height:
        return "square"
    return "portrait" if height > width else "landscape"


def run_ffmpeg(ffmpeg: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ffmpeg), "-hide_banner", *arguments],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def probe_with_ffmpeg(ffmpeg: Path, source: Path) -> dict:
    result = run_ffmpeg(ffmpeg, ["-i", str(source), "-f", "null", "-"])
    text = result.stderr
    duration = None
    duration_match = DURATION_PATTERN.search(text)
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    width = height = None
    dimensions_match = TILE_GRID_PATTERN.search(text) or VIDEO_STREAM_PATTERN.search(text)
    if dimensions_match:
        width, height = (int(value) for value in dimensions_match.groups())
    rotation_match = ROTATION_PATTERN.search(text)
    if rotation_match and abs(float(rotation_match.group(1))) in {90.0, 270.0}:
        width, height = height, width

    creation_match = CREATION_PATTERN.search(text)
    return {
        "width": width,
        "height": height,
        "duration_seconds": duration,
        "captured_at": creation_match.group(1).strip() if creation_match else None,
        "sensitive_metadata": (
            "location.ISO6709" in text or "com.apple.quicktime.location" in text
        ),
    }


def inspect_jpeg(path: Path) -> dict:
    with Image.open(path) as image:
        exif = image.getexif()
        width, height = image.size
        if exif.get(274) in {5, 6, 7, 8}:
            width, height = height, width
        captured_at = exif.get(36867) or exif.get(306)
        sensitive = any(ExifTags.TAGS.get(key) == "GPSInfo" for key in exif.keys())
    return {
        "width": width,
        "height": height,
        "duration_seconds": None,
        "captured_at": str(captured_at) if captured_at else None,
        "sensitive_metadata": sensitive,
    }


def create_jpeg_thumbnail(source: Path, target: Path, max_size: int = 640) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((max_size, max_size))
        image.save(target, "JPEG", quality=85, optimize=True)


def create_ffmpeg_image(
    ffmpeg: Path, source: Path, target: Path, seek: float | None = None
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    arguments: list[str] = []
    if seek is not None:
        arguments.extend(["-ss", f"{seek:.3f}"])
    arguments.extend(
        [
            "-i", str(source), "-map", "0:v:0", "-frames:v", "1",
            "-vf", "scale='if(gt(iw,ih),640,-2)':'if(gt(iw,ih),-2,640)'",
            "-q:v", "3", "-update", "1", "-map_metadata", "-1",
            "-y", str(target),
        ]
    )
    result = run_ffmpeg(ffmpeg, arguments)
    if result.returncode != 0 or not target.exists():
        raise RuntimeError(f"缩略图生成失败: {source.name}: {result.stderr[-500:]}")


def create_video_proxy(ffmpeg: Path, source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    arguments = [
        "-i", str(source), "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", "scale='if(gt(iw,ih),720,-2)':'if(gt(iw,ih),-2,720)',format=yuv420p",
        "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "30",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
        "-map_metadata", "-1", "-y", str(target),
    ]
    result = run_ffmpeg(ffmpeg, arguments)
    if result.returncode != 0 or not target.exists():
        target.unlink(missing_ok=True)
        raise RuntimeError(f"代理视频生成失败: {source.name}: {result.stderr[-700:]}")


def save_asset(db_path: Path, asset: dict) -> None:
    values = (
        asset["asset_id"], asset["sha256"], asset["original_path"],
        asset["filename"], asset["media_type"], asset["extension"],
        asset["size_bytes"], asset["width"], asset["height"],
        asset["duration_seconds"], asset["captured_at"], asset["orientation"],
        asset["thumbnail_path"], asset["proxy_path"],
        json.dumps(asset["keyframes"], ensure_ascii=False),
        asset["processing_status"], int(asset["sensitive_metadata"]),
        asset["warning"], asset["created_at"], asset["updated_at"],
    )
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO assets(
                asset_id, sha256, original_path, filename, media_type, extension,
                size_bytes, width, height, duration_seconds, captured_at, orientation,
                thumbnail_path, proxy_path, keyframes_json, processing_status,
                sensitive_metadata, warning, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sha256) DO UPDATE SET
                original_path=excluded.original_path,
                filename=excluded.filename,
                width=excluded.width,
                height=excluded.height,
                duration_seconds=excluded.duration_seconds,
                captured_at=excluded.captured_at,
                orientation=excluded.orientation,
                thumbnail_path=excluded.thumbnail_path,
                proxy_path=excluded.proxy_path,
                keyframes_json=excluded.keyframes_json,
                processing_status=excluded.processing_status,
                sensitive_metadata=excluded.sensitive_metadata,
                warning=excluded.warning,
                updated_at=excluded.updated_at
            """,
            values,
        )


def write_catalog(root: Path, assets: list[dict]) -> None:
    catalog_dir = root / "asset_library" / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    public_assets = []
    for asset in assets:
        public = {key: value for key, value in asset.items() if key != "sha256"}
        public["fingerprint"] = asset["sha256"][:16]
        public_assets.append(public)
        (catalog_dir / f"{asset['asset_id']}.json").write_text(
            json.dumps(public, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    fields = [
        "asset_id", "filename", "media_type", "size_bytes", "width", "height",
        "duration_seconds", "orientation", "captured_at", "processing_status",
        "sensitive_metadata", "warning", "thumbnail_path", "proxy_path",
    ]
    with (catalog_dir / "assets.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(public_assets)


def scan_assets(
    root: Path, db_path: Path, ffmpeg: Path, generate: bool = True
) -> list[dict]:
    initialize(db_path)
    incoming = root / "asset_library" / "incoming"
    files = sorted(
        path for path in incoming.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    assets: list[dict] = []
    for source in files:
        digest = sha256_file(source)
        asset_id = f"AST-{digest[:12].upper()}"
        media_type = media_type_for(source)
        timestamp = now_utc()
        warning = ""
        status = "cataloged"
        thumbnail = root / "asset_library" / "thumbnails" / f"{asset_id}.jpg"
        proxy = (
            root / "asset_library" / "proxies" / f"{asset_id}.mp4"
            if media_type == "video" else None
        )
        keyframes: list[str] = []

        if media_type == "image" and source.suffix.lower() not in {".heic", ".heif"}:
            metadata = inspect_jpeg(source)
        else:
            metadata = probe_with_ffmpeg(ffmpeg, source)

        if generate:
            try:
                if (
                    media_type == "image"
                    and source.suffix.lower() not in {".heic", ".heif"}
                ):
                    create_jpeg_thumbnail(source, thumbnail)
                else:
                    middle = (
                        (metadata.get("duration_seconds") or 0) / 2
                        if media_type == "video" else None
                    )
                    create_ffmpeg_image(ffmpeg, source, thumbnail, middle)

                if media_type == "video":
                    duration = metadata.get("duration_seconds") or 0
                    for index, fraction in enumerate((0.2, 0.5, 0.8), start=1):
                        keyframe = (
                            root / "asset_library" / "keyframes"
                            / f"{asset_id}-{index}.jpg"
                        )
                        create_ffmpeg_image(
                            ffmpeg, source, keyframe, duration * fraction
                        )
                        keyframes.append(str(keyframe.relative_to(root)))
                    assert proxy is not None
                    create_video_proxy(ffmpeg, source, proxy)
                status = "ready"
            except Exception as exc:
                status = "partial"
                warning = str(exc)

        asset = {
            "asset_id": asset_id,
            "sha256": digest,
            "original_path": str(source.resolve()),
            "filename": source.name,
            "media_type": media_type,
            "extension": source.suffix.lower(),
            "size_bytes": source.stat().st_size,
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "duration_seconds": metadata.get("duration_seconds"),
            "captured_at": metadata.get("captured_at"),
            "orientation": orientation_for(
                metadata.get("width"), metadata.get("height")
            ),
            "thumbnail_path": (
                str(thumbnail.relative_to(root)) if thumbnail.exists() else None
            ),
            "proxy_path": (
                str(proxy.relative_to(root)) if proxy and proxy.exists() else None
            ),
            "keyframes": keyframes,
            "processing_status": status,
            "sensitive_metadata": bool(metadata.get("sensitive_metadata")),
            "warning": warning,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        save_asset(db_path, asset)
        assets.append(asset)

    write_catalog(root, assets)
    return assets


def attach_assets_to_campaign(
    root: Path, db_path: Path, campaign_slug: str, assets: list[dict]
) -> Path:
    campaign_path = root / "campaigns" / campaign_slug
    if not campaign_path.is_dir():
        raise KeyError(f"未找到项目目录: {campaign_slug}")
    added_at = now_utc()
    with connect(db_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM campaigns WHERE slug = ?", (campaign_slug,)
        ).fetchone()
        if not exists:
            raise KeyError(f"未找到项目: {campaign_slug}")
        connection.executemany(
            "INSERT OR IGNORE INTO campaign_assets(campaign_slug, asset_id, added_at) "
            "VALUES (?, ?, ?)",
            [(campaign_slug, asset["asset_id"], added_at) for asset in assets],
        )

    manifest = {
        "schema_version": 1,
        "campaign": campaign_slug,
        "asset_count": len(assets),
        "assets": [asset["asset_id"] for asset in assets],
        "created_at": added_at,
        "note": "只引用原始素材，不复制、不修改源文件。",
    }
    target = campaign_path / "source" / "manifest.json"
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target



