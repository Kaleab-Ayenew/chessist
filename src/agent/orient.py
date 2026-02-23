"""Orient: screenshot -> FEN using template-based vision only."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chess

logger = logging.getLogger(__name__)


def moves_to_fen(move_strings: list[str]) -> Optional[str]:
    """Build FEN (piece placement only) from a list of SAN moves. Returns board_fen() or None."""
    board = chess.Board()
    for s in move_strings:
        s = (s or "").strip()
        if not s:
            continue
        try:
            board.push(board.parse_san(s))
        except Exception:
            return None
    return board.board_fen()


def fen_to_turn(fen: str) -> bool:
    """Return True if white to move, False if black. Default True."""
    try:
        return chess.Board(fen).turn
    except Exception:
        return True


def image_to_fen_cv(
    image_rgb,
    *,
    white_to_move: bool = True,
    save_marked_path: Optional[str | Path] = None,
    save_warped_path: Optional[str | Path] = None,
    save_edges_path: Optional[str | Path] = None,
) -> Optional[str]:
    """
    Template-based vision: extract board -> warp -> 64 squares -> template match -> FEN.
    Uses config template_fen. Tries contour first, then edges if no board found.
    Returns board FEN (piece placement) or None if board not detected.
    """
    import numpy as np
    from .config import load_config
    from .vision_template import image_to_fen_template

    # mss can return non-contiguous arrays; OpenCV expects contiguous
    image_rgb = np.ascontiguousarray(image_rgb)

    from .config import get_templates_dir
    cfg = load_config()
    template_cfg = cfg.get("template_fen") or {}
    custom_templates = template_cfg.get("templates_dir")
    if custom_templates and Path(custom_templates).is_absolute():
        templates_dir = Path(custom_templates)
    else:
        templates_dir = get_templates_dir()

    if not templates_dir.is_dir():
        logger.warning("Templates dir not found: %s", templates_dir)
        return None

    def run_pipeline(method: str):
        return image_to_fen_template(
            image_rgb,
            templates_dir,
            method=method,
            white_to_move=white_to_move,
            match_threshold=float(template_cfg.get("template_match_threshold", 0.5)),
            empty_threshold=template_cfg.get("empty_threshold"),
            piece_threshold=template_cfg.get("piece_threshold"),
            normalize=template_cfg.get("normalize", True),
            variance_empty_threshold=template_cfg.get("variance_empty_threshold"),
            use_edges=template_cfg.get("use_edges", False),
            edge_weight=template_cfg.get("edge_weight", 0.5),
            edge_method=template_cfg.get("edge_method", "gradient"),
            save_marked_path=save_marked_path,
            save_warped_path=save_warped_path,
            save_edges_path=save_edges_path,
        )

    preferred = template_cfg.get("board_extraction", "contour")
    fen = run_pipeline(preferred)
    if fen is None:
        fallback = "edges" if preferred != "edges" else "contour"
        logger.debug("Board not found with %s, trying %s", preferred, fallback)
        fen = run_pipeline(fallback)
    return fen


def image_to_fen_cv_with_bounds(
    image_rgb,
    *,
    white_to_move: bool = True,
    save_marked_path: Optional[str | Path] = None,
    save_warped_path: Optional[str | Path] = None,
    save_edges_path: Optional[str | Path] = None,
) -> Optional[tuple[str, "np.ndarray"]]:
    """
    Template-based vision that returns (fen, corners) when board is detected.
    corners: (4, 2) float32 in image/screen coords [top-left, top-right, bottom-right, bottom-left].
    Returns None if board not detected.
    """
    import numpy as np
    from .config import load_config
    from .vision_template import image_to_fen_template_with_corners

    image_rgb = np.ascontiguousarray(image_rgb)

    from .config import get_templates_dir
    cfg = load_config()
    template_cfg = cfg.get("template_fen") or {}
    custom_templates = template_cfg.get("templates_dir")
    if custom_templates and Path(custom_templates).is_absolute():
        templates_dir = Path(custom_templates)
    else:
        templates_dir = get_templates_dir()

    if not templates_dir.is_dir():
        logger.warning("Templates dir not found: %s", templates_dir)
        return None

    def run_pipeline(method: str):
        return image_to_fen_template_with_corners(
            image_rgb,
            templates_dir,
            method=method,
            white_to_move=white_to_move,
            match_threshold=float(template_cfg.get("template_match_threshold", 0.5)),
            empty_threshold=template_cfg.get("empty_threshold"),
            piece_threshold=template_cfg.get("piece_threshold"),
            normalize=template_cfg.get("normalize", True),
            variance_empty_threshold=template_cfg.get("variance_empty_threshold"),
            use_edges=template_cfg.get("use_edges", False),
            edge_weight=template_cfg.get("edge_weight", 0.5),
            edge_method=template_cfg.get("edge_method", "gradient"),
            save_marked_path=save_marked_path,
            save_warped_path=save_warped_path,
            save_edges_path=save_edges_path,
        )

    preferred = template_cfg.get("board_extraction", "contour")
    result = run_pipeline(preferred)
    if result is None:
        fallback = "edges" if preferred != "edges" else "contour"
        result = run_pipeline(fallback)
    return result
