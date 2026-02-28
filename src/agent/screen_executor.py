"""
Execute chess moves on screen via pyautogui using board corners from vision.
Maps UCI squares to screen coordinates and performs humanized click-from, click-to.
"""
from __future__ import annotations

import logging
from typing import Optional

import chess
import numpy as np

logger = logging.getLogger(__name__)

# Warped board size used in vision (must match vision_template.BOARD_SIZE)
_BOARD_SIZE = 400
_SQUARE_SIZE = 50


def _square_centers_warped() -> np.ndarray:
    """64 (x, y) centers in warped image order a1..h1, a2..h2, ..., a8..h8. (N, 2)."""
    centers = np.zeros((64, 2), dtype=np.float32)
    for sq in range(64):
        file_idx = chess.square_file(sq)
        rank = chess.square_rank(sq)
        # In warped image: row 0 = rank 8, col 0 = file a. So row = 7 - rank, col = file.
        row = 7 - rank
        col = file_idx
        centers[sq, 0] = col * _SQUARE_SIZE + _SQUARE_SIZE / 2
        centers[sq, 1] = row * _SQUARE_SIZE + _SQUARE_SIZE / 2
    return centers


def corners_to_square_centers_screen(corners: np.ndarray) -> Optional[np.ndarray]:
    """
    Map 4 board corners (image/screen coords) to 64 square centers in screen coords.
    corners: (4, 2) [top-left, top-right, bottom-right, bottom-left].
    Returns (64, 2) float32 array, order a1..h8, or None on error.
    """
    try:
        corners = np.asarray(corners, dtype=np.float32)
        if corners.shape != (4, 2):
            return None
        # Warped image corners (same order as vision_template._warp_board dst)
        warped_corners = np.array([
            [0, 0],
            [_BOARD_SIZE, 0],
            [_BOARD_SIZE, _BOARD_SIZE],
            [0, _BOARD_SIZE],
        ], dtype=np.float32)
        import cv2
        H = cv2.getPerspectiveTransform(warped_corners, corners)
        centers_warped = _square_centers_warped()  # (64, 2)
        # perspectiveTransform expects (N, 1, 2)
        pts = centers_warped.reshape(-1, 1, 2)
        screen = cv2.perspectiveTransform(pts, H)
        return screen.reshape(64, 2).astype(np.float32)
    except Exception as e:
        logger.warning("corners_to_square_centers_screen failed: %s", e)
        return None


def uci_square_to_index(uci_square: str) -> int:
    """e.g. 'e4' -> chess square index (0..63)."""
    if len(uci_square) != 2:
        return -1
    file_char, rank_char = uci_square[0].lower(), uci_square[1]
    if file_char < "a" or file_char > "h" or rank_char < "1" or rank_char > "8":
        return -1
    file_idx = ord(file_char) - ord("a")
    rank = int(rank_char) - 1
    return chess.square(file_idx, rank)


def execute_move_on_screen(
    corners: np.ndarray,
    uci: str,
    *,
    apply_jitter: bool = True,
    we_play_white: bool = True,
) -> bool:
    """
    Perform move on screen: smoothly move mouse to from-square, click, move to to-square, click.
    Uses humanized delays, jitter, and smooth mouse movement at human-like speed.
    corners: (4, 2) board corners in screen coords.
    uci: e.g. 'e2e4'.
    we_play_white: if False, the board is displayed from black's perspective (flipped); we mirror
        square indices so clicks land on the correct squares.
    Returns True if clicks were performed.
    """
    try:
        import pyautogui
    except ImportError:
        logger.error("pyautogui not installed. pip install pyautogui")
        return False

    from .humanize import jitter_xy, sleep_reaction, mouse_move_duration

    centers = corners_to_square_centers_screen(corners)
    if centers is None:
        return False

    if len(uci) < 4:
        logger.warning("Invalid UCI for screen move: %s", uci)
        return False
    from_sq, to_sq = uci[:2], uci[2:4]
    from_idx = uci_square_to_index(from_sq)
    to_idx = uci_square_to_index(to_sq)
    if from_idx < 0 or to_idx < 0:
        logger.warning("Invalid square in UCI: %s", uci)
        return False

    # When playing black, the board on screen is typically rotated 180° (black at bottom, black's
    # left on left); our corners map warped coords assuming white at bottom. Mirror both rank and
    # file so clicks land on the correct squares (63 - sq = full 180° flip).
    if not we_play_white:
        from_idx = 63 - from_idx
        to_idx = 63 - to_idx

    x_from, y_from = float(centers[from_idx, 0]), float(centers[from_idx, 1])
    x_to, y_to = float(centers[to_idx, 0]), float(centers[to_idx, 1])

    if apply_jitter:
        x_from, y_from = jitter_xy(x_from, y_from, _SQUARE_SIZE)
        x_to, y_to = jitter_xy(x_to, y_to, _SQUARE_SIZE)

    sleep_reaction()
    
    # Smooth move to from-square and click
    try:
        current_x, current_y = pyautogui.position()
        dist_to_from = ((x_from - current_x) ** 2 + (y_from - current_y) ** 2) ** 0.5
        duration_from = mouse_move_duration(dist_to_from)
        pyautogui.moveTo(x_from, y_from, duration=duration_from, tween=pyautogui.easeOutQuad)
        pyautogui.click()
    except Exception as e:
        logger.warning("pyautogui move/click (from) failed: %s", e)
        return False

    # Smooth move to to-square and click
    try:
        dist_to_to = ((x_to - x_from) ** 2 + (y_to - y_from) ** 2) ** 0.5
        duration_to = mouse_move_duration(dist_to_to)
        pyautogui.moveTo(x_to, y_to, duration=duration_to, tween=pyautogui.easeOutQuad)
        pyautogui.click()
    except Exception as e:
        logger.warning("pyautogui move/click (to) failed: %s", e)
        return False
    
    logger.info("Screen move executed: %s", uci)
    return True


def normalize_fen(fen: str) -> str:
    """Extract only piece placement from FEN for comparison."""
    return fen.split()[0] if fen else ""


def fen_after_move(fen: str, uci: str, white_to_move: Optional[bool] = None) -> Optional[str]:
    """
    Return board FEN (piece placement only) after playing the given move.
    fen: board FEN (piece placement only or full FEN).
    uci: e.g. 'e2e4'.
    white_to_move: if FEN has no turn, set from this.
    Returns piece placement only to match vision output format.
    """
    try:
        board = chess.Board()
        if " " in fen:
            board.set_fen(fen)
        else:
            board.set_board_fen(fen)
            # Clear castling/en passant for piece-only FEN to avoid invalid state
            board.set_castling_fen("-")
            board.ep_square = None
            if white_to_move is not None:
                board.turn = chess.WHITE if white_to_move else chess.BLACK
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            logger.warning("Move %s not legal in position", uci)
            return None
        board.push(move)
        return board.board_fen()
    except Exception as e:
        logger.warning("fen_after_move failed: %s", e)
        return None
