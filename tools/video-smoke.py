#!/usr/bin/env python3
"""
Quick smoke: video → mean-luma → TLM minute summary.
Run from repo root:
  python tools/video_smoke.py tests/assets/video/avsafe_flicker_10hz_60fps.mp4 --fps 60
"""
from __future__ import annotations
import argparse, json, sys
from avsafe_descriptors.video.luma import read_video_luma
from avsafe_descriptors.light import window_metrics, MinuteAggregator

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("video", help="Path to a test video")
    p.add_argument("--fps", type=float, default=None, help="Override FPS if metadata is missing")
    a = p.parse_args(argv)

    y, fs = read_video_luma(a.video, fps_override=a.fps)
    agg = MinuteAggregator()
    for m in window_metrics(y, fs=fs, window_s=1.0, step_s=1.0, mains_hint=None):
        agg.add(m)
    print(json.dumps(agg.summary(), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
