"""
Test computer vision using a sample screenshot (sample_screenshot.png in project root).

Place a screenshot of a chess board (e.g. copy last_assist_screenshot.png to sample_screenshot.png)
to verify board detection and FEN extraction without running the full assist loop.
For corner detection to pass, the image should show a clear 8x8 board with visible squares
(e.g. full board from assist capture or a region that contains the whole board).

Run: python -m unittest tests.test_vision_sample
"""
from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

# Project root: tests/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_IMAGE_PATH = PROJECT_ROOT / "sample_screenshot.png"


def _load_sample_image() -> np.ndarray | None:
    """Load sample_screenshot.png as RGB numpy array, or None if missing."""
    if not SAMPLE_IMAGE_PATH.exists():
        return None
    from PIL import Image
    img = Image.open(SAMPLE_IMAGE_PATH)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return np.array(img)


@unittest.skipUnless(
    SAMPLE_IMAGE_PATH.exists() and (PROJECT_ROOT / "templates").is_dir(),
    "sample_screenshot.png and templates/ required",
)
class TestVisionTemplatePipeline(unittest.TestCase):
    """Template-based FEN pipeline (contour + edges extraction, template matching)."""

    def test_board_corners_contour(self) -> None:
        """Contour method should return 4 corners or None."""
        from src.agent.vision_template import find_board_corners_contour
        img = _load_sample_image()
        self.assertIsNotNone(img)
        corners = find_board_corners_contour(img)
        if corners is not None:
            self.assertEqual(corners.shape, (4, 2), "expected 4 corners (x, y)")

    def test_board_corners_edges(self) -> None:
        """Edge projection method should return 4 corners or None."""
        from src.agent.vision_template import find_board_corners_edges
        img = _load_sample_image()
        self.assertIsNotNone(img)
        corners = find_board_corners_edges(img)
        if corners is not None:
            self.assertEqual(corners.shape, (4, 2), "expected 4 corners (x, y)")

    def test_image_to_fen_template_returns_valid_fen(self) -> None:
        """image_to_fen_template should return parseable FEN or None."""
        from src.agent.vision_template import image_to_fen_template
        import chess
        img = _load_sample_image()
        self.assertIsNotNone(img)
        templates_dir = PROJECT_ROOT / "templates"
        for method in ("contour", "edges"):
            fen = image_to_fen_template(img, templates_dir, method=method)
            if fen is None:
                continue
            try:
                board = chess.Board()
                board.set_board_fen(fen)
            except ValueError as e:
                self.fail(f"image_to_fen_template(method={method}) returned invalid FEN {fen!r}: {e}")


if __name__ == "__main__":
    unittest.main()
