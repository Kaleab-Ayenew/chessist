"""
Main OODA loop: Observe -> Orient -> Decide -> Act.
Runs for one game; caller can wrap in while True for 24/7.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .config import load_config
from .observer import (
    get_board_bounding_box,
    get_move_list_from_dom,
    get_fen_from_dom,
    capture_board_image,
)
from .orient import moves_to_fen, fen_to_turn, image_to_fen_cv
from .decider import best_move, uci_to_squares
from .actuator import execute_move_click_click
from .turn_detection import is_our_turn_clock, is_game_over, we_play_white_from_page
from .humanize import sleep_reaction

logger = logging.getLogger(__name__)

POLL_BOARD_INTERVAL = 1.5


async def wait_for_board(page, *, timeout_seconds: Optional[float] = None) -> bool:
    """
    Poll until a board is found on the page.
    Returns True when board is found, False if timeout_seconds is set and exceeded.
    """
    import time
    start = time.monotonic()
    while True:
        box = await get_board_bounding_box(page)
        if box is not None:
            return True
        if timeout_seconds is not None and (time.monotonic() - start) >= timeout_seconds:
            return False
        await asyncio.sleep(POLL_BOARD_INTERVAL)


async def obtain_fen(page, board_box, *, we_play_white: bool, our_turn: Optional[bool] = None):
    """Observe + Orient: vision (primary) first, then DOM fallback."""
    import chess
    cfg = load_config()
    # Vision is primary; support legacy prefer_dom (prefer_dom true => vision not first)
    prefer_vision = cfg.get("prefer_vision")
    if prefer_vision is None:
        prefer_vision = not cfg.get("prefer_dom", False)

    fen = None
    white_to_move = we_play_white

    # Primary: vision (chesscog)
    if prefer_vision:
        img = await capture_board_image(page, board_box)
        fen = image_to_fen_cv(img, white_to_move=we_play_white)
        if fen and our_turn is not None:
            white_to_move = we_play_white if our_turn else (not we_play_white)
        elif fen:
            try:
                white_to_move = chess.Board(fen).turn if " " in fen else we_play_white
            except Exception:
                pass

    # Fallback: DOM
    if not fen:
        fen = await get_fen_from_dom(page)
        if not fen:
            moves = await get_move_list_from_dom(page)
            if moves:
                fen = moves_to_fen(moves)
        if fen:
            try:
                b = chess.Board(fen) if " " in fen else chess.Board()
                if " " not in fen:
                    b.set_board_fen(fen)
                white_to_move = b.turn
            except Exception:
                pass

    return fen, white_to_move


async def run_game_loop(page, *, we_play_white: Optional[bool] = None):
    """
    Run OODA loop until game over.
    If we_play_white is None, try to detect from page.
    """
    board_box = await get_board_bounding_box(page)
    if not board_box:
        logger.error("Could not find board on page")
        return

    if we_play_white is None:
        we_play_white = await we_play_white_from_page(page)
        if we_play_white is None:
            we_play_white = True  # assume white
    logger.info("We play as %s", "white" if we_play_white else "black")

    while True:
        if await is_game_over(page):
            logger.info("Game over.")
            break

        our_turn = await is_our_turn_clock(page, we_play_white=we_play_white)
        if our_turn is False:
            await asyncio.sleep(0.5)
            continue
        if our_turn is None:
            # Assume our turn if we can't tell (e.g. start of game)
            our_turn = True

        sleep_reaction()

        fen, white_to_move = await obtain_fen(
            page, board_box, we_play_white=we_play_white, our_turn=our_turn
        )
        if not fen:
            logger.warning("Could not get FEN; retrying")
            await asyncio.sleep(0.5)
            continue

        move = best_move(fen, white_to_move=white_to_move)
        if not move:
            logger.warning("No move from engine; retrying")
            await asyncio.sleep(0.5)
            continue

        uci = move.uci()
        from_sq, to_sq = uci_to_squares(uci)
        if not from_sq or not to_sq:
            continue

        ok = await execute_move_click_click(page, board_box, from_sq, to_sq)
        if not ok:
            logger.warning("Execute move failed; retrying")
        await asyncio.sleep(0.3)
