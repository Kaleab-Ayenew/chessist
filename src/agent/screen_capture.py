"""Screen capture for assist mode: capture a region or full screen as RGB numpy array."""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def capture_region(
    left: int,
    top: int,
    width: int,
    height: int,
) -> np.ndarray:
    """
    Capture a screen region using mss. Returns RGB numpy array (H, W, 3).
    """
    import mss
    with mss.mss() as sct:
        monitor = {"left": left, "top": top, "width": width, "height": height}
        shot = sct.grab(monitor)
        # mss returns BGRA; convert to RGB
        img = np.array(shot)[:, :, :3]  # drop alpha
        img = img[:, :, ::-1]  # BGR -> RGB
    return img


def capture_full_screen(monitor_index: int = 0) -> np.ndarray:
    """
    Capture the primary (or given) monitor. Returns RGB numpy array (H, W, 3).
    monitor_index: 0 = primary, 1, 2, ... = other monitors.
    """
    import mss
    with mss.mss() as sct:
        mon = sct.monitors[monitor_index]
        shot = sct.grab(mon)
        img = np.array(shot)[:, :, :3]
        img = img[:, :, ::-1]
    return img
