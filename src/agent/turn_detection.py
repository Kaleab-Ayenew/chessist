"""Turn detection: is it our turn? Game over?"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def is_our_turn_clock(page, *, we_play_white: bool) -> Optional[bool]:
    """
    Detect whose turn by clock activity (Chess.com: active clock has a class).
    Returns True if it's our turn, False if opponent's, None if unknown.
    """
    try:
        # Chess.com often marks the active clock with a class like 'clock-active' or similar
        js = """
        () => {
            const clocks = document.querySelectorAll('[class*="clock"], [class*="Clock"]');
            for (const el of clocks) {
                const c = (el.className || '').toLowerCase();
                if (c.includes('active') || c.includes('running')) {
                    // First clock is usually white, second black (or vice versa - site dependent)
                    const isFirst = el === document.querySelector('[class*="clock"]') ||
                        Array.from(clocks).indexOf(el) === 0;
                    return isFirst;  // true = white's clock is active
                }
            }
            return null;
        }
        """
        white_active = await page.evaluate(js)
        if white_active is None:
            return None
        return white_active if we_play_white else (not white_active)
    except Exception as e:
        logger.debug("is_our_turn_clock: %s", e)
    return None


async def is_game_over(page) -> bool:
    """Check for game-over overlay or modal."""
    try:
        js = """
        () => {
            const text = (document.body?.innerText || '').toLowerCase();
            if (/game over|checkmate|stalemate|draw|you (won|lost|draw)/.test(text)) return true;
            const modals = document.querySelectorAll('[class*="modal"], [class*="overlay"], [class*="result"]');
            for (const m of modals) {
                if (m.offsetParent !== null && m.getBoundingClientRect().width > 50) return true;
            }
            return false;
        }
        """
        return await page.evaluate(js)
    except Exception:
        return False


async def we_play_white_from_page(page) -> Optional[bool]:
    """Try to detect if we are playing white (our pieces at bottom). Heuristic."""
    try:
        # Often our clock or our name is on one side; or board orientation.
        js = """
        () => {
            const body = (document.body?.innerText || '').toLowerCase();
            // If "You play as black" or similar appears
            if (body.includes('play as black') || body.includes('playing black')) return false;
            if (body.includes('play as white') || body.includes('playing white')) return true;
            return null;
        }
        """
        return await page.evaluate(js)
    except Exception:
        pass
    return None
