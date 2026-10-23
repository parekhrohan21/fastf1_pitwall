"""Brag video renderer (Issue #171): telemetry latent trajectory → broadcast-style highlight clip.

Frames are drawn with Pillow (already a dependency via fpdf2), so rendering needs nothing new.
MP4 encoding uses ``imageio`` + ``imageio-ffmpeg`` when installed; otherwise the clip is
encoded as an animated GIF with Pillow, at lower resolution / frame rate, so the feature
still works on a bare install.

Pipeline: ``generate_brag_video_frames`` → ``_frame_stream`` (one PIL frame at a time, so
memory stays flat) → ``_encode_mp4`` or ``_encode_gif``.
"""
from __future__ import annotations

import importlib.util
import io
import os
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.data.loader import _latent_frame_times  # frame clock shared with the data layer

# Frame size presets (landscape width × height); portrait swaps them. All dimensions are even,
# as H.264 requires.
RESOLUTIONS: dict[str, tuple[int, int]] = {"360p": (640, 360), "540p": (960, 540), "720p": (1280, 720)}
MAX_FRAMES = 2400          # hard cap so a long lap at 60 FPS cannot exhaust memory / time
GIF_MAX_FRAMES = 360       # GIF frames are held in memory until saved, so the cap is lower
_BG, _PANEL, _TEXT, _DIM = (14, 16, 24), (24, 27, 38), (240, 242, 248), (130, 136, 156)

_FONTS: dict[int, ImageFont.ImageFont] = {}


def _font(size: int) -> ImageFont.ImageFont:
    """Cached default font at ``size`` px (falls back to Pillow's fixed bitmap font on old Pillow)."""
    if size not in _FONTS:
        try:
            _FONTS[size] = ImageFont.load_default(size=size)
        except TypeError:
            _FONTS[size] = ImageFont.load_default()
    return _FONTS[size]


def _rgb(hex_col: str) -> tuple[int, int, int]:
    """'#RRGGBB' → (r, g, b); a bad value falls back to F1 red."""
    try:
        h = hex_col.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return 232, 0, 45


def video_size(aspect_ratio: str = "16:9", resolution: str = "540p") -> tuple[int, int]:
    """Frame (width, height) for an aspect ratio ('16:9' landscape or '9:16' portrait)."""
    w, h = RESOLUTIONS.get(resolution, RESOLUTIONS["540p"])
    return (h, w) if aspect_ratio == "9:16" else (w, h)


