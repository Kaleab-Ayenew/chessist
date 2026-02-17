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
