"""Load config from config.yaml and env."""
from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = CONFIG_DIR / "config.yaml"
if not CONFIG_PATH.exists():
    CONFIG_PATH = CONFIG_DIR / "config.example.yaml"

_default = {
    "stockfish_path": os.environ.get("STOCKFISH_PATH", "stockfish"),
    "engine": {"time_limit_seconds": 0.15, "depth_limit": 18},
    "humanization": {
        "reaction_time_mean_ms": 800,
        "reaction_time_std_ms": 150,
        "move_time_mean_ms": 250,
        "move_time_std_ms": 50,
        "click_jitter_std_fraction": 0.15,
    },
    "prefer_vision": True,  # True = vision first (primary), DOM fallback
    "chess_com_base": "https://www.chess.com",
    # Assist mode (--assist): screen capture, no browser
    "assist_poll_seconds": 2.0,
    # "assist_region": {"left": 0, "top": 0, "width": 400, "height": 400}  # optional; omit to use full screen
}


def load_config():
    cfg = _default.copy()
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            user = yaml.safe_load(f) or {}
        for k, v in user.items():
            if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
                cfg[k] = {**cfg[k], **v}
            else:
                cfg[k] = v
    return cfg


USER_CONFIG_PATH = CONFIG_DIR / "config.yaml"


def save_assist_region(left: int, top: int, width: int, height: int) -> None:
    """Write assist_region to config.yaml (merge with existing config)."""
    if USER_CONFIG_PATH.exists():
        with open(USER_CONFIG_PATH) as f:
            data = yaml.safe_load(f) or {}
    else:
        if (CONFIG_DIR / "config.example.yaml").exists():
            with open(CONFIG_DIR / "config.example.yaml") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = _default.copy()
    data["assist_region"] = {
        "left": int(left),
        "top": int(top),
        "width": int(width),
        "height": int(height),
    }
    with open(USER_CONFIG_PATH, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
