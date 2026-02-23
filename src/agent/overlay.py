"""
Tkinter overlay: control panel for chess assist and auto-play.
Provides: we play white/black, show move recommendation, auto-play toggles, start/stop agent, move display, game over message.
Runs the assist loop on the main thread via root.after() to avoid X11/xcb multi-thread crashes on Linux.
Uses standard tkinter with ttk styling for modern dark/light themes.
"""
from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import ttk
from typing import Callable

logger = logging.getLogger(__name__)

DARK_COLORS = {
    "bg": "#1a1a2e",
    "bg_secondary": "#16213e",
    "fg": "#eaeaea",
    "fg_dim": "#888888",
    "fg_muted": "#666666",
    "accent": "#4a9eff",
    "accent_hover": "#6bb3ff",
    "accent_active": "#3d8ae0",
    "success": "#4ade80",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "border": "#2d2d44",
}

LIGHT_COLORS = {
    "bg": "#f8fafc",
    "bg_secondary": "#ffffff",
    "fg": "#1e293b",
    "fg_dim": "#475569",
    "fg_muted": "#94a3b8",
    "accent": "#3b82f6",
    "accent_hover": "#60a5fa",
    "accent_active": "#2563eb",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "border": "#e2e8f0",
}

COLORS = DARK_COLORS.copy()


