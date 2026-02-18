"""
Entry point for python -m src.agent and for the auto-chess console script.
Chess assist: screen capture -> template vision (board + FEN) -> Stockfish -> overlay + terminal.
"""
from pathlib import Path

# When run from repo, project root is parent of src; when installed, cwd is primary
_PKG_ROOT = Path(__file__).resolve().parent.parent.parent


def _main() -> None:
    import argparse
    import logging
    import signal
    import sys
    import threading

    from src.agent.config import get_debug_dir, load_config

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    def run_assist_mode(we_play_white: bool, *, show_overlay: bool) -> None:
        from src.agent.assist_loop import run_assist_loop
        cfg = load_config()
        poll_interval = float(cfg.get("assist_poll_seconds", 2.0))
        if show_overlay:
            try:
                import tkinter as tk
            except ImportError:
                logger.warning("tkinter not available; overlay disabled. Use --no-overlay.")
                show_overlay = False
        if show_overlay:
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
                    run_assist_loop(we_play_white, poll_interval=poll_interval, on_move=on_move)
                except KeyboardInterrupt:
                    quit_app()

            signal.signal(signal.SIGINT, lambda s, f: quit_app())
            thread = threading.Thread(target=run_loop, daemon=True)
            thread.start()
            logger.info("Assist: open your board (e.g. Chess.com). Ctrl+C to stop.")
            root.mainloop()
        else:
            logger.info("Assist: recommended move in terminal only. Ctrl+C to stop.")
            try:
                run_assist_loop(we_play_white, poll_interval=poll_interval)
            except KeyboardInterrupt:
                logger.info("Stopped by user")

    def run_test_vision_template(method: str) -> None:
        import numpy as np
        from PIL import Image
        from src.agent.vision_template import image_to_fen_template
        cwd = Path.cwd()
        sample_path = cwd / "sample_screenshot.png"
        if not sample_path.exists():
            sample_path = _PKG_ROOT / "sample_screenshot.png"
        if not sample_path.exists():
            logger.error("sample_screenshot.png not found in current directory or package root.")
            return
        templates_dir = cwd / "templates"
        if not templates_dir.is_dir():
            templates_dir = _PKG_ROOT / "templates"
        if not templates_dir.is_dir():
            logger.error("templates/ directory not found.")
            return
        img = np.array(Image.open(sample_path).convert("RGB"))
        cfg = load_config()
        template_cfg = cfg.get("template_fen") or {}
        marked_path = get_debug_dir() / f"last_{method}_marked.png"
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
            print(f"Marked board: {marked_path} (debug: {get_debug_dir()})")
        else:
            print(f"No board detected (method={method}).")

    parser = argparse.ArgumentParser(description="Chess assist: vision + Stockfish, overlay move")
    parser.add_argument("--we-play", choices=["white", "black"], default="white")
    parser.add_argument("--assist", action="store_true", default=True)
    parser.add_argument("--no-overlay", action="store_true", help="Terminal only")
    parser.add_argument(
        "--test-vision-template",
        nargs="?",
        metavar="METHOD",
        const="contour",
        default=None,
        help="Test FEN on sample_screenshot.png; METHOD contour or edges",
    )
    args = parser.parse_args()

    if args.test_vision_template is not None:
        method = args.test_vision_template if args.test_vision_template in ("contour", "edges") else "contour"
        run_test_vision_template(method)
        return
    run_assist_mode(we_play_white=(args.we_play != "black"), show_overlay=not args.no_overlay)


if __name__ == "__main__":
    _main()
