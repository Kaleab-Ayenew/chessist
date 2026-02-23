"""
Entry point for python -m src.agent and for the auto-chess console script.
Chess assist: screen capture -> template vision (board + FEN) -> Stockfish -> overlay + terminal.
Overlay is a tkinter control panel: we play white/black, show move, auto-play, start/stop agent.
"""
from pathlib import Path

from src.agent.config import get_bundle_dir, get_templates_dir

# When run from repo, project root is parent of src; when installed/frozen, use bundle dir
_PKG_ROOT = get_bundle_dir()


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

    def run_assist_mode(we_play_white_default: bool, *, show_overlay: bool) -> None:

        cfg = load_config()
        poll_interval = float(cfg.get("assist_poll_seconds", 2.0))

        # Shared state for overlay and loop
        state = {
            "we_play_white": we_play_white_default,
            "show_recommendation": True,
            "auto_play": False,
            "agent_running": False,
        }

        def get_we_play_white() -> bool:
            return state["we_play_white"]

        def set_we_play_white(v: bool) -> None:
            state["we_play_white"] = v

        def get_show_recommendation() -> bool:
            return state["show_recommendation"]

        def set_show_recommendation(v: bool) -> None:
            state["show_recommendation"] = v

        def get_auto_play() -> bool:
            return state["auto_play"]

        def set_auto_play(v: bool) -> None:
            state["auto_play"] = v

        def get_agent_running() -> bool:
            return state["agent_running"]

        def start_agent() -> None:
            state["agent_running"] = True

        def stop_agent() -> None:
            state["agent_running"] = False

        if show_overlay:
            from src.agent.overlay import run_overlay
            run_overlay(
                get_we_play_white=get_we_play_white,
                set_we_play_white=set_we_play_white,
                get_show_recommendation=get_show_recommendation,
                set_show_recommendation=set_show_recommendation,
                get_auto_play=get_auto_play,
                set_auto_play=set_auto_play,
                get_agent_running=get_agent_running,
                start_agent=start_agent,
                stop_agent=stop_agent,
                poll_interval=poll_interval,
                should_stop=lambda: not state["agent_running"],
            )
            return

        # No overlay: terminal-only loop with fixed we_play_white
        def get_we_play_white_const() -> bool:
            return we_play_white_default

        from src.agent.assist_loop import run_assist_loop  

        logger.info("Assist: recommended move in terminal only. Ctrl+C to stop.")
        try:
            run_assist_loop(
                get_we_play_white_const,
                poll_interval=poll_interval,
                get_show_recommendation=lambda: True,
                get_auto_play=lambda: False,
            )
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
        templates_dir = get_templates_dir()
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

    parser = argparse.ArgumentParser(description="Chess assist: vision + Stockfish, overlay + auto-play")
    parser.add_argument("--we-play", choices=["white", "black"], default="white", help="Default side we play (overlay can override)")
    parser.add_argument("--assist", action="store_true", default=True)
    parser.add_argument("--no-overlay", action="store_true", help="Terminal only, no control panel")
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
    run_assist_mode(we_play_white_default=(args.we_play != "black"), show_overlay=not args.no_overlay)


if __name__ == "__main__":
    _main()
