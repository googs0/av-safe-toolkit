#!/usr/bin/env python3
"""
AV-SAFE: video → light (TLM) sanity-check CLI

Examples:
  avsafe-video-to-light --in tests/assets/video/avsafe_flicker_10hz_60fps.mp4
  avsafe-video-to-light --in clip.mp4 --fps-override 30 --window-s 1 --step-s 1
  avsafe-video-to-light --in clip.mp4 --minute --jsonl out.jsonl
"""
from __future__ import annotations
import argparse, json, sys, pathlib
from typing import Optional

from avsafe_descriptors.video.luma import read_video_luma
from avsafe_descriptors.light import window_metrics, MinuteAggregator

def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="avsafe-video-to-light",
                                description="Reduce video to luminance and compute TLM metrics.")
    p.add_argument("--in", dest="in_paths", nargs="+", required=True, help="Input video file(s).")
    p.add_argument("--fps-override", type=float, default=None, help="Override FPS if metadata missing/incorrect.")
    p.add_argument("--window-s", type=float, default=1.0, help="Window size in seconds (default: 1.0).")
    p.add_argument("--step-s", type=float, default=1.0, help="Step size in seconds (default: 1.0).")
    p.add_argument("--mains-hint", type=float, default=None, help="50 or 60 to hint spectral pick.")
    p.add_argument("--minute", action="store_true", help="Emit one per-file minute summary instead of per-window rows.")
    p.add_argument("--jsonl", type=str, default=None, help="Output path (JSON Lines). Default: stdout.")
    return p.parse_args(argv)

def main(argv=None) -> int:
    args = parse_args(argv)
    out_f = sys.stdout if args.jsonl in (None, "-") else open(args.jsonl, "w", encoding="utf-8")
    try:
        with out_f:
            for path in args.in_paths:
                y, fs = read_video_luma(path, fps_override=args.fps_override)
                if args.minute:
                    agg = MinuteAggregator()
                    for m in window_metrics(y, fs=fs, window_s=args.window_s, step_s=args.step_s,
                                            mains_hint=args.mains_hint):
                        agg.add(m)
                    row = {"source": str(pathlib.Path(path).name)} | agg.summary()
                    out_f.write(json.dumps(row) + "\n")
                else:
                    for m in window_metrics(y, fs=fs, window_s=args.window_s, step_s=args.step_s,
                                            mains_hint=args.mains_hint):
                        row = {"source": str(pathlib.Path(path).name)} | m
                        out_f.write(json.dumps(row) + "\n")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
