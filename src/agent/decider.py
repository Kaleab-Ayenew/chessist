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


def best_move(fen: str, *, white_to_move: Optional[bool] = None) -> Optional[chess.Move]:
    """
    Return best move (UCI) as chess.Move for the given board FEN.
    fen can be piece-placement only (board_fen); if so, pass white_to_move.
    """
    try:
        if " " in fen:
            board = chess.Board(fen)
        else:
            board = chess.Board()
            board.set_board_fen(fen)
            if white_to_move is not None:
                board.turn = chess.WHITE if white_to_move else chess.BLACK
    except Exception as e:
        logger.warning("Invalid FEN for engine: %s", e)
        return None

    path = get_engine_path()
    limits = get_engine_limits()
    try:
        with chess.engine.SimpleEngine.popen_uci(path) as engine:
            result = engine.play(
                board,
                chess.engine.Limit(time=limits["time"], depth=limits["depth"]),
            )
            return result.move
    except FileNotFoundError:
        logger.error("Stockfish not found at %s. Install it (e.g. apt install stockfish) or set STOCKFISH_PATH.", path)
        return None
    except Exception as e:
        logger.warning("Engine play failed: %s", e)
        return None


def move_to_uci(move: chess.Move) -> str:
    """e.g. Move.from_uci('e2e4') -> 'e2e4'."""
    return move.uci()


def uci_to_squares(uci: str) -> tuple[str, str]:
    """e.g. 'e2e4' -> ('e2', 'e4')."""
    if len(uci) >= 4:
        return uci[:2], uci[2:4]
    return "", ""
