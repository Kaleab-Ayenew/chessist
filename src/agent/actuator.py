"""Act: Playwright click-click with coordinate mapping and humanization."""
from __future__ import annotations

import logging
from typing import Optional

from .humanize import jitter_xy, sleep_move_interval
from .observer import get_square_coordinates

logger = logging.getLogger(__name__)


def _find_square_center(squares: list[dict], file_: str, rank: int) -> Optional[tuple[float, float]]:
    """Get (x, y) center for a square by file/rank. rank 1-8, file 'a'-'h'."""
    for sq in squares:
        if sq.get("file") == file_ and sq.get("rank") == rank:
            return sq["x"], sq["y"]
    return None


async def execute_move_click_click(
    page,
    board_box: dict,
    from_square: str,
    to_square: str,
    *,
    apply_jitter: bool = True,
) -> bool:
    """
    Execute move by clicking from_square then to_square (e.g. 'e2', 'e4').
    board_box and page used to get square coordinates and perform clicks.
    """
    squares = await get_square_coordinates(page, board_box)
    if not squares:
        logger.error("Could not get square coordinates")
        return False

    # Square size for jitter
    sq_size = board_box.get("width", 400) / 8

    from_xy = _find_square_center(squares, from_square[0], int(from_square[1]))
    to_xy = _find_square_center(squares, to_square[0], int(to_square[1]))
    if not from_xy or not to_xy:
        logger.error("Square not found: %s -> %s", from_square, to_square)
        return False

    if apply_jitter:
        from_xy = jitter_xy(from_xy[0], from_xy[1], sq_size)
        to_xy = jitter_xy(to_xy[0], to_xy[1], sq_size)

    try:
        await page.mouse.click(from_xy[0], from_xy[1])
        sleep_move_interval()
        await page.mouse.click(to_xy[0], to_xy[1])
        return True
    except Exception as e:
        logger.warning("execute_move_click_click failed: %s", e)
        return False
