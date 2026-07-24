"""Slice the Jon & Katie character reference SHEET into per-activity scene images.

The reference sheet (characters/refs/sheet.png) contains, in its bottom half, a
2x4 grid of 8 ready-made, perfectly-consistent activity scenes:

    row 1:  cooking | garden | fishing | grocery
    row 2:  laptop  | travel | cleaning | diary

We slice those 8 panels into individual images and use them directly as the
video scene visuals. This gives a cute, varied "day in the life" montage while
keeping Jon & Katie 100% consistent (they're literally the same artwork).

If Pillow isn't available or the sheet is missing, callers fall back gracefully.
"""
from __future__ import annotations

from pathlib import Path

# Publishing / montage order of the 8 activities.
ACTIVITY_ORDER = [
    "cooking", "garden", "fishing", "grocery",
    "laptop", "travel", "cleaning", "diary",
]

# Fractional crop boxes (left, top, right, bottom) within the full sheet.
# The bottom half is a 2x4 grid; these are intentionally slightly loose so a
# small layout variance never clips a character. Fine-tune here if needed.
ACTIVITY_BOXES = {
    "cooking":  (0.004, 0.548, 0.249, 0.773),
    "garden":   (0.251, 0.548, 0.499, 0.773),
    "fishing":  (0.501, 0.548, 0.749, 0.773),
    "grocery":  (0.751, 0.548, 0.996, 0.773),
    "laptop":   (0.004, 0.775, 0.249, 0.998),
    "travel":   (0.251, 0.775, 0.499, 0.998),
    "cleaning": (0.501, 0.775, 0.749, 0.998),
    "diary":    (0.751, 0.775, 0.996, 0.998),
}

# The big "hero" duo shot lives in the top half; used as a generic fallback ref.
HERO_BOX = (0.28, 0.03, 0.80, 0.52)


def slice_sheet(sheet_path: Path, out_dir: Path) -> dict[str, Path]:
    """Crop the 8 activity panels (+ a hero duo) from the sheet.

    Returns a dict {activity_name: image_path}. Empty dict if it can't run.
    """
    try:
        from PIL import Image
    except Exception as exc:  # Pillow not installed
        print(f"[sheet_slicer] Pillow unavailable ({exc}); skipping slice.")
        return {}

    sheet_path = Path(sheet_path)
    if not sheet_path.exists():
        return {}

    try:
        img = Image.open(sheet_path).convert("RGB")
    except Exception as exc:
        print(f"[sheet_slicer] cannot open sheet ({exc}).")
        return {}

    w, h = img.size
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}

    for name, (l, t, r, b) in ACTIVITY_BOXES.items():
        box = (int(l * w), int(t * h), int(r * w), int(b * h))
        try:
            crop = img.crop(box)
            dest = out_dir / f"{name}.png"
            crop.save(dest)
            result[name] = dest
        except Exception as exc:
            print(f"[sheet_slicer] failed to crop {name} ({exc}).")

    # Hero duo (generic fallback reference for jon/katie).
    try:
        l, t, r, b = HERO_BOX
        hero = img.crop((int(l * w), int(t * h), int(r * w), int(b * h)))
        dest = out_dir / "duo.png"
        hero.save(dest)
        result["duo"] = dest
    except Exception:
        pass

    print(f"[sheet_slicer] sliced {len(result)} images -> {out_dir}")
    return result


if __name__ == "__main__":
    import sys

    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("characters/refs/sheet.png")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("characters/refs/_scenes")
    slice_sheet(src, out)
