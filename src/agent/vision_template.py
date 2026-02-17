"""
Screenshot-to-FEN pipeline using board extraction (contour or 1D edge projection)
and masked template matching against ground-truth images.
Returns board FEN (piece placement). Supports Chess.com-style template names (wp, bk, 200, etc.).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chess
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Warp board to this size (8 squares); each square is SQUARE_SIZE x SQUARE_SIZE
SQUARE_SIZE = 50
BOARD_SIZE = 8 * SQUARE_SIZE

_SQUARES = list(chess.SQUARES)

# Chess.com asset naming (filename stem -> FEN character)
# 200 = empty square in Chess.com assets; 200_light / 200_dark for theme-agnostic empty
FEN_FROM_STEM = {
    "wp": "P", "wn": "N", "wb": "B", "wr": "R", "wq": "Q", "wk": "K",
    "bp": "p", "bn": "n", "bb": "b", "br": "r", "bq": "q", "bk": "k",
    "200": ".", "200_light": ".", "200_dark": ".", "empty": ".",
    "empty_light_square": ".", "empty_dark_square": ".",
}


def _sort_corners(points: np.ndarray) -> np.ndarray:
    """Order corners as [top-left, top-right, bottom-right, bottom-left]."""
    points = np.array(points, dtype=np.float32)
    points = points[points[:, 1].argsort()]
    points[:2] = points[:2][points[:2, 0].argsort()]
    points[2:] = points[2:][points[2:, 0].argsort()[::-1]]
    return points


# ---------------------------------------------------------------------------
# Board extraction: contour
# ---------------------------------------------------------------------------


def find_board_corners_contour(img: np.ndarray) -> Optional[np.ndarray]:
    """
    Detect 4 board corners using contour detection.
    Returns (4, 2) float32 array [top-left, top-right, bottom-right, bottom-left] or None.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
    h, w = gray.shape
    min_area = (min(h, w) ** 2) * 0.05  # board at least ~5% of image

    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    # Close small gaps so board outline is one contour
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel)
    edges = cv2.erode(edges, kernel)

    contours, _ = cv2.findContours(
        edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    best_quad = None
    best_area = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue
        epsilon = 0.02 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        if len(approx) != 4:
            continue
        # Prefer aspect ratio near 1 (square board)
        pts = approx.reshape(4, 2).astype(np.float32)
        rect = cv2.minAreaRect(pts)
        rw, rh = rect[1][0], rect[1][1]
        if rw < 2 or rh < 2:
            continue
        aspect = max(rw, rh) / min(rw, rh)
        if aspect > 1.5:
            continue
        if area > best_area:
            best_area = area
            best_quad = pts

    if best_quad is None:
        return None
    return _sort_corners(best_quad)


def save_marked_board_image(
    img: np.ndarray,
    corners: np.ndarray,
    path: Path | str,
    *,
    line_color: tuple[int, int, int] = (0, 255, 0),
    line_thickness: int = 4,
    corner_radius: int = 12,
) -> None:
    """
    Draw the detected board quad on a copy of the image and save to path.
    corners: (4, 2) in order [top-left, top-right, bottom-right, bottom-left].
    line_color is BGR (e.g. (0, 255, 0) = green).
    """
    path = Path(path)
    # OpenCV drawing uses BGR; input img is typically RGB
    if img.ndim == 3 and img.shape[2] == 3:
        marked = cv2.cvtColor(img.copy(), cv2.COLOR_RGB2BGR)
    else:
        marked = cv2.cvtColor(img.copy(), cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img.copy()
    pts = corners.astype(np.int32)
    # Draw quad outline (closed polygon)
    cv2.polylines(marked, [pts], isClosed=True, color=line_color, thickness=line_thickness)
    # Draw corners clearly (filled circles)
    for i, (x, y) in enumerate(pts):
        cv2.circle(marked, (int(x), int(y)), corner_radius, line_color, -1)
        cv2.circle(marked, (int(x), int(y)), corner_radius, (255, 255, 255), 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), marked)
    logger.info("Saved marked board image to %s", path)


# ---------------------------------------------------------------------------
# Board extraction: 1D edge projection
# ---------------------------------------------------------------------------


def find_board_corners_edges(img: np.ndarray) -> Optional[np.ndarray]:
    """
    Detect 4 board corners using 1D edge projection (gradient summed along axes).
    Returns (4, 2) float32 array [top-left, top-right, bottom-right, bottom-left] or None.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    h, w = gray.shape

    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    abs_x = np.abs(sobelx)
    abs_y = np.abs(sobely)

    # Project vertical edges onto y-axis -> strong responses at row boundaries
    row_edges = np.mean(abs_x, axis=1)
    # Project horizontal edges onto x-axis -> strong responses at column boundaries
    col_edges = np.mean(abs_y, axis=0)

    # Smooth and find peaks (local maxima)
    def find_line_positions(signal: np.ndarray, n_lines: int = 9) -> Optional[np.ndarray]:
        n_lines = min(n_lines, len(signal) // 4)
        if n_lines < 2:
            return None
        smoothed = cv2.GaussianBlur(signal.astype(np.float32).reshape(-1, 1), (0, 0), 5).ravel()
        # Peaks: where gradient changes sign from positive to negative
        diff = np.diff(smoothed)
        peaks = []
        for i in range(1, len(diff)):
            if diff[i - 1] > 0 and diff[i] <= 0:
                peaks.append(i)
        if len(peaks) < 2:
            # Fallback: equidistant
            return np.linspace(0, len(signal) - 1, n_lines, dtype=np.float32)
        peaks = np.array(peaks, dtype=np.float32)
        # Keep roughly n_lines by merging close peaks and taking strongest
        if len(peaks) > n_lines:
            # Sort by signal strength at peak
            strengths = smoothed[np.clip(peaks.astype(int), 0, len(smoothed) - 1)]
            order = np.argsort(-strengths)[:n_lines]
            peaks = np.sort(peaks[order])
        return peaks

    row_pos = find_line_positions(row_edges, 9)
    col_pos = find_line_positions(col_edges, 9)
    if row_pos is None or col_pos is None or len(row_pos) < 2 or len(col_pos) < 2:
        return None

    # Use first and last as outer boundaries
    y_min, y_max = float(row_pos[0]), float(row_pos[-1])
    x_min, x_max = float(col_pos[0]), float(col_pos[-1])
    if y_max - y_min < 20 or x_max - x_min < 20:
        return None

    corners = np.array([
        [x_min, y_min],
        [x_max, y_min],
        [x_max, y_max],
        [x_min, y_max],
    ], dtype=np.float32)
    return _sort_corners(corners)


# ---------------------------------------------------------------------------
# Warp and split into 64 squares
# ---------------------------------------------------------------------------


def _warp_board(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Warp image to fixed BOARD_SIZE x BOARD_SIZE so we have 8x8 squares."""
    src = _sort_corners(corners)
    dst = np.array([
        [0, 0],
        [BOARD_SIZE, 0],
        [BOARD_SIZE, BOARD_SIZE],
        [0, BOARD_SIZE],
    ], dtype=np.float32)
    H, _ = cv2.findHomography(src, dst)
    return cv2.warpPerspective(img, H, (BOARD_SIZE, BOARD_SIZE))


def _extract_squares(warped: np.ndarray) -> list[np.ndarray]:
    """Split warped board into 64 squares (row 0 = top = rank 8, col 0 = left = file a)."""
    squares = []
    for row in range(8):
        for col in range(8):
            y1, y2 = row * SQUARE_SIZE, (row + 1) * SQUARE_SIZE
            x1, x2 = col * SQUARE_SIZE, (col + 1) * SQUARE_SIZE
            sq = warped[y1:y2, x1:x2]
            squares.append(sq)
    return squares


def _square_index_to_chess_square(row: int, col: int) -> int:
    """Map (row, col) in warped image to chess square. row 0 = rank 8, col 0 = file a."""
    file_idx = col
    rank = 7 - row
    return chess.square(file_idx, rank)


# ---------------------------------------------------------------------------
# Template loading and matching
# ---------------------------------------------------------------------------


def _stem_to_fen_char(stem: str) -> Optional[str]:
    """Map template filename stem to FEN character or None if unknown."""
    key = stem.lower().strip()
    return FEN_FROM_STEM.get(key)


def _normalize_patch(patch: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Zero-mean, unit-variance normalization (theme-agnostic). patch: grayscale float or uint8."""
    if patch.dtype != np.float64:
        patch = np.asarray(patch, dtype=np.float64)
    mean = np.mean(patch)
    std = np.std(patch)
    if std < eps:
        return patch - mean
    return (patch - mean) / (std + eps)


def _variance_in_center(
    square: np.ndarray,
    size: int = SQUARE_SIZE,
    center_fraction: float = 0.6,
) -> float:
    """
    Variance of grayscale intensity in the central region of the square.
    Empty (flat) squares have low variance; occupied squares (piece vs background) have higher variance.
    square: RGB or BGR, any size (will be resized to size x size).
    center_fraction: use central 60% of width/height (0.6 = 60%).
    Returns variance (scalar).
    """
    sq = cv2.resize(square, (size, size), interpolation=cv2.INTER_AREA)
    if sq.ndim == 3:
        gray = cv2.cvtColor(sq, cv2.COLOR_BGR2GRAY)
    else:
        gray = sq
    h, w = gray.shape
    margin = (1.0 - center_fraction) / 2.0
    y1 = int(h * margin)
    y2 = int(h * (1 - margin))
    x1 = int(w * margin)
    x2 = int(w * (1 - margin))
    center = gray[y1:y2, x1:x2]
    return float(np.var(center))


def patch_to_edge_map(
    gray: np.ndarray,
    method: str = "gradient",
    blur_ksize: int = 3,
) -> np.ndarray:
    """
    Convert grayscale patch to edge map for shape-based matching (theme-agnostic).
    method: "gradient" (Sobel magnitude) or "canny".
    Returns float32 array same shape as input, suitable for matchTemplate.
    """
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    gray = np.asarray(gray, dtype=np.uint8)
    if blur_ksize > 0:
        gray = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)
    if method == "canny":
        edge = cv2.Canny(gray, 50, 150)
        return edge.astype(np.float32)
    # gradient: Sobel magnitude
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    mag = np.clip(mag, 0, None).astype(np.float32)
    # Normalize for correlation (zero-mean unit-variance)
    return _normalize_patch(mag).astype(np.float32)


def _make_piece_mask(template_bgr: np.ndarray) -> np.ndarray:
    """
    Build a binary mask for piece-only matching: 1 where piece is, 0 on background.
    Uses border color as background; pixels differing from border are piece.
    """
    h, w = template_bgr.shape[:2]
    gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
    # Sample border pixels to estimate background
    border = np.concatenate([
        gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]
    ])
    bg_median = float(np.median(border))
    bg_std = max(float(np.std(border)), 5.0)
    # Piece pixels are those far enough from background
    diff = np.abs(gray.astype(np.float32) - bg_median)
    _, mask = cv2.threshold(
        (255 * np.clip(diff / (bg_std * 2), 0, 1)).astype(np.uint8),
        30, 255, cv2.THRESH_BINARY
    )
    return mask


def load_templates(
    templates_dir: Path,
    target_size: int = SQUARE_SIZE,
    extensions: tuple[str, ...] = (".png", ".jpg", ".jpeg"),
) -> list[tuple[np.ndarray, Optional[np.ndarray], str]]:
    """
    Load all templates from directory. Returns list of (template_bgr, mask_or_None, fen_char).
    template_bgr and optional mask are resized to target_size x target_size.
    """
    templates_dir = Path(templates_dir)
    if not templates_dir.is_dir():
        return []

    out = []
    for path in sorted(templates_dir.iterdir()):
        if path.suffix.lower() not in extensions:
            continue
        stem = path.stem
        if stem.endswith("_mask"):
            continue
        fen_char = _stem_to_fen_char(stem)
        if fen_char is None:
            logger.debug("Unknown template stem %r, skipping", stem)
            continue
        img = cv2.imread(str(path))
        if img is None:
            logger.debug("Could not read template %s (may be non-image, e.g. redirect)", path)
            continue
        # Keep BGR for cv2.matchTemplate
        template = cv2.resize(img, (target_size, target_size), interpolation=cv2.INTER_AREA)
        mask_path = templates_dir / f"{stem}_mask{path.suffix}"
        mask = None
        if mask_path.exists():
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is not None:
                mask = cv2.resize(mask, (target_size, target_size), interpolation=cv2.INTER_NEAREST)
        # Theme-agnostic: for piece templates without a mask, auto-generate one (piece-only matching)
        if fen_char != "." and mask is None:
            mask = _make_piece_mask(template)
        out.append((template, mask, fen_char))
    return out


def _prepare_square(square_rgb: np.ndarray, normalize: bool) -> tuple[np.ndarray, Optional[np.ndarray]]:
    """Resize to SQUARE_SIZE, convert to BGR; optionally return normalized grayscale for matching."""
    sq = cv2.resize(square_rgb, (SQUARE_SIZE, SQUARE_SIZE), interpolation=cv2.INTER_AREA)
    if sq.ndim == 3 and sq.shape[2] == 3:
        sq_bgr = cv2.cvtColor(sq, cv2.COLOR_RGB2BGR)
    else:
        sq_bgr = sq
    if not normalize:
        return sq_bgr, None
    gray = cv2.cvtColor(sq_bgr, cv2.COLOR_BGR2GRAY)
    norm = _normalize_patch(gray).astype(np.float32)
    return sq_bgr, norm


def _match_one(
    sq_bgr: np.ndarray,
    sq_norm: Optional[np.ndarray],
    templ: np.ndarray,
    mask: Optional[np.ndarray],
    normalize: bool,
) -> float:
    """Single template match; returns correlation score. Uses sq_norm if normalize and sq_norm is not None."""
    h, w = sq_bgr.shape[:2]
    if templ.shape[:2] != (h, w):
        templ = cv2.resize(templ, (w, h), interpolation=cv2.INTER_AREA)
        if mask is not None:
            mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    if normalize and sq_norm is not None:
        if templ.ndim == 3:
            templ_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
        else:
            templ_gray = templ
        templ_norm = _normalize_patch(templ_gray).astype(np.float32)
        img = sq_norm
        tpl = templ_norm
    else:
        img = sq_bgr
        tpl = templ
    try:
        if mask is not None:
            result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED, mask=mask)
        else:
            result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    except cv2.error:
        result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    return float(result.flat[0])


def _match_one_edge(
    sq_bgr: np.ndarray,
    templ: np.ndarray,
    mask: Optional[np.ndarray],
    edge_method: str = "gradient",
) -> float:
    """Match using edge maps (shape-based, theme-agnostic). Returns correlation in [-1, 1]."""
    h, w = sq_bgr.shape[:2]
    if templ.shape[:2] != (h, w):
        templ = cv2.resize(templ, (w, h), interpolation=cv2.INTER_AREA)
        if mask is not None:
            mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    sq_gray = cv2.cvtColor(sq_bgr, cv2.COLOR_BGR2GRAY)
    templ_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY) if templ.ndim == 3 else templ
    sq_edge = patch_to_edge_map(sq_gray, method=edge_method)
    tpl_edge = patch_to_edge_map(templ_gray, method=edge_method)
    try:
        if mask is not None:
            result = cv2.matchTemplate(sq_edge, tpl_edge, cv2.TM_CCOEFF_NORMED, mask=mask)
        else:
            result = cv2.matchTemplate(sq_edge, tpl_edge, cv2.TM_CCOEFF_NORMED)
    except cv2.error:
        result = cv2.matchTemplate(sq_edge, tpl_edge, cv2.TM_CCOEFF_NORMED)
    return float(result.flat[0])


def _match_square_to_templates(
    square_rgb: np.ndarray,
    empty_templates: list[tuple[np.ndarray, Optional[np.ndarray], str]],
    piece_templates: list[tuple[np.ndarray, Optional[np.ndarray], str]],
    empty_threshold: float,
    piece_threshold: float,
    normalize: bool = True,
    variance_empty_threshold: Optional[float] = None,
    use_edges: bool = False,
    edge_weight: float = 0.5,
    edge_method: str = "gradient",
) -> str:
    """
    Theme-agnostic: occupancy first (empty vs occupied), then piece matching.
    If variance_empty_threshold is set: low variance (flat square) -> empty; high variance -> piece matching only (no empty-template check).
    Otherwise: occupancy by empty-template correlation; if use_edges, piece choice uses combined norm + edge score.
    """
    sq_bgr, sq_norm = _prepare_square(square_rgb, normalize)

    # Occupancy: variance first (flat = empty). When used, high-variance squares skip empty-template and go to piece matching.
    if variance_empty_threshold is not None:
        var = _variance_in_center(square_rgb)
        if var < variance_empty_threshold:
            return "."
        # High variance: do not use empty-template to label empty; go straight to piece matching
    else:
        # Occupancy: empty-template correlation only
        if empty_templates:
            best_empty = max(
                _match_one(sq_bgr, sq_norm, t, m, normalize)
                for t, m, _ in empty_templates
            )
            if best_empty >= empty_threshold:
                return "."

    def score_fn(templ: np.ndarray, mask: Optional[np.ndarray]) -> float:
        norm_s = _match_one(sq_bgr, sq_norm, templ, mask, normalize)
        if not use_edges:
            return norm_s
        edge_s = _match_one_edge(sq_bgr, templ, mask, edge_method=edge_method)
        return (1.0 - edge_weight) * norm_s + edge_weight * edge_s

    if not piece_templates:
        return "."

    best_char = "."
    best_score = piece_threshold
    for templ, mask, fen_char in piece_templates:
        score = score_fn(templ, mask)
        if score > best_score:
            best_score = score
            best_char = fen_char
    return best_char


# ---------------------------------------------------------------------------
# FEN construction
# ---------------------------------------------------------------------------


def _squares_to_fen(square_fen_chars: list[str]) -> str:
    """Build FEN piece placement from 64 FEN characters (row 0 = rank 8, col 0 = file a)."""
    # square_fen_chars[i] for i = row*8+col -> rank 8-row, file col
    board = chess.Board()
    board.clear()
    for row in range(8):
        for col in range(8):
            idx = row * 8 + col
            c = square_fen_chars[idx]
            if c and c != ".":
                sq = _square_index_to_chess_square(row, col)
                try:
                    piece = chess.Piece.from_symbol(c)
                    board.set_piece_at(sq, piece)
                except ValueError:
                    pass
    return board.board_fen()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def image_to_fen_template(
    img: np.ndarray,
    templates_dir: Path | str,
    *,
    method: str = "contour",
    white_to_move: bool = True,
    match_threshold: float = 0.5,
    empty_threshold: Optional[float] = None,
    piece_threshold: Optional[float] = None,
    normalize: bool = True,
    variance_empty_threshold: Optional[float] = None,
    use_edges: bool = False,
    edge_weight: float = 0.5,
    edge_method: str = "gradient",
    save_marked_path: Optional[Path | str] = None,
) -> Optional[str]:
    """
    Run the template-based pipeline: extract board -> warp -> 64 squares -> template match -> FEN.
    Theme-agnostic: occupancy first (empty vs occupied), normalized matching, piece-only masks.
    variance_empty_threshold: if set, squares with center variance below this are empty (flat); high-variance squares use piece matching only.
    use_edges: if True, combine normalized intensity with edge (shape) matching for robustness.
    edge_weight: weight for edge score when use_edges True; (1-edge_weight) for normalized.
    edge_method: "gradient" (Sobel magnitude) or "canny" for edge map.
    """
    templates_dir = Path(templates_dir)
    if not templates_dir.is_dir():
        logger.warning("Templates dir not found: %s", templates_dir)
        return None

    if empty_threshold is None:
        empty_threshold = 0.82
    if piece_threshold is None:
        piece_threshold = match_threshold if match_threshold > 0 else 0.45

    if method == "contour":
        corners = find_board_corners_contour(img)
    elif method == "edges":
        corners = find_board_corners_edges(img)
    else:
        logger.warning("Unknown method %r, using contour", method)
        corners = find_board_corners_contour(img)

    if corners is None:
        logger.debug("Board corners not detected (method=%s)", method)
        return None

    if save_marked_path:
        save_marked_board_image(img, corners, save_marked_path)

    warped = _warp_board(img, corners)
    squares = _extract_squares(warped)
    templates = load_templates(templates_dir, target_size=SQUARE_SIZE)
    if not templates:
        logger.warning("No templates loaded from %s", templates_dir)
        return None

    empty_templates = [(t, m, c) for t, m, c in templates if c == "."]
    piece_templates = [(t, m, c) for t, m, c in templates if c != "."]

    square_fen_chars = [
        _match_square_to_templates(
            sq,
            empty_templates,
            piece_templates,
            empty_threshold,
            piece_threshold,
            normalize=normalize,
            variance_empty_threshold=variance_empty_threshold,
            use_edges=use_edges,
            edge_weight=edge_weight,
            edge_method=edge_method,
        )
        for sq in squares
    ]
    return _squares_to_fen(square_fen_chars)
