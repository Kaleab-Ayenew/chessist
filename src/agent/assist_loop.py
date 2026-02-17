"""
Assist mode: capture screen region -> vision (FEN) -> Stockfish -> show recommended move.
No browser; user opens Chess.com themselves and makes the move manually.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Optional

import chess

from .config import load_config
from .screen_capture import capture_region, capture_full_screen
from .orient import image_to_fen_cv
from .decider import best_move

logger = logging.getLogger(__name__)

# Project root for saving last screenshot
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LAST_SCREENSHOT_PATH = _PROJECT_ROOT / "last_assist_screenshot.png"


def _get_region_from_config():
    """Return (left, top, width, height) or None to use full screen."""
    cfg = load_config()
    region = cfg.get("assist_region")
    if not region or not isinstance(region, dict):
        return None
    try:
        return (
            int(region.get("left", 0)),
            int(region.get("top", 0)),
            int(region.get("width", 400)),
            int(region.get("height", 400)),
        )
    except (TypeError, ValueError):
        return None


def run_assist_loop(
    we_play_white: bool,
    *,
    poll_interval: float = 2.0,
    on_move: Optional[Callable[[str, str], None]] = None,
) -> None:
    """
    Run the assist loop: capture screen, get FEN, get best move, call on_move(uci, san).
    Runs until KeyboardInterrupt. on_move(uci, san) is called each time a move is computed.
    """
    region = _get_region_from_config()
    if region is None:
        logger.info("No assist_region in config; capturing full screen (vision will find board).")
    logger.info("Last screenshot saved each poll to %s", LAST_SCREENSHOT_PATH)

    last_uci: Optional[str] = None
    while True:
        try:
            if region is not None:
                left, top, width, height = region
                img = capture_region(left, top, width, height)
                h, w = img.shape[:2]
                logger.info("Screenshot: %dx%d (region %d,%d)", w, h, left, top)
            else:
                img = capture_full_screen(0)
                h, w = img.shape[:2]
                logger.info("Screenshot: %dx%d (full screen)", w, h)

            # Save last screenshot for inspection (overwritten each poll)
            try:
                from PIL import Image
                Image.fromarray(img).save(LAST_SCREENSHOT_PATH)
                logger.debug("Saved last screenshot to %s", LAST_SCREENSHOT_PATH)
            except Exception as e:
                logger.debug("Could not save screenshot: %s", e)

            fen = image_to_fen_cv(img, white_to_move=we_play_white)
            if not fen:
                logger.info("Vision: no board detected")
                time.sleep(poll_interval)
                continue
            logger.info("Vision: FEN obtained")

            move = best_move(fen, white_to_move=we_play_white)
            if not move:
                logger.info("Engine: no move")
                time.sleep(poll_interval)
                continue

            uci = move.uci()
            try:
                b = chess.Board(fen)
                if " " not in fen:
                    b.set_board_fen(fen)
                    b.turn = chess.WHITE if we_play_white else chess.BLACK
                san = b.san(move)
            except Exception:
                san = uci

            if uci != last_uci:
                last_uci = uci
                if on_move:
                    on_move(uci, san)
                logger.info("Recommended: %s  (%s)", uci, san)

        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.debug("Assist step failed: %s", e)

        time.sleep(poll_interval)
