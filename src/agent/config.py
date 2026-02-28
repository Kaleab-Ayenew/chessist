"""Load config from config.yaml and env."""
from pathlib import Path
import logging
import os
import sys
import tempfile
import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()


def get_bundle_dir() -> Path:
    """Get the bundle directory for PyInstaller frozen apps, or package root otherwise."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def get_templates_dir() -> Path:
    """Get the templates directory, handling both frozen and development environments."""
    bundle_dir = get_bundle_dir()
    templates_dir = bundle_dir / "templates"
    if templates_dir.is_dir():
        return templates_dir
    cwd_templates = Path.cwd() / "templates"
    if cwd_templates.is_dir():
        return cwd_templates
    return templates_dir


# Prefer config in cwd (e.g. when user runs from project dir); else package root
_CWD = Path.cwd()
_PACKAGE_ROOT = get_bundle_dir()
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
    "engine": {
        "time_limit_seconds": 0.15,
        "depth_limit": 18,
        "hash_mb": 512,
        "threads": 4,
    },
    "assist_poll_seconds": 2.0,
    "humanization": {
        "reaction_time_mean_ms": 800,
        "reaction_time_std_ms": 150,
        "move_time_mean_ms": 250,
        "move_time_std_ms": 50,
        "click_jitter_std_fraction": 0.15,
    },
    "prefer_dom": True,
    "chess_com_base": "https://www.chess.com",
    "assist_region": {
        "left": 283,
        "top": 275,
        "width": 720,
        "height": 718,
    },
    "template_fen": {
        "empty_threshold": 0.9,
        "piece_threshold": 0.1,
        "normalize": True,
        "variance_empty_threshold": 100.0,
        "use_edges": True,
        "edge_weight": 0.8,
        "edge_method": "gradient",
    },
}

_runtime_engine_settings: dict = {}


def get_runtime_engine_settings() -> dict:
    """Get runtime engine settings (set by UI sliders)."""
    return _runtime_engine_settings.copy()


def set_runtime_engine_setting(key: str, value) -> None:
    """Set a runtime engine setting (called by UI sliders)."""
    _runtime_engine_settings[key] = value


def clear_runtime_engine_settings() -> None:
    """Clear all runtime engine settings."""
    _runtime_engine_settings.clear()


def _ensure_default_config_file() -> None:
    """If config.yaml does not exist, write default config so the app has a persistent config from first run."""
    if USER_CONFIG_PATH.exists():
        return
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(USER_CONFIG_PATH, "w") as f:
            yaml.dump(_default.copy(), f, default_flow_style=False, allow_unicode=True)
        logger.info("Created config.yaml with defaults at %s", USER_CONFIG_PATH)
    except OSError as e:
        logger.warning("Could not create config.yaml at %s: %s", USER_CONFIG_PATH, e)


def load_config():
    global CONFIG_PATH
    _ensure_default_config_file()
    if USER_CONFIG_PATH.exists():
        CONFIG_PATH = USER_CONFIG_PATH
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


def save_stockfish_path(path: str) -> None:
    """Persist stockfish_path to the user config file (config.yaml)."""
    user = {}
    if USER_CONFIG_PATH.exists():
        with open(USER_CONFIG_PATH) as f:
            user = yaml.safe_load(f) or {}
    user["stockfish_path"] = path
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(USER_CONFIG_PATH, "w") as f:
        yaml.dump(user, f, default_flow_style=False, allow_unicode=True)


def get_debug_dir() -> Path:
    """Cross-platform directory for debug images (assist screenshots, marked board, etc.)."""
    d = Path(tempfile.gettempdir()) / "auto_chess"
    d.mkdir(parents=True, exist_ok=True)
    return d
