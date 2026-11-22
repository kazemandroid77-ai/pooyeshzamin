from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import Resource
from psd_tools.psd.image_resources import ImageResource, ResoulutionInfo

ROOT = Path(".")
OUT = Path("dist/psd")
OUT.mkdir(parents=True, exist_ok=True)
sources = sorted(
    (p for p in ROOT.glob("*.png") if p.is_file()),
    key=lambda p: p.name.casefold(),
)
if len(sources) != 55:
    raise SystemExit(f"Expected exactly 55 root PNG files; found {len(sources)}")

manifest = []


def opened_mode(path: Path) -> str:
    with Image.open(path) as source_image:
        return source_image.mode

for source in sources:
    with Image.open(source) as opened:
        opened.load()
        image = opened.copy()
    if image.width < 1 or image.height < 1:
        raise ValueError(f"Invalid image dimensions: {source.name}")

    # Preserve source pixels and transparency; do not resample or invent detail.
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

    psd = PSDImage.new("RGB", image.size, color=0)
    # PSD legacy layer-name fields use Mac Roman; keep the internal layer label ASCII-safe.
    # The original Unicode filename is preserved in the PSD filename and manifest.
    layer = PixelLayer.frompil(image, psd, name="Artwork")
    psd.append(layer)

    # Photoshop Resolution Info stores pixels-per-inch as 16.16 fixed point.
    resolution = ResoulutionInfo(
        horizontal=300 * 65536,
        horizontal_unit=1,
        width_unit=1,
        vertical=300 * 65536,
        vertical_unit=1,
        height_unit=1,
    )
    psd.image_resources[Resource.RESOLUTION_INFO] = ImageResource(
        key=Resource.RESOLUTION_INFO,
        data=resolution,
    )

    destination = OUT / f"{source.stem}.psd"
    psd.save(destination)

    # Reopen each output to verify PSD structure, layer count, dimensions and DPI.
    check = PSDImage.open(destination)
    info = check.image_resources.get_data(Resource.RESOLUTION_INFO)
    if len(check) != 1 or check.size != image.size:
        raise RuntimeError(f"PSD validation failed: {destination.name}")
    if not info or round(info.horizontal / 65536) != 300 or round(info.vertical / 65536) != 300:
        raise RuntimeError(f"300 DPI metadata validation failed: {destination.name}")

    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest.append({
        "source": source.name,
        "output": destination.name,
        "width_px": image.width,
        "height_px": image.height,
        "dpi_x": 300,
        "dpi_y": 300,
        "source_mode": opened_mode(source),
        "psd_sha256": digest,
    })
    print(f"OK {source.name} -> {destination.name} ({image.width}x{image.height}, 300 DPI)")

with (OUT / "manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(manifest[0].keys()))
    writer.writeheader()
    writer.writerows(manifest)

(OUT / "PRINT_NOTES.txt").write_text(
    "55 independent, editable PSD documents. Each PSD contains one editable pixel layer.\n"
    "Resolution metadata: 300 pixels per inch (PPI/DPI). Source pixel dimensions and transparency are preserved.\n"
    "No resampling or artificial upscaling was performed.\n"
    "Color mode is preserved as RGB/RGBA-compatible PSD content; no CMYK conversion was applied.\n"
    "Before production printing, confirm the printer's required CMYK ICC profile, trim size, bleed, and safe area.\n",
    encoding="utf-8",
)
if len(list(OUT.glob("*.psd"))) != 55:
    raise SystemExit("Expected 55 PSD outputs")
print("Successfully generated and validated 55 PSD files.")
