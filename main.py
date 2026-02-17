#!/usr/bin/env python3
"""
Autonomous Chess.com agent — main entry.
Launches browser, navigates to Chess.com. By default waits for you to press Enter
in the terminal after logging in and starting a game, then the agent plays.
Use --wait-for-board to poll until a board appears, or --no-wait to start immediately.
Anti-detection: stealth context, realistic UA, Chromium flags, optional persistent profile and system Chrome.

Assist mode (--assist): no browser. You open Chess.com yourself; the app captures the screen,
runs vision + Stockfish, and shows the recommended move in the terminal and optionally in an overlay window.
Use --assist-set-region to open a GUI to select the board area and save it to config.
"""
import argparse
import asyncio
import logging
import sys
import threading
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.agent.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_assist_mode(we_play_white: bool, *, show_overlay: bool) -> None:
    """Assist mode: capture screen -> vision -> Stockfish -> show move in terminal and optionally overlay."""
    from src.agent.assist_loop import run_assist_loop

    cfg = load_config()
    poll_interval = float(cfg.get("assist_poll_seconds", 2.0))

    if show_overlay:
        try:
            import tkinter as tk
        except ImportError:
            logger.warning("tkinter not available; overlay disabled. Use --no-overlay to hide this.")
            show_overlay = False

    if show_overlay:
        import signal
        root = tk.Tk()
        root.title("Chess assist")
        root.attributes("-topmost", True)
        root.resizable(True, False)
        root.geometry("320x120+20+20")
        label_uci = tk.Label(root, text="—", font=("Sans", 24), fg="#333")
        label_uci.pack(pady=(12, 4))
        label_san = tk.Label(root, text="", font=("Sans", 18), fg="#666")
        label_san.pack(pady=(0, 12))

        def on_move(uci: str, san: str) -> None:
            def update() -> None:
                label_uci.config(text=uci)
                label_san.config(text=f"Play: {san}")

            root.after(0, update)

        def quit_app() -> None:
            root.after(0, root.destroy)

        def run_loop() -> None:
            try:
                run_assist_loop(
                    we_play_white,
                    poll_interval=poll_interval,
                    on_move=on_move,
                )
            except KeyboardInterrupt:
                quit_app()

        # So Ctrl+C closes the overlay and exits (main thread is in mainloop)
        def sigint_handler(_signum, _frame) -> None:
            quit_app()

        signal.signal(signal.SIGINT, sigint_handler)
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        logger.info(
            "Assist mode: open Chess.com in your browser. Recommended move in terminal and overlay. Ctrl+C to stop."
        )
        root.mainloop()
    else:
        logger.info(
            "Assist mode: open Chess.com in your browser. Recommended move in terminal. Ctrl+C to stop."
        )
        try:
            run_assist_loop(we_play_white, poll_interval=poll_interval)
        except KeyboardInterrupt:
            logger.info("Stopped by user")


def _run_test_vision() -> None:
    """Run vision on sample_screenshot.png and print FEN (for testing CV)."""
    from pathlib import Path
    import numpy as np
    from PIL import Image

    project_root = Path(__file__).resolve().parent
    sample_path = project_root / "sample_screenshot.png"
    if not sample_path.exists():
        logger.error("sample_screenshot.png not found in project root. Copy a board screenshot there (e.g. from last_assist_screenshot.png).")
        return
    img = np.array(Image.open(sample_path).convert("RGB"))
    from src.agent.orient import image_to_fen_cv
    fen = image_to_fen_cv(img, white_to_move=True)
    if fen:
        print("FEN:", fen)
    else:
        print("No board detected.")


def _run_test_vision_template(method: str) -> None:
    """Run template-based vision on sample_screenshot.png; method is 'contour' or 'edges'."""
    from pathlib import Path
    import numpy as np
    from PIL import Image

    project_root = Path(__file__).resolve().parent
    sample_path = project_root / "sample_screenshot.png"
    if not sample_path.exists():
        logger.error("sample_screenshot.png not found in project root.")
        return
    templates_dir = project_root / "templates"
    if not templates_dir.is_dir():
        logger.error("templates/ directory not found. Add Chess.com piece images (wp.png, bk.png, 200.png, etc.).")
        return
    img = np.array(Image.open(sample_path).convert("RGB"))
    from src.agent.vision_template import image_to_fen_template
    cfg = load_config()
    template_cfg = cfg.get("template_fen") or {}
    marked_path = project_root / f"last_{method}_marked.png"
    fen = image_to_fen_template(
        img,
        templates_dir,
        method=template_cfg.get("board_extraction", method),
        save_marked_path=marked_path,
        match_threshold=float(template_cfg.get("template_match_threshold", 0.5)),
        empty_threshold=template_cfg.get("empty_threshold"),
        piece_threshold=template_cfg.get("piece_threshold"),
        normalize=template_cfg.get("normalize", True),
        variance_empty_threshold=template_cfg.get("variance_empty_threshold"),
        use_edges=template_cfg.get("use_edges", False),
        edge_weight=template_cfg.get("edge_weight", 0.5),
        edge_method=template_cfg.get("edge_method", "gradient"),
    )
    if fen:
        print(f"FEN ({method}):", fen)
        print(f"Marked board image: {marked_path}")
    else:
        print(f"No board detected (method={method}).")


