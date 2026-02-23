"""
Assist mode: full-screen capture -> vision (board extraction + FEN) -> Stockfish -> show move.
Supports move recommendation display and/or auto-play (pyautogui). Tracks FEN after our move
to wait for opponent before playing next move. Detects game over.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import chess
import chess.engine

from .config import load_config, get_debug_dir
from .screen_capture import capture_full_screen
from .orient import image_to_fen_cv, image_to_fen_cv_with_bounds
from .decider import (
    best_move,
    get_engine_path,
    is_empty_board_fen,
    is_valid_fen,
    game_outcome_message,
)
from .screen_executor import execute_move_on_screen, fen_after_move, normalize_fen

logger = logging.getLogger(__name__)


def _board_from_fen(fen: str, white_to_move: bool) -> chess.Board:
    """Create a chess.Board from FEN (piece-only or full), clearing castling/ep for piece-only."""
    b = chess.Board()
    if " " in fen:
        b.set_fen(fen)
    else:
        b.set_board_fen(fen)
        b.set_castling_fen("-")
        b.ep_square = None
        b.turn = chess.WHITE if white_to_move else chess.BLACK
    return b


# State for run_assist_loop_step (one iteration); caller keeps this between steps.
AssistStepState = Dict[str, Any]

_DEBUG_DIR = get_debug_dir()
LAST_SCREENSHOT_PATH = _DEBUG_DIR / "last_assist_screenshot.png"
LAST_BOARD_MARKED_PATH = _DEBUG_DIR / "last_board_marked.png"
LAST_BOARD_WARPED_PATH = _DEBUG_DIR / "last_board_warped.png"
LAST_BOARD_EDGES_PATH = _DEBUG_DIR / "last_board_edges.png"


def _board_turn_white(fen: str, we_play_white: bool) -> bool:
    """True if it's white to move (from FEN or inferred from piece-only)."""
    try:
        if " " in fen:
            return chess.Board(fen).turn
        # Piece-only FEN: we can't know turn; caller uses fen_after_our_move for auto_play
        return we_play_white
    except Exception:
        return we_play_white


def initial_assist_step_state() -> AssistStepState:
    """State dict for the first call to run_assist_loop_step."""
    return {
        "last_uci": None,
        "last_fen": None,
        "fen_after_our_move": None,
        "last_game_over_message": None,
    }


