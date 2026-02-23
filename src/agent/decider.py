"""Decide: Stockfish UCI -> best move from FEN."""
from __future__ import annotations

import logging
import os
from typing import Optional

import chess
import chess.engine

from .config import load_config, get_runtime_engine_settings

logger = logging.getLogger(__name__)


def get_engine_path() -> str:
    cfg = load_config()
    return os.path.expanduser(cfg.get("stockfish_path", "stockfish"))


def get_engine_limits() -> dict:
    """Get engine limits, with runtime settings taking precedence over config."""
    runtime = get_runtime_engine_settings()
    cfg = load_config()
    eng = cfg.get("engine", {})
    return {
        "time": runtime.get("time_limit_seconds", eng.get("time_limit_seconds", 5.0)),
        "depth": runtime.get("depth_limit", eng.get("depth_limit", 30)),
        "hash_mb": runtime.get("hash_mb", eng.get("hash_mb", 512)),
        "threads": runtime.get("threads", eng.get("threads", 4)),
    }


def configure_engine(engine: chess.engine.SimpleEngine) -> None:
    """Apply UCI options (Hash, Threads) from config/runtime settings."""
    limits = get_engine_limits()
    options = {}
    if limits.get("hash_mb"):
        options["Hash"] = int(limits["hash_mb"])
    if limits.get("threads"):
        options["Threads"] = int(limits["threads"])
    if options:
        try:
            engine.configure(options)
            logger.info("Engine configured: Hash=%sMB, Threads=%s", options.get("Hash"), options.get("Threads"))
        except Exception as e:
            logger.warning("Failed to configure engine: %s", e)


# Piece placement for an empty board (no pieces); vision often returns this when no real board is visible.
EMPTY_BOARD_FEN = "8/8/8/8/8/8/8/8"


def is_empty_board_fen(fen: str) -> bool:
    """Return True if FEN describes an empty board (no pieces). Treat as 'no board' for assist."""
    if not fen or not fen.strip():
        return True
    placement = fen.split()[0].strip() if fen else ""
    return placement == EMPTY_BOARD_FEN


def validate_fen(fen: str) -> tuple[bool, Optional[str]]:
    """
    Validate FEN and return (is_valid, error_reason).
    
    Checks:
    - FEN is parseable by python-chess
    - Exactly one king per side
    - No pawns on 1st or 8th rank
    - Reasonable piece counts (max 16 per side, max 10 of any non-king piece type)
    - Total pieces <= 32
    - python-chess board.is_valid() passes (checks king safety, etc.)
    
    Returns:
        (True, None) if valid
        (False, "reason string") if invalid
    """
    if not fen or not fen.strip():
        return False, "empty FEN"
    
    try:
        if " " in fen:
            board = chess.Board(fen)
        else:
            board = chess.Board()
            board.set_board_fen(fen)
            # Clear castling rights and en passant since we only have piece placement.
            # Without this, is_valid() fails if kings have moved from starting squares
            # but default castling rights (KQkq) are still set.
            board.set_castling_fen("-")
            board.ep_square = None
    except Exception as e:
        return False, f"unparseable FEN: {e}"
    
    # Exactly one king per side
    white_kings = len(board.pieces(chess.KING, chess.WHITE))
    black_kings = len(board.pieces(chess.KING, chess.BLACK))
    if white_kings != 1 or black_kings != 1:
        return False, f"wrong king count (white={white_kings}, black={black_kings}, need 1 each)"
    
    # No pawns on 1st or 8th rank (impossible positions)
    pawns = board.pawns
    if pawns & (chess.BB_RANK_1 | chess.BB_RANK_8):
        return False, "pawns on 1st or 8th rank (impossible)"
    
    # Count pieces per side
    white_pieces = 0
    black_pieces = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            if piece.color == chess.WHITE:
                white_pieces += 1
            else:
                black_pieces += 1
    
    # Max 16 pieces per side (1 king + 1 queen + 2 rooks + 2 bishops + 2 knights + 8 pawns)
    if white_pieces > 16 or black_pieces > 16:
        return False, f"too many pieces (white={white_pieces}, black={black_pieces}, max 16 each)"
    
    # Check for impossible piece counts (accounting for promotions)
    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color else "black"
        pawns_count = len(board.pieces(chess.PAWN, color))
        if pawns_count > 8:
            return False, f"too many {side} pawns ({pawns_count}, max 8)"
        
        queens = len(board.pieces(chess.QUEEN, color))
        rooks = len(board.pieces(chess.ROOK, color))
        bishops = len(board.pieces(chess.BISHOP, color))
        knights = len(board.pieces(chess.KNIGHT, color))
        
        # Promotions possible = 8 - current_pawns
        max_promotions = 8 - pawns_count
        
        # Check each piece type doesn't exceed original + possible promotions
        if queens > 1 + max_promotions:
            return False, f"too many {side} queens ({queens}, max {1 + max_promotions} with {pawns_count} pawns)"
        if rooks > 2 + max_promotions:
            return False, f"too many {side} rooks ({rooks}, max {2 + max_promotions} with {pawns_count} pawns)"
        if bishops > 2 + max_promotions:
            return False, f"too many {side} bishops ({bishops}, max {2 + max_promotions} with {pawns_count} pawns)"
        if knights > 2 + max_promotions:
            return False, f"too many {side} knights ({knights}, max {2 + max_promotions} with {pawns_count} pawns)"
    
    # Use python-chess built-in validation (checks king positions, etc.)
    # Note: is_valid() can be strict about side-to-move being in check, so we
    # temporarily set turn to the side NOT giving check if needed
    if not board.is_valid():
        board.turn = not board.turn
        if not board.is_valid():
            return False, "invalid board state (king in check by opponent or other issue)"
    
    return True, None


def is_valid_fen(fen: str) -> bool:
    """Return True if FEN is valid. Logs warning with reason if invalid."""
    valid, reason = validate_fen(fen)
    if not valid and reason:
        logger.warning("Invalid FEN rejected: %s (FEN: %s)", reason, fen[:50] if fen else "None")
    return valid


def _board_from_fen(fen: str, white_to_move: Optional[bool] = None) -> Optional[chess.Board]:
    try:
        if " " in fen:
            return chess.Board(fen)
        board = chess.Board()
        board.set_board_fen(fen)
        # Clear castling/en passant for piece-only FEN to avoid invalid state
        board.set_castling_fen("-")
        board.ep_square = None
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


def game_outcome_message(fen: str, *, white_to_move: Optional[bool] = None) -> Optional[str]:
    """
    If the position is game over, return a short message (e.g. "White wins by checkmate").
    Otherwise return None.
    """
    board = _board_from_fen(fen, white_to_move=white_to_move)
    if board is None:
        return None
    if not board.is_game_over():
        return None
    outcome = board.outcome()
    if outcome is None:
        return "Game over"
    winner = outcome.winner
    term = outcome.termination
    if winner is not None:
        side = "White" if winner else "Black"
        if term == chess.Termination.CHECKMATE:
            return f"{side} wins by checkmate"
        if term == chess.Termination.STALEMATE:
            return "Draw (stalemate)"
    if term == chess.Termination.INSUFFICIENT_MATERIAL:
        return "Draw (insufficient material)"
    if term == chess.Termination.FIFTY_MOVES:
        return "Draw (50 moves)"
    if term == chess.Termination.THREEFOLD_REPETITION:
        return "Draw (repetition)"
    if term == chess.Termination.FIVEFOLD_REPETITION:
        return "Draw (5-fold repetition)"
    if term == chess.Termination.SEVENTYFIVE_MOVES:
        return "Draw (75 moves)"
    return "Game over"
