"""Signal generation (thin module boundary for the research stack)."""

from __future__ import annotations

from .research import build_signal, signal_significance

__all__ = ["build_signal", "signal_significance"]
