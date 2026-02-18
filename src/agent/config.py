"""Load config from config.yaml and env."""
from pathlib import Path
import os
import tempfile
import yaml
from dotenv import load_dotenv

load_dotenv()

# Prefer config in cwd (e.g. when user runs from project dir); else package root
_CWD = Path.cwd()
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent
if (_CWD / "config.yaml").exists():
    CONFIG_DIR = _CWD
    CONFIG_PATH = _CWD / "config.yaml"
elif (_CWD / "config.example.yaml").exists() and not (_CWD / "config.yaml").exists():
    CONFIG_DIR = _CWD
    CONFIG_PATH = _CWD / "config.example.yaml"
else:
    CONFIG_DIR = _PACKAGE_ROOT
    CONFIG_PATH = _PACKAGE_ROOT / "config.yaml"
    if not CONFIG_PATH.exists():
        CONFIG_PATH = _PACKAGE_ROOT / "config.example.yaml"

_default = {
    "stockfish_path": os.environ.get("STOCKFISH_PATH", "stockfish"),
    "engine": {"time_limit_seconds": 0.15, "depth_limit": 18},
    "assist_poll_seconds": 2.0,
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


def get_debug_dir() -> Path:
    """Cross-platform directory for debug images (assist screenshots, marked board, etc.)."""
    d = Path(tempfile.gettempdir()) / "auto_chess"
    d.mkdir(parents=True, exist_ok=True)
    return d
