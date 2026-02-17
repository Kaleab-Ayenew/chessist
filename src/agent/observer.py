"""Observe: DOM inspection and screenshot capture for Chess.com."""
from __future__ import annotations

import base64
import io
import logging
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# Chess.com selectors (may need adjustment if site changes)
BOARD_SELECTOR = "div[class*='board']"
# Move list: various possible structures
MOVE_LIST_SELECTORS = [
    "div[class*='move-list']",
    "div[class*='vertical-move-list']",
    "div[class*=' moves']",
    "div[data-cy='move-list']",
]
# Square elements (some boards use piece elements with data-square or similar)
SQUARE_ATTR = "data-square"


async def get_board_bounding_box(page) -> Optional[dict]:
    """Get board container bounding rect: {x, y, width, height} in viewport coords."""
    try:
        # Try common board container selectors
        for sel in [
            "div[class*='board'][class*='board-']",
            "div.board",
            "main div[class*='board']",
            "div[class*='game-board']",
        ]:
            el = await page.query_selector(sel)
            if el:
                box = await el.bounding_box()
                if box and box.get("width", 0) > 100:
                    return box
        # Fallback: find largest square-like div that could be the board
        divs = await page.query_selector_all("div")
        best = None
        best_area = 0
        for d in divs:
            box = await d.bounding_box()
            if not box:
                continue
            w, h = box.get("width", 0), box.get("height", 0)
            if 300 <= w <= 800 and 300 <= h <= 800 and abs(w - h) < 50:
                if w * h > best_area:
                    best_area = w * h
                    best = box
        return best
    except Exception as e:
        logger.warning("get_board_bounding_box failed: %s", e)
    return None


async def get_move_list_from_dom(page) -> Optional[list[str]]:
    """
    Extract move list from Chess.com DOM.
    Returns list of move strings, e.g. ['e4', 'e5', 'Nf3', 'Nc6'].
    """
    try:
        # Chess.com often stores moves in elements with move text or data attributes.
        # Try to get move list from vertical move list or similar.
        js = """
        () => {
            const moves = [];
            // Try vertical move list
            const moveDivs = document.querySelectorAll('[class*="move"], [class*="Move"]');
            for (const el of moveDivs) {
                const text = (el.textContent || '').trim();
                // Filter to plausible SAN moves (e.g. e4, Nf3, O-O)
                if (/^[NBRQK]?[a-h]?[1-8]?[x]?[a-h][1-8](=[NBRQ])?[+#]?$/.test(text) ||
                    /^[a-h][1-8](=[NBRQ])?[+#]?$/.test(text) ||
                    /^O-O(-O)?$/.test(text)) {
                    if (text && !moves.includes(text)) moves.push(text);
                }
            }
            if (moves.length > 0) return moves;

            // Try data from game state (some sites expose this)
            const gameState = window.__CHESS_COM__ || window.gameState || window.chess;
            if (gameState && Array.isArray(gameState.moves)) return gameState.moves;
            if (gameState && gameState.moveList) return gameState.moveList;

            // Try move list container text and parse numbers + moves
            const list = document.querySelector('[class*="move-list"], [class*="vertical-move-list"]');
            if (list) {
                const raw = (list.textContent || '').replace(/\\d+\\.\\s*/g, ' ').split(/\\s+/).filter(Boolean);
                return raw.filter(s => s.length >= 2 && s.length <= 7);
            }
            return null;
        }
        """
        out = await page.evaluate(js)
        if out and isinstance(out, list) and len(out) > 0:
            return out
    except Exception as e:
        logger.debug("get_move_list_from_dom failed: %s", e)
    return None


async def get_fen_from_dom(page) -> Optional[str]:
    """
    Try to read FEN or build from move list via page JS.
    Returns FEN string (piece placement only) or None.
    """
    try:
        js_fen = """
        () => {
            const g = window.chesscom || window.__CHESS_COM__ || window.gameController;
            if (g && typeof g.getFen === 'function') return g.getFen();
            if (g && g.fen) return g.fen;
            if (g && g.position) return g.position;
            return null;
        }
        """
        fen = await page.evaluate(js_fen)
        if fen and isinstance(fen, str) and len(fen) > 20:
            return fen.strip()
    except Exception:
        pass
    return None


async def capture_board_image(page, board_box: dict) -> np.ndarray:
    """Capture screenshot of board region as RGB numpy array."""
    x, y = board_box.get("x", 0), board_box.get("y", 0)
    w, h = int(board_box.get("width", 400)), int(board_box.get("height", 400))
    clip = {"x": x, "y": y, "width": w, "height": h}
    screenshot_bytes = await page.screenshot(clip=clip)
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    return np.array(img)


async def get_square_coordinates(page, board_box: dict) -> Optional[list[dict]]:
    """
    Get center (x,y) for each of 64 squares in board order (a1..h8 from white's view).
    Returns list of {x, y, file, rank} for each square, or None if we can't compute.
    """
    try:
        x0 = board_box.get("x", 0)
        y0 = board_box.get("y", 0)
        w = board_box.get("width", 400)
        h = board_box.get("height", 400)
        # Chess.com: white is usually at bottom (rank 1), a1 bottom-left.
        # So from viewport: left->right = a->h, bottom->top = rank 1->8.
        # So first row (y near y0+h) = rank 1, last row (y near y0) = rank 8.
        sq_w, sq_h = w / 8, h / 8
        squares = []
        for row in range(8):   # 0 = rank 8 (top), 7 = rank 1 (bottom)
            for col in range(8):  # 0 = a, 7 = h
                # center of square
                cx = x0 + (col + 0.5) * sq_w
                cy = y0 + (row + 0.5) * sq_h
                file_ = chr(ord("a") + col)
                rank = 8 - row
                squares.append({"x": cx, "y": cy, "file": file_, "rank": rank})
        return squares
    except Exception as e:
        logger.warning("get_square_coordinates failed: %s", e)
    return None