def run_assist_loop_step(
    engine: chess.engine.SimpleEngine,
    state: AssistStepState,
    poll_interval: float,
    get_we_play_white: Callable[[], bool],
    *,
    on_move: Optional[Callable[[str, str], None]] = None,
    on_game_over: Optional[Callable[[str], None]] = None,
    get_show_recommendation: Optional[Callable[[], bool]] = None,
    get_auto_play: Optional[Callable[[], bool]] = None,
) -> Tuple[AssistStepState, float]:
    """
    Run one assist iteration (capture, vision, optional engine/execute).
    Returns (updated_state, delay_seconds) so the caller can schedule the next step
    on the main thread (e.g. root.after). Use this from the overlay to avoid X11
    multi-thread issues: all X usage (mss, pyautogui) happens on the same thread as the GUI.
    """
    last_uci = state.get("last_uci")
    last_fen = state.get("last_fen")
    fen_after_our_move = state.get("fen_after_our_move")
    last_game_over_message = state.get("last_game_over_message")
    next_state = {
        "last_uci": last_uci,
        "last_fen": last_fen,
        "fen_after_our_move": fen_after_our_move,
        "last_game_over_message": last_game_over_message,
    }

    try:
        we_play_white = get_we_play_white()
        show_rec = get_show_recommendation() if get_show_recommendation else True
        auto_play = get_auto_play() if get_auto_play else False

        img = capture_full_screen(0)
        logger.debug("Screenshot: %dx%d", img.shape[1], img.shape[0])
        try:
            from PIL import Image
            Image.fromarray(img).save(LAST_SCREENSHOT_PATH)
        except Exception:
            pass

        fen: Optional[str] = None
        corners = None
        if auto_play:
            result = image_to_fen_cv_with_bounds(
                img,
                white_to_move=we_play_white,
                save_marked_path=LAST_BOARD_MARKED_PATH,
                save_warped_path=LAST_BOARD_WARPED_PATH,
                save_edges_path=LAST_BOARD_EDGES_PATH,
            )
            if result is not None:
                fen, corners = result
        else:
            fen = image_to_fen_cv(
                img,
                white_to_move=we_play_white,
                save_marked_path=LAST_BOARD_MARKED_PATH,
                save_warped_path=LAST_BOARD_WARPED_PATH,
                save_edges_path=LAST_BOARD_EDGES_PATH,
            )

        if not fen or is_empty_board_fen(fen):
            logger.info("Vision: no board detected")
            next_state["last_fen"] = None
            next_state["fen_after_our_move"] = None
            return (next_state, poll_interval)

        logger.info("Vision: FEN obtained")
        if not is_valid_fen(fen):
            logger.warning("Invalid FEN (validation failed); skipping")
            return (next_state, poll_interval)

        msg = game_outcome_message(fen, white_to_move=we_play_white)
        if msg is not None:
            if msg != last_game_over_message and on_game_over:
                on_game_over(msg)
            next_state["last_game_over_message"] = msg
            next_state["fen_after_our_move"] = None
            return (next_state, poll_interval)
        next_state["last_game_over_message"] = None

        if auto_play and corners is not None:
            if fen_after_our_move is not None:
                if normalize_fen(fen) == normalize_fen(fen_after_our_move):
                    return (next_state, poll_interval)
            elif not we_play_white:
                return (next_state, poll_interval)

            move = best_move(fen, white_to_move=we_play_white, engine=engine)
            if not move:
                return (next_state, poll_interval)
            uci = move.uci()
            try:
                b = _board_from_fen(fen, we_play_white)
                san = b.san(move)
            except Exception:
                san = uci
            if show_rec and on_move:
                on_move(uci, san)
            executed = execute_move_on_screen(corners, uci, apply_jitter=True)
            if executed:
                next_fen = fen_after_move(fen, uci, white_to_move=we_play_white)
                next_state["fen_after_our_move"] = next_fen
                next_state["last_uci"] = uci
                next_state["last_fen"] = fen
            return (next_state, poll_interval)

        if fen == last_fen:
            logger.debug("FEN unchanged; skipping engine")
            return (next_state, poll_interval)
        next_state["last_fen"] = fen
        move = best_move(fen, white_to_move=we_play_white, engine=engine)
        if not move:
            return (next_state, poll_interval)
        uci = move.uci()
        try:
            b = _board_from_fen(fen, we_play_white)
            san = b.san(move)
        except Exception:
            san = uci
        if uci != last_uci:
            next_state["last_uci"] = uci
            if show_rec and on_move:
                on_move(uci, san)
            logger.info("Recommended: %s  (%s)", uci, san)
        return (next_state, poll_interval)

    except chess.engine.EngineTerminatedError:
        logger.warning("Stockfish crashed.")
        next_state["engine_dead"] = True
        return (next_state, poll_interval)
    except Exception as e:
        logger.debug("Assist step failed: %s", e)
        return (next_state, poll_interval)