# Chromium launch args to reduce automation fingerprint (e.g. navigator.webdriver, automation UI)
STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-popup-blocking",
]

# Realistic browser context: looks like a normal Chrome user
STEALTH_CONTEXT = {
    "viewport": {"width": 1280, "height": 720},
    "locale": "en-US",
    "timezone_id": "America/New_York",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
}


async def main():
    parser = argparse.ArgumentParser(description="Autonomous Chess.com agent")
    parser.add_argument(
        "--url",
        default=None,
        help="Chess.com game URL (or start from home and navigate manually)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless",
    )
    parser.add_argument(
        "--we-play",
        choices=["white", "black", "auto"],
        default="auto",
        help="Which color we play (auto = detect from page)",
    )
    _NOT_GIVEN = object()
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Start game loop immediately (may exit if no board yet)",
    )
    parser.add_argument(
        "--wait-for-board",
        nargs="?",
        default=_NOT_GIVEN,
        const=None,
        metavar="SECS",
        help="Poll until board is found (SECS=timeout in seconds; omit for no timeout)",
    )
    parser.add_argument(
        "--chrome",
        action="store_true",
        help="Use installed Google Chrome instead of Playwright Chromium (better fingerprint)",
    )
    parser.add_argument(
        "--user-data-dir",
        metavar="PATH",
        default=None,
        help="Use persistent browser profile (login once, reuse cookies/session)",
    )
    parser.add_argument(
        "--assist",
        action="store_true",
        help="Assist mode: capture screen, show recommended move (no browser; you move manually)",
    )
    parser.add_argument(
        "--no-overlay",
        action="store_true",
        help="In assist mode, only print to terminal (no overlay window)",
    )
    parser.add_argument(
        "--assist-set-region",
        action="store_true",
        help="Open GUI to select board region (drag rectangle, save to config.yaml); then exit",
    )
    parser.add_argument(
        "--test-vision",
        action="store_true",
        help="Run vision on sample_screenshot.png and print FEN (for testing CV without assist loop)",
    )
    parser.add_argument(
        "--test-vision-template",
        nargs="?",
        metavar="METHOD",
        const="contour",
        default=None,
        help="Run template-based FEN on sample_screenshot.png; METHOD is 'contour' or 'edges' (default: contour)",
    )
    args = parser.parse_args()
    # Normalize --wait-for-board: convert numeric string to float
    if args.wait_for_board is not _NOT_GIVEN and args.wait_for_board is not None:
        args.wait_for_board = float(args.wait_for_board)

    # --- Region picker: one-shot GUI to set assist_region in config ---
    if args.assist_set_region:
        from src.agent.assist_region_picker import run_region_picker
        run_region_picker()
        return

    # --- Test vision on sample screenshot ---
    if args.test_vision:
        _run_test_vision()
        return
    if args.test_vision_template is not None:
        method = args.test_vision_template if args.test_vision_template in ("contour", "edges") else "contour"
        _run_test_vision_template(method)
        return

    # --- Assist mode: no Playwright, screen capture + vision + Stockfish, show move ---
    if args.assist:
        run_assist_mode(
            we_play_white=(args.we_play != "black"),
            show_overlay=not args.no_overlay,
        )
        return

    # --- Browser mode ---
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
    from src.agent.loop import run_game_loop, wait_for_board

    cfg = load_config()
    base = cfg.get("chess_com_base", "https://www.chess.com")
    url = args.url or base

    we_play_white = None
    if args.we_play == "white":
        we_play_white = True
    elif args.we_play == "black":
        we_play_white = False

    launch_opts = {
        "headless": args.headless,
        "args": STEALTH_LAUNCH_ARGS,
        "ignore_default_args": ["--enable-automation"],
    }
    if args.chrome:
        launch_opts["channel"] = "chrome"

    async with async_playwright() as p:
        if args.user_data_dir:
            # Persistent profile: reuse cookies/session (log in once)
            context = await p.chromium.launch_persistent_context(
                args.user_data_dir,
                **launch_opts,
                **STEALTH_CONTEXT,
            )
            browser = None
        else:
            browser = await p.chromium.launch(**launch_opts)
            context = await browser.new_context(**STEALTH_CONTEXT)

        await Stealth().apply_stealth_async(context)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")

        logger.info("Browser open. Log in and start a game if needed, then the agent will play.")
        logger.info("Press Ctrl+C to stop.")

        # Wait phase: --wait-for-board, or Enter (default), or --no-wait
        if args.wait_for_board is not _NOT_GIVEN:
            timeout = args.wait_for_board  # None = infinite, float = seconds
            ok = await wait_for_board(page, timeout_seconds=timeout)
            if not ok:
                logger.error("No board found within %s seconds.", timeout)
                return
        elif not args.no_wait:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: input("Press Enter when you're in a game and ready for the agent to play... "),
            )

        try:
            await run_game_loop(page, we_play_white=we_play_white)
        except KeyboardInterrupt:
            logger.info("Stopped by user")
        finally:
            if browser is not None:
                await browser.close()
            else:
                await context.close()


if __name__ == "__main__":
    asyncio.run(main())
