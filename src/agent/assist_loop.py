"""
Assist mode: full-screen capture -> vision (board extraction + FEN) -> Stockfish -> show move.
No browser; user opens the board (e.g. Chess.com); app shows recommended move in overlay and terminal.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Optional

import chess
import chess.engine

from .config import load_config, get_debug_dir
from .screen_capture import capture_full_screen
from .orient import image_to_fen_cv
from .decider import best_move, get_engine_path, is_empty_board_fen, is_valid_fen

logger = logging.getLogger(__name__)

_DEBUG_DIR = get_debug_dir()
LAST_SCREENSHOT_PATH = _DEBUG_DIR / "last_assist_screenshot.png"
LAST_BOARD_MARKED_PATH = _DEBUG_DIR / "last_board_marked.png"
LAST_BOARD_WARPED_PATH = _DEBUG_DIR / "last_board_warped.png"
LAST_BOARD_EDGES_PATH = _DEBUG_DIR / "last_board_edges.png"


def run_assist_loop(
    we_play_white: bool,
    *,
    poll_interval: float = 2.0,
    on_move: Optional[Callable[[str, str], None]] = None,
) -> None:
    """
    Run the assist loop: full-screen capture -> FEN -> best move -> on_move(uci, san).
    Board is detected from the full screenshot. One Stockfish process is reused for the session.
    """
    logger.debug("Debug images: %s", _DEBUG_DIR)
    path = get_engine_path()
    try:
        engine = chess.engine.SimpleEngine.popen_uci(path)
    except FileNotFoundError:
        logger.error("Stockfish not found at %s. Install it or set stockfish_path in config.", path)
        return
    last_uci: Optional[str] = None
    last_fen: Optional[str] = None
    try:
        while True:
            try:
                img = capture_full_screen(0)
                logger.debug("Screenshot: %dx%d", img.shape[1], img.shape[0])

                try:
                    from PIL import Image
                    Image.fromarray(img).save(LAST_SCREENSHOT_PATH)
                except Exception:
                    pass

                fen = image_to_fen_cv(
                    img,
                    white_to_move=we_play_white,
                    save_marked_path=LAST_BOARD_MARKED_PATH,
                    save_warped_path=LAST_BOARD_WARPED_PATH,
                    save_edges_path=LAST_BOARD_EDGES_PATH,
                )
                if not fen or is_empty_board_fen(fen):
                    logger.info("Vision: no board detected")
                    last_fen = None
                    time.sleep(poll_interval)
                    continue
                logger.info("Vision: FEN obtained")
                print("FEN:", fen)

                if not is_valid_fen(fen):
                    logger.warning("Invalid FEN (validation failed); skipping Stockfish")
                    time.sleep(poll_interval)
                    continue

                if fen == last_fen:
                    logger.debug("FEN unchanged; skipping engine")
                    time.sleep(poll_interval)
                    continue

                last_fen = fen
                move = best_move(fen, white_to_move=we_play_white, engine=engine)
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
            except chess.engine.EngineTerminatedError:
                logger.warning("Stockfish crashed; restarting engine.")
                try:
                    engine.quit()
                except Exception:
                    pass
                try:
                    engine = chess.engine.SimpleEngine.popen_uci(path)
                except Exception as e:
                    logger.error("Could not restart Stockfish: %s", e)
                    break
            except Exception as e:
                logger.debug("Assist step failed: %s", e)

            time.sleep(poll_interval)
    finally:
        try:
            engine.quit()
        except Exception:
            pass
