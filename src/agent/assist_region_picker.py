"""
GUI to set assist capture region: overlay waits for your signal, then full-screen screenshot, drag rectangle, save to config.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def run_region_picker() -> None:
    """
    Show an overlay assistant; when user clicks "Capture screen", capture primary screen,
    show in a window for drag-rectangle, then save to config.yaml.
    """
    import tkinter as tk

    from .screen_capture import capture_full_screen
    from .config import save_assist_region, USER_CONFIG_PATH

    # Step 1: overlay assistant — wait for user signal before capturing
    overlay = tk.Tk()
    overlay.title("Assist region")
    overlay.attributes("-topmost", True)
    overlay.resizable(False, False)
    overlay.geometry("340x140+50+50")
    tk.Label(
        overlay,
        text="Position the chess board on screen,\nthen click to capture.",
        font=("Sans", 12),
    ).pack(pady=(16, 8), padx=20)
    tk.Button(
        overlay,
        text="Capture screen",
        command=overlay.destroy,
        font=("Sans", 14),
        padx=16,
        pady=8,
    ).pack(pady=(0, 16))
    overlay.protocol("WM_DELETE_WINDOW", overlay.destroy)
    overlay.mainloop()

    # Step 2: capture and show region selection
    _run_region_selection(capture_full_screen(0), save_assist_region, USER_CONFIG_PATH)


def _run_region_selection(img_arr, save_assist_region_fn, config_path) -> None:
    """Show screenshot in window; user drags rectangle, Save writes to config."""
    import tkinter as tk
    from PIL import Image, ImageTk

    actual_h, actual_w = img_arr.shape[:2]
    pil_img = Image.fromarray(img_arr)

    root = tk.Tk()
    root.title("Set assist region — drag around the board, then Save")
    root.attributes("-topmost", True)

    # Scale to fit screen (e.g. 90% of screen height or width)
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    max_display_w = int(screen_w * 0.9)
    max_display_h = int(screen_h * 0.9)
    scale = min(max_display_w / actual_w, max_display_h / actual_h, 1.0)
    display_w = int(actual_w * scale)
    display_h = int(actual_h * scale)

    pil_scaled = pil_img.resize((display_w, display_h), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(pil_scaled)
    root._photo_ref = photo

    canvas = tk.Canvas(root, width=display_w, height=display_h, highlightthickness=0)
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)

    rect_id: Optional[int] = None
    start_xy: Optional[Tuple[int, int]] = None
    current_xy: Optional[Tuple[int, int]] = None

    def to_actual(x_disp: int, y_disp: int) -> Tuple[int, int]:
        x_actual = int(x_disp / scale)
        y_actual = int(y_disp / scale)
        x_actual = max(0, min(actual_w, x_actual))
        y_actual = max(0, min(actual_h, y_actual))
        return x_actual, y_actual

    def on_press(event: tk.Event) -> None:
        nonlocal start_xy, current_xy, rect_id
        start_xy = (event.x, event.y)
        current_xy = start_xy
        if rect_id is not None:
            canvas.delete(rect_id)
        rect_id = canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="lime", width=2
        )

    def on_drag(event: tk.Event) -> None:
        nonlocal current_xy, rect_id
        if start_xy is None or rect_id is None:
            return
        current_xy = (event.x, event.y)
        x0, y0 = start_xy
        x1, y1 = current_xy
        canvas.coords(rect_id, x0, y0, x1, y1)

    def on_release(event: tk.Event) -> None:
        nonlocal current_xy
        if start_xy is not None:
            current_xy = (event.x, event.y)

    canvas.bind("<Button-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)

    def get_rect_actual() -> Optional[Tuple[int, int, int, int]]:
        if start_xy is None or current_xy is None:
            return None
        x0, y0 = to_actual(start_xy[0], start_xy[1])
        x1, y1 = to_actual(current_xy[0], current_xy[1])
        left = min(x0, x1)
        top = min(y0, y1)
        width = abs(x1 - x0)
        height = abs(y1 - y0)
        if width < 10 or height < 10:
            return None
        return left, top, width, height

    def save_and_close() -> None:
        r = get_rect_actual()
        if r is None:
            tk.messagebox.showinfo("No region", "Drag a rectangle around the board first.")
            return
        left, top, width, height = r
        save_assist_region_fn(left, top, width, height)
        logger.info("Saved assist_region to %s", config_path)
        root.destroy()

    def cancel() -> None:
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=8)
    tk.Button(btn_frame, text="Save region", command=save_and_close).pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="Cancel", command=cancel).pack(side=tk.LEFT, padx=4)

    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()
