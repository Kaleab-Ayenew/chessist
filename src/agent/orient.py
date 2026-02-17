"""Orient: raw observations -> FEN (ONNX vision primary, then chesscog, then DOM)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chess

logger = logging.getLogger(__name__)

# Prefer ONNX when onnx_models/ is present (no PyTorch needed)
def _onnx_models_dir() -> Optional[Path]:
    root = Path(__file__).resolve().parent.parent.parent
    d = root / "onnx_models"
    return d if (d / "metadata.json").exists() else None


def moves_to_fen(move_strings: list[str]) -> Optional[str]:
    """
    Build FEN (piece placement only) from a list of SAN moves.
    Returns board_fen() string or None if parsing fails.
    """
    board = chess.Board()
    for s in move_strings:
        s = (s or "").strip()
        if not s:
            continue
        try:
            move = board.parse_san(s)
            board.push(move)
        except Exception as e:
            logger.debug("Parse move %r: %s", s, e)
            return None
    return board.board_fen()


def fen_to_turn(fen: str) -> bool:
    """Return True if white to move, False if black. Default True."""
    try:
        b = chess.Board(fen)
        return b.turn
    except Exception:
        return True


# Chesscog recognizer (vision primary)
_chesscog_recognizer = None


def _get_chesscog_recognizer():
    global _chesscog_recognizer
    if _chesscog_recognizer is None:
        from chesscog.recognition.recognition import ChessRecognizer
        from chesscog.occupancy_classifier.download_model import ensure_model as ensure_occupancy
        from chesscog.piece_classifier.download_model import ensure_model as ensure_piece
        ensure_occupancy()
        ensure_piece()
        _chesscog_recognizer = ChessRecognizer()
    return _chesscog_recognizer


def image_to_fen_cv(image_rgb, *, white_to_move: bool = True) -> Optional[str]:
    """
    Vision: ONNX (primary if onnx_models/ present) else chesscog.
    Returns board FEN (piece placement) or None on failure (then DOM is used).
    """
    # 1) Try ONNX first when onnx_models/ is present (no torch/chesscog needed)
    onnx_dir = _onnx_models_dir()
    if onnx_dir is not None:
        try:
            from .vision_onnx import image_to_fen_onnx
            fen = image_to_fen_onnx(image_rgb, white_to_move=white_to_move, models_dir=onnx_dir)
            return fen  # may be None if board not detected
        except Exception as e:
            logger.debug("ONNX vision failed: %s", e)
            return None
    # 2) Fallback to chesscog only when ONNX is not available
    try:
        recognizer = _get_chesscog_recognizer()
        board, _ = recognizer.predict(image_rgb, turn=chess.WHITE if white_to_move else chess.BLACK)
        return board.board_fen()
    except Exception as e:
        logger.warning("chesscog inference failed: %s", e)
        return None
