"""Humanization: Gaussian jitter for timing and click positions."""
import random
import time
import logging
from .config import load_config

logger = logging.getLogger(__name__)


def _gauss(mean: float, std: float, low: float, high: float) -> float:
    x = random.gauss(mean, std)
    return max(low, min(high, x))


def reaction_delay_ms() -> float:
    """Delay before acting (e.g. after we see our turn)."""
    cfg = load_config().get("humanization", {})
    mean = cfg.get("reaction_time_mean_ms", 800)
    std = cfg.get("reaction_time_std_ms", 150)
    return _gauss(mean, std, 200, 2500)


def move_delay_ms() -> float:
    """Delay between first click and second click (move time)."""
    cfg = load_config().get("humanization", {})
    mean = cfg.get("move_time_mean_ms", 250)
    std = cfg.get("move_time_std_ms", 50)
    return _gauss(mean, std, 50, 800)


def mouse_move_duration(distance_px: float) -> float:
    """
    Calculate humanized mouse movement duration based on distance.
    Uses Fitts's Law approximation: longer distances take more time, with some randomness.
    Returns duration in seconds.
    """
    cfg = load_config().get("humanization", {})
    # Base speed in pixels per second (how fast the mouse moves on average)
    base_speed = cfg.get("mouse_speed_px_per_sec", 800)
    # Minimum duration even for tiny movements
    min_duration = cfg.get("mouse_min_duration_sec", 0.08)
    # Maximum duration to cap very long movements
    max_duration = cfg.get("mouse_max_duration_sec", 0.6)
    # Randomness factor (std as fraction of calculated duration)
    jitter_frac = cfg.get("mouse_duration_jitter_frac", 0.15)
    
    # Base duration from distance
    base_duration = distance_px / base_speed
    
    # Add some randomness
    std = base_duration * jitter_frac
    duration = _gauss(base_duration, std, min_duration, max_duration)
    
    return duration


def jitter_xy(x: float, y: float, square_size: float) -> tuple[float, float]:
    """Add Gaussian jitter to click position. square_size = width/height of one square."""
    cfg = load_config().get("humanization", {})
    frac = cfg.get("click_jitter_std_fraction", 0.15)
    std = square_size * frac
    dx = random.gauss(0, std)
    dy = random.gauss(0, std)
    return x + dx, y + dy


def sleep_reaction():
    """Sleep for humanized reaction time (seconds)."""
    t = reaction_delay_ms() / 1000.0
    logger.debug("Reaction delay %.2fs", t)
    time.sleep(t)


def sleep_move_interval():
    """Sleep for humanized move interval (seconds)."""
    t = move_delay_ms() / 1000.0
    logger.debug("Move interval %.2fs", t)
    time.sleep(t)
