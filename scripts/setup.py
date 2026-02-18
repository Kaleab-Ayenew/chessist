#!/usr/bin/env python3
"""
Setup script for Chess Assist (template vision + Stockfish overlay).
Run from project root: python scripts/setup.py
Creates venv, installs requirements.txt, optionally downloads Stockfish, copies config.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"
STOCKFISH_DIR = PROJECT_ROOT / ".stockfish"
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_EXAMPLE = PROJECT_ROOT / "config.example.yaml"
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
GITHUB_API_LATEST = "https://api.github.com/repos/official-stockfish/Stockfish/releases/latest"

# Stockfish asset name patterns: (platform_key, arch) -> list of preferred asset substrings (first match wins)
# Asset names look like: stockfish-ubuntu-x86-64-avx2.tar, stockfish-macos-m1-apple-silicon.tar, stockfish-windows-x86-64-avx2.zip
STOCKFISH_ASSET_PREFERENCES = {
    ("linux", "x86_64"): ["ubuntu-x86-64-avx2", "ubuntu-x86-64-bmi2", "ubuntu-x86-64-sse41-popcnt", "ubuntu-x86-64"],
    ("linux", "aarch64"): ["ubuntu-aarch64", "linux-aarch64"],
    ("linux", "armv7"): ["ubuntu-arm", "linux-arm"],
    ("darwin", "arm64"): ["macos-m1-apple-silicon", "macos-apple-silicon", "macos-arm"],
    ("darwin", "x86_64"): ["macos-x86-64-avx2", "macos-x86-64-bmi2", "macos-x86-64-sse41", "macos-x86-64"],
    ("windows", "x86_64"): ["windows-x86-64-avx2", "windows-x86-64-bmi2", "windows-x86-64-sse41", "windows-x86-64"],
    ("windows", "AMD64"): ["windows-x86-64-avx2", "windows-x86-64-bmi2", "windows-x86-64-sse41", "windows-x86-64"],
}


def log(msg: str) -> None:
    print(f"[setup] {msg}", flush=True)


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> bool:
    cwd = cwd or PROJECT_ROOT
    env = env or os.environ.copy()
    log(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=cwd, env=env, check=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"Command failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        log(f"Command not found: {cmd[0]}")
        return False


def detect_platform() -> tuple[str, str]:
    system = platform.system().lower()
    if system == "darwin":
        system = "darwin"
    elif "linux" in system or system == "linux":
        system = "linux"
    elif system == "windows":
        system = "windows"
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        machine = "x86_64"
    elif machine in ("aarch64", "arm64"):
        machine = "aarch64" if system != "windows" else "x86_64"  # Windows often reports AMD64
    if system == "windows":
        machine = "x86_64"  # prefer 64-bit
    return system, machine


def get_python_exe() -> Path:
    """Path to Python executable (venv bin if present)."""
    if VENV_DIR.exists():
        if sys.platform == "win32":
            return VENV_DIR / "Scripts" / "python.exe"
        return VENV_DIR / "bin" / "python"
    return Path(sys.executable)


def get_pip_exe() -> Path:
    if VENV_DIR.exists():
        if sys.platform == "win32":
            return VENV_DIR / "Scripts" / "pip.exe"
        return VENV_DIR / "bin" / "pip"
    return Path(sys.executable).parent / "pip" + (".exe" if sys.platform == "win32" else "")


def create_venv() -> bool:
    if VENV_DIR.exists():
        log("Virtual environment already exists at .venv")
        return True
    log("Creating virtual environment at .venv")
    if not run([sys.executable, "-m", "venv", str(VENV_DIR)]):
        return False
    # Ensure pip is available (some systems create venv without pip)
    py = get_python_exe()
    if not (VENV_DIR / "bin" / "pip").exists() and not (VENV_DIR / "Scripts" / "pip.exe").exists():
        run([str(py), "-m", "ensurepip", "--upgrade"], env=os.environ.copy())
    return True


def install_requirements() -> bool:
    py = get_python_exe()
    # Ensure pip is available (e.g. venv created without pip)
    try:
        subprocess.run([str(py), "-m", "pip", "--version"], cwd=PROJECT_ROOT, capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        log("Bootstrapping pip in venv...")
        run([str(py), "-m", "ensurepip", "--upgrade"], env=os.environ.copy())
    cmd = [str(py), "-m", "pip", "install", "-r", str(REQUIREMENTS)]
    return run(cmd)


def fetch_stockfish_asset_url() -> tuple[str | None, str | None]:
    """Returns (download_url, asset_filename) or (None, None)."""
    system, machine = detect_platform()
    key = (system, machine)
    prefs = STOCKFISH_ASSET_PREFERENCES.get(key)
    if not prefs:
        prefs = STOCKFISH_ASSET_PREFERENCES.get((system, "x86_64")) or []
    try:
        req = urllib.request.Request(GITHUB_API_LATEST, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except Exception as e:
        log(f"Failed to fetch Stockfish release info: {e}")
        return None, None
    assets = data.get("assets", [])
    platform_sub = {"linux": "ubuntu", "darwin": "macos", "windows": "windows"}
    sub = platform_sub.get(system, "")
    for pref in prefs:
        for a in assets:
            name = a.get("name", "")
            if sub in name and pref in name:
                url = a.get("browser_download_url")
                if url:
                    return url, name
    # Fallback: any asset for this platform
    for a in assets:
        name = a.get("name", "")
        if sub and sub in name and ("x86_64" in name or "x86-64" in name or "m1" in name or "apple" in name or "aarch64" in name):
            return a.get("browser_download_url"), name
    return None, None


def find_stockfish_binary(extract_dir: Path) -> Path | None:
    """Locate stockfish or stockfish.exe inside extracted tree.
    Official releases use names like stockfish, stockfish.exe, or stockfish-<platform>-x86-64-avx2."""
    for root, _dirs, files in os.walk(extract_dir):
        for f in files:
            if f in ("stockfish", "stockfish.exe"):
                return Path(root) / f
            # GitHub release tarballs use platform-specific names, e.g. stockfish-ubuntu-x86-64-avx2
            if f.startswith("stockfish") and not f.endswith((".md", ".txt", ".cff", ".cpp", ".h", ".py")):
                candidate = Path(root) / f
                if os.access(candidate, os.X_OK) or sys.platform == "win32":
                    return candidate
    return None


def download_and_extract_stockfish() -> bool:
    url, filename = fetch_stockfish_asset_url()
    if not url or not filename:
        log("Could not determine Stockfish download URL for this platform.")
        return False
    STOCKFISH_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = STOCKFISH_DIR / filename
    expected_size = None
    if not archive_path.exists():
        log(f"Downloading Stockfish: {filename}")
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
            with urllib.request.urlopen(req, timeout=60) as r:
                expected_size = r.headers.get("Content-Length")
                expected_size = int(expected_size) if expected_size else None
                with open(archive_path, "wb") as f:
                    f.write(r.read())
        except Exception as e:
            log(f"Download failed: {e}")
            if archive_path.exists():
                archive_path.unlink(missing_ok=True)
            return False
    if expected_size is None and archive_path.exists():
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as r:
                expected_size = r.headers.get("Content-Length")
                expected_size = int(expected_size) if expected_size else None
        except Exception:
            pass
    if expected_size is not None and archive_path.stat().st_size != expected_size:
        log(f"Download incomplete (got {archive_path.stat().st_size}, expected {expected_size}); removing and retrying once.")
        archive_path.unlink(missing_ok=True)
        try:
            urllib.request.urlretrieve(url, archive_path)
        except Exception as e:
            log(f"Retry download failed: {e}")
            return False
    extract_dir = STOCKFISH_DIR / "extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        if filename.endswith(".tar") or filename.endswith(".tar.gz"):
            with tarfile.open(archive_path) as tf:
                # Python 3.12+ use filter='data' to avoid deprecation and 3.14 default change
                if sys.version_info >= (3, 12):
                    tf.extractall(extract_dir, filter="data")
                else:
                    tf.extractall(extract_dir)
        elif filename.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(extract_dir)
        else:
            log(f"Unknown archive format: {filename}")
            return False
    except Exception as e:
        log(f"Extract failed: {e}")
        if archive_path.exists():
            log("Removing partial archive; run setup again to re-download.")
            archive_path.unlink(missing_ok=True)
        return False
    binary = find_stockfish_binary(extract_dir)
    if not binary:
        log("Could not find stockfish binary in archive.")
        return False
    # Prefer a fixed path so .env can point to it
    dest = STOCKFISH_DIR / ("stockfish.exe" if sys.platform == "win32" else "stockfish")
    if binary.resolve() != dest.resolve():
        shutil.copy2(binary, dest)
    if sys.platform != "win32":
        os.chmod(dest, 0o755)
    log(f"Stockfish installed at {dest}")
    return True


def ensure_stockfish() -> bool:
    """Use system Stockfish if available, else download."""
    if shutil.which("stockfish"):
        log("Stockfish found in PATH; skipping download.")
        return True
    if sys.platform == "win32" and shutil.which("stockfish.exe"):
        log("Stockfish found in PATH; skipping download.")
        return True
    return download_and_extract_stockfish()


def write_env_stockfish_path(path: Path) -> None:
    lines = []
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                if line.strip().startswith("STOCKFISH_PATH="):
                    continue
                lines.append(line)
    lines.append(f"STOCKFISH_PATH={path}\n")
    with open(ENV_FILE, "w") as f:
        f.writelines(lines)
    log(f"Wrote STOCKFISH_PATH to {ENV_FILE}")


def ensure_config() -> bool:
    if CONFIG_FILE.exists():
        log("config.yaml already exists")
        return True
    if not CONFIG_EXAMPLE.exists():
        log("config.example.yaml not found; skipping config copy.")
        return True
    shutil.copy2(CONFIG_EXAMPLE, CONFIG_FILE)
    log("Created config.yaml from config.example.yaml")
    return True


def main() -> int:
    log("Chess Assist — setup (template vision + Stockfish)")
    os.chdir(PROJECT_ROOT)
    if not REQUIREMENTS.exists():
        log(f"Requirements not found: {REQUIREMENTS}. Run from project root.")
        return 1
    if not create_venv():
        return 1
    if not install_requirements():
        return 1
    if ensure_stockfish():
        dest = STOCKFISH_DIR / ("stockfish.exe" if sys.platform == "win32" else "stockfish")
        if dest.exists():
            write_env_stockfish_path(dest.resolve())
    else:
        log("Stockfish setup failed. Install manually and set STOCKFISH_PATH in .env")
    ensure_config()
    log("Setup complete. Activate the venv and run: python main.py")
    if sys.platform == "win32":
        log("  .venv\\Scripts\\activate")
    else:
        log("  source .venv/bin/activate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
