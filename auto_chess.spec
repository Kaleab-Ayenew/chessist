# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for auto_chess (cross-platform).
Build with: pyinstaller --clean auto_chess.spec
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all submodules for packages with lazy imports
mss_imports = collect_submodules('mss')
pyautogui_imports = collect_submodules('pyautogui')
pyscreeze_imports = collect_submodules('pyscreeze')

platform_hidden = []
if sys.platform == 'linux':
    platform_hidden += ['Xlib']
elif sys.platform == 'win32':
    # pywin32 modules required by pyautogui (must have pywin32 in requirements)
    platform_hidden += [
        'pywin32',
        'win32api',
        'win32con',
        'pywintypes',
        'win32gui',
        'win32process',
        'win32clipboard',
    ]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('config.example.yaml', '.'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'cv2',
        'pyautogui',
        'chess',
        'chess.engine',
        'chess.pgn',
        'yaml',
        'dotenv',
        'numpy',
        'PIL',
        'PIL.Image',
        'tkinter',
        'tkinter.ttk',
        # mss and all its submodules (platform-specific)
        'mss',
        'mss.base',
        'mss.screenshot',
        'mss.tools',
        'mss.exception',
        'mss.factory',
        'mss.models',
        'mss.linux',
        'mss.darwin',
        'mss.windows',
        # pyautogui and its dependencies
        'pyscreeze',
        'pygetwindow',
        'pymsgbox',
        'pytweening',
        'pyperclip',
        'mouseinfo',
    ] + platform_hidden + mss_imports + pyautogui_imports + pyscreeze_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='auto_chess',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='auto_chess.ico' if sys.platform == 'win32' else None,
)
