"""
Video → luminance time series helper for AV-SAFE.

- read_video_luma(): returns (y, fs) where y is mean luma per frame and fs is fps.
- mean_luma(): Rec.601 luma from an RGB frame.
"""

from __future__ import annotations
import numpy as np

def mean_luma(frame: np.ndarray) -> float:
    # frame: HxWx3, uint8 or float
    f = frame.astype(np.float32)
    # Rec.601 luma (sufficient for synthetic/integration tests)
    return float((0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]).mean())

def _probe_fps(path: str) -> float | None:
    # Try imageio.v3 metadata first
    try:
        import imageio.v3 as iio
        meta0 = iio.immeta(path, index=0)  # may contain "fps" or "framerate"
        for k in ("fps", "framerate", "FramesPerSecond"):
            if k in meta0 and meta0[k]:
                return float(meta0[k])
    except Exception:
        pass
    return None

def read_video_luma(path: str, fps_override: float | None = None) -> tuple[np.ndarray, float]:
    """
    Read a video file and return (y, fs):
      y: np.ndarray of shape [n_frames], mean luma per frame
      fs: frames per second (float)

    Requires: imageio>=2.26 with imageio-ffmpeg installed for MP4.
    """
    import imageio.v3 as iio

    fs = fps_override or _probe_fps(path)
    if fs is None:
        raise RuntimeError(
            f"Could not determine FPS for {path}. "
            "Pass fps_override=... or ensure imageio-ffmpeg is installed."
        )

    y_vals: list[float] = []
    for frame in iio.imiter(path):  # yields HxWx3 uint8 frames
        y_vals.append(mean_luma(frame))
    return np.asarray(y_vals, dtype=np.float32), float(fs)