def _layout(w: int, h: int) -> dict[str, tuple[int, int, int, int]]:
    """Rectangles (x0, y0, x1, y1) for the track, HUD and latent mini-plot."""
    m = max(8, w // 80)
    if w >= h:                                       # landscape: track left, HUD right
        split = int(w * 0.58)
        return {"track": (m, m, split - m, h - m), "hud": (split, m, w - m, int(h * 0.68)),
                "latent": (split, int(h * 0.7), w - m, h - m)}
    split = int(h * 0.44)                            # portrait: track top, HUD below
    return {"track": (m, m, w - m, split - m), "hud": (m, split, w - m, int(h * 0.82)),
            "latent": (m, int(h * 0.84), w - m, h - m)}


def _fit(xs: np.ndarray, ys: np.ndarray, rect: tuple[int, int, int, int], ref: tuple[np.ndarray, np.ndarray]):
    """Map world coordinates into ``rect`` with a uniform scale, using ``ref`` for the bounds."""
    x0, y0, x1, y1 = rect
    rx, ry = ref
    span_x, span_y = max(rx.max() - rx.min(), 1e-6), max(ry.max() - ry.min(), 1e-6)
    pad = 0.08
    sc = min((x1 - x0) * (1 - 2 * pad) / span_x, (y1 - y0) * (1 - 2 * pad) / span_y)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    px = cx + (xs - (rx.max() + rx.min()) / 2) * sc
    py = cy - (ys - (ry.max() + ry.min()) / 2) * sc        # screen y grows downward
    return px, py


def _base_image(w, h, lay, latent, latent2, label, label2, colour):
    """Static background: panels, the circuit outline and the latent trajectory outline."""
    img = Image.new("RGB", (w, h), _BG)
    d = ImageDraw.Draw(img)
    for key in ("track", "hud", "latent"):
        d.rounded_rectangle(lay[key], radius=10, fill=_PANEL)
    allx = np.concatenate([latent["x"]] + ([latent2["x"]] if latent2 else []))
    ally = np.concatenate([latent["y"]] + ([latent2["y"]] if latent2 else []))
    px, py = _fit(latent["x"], latent["y"], lay["track"], (allx, ally))
    if latent["has_xy"]:
        d.line(list(zip(px.tolist(), py.tolist())), fill=(70, 76, 96), width=max(3, w // 160))
    else:                                            # no position data: a progress line on distance
        mid = (lay["track"][1] + lay["track"][3]) // 2
        d.line([(lay["track"][0] + 16, mid), (lay["track"][2] - 16, mid)], fill=(70, 76, 96), width=4)
    z = latent["z"]
    lx, ly = _fit(z[:, 0], z[:, 1] if z.shape[1] > 1 else np.zeros(len(z)), lay["latent"], (z[:, 0], z[:, 1] if z.shape[1] > 1 else np.zeros(len(z))))
    d.line(list(zip(lx.tolist(), ly.tolist())), fill=(60, 66, 90), width=2)
    d.text((lay["latent"][0] + 10, lay["latent"][1] + 6), "LATENT SPACE  z1 / z2", font=_font(max(10, h // 45)), fill=_DIM)
    title = label + (f"  vs  {label2}" if label2 else "")
    d.text((lay["track"][0] + 14, lay["track"][1] + 10), title, font=_font(max(14, h // 26)), fill=_rgb(colour))
    return img, (px, py), (lx, ly)


def _frame_stream(latent, moments, fps, w, h, speed, clips, latent2, colour, colour2, label, label2):
    """Yield one RGB PIL frame at a time for the whole clip."""
    lay = _layout(w, h)
    base, (px, py), (lx, ly) = _base_image(w, h, lay, latent, latent2, label, label2, colour)
    frame_t = _latent_frame_times(latent, fps, speed, clips)
    t = latent["t"]
    rpm_max = max(float(np.max(latent["rpm"])), 1.0)
    c1, c2 = _rgb(colour), _rgb(colour2)

    if latent2 is not None:                           # second car shares the first car's scale
        allx = np.concatenate([latent["x"], latent2["x"]])
        ally = np.concatenate([latent["y"], latent2["y"]])
        px2, py2 = _fit(latent2["x"], latent2["y"], lay["track"], (allx, ally))
        px, py = _fit(latent["x"], latent["y"], lay["track"], (allx, ally))

    hx0, hy0, hx1, hy1 = lay["hud"]
    for tau in frame_t:
        i = int(np.clip(np.searchsorted(t, tau), 0, len(t) - 1))
        img = base.copy()
        d = ImageDraw.Draw(img)

        # Track: the part of the lap already driven, then the car marker(s).
        if i > 1:
            d.line(list(zip(px[:i + 1].tolist(), py[:i + 1].tolist())), fill=c1, width=max(3, w // 200))
        r = max(6, w // 110)
        d.ellipse([px[i] - r, py[i] - r, px[i] + r, py[i] + r], fill=(255, 255, 255), outline=c1, width=3)
        if latent2 is not None:
            j = int(np.clip(np.searchsorted(latent2["t"], tau), 0, len(latent2["t"]) - 1))
            d.ellipse([px2[j] - r, py2[j] - r, px2[j] + r, py2[j] + r], fill=(255, 255, 255), outline=c2, width=3)

        # Latent mini-plot: the dot rides the manifold.
        d.ellipse([lx[i] - 5, ly[i] - 5, lx[i] + 5, ly[i] + 5], fill=c1)

        # HUD: speed, gear, DRS.
        u = h / 540.0 if w >= h else w / 540.0
        d.text((hx0 + 16, hy0 + 8), f"{latent['speed'][i]:.0f}", font=_font(int(64 * u)), fill=_TEXT)
        d.text((hx0 + 16, hy0 + int(76 * u)), "km/h", font=_font(int(16 * u)), fill=_DIM)
        d.text((hx1 - int(70 * u), hy0 + 8), f"{int(latent['gear'][i])}", font=_font(int(54 * u)), fill=c1)
        d.text((hx1 - int(70 * u), hy0 + int(66 * u)), "GEAR", font=_font(int(13 * u)), fill=_DIM)
        if latent["drs"][i] > 0.5:
            d.rounded_rectangle([hx0 + 16, hy0 + int(100 * u), hx0 + 16 + int(58 * u), hy0 + int(122 * u)], radius=6, fill=(0, 200, 120))
            d.text((hx0 + 24, hy0 + int(103 * u)), "DRS", font=_font(int(15 * u)), fill=(0, 0, 0))

        # RPM rev-light bar: 15 segments, green → amber → red.
        segs, bar_y, bar_h = 15, hy0 + int(134 * u), int(16 * u)
        seg_w = (hx1 - hx0 - 32) / segs
        lit = int(round(segs * min(latent["rpm"][i] / rpm_max, 1.0)))
        for n in range(segs):
            col = (0, 210, 110) if n < 7 else ((255, 190, 0) if n < 11 else (255, 60, 60))
            x = hx0 + 16 + n * seg_w
            d.rectangle([x + 1, bar_y, x + seg_w - 2, bar_y + bar_h], fill=col if n < lit else (45, 49, 66))

        # Pedal meters (throttle green, brake red) and friction circle (a_lat × a_lon).
        py0 = bar_y + bar_h + int(14 * u)
        mh = max(30, hy1 - py0 - 16)
        for k_, (val, col, name) in enumerate(((latent["throttle"][i] / 100.0, (0, 210, 110), "THR"),
                                               (float(latent["brake"][i]), (255, 60, 60), "BRK"))):
            bx = hx0 + 16 + k_ * int(46 * u)
            d.rectangle([bx, py0, bx + int(30 * u), py0 + mh], fill=(45, 49, 66))
            d.rectangle([bx, py0 + mh * (1 - min(max(val, 0), 1)), bx + int(30 * u), py0 + mh], fill=col)
            d.text((bx, py0 + mh + 2), name, font=_font(int(11 * u)), fill=_DIM)
        fc_r = min(mh, (hx1 - hx0) - int(120 * u)) / 2
        fcx, fcy = hx1 - 16 - fc_r, py0 + mh / 2
        d.ellipse([fcx - fc_r, fcy - fc_r, fcx + fc_r, fcy + fc_r], outline=(70, 76, 96), width=2)
        d.line([(fcx - fc_r, fcy), (fcx + fc_r, fcy)], fill=(45, 49, 66))
        d.line([(fcx, fcy - fc_r), (fcx, fcy + fc_r)], fill=(45, 49, 66))
        for back, a in ((6, 90), (3, 150), (0, 255)):         # short fading trail
            q = max(i - back * 3, 0)
            gx = float(np.clip(latent["a_lat"][q] / 5.0, -1, 1))
            gy = float(np.clip(-latent["a_lon"][q] / 5.0, -1, 1))
            rr = 4 if back else 7
            d.ellipse([fcx + gx * fc_r - rr, fcy + gy * fc_r - rr, fcx + gx * fc_r + rr, fcy + gy * fc_r + rr],
                      fill=tuple(int(c * a / 255) for c in c1))

        # Brag badge: shown for ~2 s of video after a highlight moment.
        window = 2.0 * max(speed, 1.0)
        active = [m for m in moments if -0.3 * speed <= tau - m["t_s"] <= window]
        if active:
            m = active[-1]
            bw, bh = int(w * 0.5) if w >= h else int(w * 0.9), int(h * 0.09 if w >= h else h * 0.06)
            bx0 = (lay["track"][0] + lay["track"][2]) // 2 - bw // 2 if w >= h else (w - bw) // 2
            by0 = lay["track"][3] - bh - 14
            d.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=12, fill=(10, 10, 14), outline=c1, width=3)
            d.text((bx0 + 16, by0 + bh * 0.2), "BRAG  " + m["label"], font=_font(max(14, int(bh * 0.5))), fill=_TEXT)

        yield img


def _mp4_available() -> bool:
    """True when both imageio and imageio-ffmpeg can be imported."""
    return importlib.util.find_spec("imageio") is not None and importlib.util.find_spec("imageio_ffmpeg") is not None


def _encode_mp4(frames, fps: int) -> bytes:
    """Stream frames into an H.264 MP4 via imageio and return the file bytes."""
    import imageio.v2 as imageio
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        writer = imageio.get_writer(path, fps=fps, codec="libx264", macro_block_size=2, quality=7)
        try:
            for f in frames:
                writer.append_data(np.asarray(f))
        finally:
            writer.close()
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.remove(path)


def _encode_gif(frames, fps: int) -> bytes:
    """Encode frames as an endlessly looping animated GIF with a 64-colour palette."""
    pal = [f.quantize(colors=64, method=Image.Quantize.FASTOCTREE) for f in frames]
    buf = io.BytesIO()
    pal[0].save(buf, format="GIF", save_all=True, append_images=pal[1:], duration=int(1000 / fps), loop=0, optimize=False)
    return buf.getvalue()


def generate_brag_video_frames(
    latent_data: dict | None,
    moments: list[dict],
    fps: int = 30,
    aspect_ratio: str = "16:9",
    resolution: str = "540p",
    speed: float = 1.0,
    clips: list[tuple[float, float]] | None = None,
    latent_data2: dict | None = None,
    colour: str = "#E8002D",
    colour2: str = "#FF8700",
    label: str = "",
    label2: str = "",
    force_gif: bool = False,
) -> tuple[bytes, str]:
    """Render the highlight clip and return ``(video_bytes, mime_type)``.

    ``mime_type`` is ``video/mp4`` when imageio-ffmpeg is installed, else ``image/gif``.
    Returns ``(b"", "")`` if there is no latent data. Playback ``speed`` is raised
    automatically when the clip would exceed ``MAX_FRAMES``.
    """
    if not latent_data or len(latent_data.get("t", [])) < 2:
        return b"", ""
    use_mp4 = _mp4_available() and not force_gif

    if not use_mp4:                                  # GIF is memory-hungry: smaller and slower
        resolution, fps = "360p", min(fps, 15)
    w, h = video_size(aspect_ratio, resolution)

    duration = sum(b - a for a, b in clips) if clips else float(latent_data["t"][-1])
    cap = MAX_FRAMES if use_mp4 else GIF_MAX_FRAMES
    speed = max(speed, duration * fps / cap)

    def stream():
        return _frame_stream(latent_data, moments, fps, w, h, speed, clips, latent_data2, colour, colour2, label, label2)

    if use_mp4:
        try:
            return _encode_mp4(stream(), fps), "video/mp4"
        except Exception:
            # ffmpeg missing or encoder error: drop to the GIF path rather than fail the feature.
            return generate_brag_video_frames(latent_data, moments, fps, aspect_ratio, resolution, speed, clips,
                                              latent_data2, colour, colour2, label, label2, force_gif=True)
    return _encode_gif(list(stream()), fps), "image/gif"
