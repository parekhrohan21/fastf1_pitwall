"""Tests for the Automated Session Brag Video / telemetry latent space (Issue #171)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest
from src.data.loader import (
    _build_telemetry_latent_manifold, _extract_brag_worthy_moments,
    _interpolate_latent_trajectory, _latent_frame_times,
)
from src.charts import video
from src.charts.video import generate_brag_video_frames, video_size
from src.charts.plotly import build_latent_space_projection_fig
from src.ui.components import _reel_clips, _generate_brag_result


def _tel(n=300, dt=0.2, xy=True):
    """Synthetic lap on an oval: speed 200 ± 100 km/h, brake while slowing, DRS when fastest."""
    th = np.linspace(0, 2 * np.pi, n)
    speed = 200 + 100 * np.cos(3 * th)
    df = pd.DataFrame({
        "Time": pd.to_timedelta(np.arange(n) * dt, unit="s"),
        "Distance": np.cumsum(speed / 3.6 * dt),
        "Speed": speed, "Throttle": np.where(np.gradient(speed) > 0, 100.0, 0.0),
        "Brake": np.gradient(speed) < -1, "RPM": 8000 + speed * 15,
        "nGear": (speed // 45).clip(1, 8), "DRS": np.where(speed > 285, 12, 0),
    })
    if xy:
        df["X"], df["Y"] = np.cos(th) * 3000, np.sin(th) * 2000
    return df


@pytest.fixture
def latent():
    return _build_telemetry_latent_manifold("k", "AAA", 7, _tel())


def test_latent_manifold_dimensions_and_variance(latent):
    assert latent["z"].shape == (300, 3) and latent["k"] == 3
    ev = latent["explained_variance"]
    assert len(ev) == 3 and (ev > 0).all() and ev.sum() <= 1.0 + 1e-9
    assert ev[0] >= ev[1] >= ev[2]                     # principal axes come out in order
    assert {"Speed", "a_lon", "a_lat"}.issubset(latent["channels"])
    assert latent["has_xy"] is True


def test_latent_manifold_without_position_or_with_bad_input():
    assert _build_telemetry_latent_manifold("k2", "AAA", 7, _tel(xy=False))["has_xy"] is False
    assert _build_telemetry_latent_manifold("k3", "AAA", 7, _tel(n=10)) is None            # too short
    assert _build_telemetry_latent_manifold("k4", "AAA", 7, pd.DataFrame()) is None
    assert _build_telemetry_latent_manifold("k5", "AAA", 7, _tel().drop(columns=["Speed"])) is None


def test_moments_top_speed_and_braking(latent):
    moms = {m["type"]: m for m in _extract_brag_worthy_moments("k", "AAA", pd.DataFrame(), latent)}
    top = moms["top_speed"]
    assert top["value"] == pytest.approx(latent["speed"].max())
    assert top["t_s"] == pytest.approx(latent["t"][int(np.argmax(latent["speed"]))])
    assert "DRS" in top["label"]
    assert moms["peak_braking"]["value"] == pytest.approx(abs(latent["a_lon"].min()))
    assert moms["apex_speed"]["value"] < top["value"]


def _laps(sector_times):
    """AAA lap 7 plus a rival; sector_times = AAA's three sector seconds."""
    rows = [("AAA", 7, *sector_times), ("AAA", 8, 31.0, 31.0, 31.0), ("BBB", 7, 30.5, 28.0, 31.0)]
    return pd.DataFrame({
        "Driver": [r[0] for r in rows], "LapNumber": [r[1] for r in rows],
        **{f"Sector{n}Time": [pd.to_timedelta(r[1 + n], unit="s") for r in rows] for n in (1, 2, 3)},
    })


def test_sector_moments_purple_and_personal_best(latent):
    # S1 29.0 beats everyone (purple); S2 29.5 beats AAA's other lap (31) but not BBB's 28 (PB); S3 32 is neither.
    moms = _extract_brag_worthy_moments("k", "AAA", _laps([29.0, 29.5, 32.0]), latent)
    labels = [m["label"] for m in moms]
    assert "PURPLE SECTOR 1" in labels and "PERSONAL BEST SECTOR 2" in labels
    assert not any("SECTOR 3" in l for l in labels)
    assert [m["t_s"] for m in moms] == sorted(m["t_s"] for m in moms)


def test_moments_empty_for_missing_data():
    assert _extract_brag_worthy_moments("k", "AAA", pd.DataFrame(), None) == []


def test_interpolation_frame_count_and_continuity(latent):
    z30 = _interpolate_latent_trajectory(latent, target_fps=30)
    assert abs(len(z30) - round(latent["t"][-1] * 30)) <= 1
    assert z30.shape[1] == 3
    # 4x playback has a quarter of the frames, and a smooth path has no jumps between frames.
    assert abs(len(_interpolate_latent_trajectory(latent, 30, speed=4.0)) - len(z30) / 4) <= 1
    span = np.ptp(latent["z"], axis=0)
    assert (np.abs(np.diff(z30, axis=0)).max(axis=0) < 0.2 * span).all()
    assert len(_interpolate_latent_trajectory(latent, 60)) > len(z30)


