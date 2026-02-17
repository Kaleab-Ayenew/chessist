"""
Vision pipeline using ONNX models only (no PyTorch/chesscog at runtime).
Requires: onnx_models/occupancy.onnx, onnx_models/piece.onnx, onnx_models/metadata.json.
Constants (SQUARE_SIZE, crop logic) match chesscog for compatibility with exported models.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import chess
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Match chesscog occupancy_classifier/create_dataset.py
SQUARE_SIZE_OCC = 50
BOARD_SIZE_OCC = 8 * SQUARE_SIZE_OCC
IMG_SIZE_OCC = BOARD_SIZE_OCC + 2 * SQUARE_SIZE_OCC

# Match chesscog piece_classifier/create_dataset.py
SQUARE_SIZE_PIECE = 50
BOARD_SIZE_PIECE = 8 * SQUARE_SIZE_PIECE
IMG_SIZE_PIECE = BOARD_SIZE_PIECE * 2
MARGIN_PIECE = (IMG_SIZE_PIECE - BOARD_SIZE_PIECE) / 2
MIN_H_INC, MAX_H_INC = 1, 3
MIN_W_INC, MAX_W_INC = 0.25, 1
OUT_WIDTH_PIECE = int((1 + MAX_W_INC) * SQUARE_SIZE_PIECE)
OUT_HEIGHT_PIECE = int((1 + MAX_H_INC) * SQUARE_SIZE_PIECE)

_SQUARES = list(chess.SQUARES)


def _sort_corners(points: np.ndarray) -> np.ndarray:
    """Order corners as [top-left, top-right, bottom-right, bottom-left]."""
    points = np.array(points, dtype=np.float32)
    points = points[points[:, 1].argsort()]
    points[:2] = points[:2][points[:2, 0].argsort()]
    points[2:] = points[2:][points[2:, 0].argsort()[::-1]]
    return points


def find_board_corners(img: np.ndarray) -> Optional[np.ndarray]:
    """
    Detect 4 outer board corners using OpenCV chessboard corners (7x7 inner grid).
    Returns (4, 2) float32 array or None if detection fails.
    Tries several flags so green/low-contrast boards (e.g. Chess.com themes) are detected.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
    # findChessboardCorners expects (columns, rows) = (7, 7) for 8x8 board inner corners
    board_size = (7, 7)
    flags_to_try = [
        None,  # default
        cv2.CALIB_CB_ADAPTIVE_THRESH,  # helps when square contrast is low (e.g. green board)
        cv2.CALIB_CB_NORMALIZE_IMAGE,   # normalize gamma
        cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE,
    ]
    corners = None
    for flags in flags_to_try:
        if flags is None:
            ok, result = cv2.findChessboardCorners(gray, board_size)
        else:
            ok, result = cv2.findChessboardCorners(gray, board_size, flags)
        if ok and result is not None and len(result) == 49:
            corners = result
            break
    if corners is None:
        return None
    corners = corners.reshape(-1, 2).astype(np.float32)
    # Grid: row 0 = indices 0..6, row 1 = 7..13, ...; col = index % 7
    # Extrapolate one square outward for outer corners
    c00 = corners[0]
    c06 = corners[6]
    c70 = corners[7 * 7 - 7]
    c76 = corners[7 * 7 - 1]
    vec_right = corners[1] - corners[0]
    vec_down = corners[7] - corners[0]
    top_left = c00 - vec_right - vec_down
    top_right = c06 + vec_right - vec_down
    bottom_right = c76 + vec_right + vec_down
    bottom_left = c70 - vec_right + vec_down
    four = np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)
    return _sort_corners(four)