def _apply_theme(root: tk.Tk, style: ttk.Style, colors: dict) -> None:
    """Apply theme colors to all ttk styles."""
    global COLORS
    COLORS.update(colors)

    root.configure(bg=colors["bg"])

    style.configure(".", background=colors["bg"], foreground=colors["fg"], borderwidth=0)
    style.configure("TFrame", background=colors["bg"])
    style.configure("TLabel", background=colors["bg"], foreground=colors["fg"], font=("Segoe UI", 12))
    style.configure("TCheckbutton", background=colors["bg"], foreground=colors["fg"], font=("Segoe UI", 12))
    style.map("TCheckbutton", background=[("active", colors["bg"])])

    style.configure(
        "Accent.TButton",
        background=colors["accent"],
        foreground="#ffffff",
        font=("Segoe UI", 12, "bold"),
        padding=(20, 10),
        borderwidth=0,
    )
    style.map(
        "Accent.TButton",
        background=[("active", colors["accent_active"]), ("disabled", colors["fg_muted"])],
        foreground=[("disabled", colors["bg"])],
    )

    style.configure(
        "Secondary.TButton",
        background=colors["bg_secondary"],
        foreground=colors["fg"],
        font=("Segoe UI", 12),
        padding=(20, 10),
        borderwidth=1,
    )
    style.map(
        "Secondary.TButton",
        background=[("active", colors["border"]), ("disabled", colors["bg_secondary"])],
        foreground=[("disabled", colors["fg_muted"])],
    )

    style.configure(
        "Theme.TButton",
        background=colors["bg_secondary"],
        foreground=colors["fg"],
        font=("Segoe UI", 11),
        padding=(10, 6),
        borderwidth=1,
    )
    style.map(
        "Theme.TButton",
        background=[("active", colors["border"])],
    )

    style.configure("Move.TLabel", background=colors["bg"], font=("Consolas", 32, "bold"), foreground=colors["accent"])
    style.configure("San.TLabel", background=colors["bg"], font=("Segoe UI", 16), foreground=colors["fg_dim"])
    style.configure("Status.TLabel", background=colors["bg"], font=("Segoe UI", 13), foreground=colors["fg_muted"])
    style.configure("Warning.TLabel", background=colors["bg"], font=("Segoe UI", 13), foreground=colors["warning"])
    style.configure("Header.TLabel", background=colors["bg"], font=("Segoe UI", 13), foreground=colors["fg"])

    style.configure(
        "TCombobox",
        fieldbackground=colors["bg_secondary"],
        background=colors["bg_secondary"],
        foreground=colors["fg"],
        arrowcolor=colors["fg"],
        borderwidth=1,
        relief="flat",
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", colors["bg_secondary"])],
        selectbackground=[("readonly", colors["accent"])],
        selectforeground=[("readonly", "#ffffff")],
    )

    style.configure("TSeparator", background=colors["border"])

    style.configure(
        "TScale",
        background=colors["bg"],
        troughcolor=colors["bg_secondary"],
        sliderthickness=16,
        borderwidth=0,
    )
    style.map("TScale", background=[("active", colors["bg"])])

    style.configure("SliderLabel.TLabel", background=colors["bg"], font=("Segoe UI", 10), foreground=colors["fg_dim"])
    style.configure("SliderValue.TLabel", background=colors["bg"], font=("Consolas", 10, "bold"), foreground=colors["accent"])
    style.configure("EngineHeader.TLabel", background=colors["bg"], font=("Segoe UI", 11, "bold"), foreground=colors["fg"])

    root.option_add("*TCombobox*Listbox.background", colors["bg_secondary"])
    root.option_add("*TCombobox*Listbox.foreground", colors["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", colors["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")


def _configure_theme(root: tk.Tk, dark: bool = True) -> ttk.Style:
    """Configure ttk styles for the selected theme."""
    style = ttk.Style(root)
    style.theme_use("clam")
    colors = DARK_COLORS if dark else LIGHT_COLORS
    _apply_theme(root, style, colors)
    return style


def run_overlay(
    get_we_play_white: Callable[[], bool],
    set_we_play_white: Callable[[bool], None],
    get_show_recommendation: Callable[[], bool],
    set_show_recommendation: Callable[[bool], None],
    get_auto_play: Callable[[], bool],
    set_auto_play: Callable[[bool], None],
    get_agent_running: Callable[[], bool],
    start_agent: Callable[[], None],
    stop_agent: Callable[[], None],
    poll_interval: float,
    should_stop: Callable[[], bool],
) -> None:
    """
    Run the tkinter overlay and block until window is closed.
    The assist loop runs on the main thread (root.after) so all X11 use (mss, pyautogui) is single-threaded.
    """
    root = tk.Tk()
    root.title("Auto Chess")
    root.configure(bg=COLORS["bg"])
    root.attributes("-topmost", True)
    root.geometry("380x580+20+20")
    root.minsize(340, 540)
    root.resizable(True, True)

    theme_state = {"dark": True}
    style = _configure_theme(root, dark=True)

    from src.agent.assist_loop import initial_assist_step_state, run_assist_loop_step
    from src.agent.decider import get_engine_path, get_engine_limits, configure_engine
    from src.agent.config import set_runtime_engine_setting
    import chess.engine

    main_frame = ttk.Frame(root, padding=20)
    main_frame.pack(fill="both", expand=True)

    move_frame = ttk.Frame(main_frame)
    move_frame.pack(fill="x", pady=(0, 16))

    label_move = ttk.Label(move_frame, text="—", style="Move.TLabel", anchor="center")
    label_move.pack(fill="x")

    label_san = ttk.Label(move_frame, text="", style="San.TLabel", anchor="center")
    label_san.pack(fill="x")

    label_status = ttk.Label(move_frame, text="Ready", style="Status.TLabel", anchor="center")
    label_status.pack(fill="x", pady=(6, 0))

    def on_move(uci: str, san: str) -> None:
        label_move.configure(text=uci)
        label_san.configure(text=f"Play: {san}")

    def on_game_over(message: str) -> None:
        label_status.configure(text=message, style="Warning.TLabel")
        label_move.configure(text="—")
        label_san.configure(text="")

    ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=10)

    settings_frame = ttk.Frame(main_frame)
    settings_frame.pack(fill="x", pady=(0, 10))

    color_frame = ttk.Frame(settings_frame)
    color_frame.pack(fill="x", pady=6)

    ttk.Label(color_frame, text="We play:", style="Header.TLabel").pack(side="left", padx=(0, 10))

    color_var = tk.StringVar(value="White" if get_we_play_white() else "Black")

    def on_color_change(event=None):
        set_we_play_white(color_var.get() == "White")

    color_combo = ttk.Combobox(
        color_frame,
        textvariable=color_var,
        values=["White", "Black"],
        state="readonly",
        width=10,
    )
    color_combo.pack(side="left")
    color_combo.bind("<<ComboboxSelected>>", on_color_change)

    show_var = tk.BooleanVar(value=get_show_recommendation())

    def on_show_toggle():
        set_show_recommendation(show_var.get())

    check_show = ttk.Checkbutton(
        settings_frame,
        text="Show move recommendation",
        variable=show_var,
        command=on_show_toggle,
    )
    check_show.pack(anchor="w", pady=6)

    auto_var = tk.BooleanVar(value=get_auto_play())

    def on_auto_toggle():
        set_auto_play(auto_var.get())

    check_auto = ttk.Checkbutton(
        settings_frame,
        text="Auto-play moves (pyautogui)",
        variable=auto_var,
        command=on_auto_toggle,
    )
    check_auto.pack(anchor="w", pady=6)

    theme_frame = ttk.Frame(settings_frame)
    theme_frame.pack(fill="x", pady=(10, 0))

    ttk.Label(theme_frame, text="Theme:", style="Header.TLabel").pack(side="left", padx=(0, 10))

    def toggle_theme():
        theme_state["dark"] = not theme_state["dark"]
        colors = DARK_COLORS if theme_state["dark"] else LIGHT_COLORS
        _apply_theme(root, style, colors)
        btn_theme.configure(text="Light" if theme_state["dark"] else "Dark")

    btn_theme = ttk.Button(
        theme_frame,
        text="Light",
        style="Theme.TButton",
        command=toggle_theme,
        width=8,
    )
    btn_theme.pack(side="left")

    ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=10)

    engine_frame = ttk.Frame(main_frame)
    engine_frame.pack(fill="x", pady=(0, 10))

    ttk.Label(engine_frame, text="Engine Settings", style="EngineHeader.TLabel").pack(anchor="w", pady=(0, 8))

    initial_limits = get_engine_limits()
    max_threads = os.cpu_count() or 8
    engine_needs_restart = {"value": False}

    def create_slider_row(parent, label: str, from_: float, to: float, initial: float, key: str, fmt: str = "{:.1f}", is_int: bool = False, needs_restart: bool = False):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)

        ttk.Label(row, text=label, style="SliderLabel.TLabel", width=12).pack(side="left")

        var = tk.DoubleVar(value=initial)
        value_label = ttk.Label(row, text=fmt.format(initial), style="SliderValue.TLabel", width=6)
        value_label.pack(side="right")

        def on_change(val):
            v = int(float(val)) if is_int else float(val)
            value_label.configure(text=fmt.format(v))
            set_runtime_engine_setting(key, v)
            if needs_restart:
                engine_needs_restart["value"] = True
                btn_restart_engine.configure(state="normal")

        slider = ttk.Scale(row, from_=from_, to=to, variable=var, orient="horizontal", command=on_change)
        slider.pack(side="left", fill="x", expand=True, padx=(0, 8))

        return var

    time_var = create_slider_row(engine_frame, "Time (s):", 0.1, 30.0, initial_limits["time"], "time_limit_seconds", "{:.1f}")
    depth_var = create_slider_row(engine_frame, "Depth:", 10, 40, initial_limits["depth"], "depth_limit", "{:.0f}", is_int=True)
    hash_var = create_slider_row(engine_frame, "Hash (MB):", 16, 4096, initial_limits["hash_mb"], "hash_mb", "{:.0f}", is_int=True, needs_restart=True)
    threads_var = create_slider_row(engine_frame, "Threads:", 1, max_threads, min(initial_limits["threads"], max_threads), "threads", "{:.0f}", is_int=True, needs_restart=True)

    restart_frame = ttk.Frame(engine_frame)
    restart_frame.pack(fill="x", pady=(6, 0))

    def do_restart_engine():
        if run_state.get("engine") is not None:
            try:
                run_state["engine"].quit()
            except Exception:
                pass
            run_state["engine"] = None
        path = get_engine_path()
        try:
            engine = chess.engine.SimpleEngine.popen_uci(path)
            configure_engine(engine)
            run_state["engine"] = engine
            engine_needs_restart["value"] = False
            btn_restart_engine.configure(state="disabled")
            label_status.configure(text="Engine restarted", style="Status.TLabel")
            logger.info("Engine restarted with new settings")
        except Exception as e:
            logger.error("Failed to restart engine: %s", e)
            label_status.configure(text="Restart failed", style="Warning.TLabel")

    btn_restart_engine = ttk.Button(
        restart_frame,
        text="Apply Hash/Threads",
        style="Theme.TButton",
        command=do_restart_engine,
        state="disabled",
    )
    btn_restart_engine.pack(side="left")

    run_state: dict = {"engine": None, "assist_state": None, "after_id": None}

    def clear_running() -> None:
        btn_start.configure(state="normal")
        btn_stop.configure(state="disabled")
        label_status.configure(text="Stopped", style="Status.TLabel")
        if run_state["after_id"] is not None:
            root.after_cancel(run_state["after_id"])
            run_state["after_id"] = None
        if run_state["engine"] is not None:
            try:
                run_state["engine"].quit()
            except Exception:
                pass
            run_state["engine"] = None

    def restart_engine() -> bool:
        """Restart Stockfish after a crash. Returns True on success."""
        if run_state["engine"] is not None:
            try:
                run_state["engine"].quit()
            except Exception:
                pass
            run_state["engine"] = None
        path = get_engine_path()
        try:
            run_state["engine"] = chess.engine.SimpleEngine.popen_uci(path)
            configure_engine(run_state["engine"])
            engine_needs_restart["value"] = False
            btn_restart_engine.configure(state="disabled")
            logger.info("Stockfish restarted successfully.")
            return True
        except Exception as e:
            logger.error("Could not restart Stockfish: %s", e)
            return False

    def do_step() -> None:
        if should_stop():
            clear_running()
            return
        engine = run_state["engine"]
        state = run_state["assist_state"]
        if engine is None or state is None:
            clear_running()
            return
        try:
            next_state, delay = run_assist_loop_step(
                engine,
                state,
                poll_interval,
                get_we_play_white,
                on_move=on_move,
                on_game_over=on_game_over,
                get_show_recommendation=get_show_recommendation,
                get_auto_play=get_auto_play,
            )
        except Exception as e:
            run_state["after_id"] = root.after(int(poll_interval * 1000), do_step)
            return
        run_state["assist_state"] = next_state
        if next_state.get("engine_dead"):
            logger.warning("Stockfish crashed; restarting...")
            label_status.configure(text="Restarting engine…", style="Warning.TLabel")
            if restart_engine():
                next_state["engine_dead"] = False
                run_state["assist_state"] = next_state
                label_status.configure(text="Running…", style="Status.TLabel")
                run_state["after_id"] = root.after(int(delay * 1000), do_step)
            else:
                label_status.configure(text="Engine restart failed", style="Warning.TLabel")
                clear_running()
            return
        run_state["after_id"] = root.after(int(delay * 1000), do_step)

    def do_start_agent() -> None:
        if get_agent_running():
            return
        path = get_engine_path()
        try:
            engine = chess.engine.SimpleEngine.popen_uci(path)
            configure_engine(engine)
        except FileNotFoundError:
            logger.error("Stockfish not found at %s. Install it or set stockfish_path in config.", path)
            label_status.configure(text="Stockfish not found", style="Warning.TLabel")
            return
        except Exception as e:
            logger.error("Failed to start Stockfish: %s", e)
            label_status.configure(text=f"Engine error: {e}", style="Warning.TLabel")
            return
        btn_start.configure(state="disabled")
        btn_stop.configure(state="normal")
        btn_restart_engine.configure(state="disabled")
        engine_needs_restart["value"] = False
        label_status.configure(text="Running…", style="Status.TLabel")
        start_agent()
        run_state["engine"] = engine
        run_state["assist_state"] = initial_assist_step_state()
        run_state["after_id"] = root.after(0, do_step)

    def do_stop_agent() -> None:
        stop_agent()

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill="x", pady=(16, 0))

    btn_start = ttk.Button(button_frame, text="Start", style="Accent.TButton", command=do_start_agent)
    btn_start.pack(side="left", padx=(0, 12))

    btn_stop = ttk.Button(button_frame, text="Stop", style="Secondary.TButton", command=do_stop_agent, state="disabled")
    btn_stop.pack(side="left")

    def on_closing() -> None:
        stop_agent()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    logger.info("Overlay: control panel open. Start agent when ready.")
    root.mainloop()
