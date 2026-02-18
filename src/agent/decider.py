"""Decide: Stockfish UCI -> best move from FEN."""
from __future__ import annotations

import logging
import os
from typing import Optional

import chess
import chess.engine

from .config import load_config

logger = logging.getLogger(__name__)


def get_engine_path() -> str:
    cfg = load_config()
    return os.path.expanduser(cfg.get("stockfish_path", "stockfish"))


def get_engine_limits():
    cfg = load_config()
    eng = cfg.get("engine", {})
    return {
        "time": eng.get("time_limit_seconds", 0.15),
        "depth": eng.get("depth_limit", 18),
    }


# Piece placement for an empty board (no pieces); vision often returns this when no real board is visible.
EMPTY_BOARD_FEN = "8/8/8/8/8/8/8/8"


def is_empty_board_fen(fen: str) -> bool:
    """Return True if FEN describes an empty board (no pieces). Treat as 'no board' for assist."""
    if not fen or not fen.strip():
        return True
    placement = fen.split()[0].strip() if fen else ""
    return placement == EMPTY_BOARD_FEN


def is_valid_fen(fen: str) -> bool:
    """Return True if the FEN string is valid (piece placement parseable by python-chess)."""
    try:
        if " " in fen:
            chess.Board(fen)
        else:
            board = chess.Board()
            board.set_board_fen(fen)
        return True
    except Exception:
        return False


def _board_from_fen(fen: str, white_to_move: Optional[bool] = None) -> Optional[chess.Board]:
    try:
        if " " in fen:
            return chess.Board(fen)
        board = chess.Board()
        board.set_board_fen(fen)
        if white_to_move is not None:
            board.turn = chess.WHITE if white_to_move else chess.BLACK
        return board
    except Exception:
        return None


def best_move(
    fen: str,
    *,
    white_to_move: Optional[bool] = None,
    engine: Optional[chess.engine.SimpleEngine] = None,
) -> Optional[chess.Move]:
    """
    Return best move for the given board FEN.
    If engine is provided, use it (caller owns lifecycle). Otherwise spawn and close a new process.
    """
    board = _board_from_fen(fen, white_to_move=white_to_move)
    if board is None:
        logger.warning("Invalid FEN for engine")
        return None

    limits = get_engine_limits()
    path = get_engine_path()
    own_engine = False
    if engine is None:
        try:
            engine = chess.engine.SimpleEngine.popen_uci(path)
            own_engine = True
        except FileNotFoundError:
            logger.error("Stockfish not found at %s. Install it or set stockfish_path in config.", path)
            return None

    try:
        result = engine.play(
            board,
            chess.engine.Limit(time=limits["time"], depth=limits["depth"]),
        )
        return result.move
    except chess.engine.EngineTerminatedError as e:
        logger.warning("Engine crashed (e.g. exit -11): %s. Try a different Stockfish build (e.g. non-AVX2).", e)
        if not own_engine:
            raise  # Caller can restart the engine
        return None
    except FileNotFoundError:
        logger.error("Stockfish not found at %s.", path)
        return None
    except Exception as e:
        logger.warning("Engine play failed: %s", e)
        return None
    finally:
        if own_engine and engine is not None:
            try:
                engine.quit()
            except Exception:
                pass


def move_to_uci(move: chess.Move) -> str:
    """e.g. Move.from_uci('e2e4') -> 'e2e4'."""
    return move.uci()


def uci_to_squares(uci: str) -> tuple[str, str]:
    """e.g. 'e2e4' -> ('e2', 'e4')."""
    if len(uci) >= 4:
        return uci[:2], uci[2:4]
    return "", ""