def warp_occupancy(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Warp image to fixed grid for occupancy crops (matches chesscog)."""
    src = _sort_corners(corners)
    dst = np.array([
        [SQUARE_SIZE_OCC, SQUARE_SIZE_OCC],
        [BOARD_SIZE_OCC + SQUARE_SIZE_OCC, SQUARE_SIZE_OCC],
        [BOARD_SIZE_OCC + SQUARE_SIZE_OCC, BOARD_SIZE_OCC + SQUARE_SIZE_OCC],
        [SQUARE_SIZE_OCC, BOARD_SIZE_OCC + SQUARE_SIZE_OCC],
    ], dtype=np.float32)
    H, _ = cv2.findHomography(src, dst)
    return cv2.warpPerspective(img, H, (IMG_SIZE_OCC, IMG_SIZE_OCC))


def crop_square_occupancy(warped: np.ndarray, square: int, turn: chess.Color) -> np.ndarray:
    """Crop one square for occupancy (100x100)."""
    rank = chess.square_rank(square)
    file = chess.square_file(square)
    if turn == chess.WHITE:
        row, col = 7 - rank, file
    else:
        row, col = rank, 7 - file
    r1 = int(SQUARE_SIZE_OCC * (row + 0.5))
    r2 = int(SQUARE_SIZE_OCC * (row + 2.5))
    c1 = int(SQUARE_SIZE_OCC * (col + 0.5))
    c2 = int(SQUARE_SIZE_OCC * (col + 2.5))
    return warped[r1:r2, c1:c2]


def warp_piece(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Warp image for piece crops (matches chesscog piece create_dataset)."""
    src = _sort_corners(corners)
    dst = np.array([
        [MARGIN_PIECE, MARGIN_PIECE],
        [BOARD_SIZE_PIECE + MARGIN_PIECE, MARGIN_PIECE],
        [BOARD_SIZE_PIECE + MARGIN_PIECE, BOARD_SIZE_PIECE + MARGIN_PIECE],
        [MARGIN_PIECE, BOARD_SIZE_PIECE + MARGIN_PIECE],
    ], dtype=np.float32)
    H, _ = cv2.findHomography(src, dst)
    return cv2.warpPerspective(img, H, (IMG_SIZE_PIECE, IMG_SIZE_PIECE))


def crop_square_piece(warped: np.ndarray, square: int, turn: chess.Color) -> np.ndarray:
    """Crop one square for piece classifier (variable size, then caller resizes)."""
    rank = chess.square_rank(square)
    file = chess.square_file(square)
    if turn == chess.WHITE:
        row, col = 7 - rank, file
    else:
        row, col = rank, 7 - file
    height_inc = MIN_H_INC + (MAX_H_INC - MIN_H_INC) * ((7 - row) / 7)
    left_inc = 0 if col >= 4 else MIN_W_INC + (MAX_W_INC - MIN_W_INC) * ((3 - col) / 3)
    right_inc = 0 if col < 4 else MIN_W_INC + (MAX_W_INC - MIN_W_INC) * ((col - 4) / 3)
    x1 = int(MARGIN_PIECE + SQUARE_SIZE_PIECE * (col - left_inc))
    x2 = int(MARGIN_PIECE + SQUARE_SIZE_PIECE * (col + 1 + right_inc))
    y1 = int(MARGIN_PIECE + SQUARE_SIZE_PIECE * (row - height_inc))
    y2 = int(MARGIN_PIECE + SQUARE_SIZE_PIECE * (row + 1))
    w, h = x2 - x1, y2 - y1
    cropped = warped[y1:y2, x1:x2]
    if col < 4:
        cropped = cv2.flip(cropped, 1)
    out = np.zeros((OUT_HEIGHT_PIECE, OUT_WIDTH_PIECE, 3), dtype=cropped.dtype)
    out[OUT_HEIGHT_PIECE - h:, :w] = cropped
    return out


def _preprocess_occupancy(square_imgs: list[np.ndarray], target_h: int, target_w: int) -> np.ndarray:
    """Resize to target and normalize to [0,1] then NCHW. No ImageNet mean/std for occupancy (often none in chesscog)."""
    out = []
    for im in square_imgs:
        if im.shape[0] != target_h or im.shape[1] != target_w:
            im = cv2.resize(im, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        # 0-255 -> 0-1, then HWC -> CHW
        x = im.astype(np.float32) / 255.0
        x = np.transpose(x, (2, 0, 1))
        out.append(x)
    return np.stack(out).astype(np.float32)


def _preprocess_piece(piece_imgs: list[np.ndarray], target_h: int, target_w: int, mean: list[float], std: list[float]) -> np.ndarray:
    """Resize, normalize with mean/std, NCHW."""
    mean = np.array(mean, dtype=np.float32).reshape(1, 3, 1, 1)
    std = np.array(std, dtype=np.float32).reshape(1, 3, 1, 1)
    out = []
    for im in piece_imgs:
        if im.shape[0] != target_h or im.shape[1] != target_w:
            im = cv2.resize(im, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        x = im.astype(np.float32) / 255.0
        x = np.transpose(x, (2, 0, 1))[np.newaxis, ...]
        x = (x - mean) / std
        out.append(x)
    return np.concatenate(out, axis=0).astype(np.float32)


def _name_to_piece(name: str) -> Optional[chess.Piece]:
    """Map class name like 'white pawn' or 'White Pawn' to chess.Piece."""
    name = name.strip().lower()
    parts = name.split()
    if len(parts) != 2:
        return None
    color_name, piece_name = parts
    color = chess.WHITE if color_name in ("white", "w") else chess.BLACK
    sym = {"pawn": "p", "knight": "n", "bishop": "b", "rook": "r", "queen": "q", "king": "k"}.get(piece_name)
    if not sym:
        return None
    # piece_type 1..6 = PAWN..KING in python-chess
    piece_type = chess.PIECE_SYMBOLS.index(sym) + 1
    return chess.Piece(piece_type, color)


class ONNXVision:
    """Run board recognition using ONNX models only."""

    def __init__(self, models_dir: Path | str):
        self.models_dir = Path(models_dir)
        self._meta: dict[str, Any] = {}
        self._occ_session = None
        self._piece_session = None
        self._load()

    def _load(self) -> None:
        meta_path = self.models_dir / "metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Metadata not found: {meta_path}")
        with open(meta_path) as f:
            self._meta = json.load(f)
        occ_path = self.models_dir / "occupancy.onnx"
        piece_path = self.models_dir / "piece.onnx"
        if not occ_path.exists() or not piece_path.exists():
            raise FileNotFoundError(f"ONNX models not found in {self.models_dir}")
        import onnxruntime as ort
        self._occ_session = ort.InferenceSession(str(occ_path), providers=["CPUExecutionProvider"])
        self._piece_session = ort.InferenceSession(str(piece_path), providers=["CPUExecutionProvider"])

    def predict(self, img: np.ndarray, turn: chess.Color = chess.WHITE) -> Optional[chess.Board]:
        """Run full pipeline: corners -> warp -> occupancy -> piece -> board."""
        corners = find_board_corners(img)
        if corners is None:
            logger.debug("Board corners not detected")
            return None
        occ_meta = self._meta.get("occupancy", {})
        piece_meta = self._meta.get("piece", {})
        occ_h = occ_meta.get("height", 100)
        occ_w = occ_meta.get("width", 100)
        piece_h = piece_meta.get("height", 224)
        piece_w = piece_meta.get("width", 224)
        mean = piece_meta.get("mean", [0.485, 0.456, 0.406])
        std = piece_meta.get("std", [0.229, 0.224, 0.225])
        occupied_idx = occ_meta.get("occupied_class_index", 1)
        piece_classes = piece_meta.get("classes", [])

        warped_occ = warp_occupancy(img, corners)
        square_imgs = [crop_square_occupancy(warped_occ, sq, turn) for sq in _SQUARES]
        occ_input = _preprocess_occupancy(square_imgs, occ_h, occ_w)
        occ_out, = self._occ_session.run(None, {"squares": occ_input})
        occupancy = (occ_out.argmax(axis=-1) == occupied_idx)

        occupied_squares = [sq for sq in _SQUARES if occupancy[_SQUARES.index(sq)]]
        if not occupied_squares:
            board = chess.Board()
            board.clear()
            return board

        warped_piece = warp_piece(img, corners)
        piece_imgs = [crop_square_piece(warped_piece, sq, turn) for sq in occupied_squares]
        piece_input = _preprocess_piece(piece_imgs, piece_h, piece_w, mean, std)
        piece_out, = self._piece_session.run(None, {"pieces": piece_input})
        piece_preds = piece_out.argmax(axis=1)

        board = chess.Board()
        board.clear()
        for sq, idx in zip(occupied_squares, piece_preds):
            if idx < len(piece_classes):
                name = piece_classes[idx]
                piece = _name_to_piece(name) if isinstance(name, str) else None
                if piece is not None:
                    board.set_piece_at(sq, piece)
        return board


_onnx_vision: Optional[ONNXVision] = None


def get_onnx_vision(models_dir: Optional[Path | str] = None) -> Optional[ONNXVision]:
    """Get or create ONNX vision instance. models_dir defaults to PROJECT_ROOT/onnx_models."""
    global _onnx_vision
    if models_dir is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        models_dir = project_root / "onnx_models"
    models_dir = Path(models_dir)
    if not (models_dir / "metadata.json").exists():
        return None
    if _onnx_vision is None:
        try:
            _onnx_vision = ONNXVision(models_dir)
        except Exception as e:
            logger.warning("ONNX vision init failed: %s", e)
            return None
    return _onnx_vision


def image_to_fen_onnx(image_rgb: np.ndarray, *, white_to_move: bool = True, models_dir: Optional[Path | str] = None) -> Optional[str]:
    """
    Run ONNX-only vision on an RGB image. Returns board FEN or None.
    """
    vision = get_onnx_vision(models_dir)
    if vision is None:
        return None
    turn = chess.WHITE if white_to_move else chess.BLACK
    board = vision.predict(image_rgb, turn=turn)
    if board is None:
        return None
    return board.board_fen()