def run_assist_loop(
    get_we_play_white: Callable[[], bool],
    *,
    poll_interval: float = 2.0,
    on_move: Optional[Callable[[str, str], None]] = None,
    on_game_over: Optional[Callable[[str], None]] = None,
    get_show_recommendation: Optional[Callable[[], bool]] = None,
    get_auto_play: Optional[Callable[[], bool]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> None:
    """
    Run the assist/auto-play loop.

    - get_we_play_white(): whether we play white.
    - on_move(uci, san): called when a move is recommended or executed (if show recommendation).
    - on_game_over(message): called when game over is detected.
    - get_show_recommendation(): if True, show recommended move in overlay.
    - get_auto_play(): if True, execute moves with pyautogui and wait for opponent.
    - should_stop(): if True, exit the loop.

    When auto_play is True, uses vision with bounds to get board corners, tracks FEN after
    our move, and only plays when the board FEN changes (opponent has moved). When
    show_recommendation is True, still calls on_move for display.
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
    fen_after_our_move: Optional[str] = None  # expected FEN after we play; when vision matches, we wait for opponent
    last_game_over_message: Optional[str] = None

    def stop() -> bool:
        return should_stop is not None and should_stop()

    try:
        while not stop():
            try:
                we_play_white = get_we_play_white()
                show_rec = get_show_recommendation() if get_show_recommendation else True
                auto_play = get_auto_play() if get_auto_play else False

                img = capture_full_screen(0)
                logger.debug("Screenshot: %dx%d", img.shape[1], img.shape[0])
                try:
                    from PIL import Image
                    Image.fromarray(img).save(LAST_SCREENSHOT_PATH)
                except Exception:
                    pass

                fen: Optional[str] = None
                corners = None
                if auto_play:
                    result = image_to_fen_cv_with_bounds(
                        img,
                        white_to_move=we_play_white,
                        save_marked_path=LAST_BOARD_MARKED_PATH,
                        save_warped_path=LAST_BOARD_WARPED_PATH,
                        save_edges_path=LAST_BOARD_EDGES_PATH,
                    )
                    if result is not None:
                        fen, corners = result
                else:
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
                    fen_after_our_move = None
                    time.sleep(poll_interval)
                    continue

                logger.info("Vision: FEN obtained")
                if not is_valid_fen(fen):
                    logger.warning("Invalid FEN (validation failed); skipping")
                    time.sleep(poll_interval)
                    continue

                # Game over?
                msg = game_outcome_message(fen, white_to_move=we_play_white)
                if msg is not None:
                    if msg != last_game_over_message and on_game_over:
                        on_game_over(msg)
                    last_game_over_message = msg
                    fen_after_our_move = None
                    time.sleep(poll_interval)
                    continue
                last_game_over_message = None

                # Auto-play: play when (fen_after_our_move is None and we're white = first move)
                # or when fen_after_our_move is set and vision != fen_after_our_move (opponent moved)
                if auto_play and corners is not None:
                    if fen_after_our_move is not None:
                        if normalize_fen(fen) == normalize_fen(fen_after_our_move):
                            # Still waiting for opponent
                            time.sleep(poll_interval)
                            continue
                        # Opponent has moved; play our move
                    elif not we_play_white:
                        # We play black; fen_after_our_move None means wait for white's first move
                        time.sleep(poll_interval)
                        continue
                    # Get best move and execute
                    move = best_move(fen, white_to_move=we_play_white, engine=engine)
                    if not move:
                        time.sleep(poll_interval)
                        continue
                    uci = move.uci()
                    try:
                        b = _board_from_fen(fen, we_play_white)
                        san = b.san(move)
                    except Exception:
                        san = uci

                    if show_rec and on_move:
                        on_move(uci, san)
                    executed = execute_move_on_screen(corners, uci, apply_jitter=True)
                    if executed:
                        next_fen = fen_after_move(fen, uci, white_to_move=we_play_white)
                        fen_after_our_move = next_fen
                        last_uci = uci
                        last_fen = fen
                    time.sleep(poll_interval)
                    continue

                # Assist only (no auto_play): show recommendation when FEN changed
                if fen == last_fen:
                    logger.debug("FEN unchanged; skipping engine")
                    time.sleep(poll_interval)
                    continue
                last_fen = fen
                move = best_move(fen, white_to_move=we_play_white, engine=engine)
                if not move:
                    time.sleep(poll_interval)
                    continue
                uci = move.uci()
                try:
                    b = _board_from_fen(fen, we_play_white)
                    san = b.san(move)
                except Exception:
                    san = uci
                if uci != last_uci:
                    last_uci = uci
                    if show_rec and on_move:
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