def test_frame_clock_clips(latent):
    times = _latent_frame_times(latent, 10, 1.0, clips=[(0, 2), (10, 12)])
    assert len(times) == 40 and times[0] == 0 and times[-1] == pytest.approx(12)
    assert len(_latent_frame_times(latent, 10, 1.0, clips=[(500, 600)])) == 2   # out of range → fallback


def test_reel_clips_merge_overlapping_windows():
    clips = _reel_clips([{"t_s": 10.0}, {"t_s": 12.0}, {"t_s": 30.0}], pad=2.5)
    assert clips == [(7.5, 14.5), (27.5, 32.5)]


def test_video_size_aspect_ratios():
    assert video_size("16:9", "540p") == (960, 540)
    assert video_size("9:16", "540p") == (540, 960)
    assert all(v % 2 == 0 for v in video_size("16:9", "720p"))


def test_gif_fallback_encoding(latent, monkeypatch):
    monkeypatch.setattr(video, "_mp4_available", lambda: False)
    moms = _extract_brag_worthy_moments("k", "AAA", pd.DataFrame(), latent)
    data, mime = generate_brag_video_frames(latent, moms, fps=10, speed=8.0, label="AAA")
    assert mime == "image/gif" and data[:4] == b"GIF8"
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(data))
    assert img.n_frames >= 5 and img.size == (640, 360)


def test_portrait_duel_and_clip_render(latent, monkeypatch):
    monkeypatch.setattr(video, "_mp4_available", lambda: False)
    other = _build_telemetry_latent_manifold("k6", "BBB", 3, _tel(dt=0.21))
    data, mime = generate_brag_video_frames(latent, [], fps=10, aspect_ratio="9:16", speed=1.0,
                                            clips=[(0, 2), (20, 22)], latent_data2=other, label="A", label2="B")
    from PIL import Image
    import io
    assert mime == "image/gif" and Image.open(io.BytesIO(data)).size == (360, 640)


def test_no_latent_data_returns_empty():
    assert generate_brag_video_frames(None, []) == (b"", "")


def test_mp4_failure_falls_back_to_gif(latent, monkeypatch):
    monkeypatch.setattr(video, "_mp4_available", lambda: True)
    def boom(frames, fps):
        raise RuntimeError("no ffmpeg")
    monkeypatch.setattr(video, "_encode_mp4", boom)
    data, mime = generate_brag_video_frames(latent, [], fps=10, speed=8.0)
    assert mime == "image/gif" and data[:4] == b"GIF8"


def test_frame_cap_raises_playback_speed(latent, monkeypatch):
    monkeypatch.setattr(video, "_mp4_available", lambda: False)
    monkeypatch.setattr(video, "GIF_MAX_FRAMES", 12)
    from PIL import Image
    import io
    data, _ = generate_brag_video_frames(latent, [], fps=30, speed=1.0)
    assert Image.open(io.BytesIO(data)).n_frames <= 13


def test_projection_figure(latent):
    moms = _extract_brag_worthy_moments("k", "AAA", pd.DataFrame(), latent)
    fig = build_latent_space_projection_fig(latent, moms)
    assert isinstance(fig, go.Figure) and fig.data[0].type == "scatter3d" and len(fig.data) == 2
    assert build_latent_space_projection_fig(None) is None


class _Lap(dict):
    def __init__(self, tel, n):
        super().__init__(LapNumber=n); self._tel = tel
    def get_telemetry(self):
        return self._tel


class _Laps:
    """Just enough of fastf1.core.Laps for _generate_brag_result."""
    def __init__(self, tel): self.tel = tel
    def pick_drivers(self, drv): return self
    def pick_fastest(self): return _Lap(self.tel, 7)


class _Sess:
    def __init__(self, tel): self.laps = _Laps(tel)


def test_generate_result_handles_missing_and_valid_telemetry(monkeypatch):
    monkeypatch.setattr(video, "_mp4_available", lambda: False)
    ok = _generate_brag_result(_Sess(_tel()), pd.DataFrame(), "AAA", 7, "kk", "Fastest Lap", "16:9", "360p", 10, 8,
                               "#E8002D", "#FF8700", "A", "", None)
    assert ok["mime"] == "image/gif" and ok["moments"] and ok["latent"]["k"] == 3
    bad = _generate_brag_result(_Sess(_tel(n=5)), pd.DataFrame(), "AAA", 7, "kk2", "Fastest Lap", "16:9", "360p", 10, 8,
                                "#E8002D", "#FF8700", "A", "", None)
    assert "incomplete" in bad["error"]
