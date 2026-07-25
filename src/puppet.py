"""Puppet animation engine — REAL talking characters, free, CPU-only.

Instead of an AI video model (which on free GPUs only produces a faint wiggle),
this animates Jon & Katie like a cartoon puppet rig:

  * lip-sync   : the speaker's mouth opens/closes in time with their voice
                 (driven by the actual audio envelope of that scene's mp3)
  * blinking   : periodic eye blinks (if a blink sprite is provided)
  * body life  : gentle bounce/bob + a subtle lean, per character
  * camera     : slow push-in on the background so shots feel alive
  * staging    : the speaking character is bigger/front, the other idles beside

Everything is Pillow + FFmpeg, so it needs NO GPU and runs fine on GitHub
Actions. Output is one mp4 per scene, matching what assemble.py expects.

Sprites (characters/sprites/, PNG, plain background is auto-removed):
    jon_closed.png    jon_open.png    [jon_blink.png]
    katie_closed.png  katie_open.png  [katie_blink.png]
Backgrounds: the activity panels sliced from characters/refs/sheet.png.
"""
from __future__ import annotations

import array
import math
import shutil
import subprocess
from pathlib import Path

FPS = 25
W, H = 1920, 1080
SR = 16000  # audio sample rate used for the lip-sync envelope


# ─────────────────────────────── audio → mouth ───────────────────────────────
def audio_envelope(audio_path: Path, fps: int = FPS) -> list[float]:
    """Per-frame loudness (0..1) of an audio file, used to drive the mouth."""
    if not audio_path or not Path(audio_path).exists():
        return []
    try:
        res = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(audio_path),
             "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(SR), "-"],
            capture_output=True, timeout=120,
        )
        if res.returncode != 0 or not res.stdout:
            return []
        samples = array.array("h")
        data = res.stdout
        samples.frombytes(data[: len(data) - (len(data) % 2)])
    except Exception:
        return []

    win = max(1, SR // fps)
    env: list[float] = []
    for start in range(0, len(samples), win):
        chunk = samples[start:start + win]
        if not chunk:
            break
        acc = 0
        for s in chunk:
            acc += s * s
        env.append(math.sqrt(acc / len(chunk)) / 32768.0)

    peak = max(env) if env else 0.0
    if peak <= 0:
        return [0.0] * len(env)
    return [min(1.0, v / peak) for v in env]


# ──────────────────────────────── sprites ────────────────────────────────────
def _auto_transparent(img):
    """Make a plain (near-uniform) background transparent so cutouts sit nicely."""
    from PIL import Image

    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    # only strip if the corners agree (i.e. it really is a plain backdrop)
    r0 = sum(c[0] for c in corners) / 4
    g0 = sum(c[1] for c in corners) / 4
    b0 = sum(c[2] for c in corners) / 4
    spread = max(
        max(abs(c[0] - r0), abs(c[1] - g0), abs(c[2] - b0)) for c in corners
    )
    if spread > 28:
        return img  # busy background: leave as-is

    tol = 42
    out = Image.new("RGBA", img.size)
    op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if abs(r - r0) < tol and abs(g - g0) < tol and abs(b - b0) < tol:
                op[x, y] = (r, g, b, 0)
            else:
                op[x, y] = (r, g, b, a)
    return out


def load_sprites(sprites_dir: Path) -> dict:
    """Load jon/katie mouth-closed, mouth-open and (optional) blink sprites."""
    from PIL import Image

    sprites: dict = {}
    if not sprites_dir.exists():
        return sprites
    for who in ("jon", "katie"):
        entry: dict = {}
        for state in ("closed", "open", "blink"):
            for name in (f"{who}_{state}.png", f"{who}-{state}.png"):
                p = sprites_dir / name
                if p.exists():
                    try:
                        entry[state] = _auto_transparent(Image.open(p))
                    except Exception as exc:
                        print(f"[puppet] cannot load {name}: {exc}")
                    break
        # a single plain image (jon.png) can still act as the closed mouth
        if "closed" not in entry:
            p = sprites_dir / f"{who}.png"
            if p.exists():
                try:
                    entry["closed"] = _auto_transparent(Image.open(p))
                except Exception:
                    pass
        if entry.get("closed") is not None:
            entry.setdefault("open", entry["closed"])
            sprites[who] = entry
    return sprites


def _fit_height(img, target_h: int):
    w, h = img.size
    if h == 0:
        return img
    scale = target_h / h
    return img.resize((max(1, int(w * scale)), target_h))


# ──────────────────────────────── rendering ──────────────────────────────────
def _background(bg_path: Path | None, frame_idx: int, total: int):
    """Background with a slow camera push-in (Ken-Burns on the scene art)."""
    from PIL import Image

    if bg_path and Path(bg_path).exists():
        try:
            bg = Image.open(bg_path).convert("RGB")
        except Exception:
            bg = Image.new("RGB", (W, H), (246, 214, 194))
    else:
        bg = Image.new("RGB", (W, H), (246, 214, 194))

    # cover W×H
    bw, bh = bg.size
    scale = max(W / bw, H / bh) * 1.12  # a little headroom for the push-in
    bg = bg.resize((max(W, int(bw * scale)), max(H, int(bh * scale))))

    t = frame_idx / max(total - 1, 1)
    zoom = 1.0 + 0.06 * t                     # gentle push-in
    bw, bh = bg.size
    cw, ch = int(W / zoom), int(H / zoom)
    cx = int((bw - cw) / 2 + math.sin(t * math.pi) * 18)  # tiny drift
    cy = int((bh - ch) / 2)
    bg = bg.crop((cx, cy, cx + cw, cy + ch)).resize((W, H))
    return bg


def render_scene(
    scene: dict,
    bg_path: Path | None,
    audio_path: Path | None,
    sprites: dict,
    out_mp4: Path,
    seconds: float,
) -> bool:
    """Render one animated scene (talking puppet over the scene art)."""
    from PIL import Image

    total = max(int(seconds * FPS), FPS)
    env = audio_envelope(Path(audio_path)) if audio_path else []

    speaker = (scene.get("speaker") or "").strip().lower()
    if speaker not in ("jon", "katie"):
        speaker = "jon" if scene.get("id", 1) % 2 else "katie"
    other = "katie" if speaker == "jon" else "jon"

    spk = sprites.get(speaker) or {}
    oth = sprites.get(other) or {}
    if not spk and not oth:
        return False

    # pre-scale sprite variants once (speaker larger / in front)
    spk_h, oth_h = int(H * 0.66), int(H * 0.52)
    spk_v = {k: _fit_height(v, spk_h) for k, v in spk.items() if v is not None}
    oth_v = {k: _fit_height(v, oth_h) for k, v in oth.items() if v is not None}

    frames_dir = out_mp4.parent / f"_frames_{out_mp4.stem}"
    if frames_dir.exists():
        shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    speaker_left = scene.get("id", 1) % 2 == 1  # alternate staging per scene

    for i in range(total):
        canvas = _background(bg_path, i, total)

        # --- animation curves -------------------------------------------------
        t = i / FPS
        spk_bob = int(9 * math.sin(t * 5.0))           # lively bounce
        oth_bob = int(6 * math.sin(t * 3.2 + 1.1))     # calmer idle
        loud = env[i] if i < len(env) else 0.0
        talking = loud > 0.16
        blink = (i % int(FPS * 2.6)) < 3               # ~3 frames every 2.6s

        # --- pick sprite variants --------------------------------------------
        spk_img = spk_v.get("open") if talking else spk_v.get("closed")
        if blink and not talking and spk_v.get("blink") is not None:
            spk_img = spk_v["blink"]
        oth_img = oth_v.get("blink") if (blink and oth_v.get("blink") is not None) \
            else oth_v.get("closed")

        # --- place characters -------------------------------------------------
        base_y = int(H * 0.97)
        spk_x = int(W * (0.30 if speaker_left else 0.70))
        oth_x = int(W * (0.72 if speaker_left else 0.28))

        for img, x, bob in ((oth_img, oth_x, oth_bob), (spk_img, spk_x, spk_bob)):
            if img is None:
                continue
            iw, ih = img.size
            canvas.paste(img, (x - iw // 2, base_y - ih + bob), img)

        canvas.save(frames_dir / f"f_{i:05d}.png")

    # --- frames -> mp4 --------------------------------------------------------
    cmd = [
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", str(frames_dir / "f_%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out_mp4),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    shutil.rmtree(frames_dir, ignore_errors=True)
    if res.returncode != 0:
        print(f"[puppet] ffmpeg failed: {res.stderr[-400:]}")
        return False
    return True
