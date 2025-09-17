"""
Light (Temporal Light Modulation) descriptors.

Exports:
    tlm_metrics       -> metrics for one window of light samples
    window_metrics    -> generator yielding metrics per window
    MinuteAggregator  -> collect per-window metrics and emit minute summaries
"""
from .tlm import tlm_metrics, window_metrics, MinuteAggregator

__all__ = ["tlm_metrics", "window_metrics", "MinuteAggregator"]
