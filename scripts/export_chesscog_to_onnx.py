#!/usr/bin/env python3
"""
Export chesscog occupancy and piece classifiers to ONNX.
Run on a machine with PyTorch and chesscog installed (e.g. SSH to ovh):
  pip install torch torchvision "chesscog @ git+https://github.com/georg-wolflein/chesscog.git" recap ...
  python -m chesscog.occupancy_classifier.download_model
  python -m chesscog.piece_classifier.download_model
  python scripts/export_chesscog_to_onnx.py

Output: onnx_models/occupancy.onnx, onnx_models/piece.onnx, onnx_models/metadata.json
Copy onnx_models/ into the project and use with vision_onnx (no PyTorch needed locally).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "onnx_models"


def main() -> int:
    try:
        import torch
        # PyTorch 2.6+ defaults to weights_only=True; chesscog .pt files use custom classes
        _orig = torch.load
        def _load(*a, **kw):
            kw.setdefault("weights_only", False)
            return _orig(*a, **kw)
        torch.load = _load
        from chesscog.occupancy_classifier.download_model import ensure_model as ensure_occupancy
        from chesscog.piece_classifier.download_model import ensure_model as ensure_piece
        from chesscog.recognition.recognition import ChessRecognizer
        from recap import URI
    except ImportError as e:
        print("This script requires PyTorch and chesscog. Install with:", file=sys.stderr)
        print("  pip install torch torchvision 'chesscog @ git+https://github.com/georg-wolflein/chesscog.git' recap", file=sys.stderr)
        print("Then run the chesscog model download scripts (see module docstring).", file=sys.stderr)
        print(f"Error: {e!r}", file=sys.stderr)
        raise SystemExit(1) from e

    ensure_occupancy()
    ensure_piece()

    # Use site-packages/models so we find the downloaded classifiers (recap URI may resolve to cwd otherwise)
    import chesscog as _chesscog
    classifiers_folder = Path(_chesscog.__file__).resolve().parent.parent / "models"
    if not (classifiers_folder / "occupancy_classifier").exists():
        classifiers_folder = Path(URI("models://"))
    recognizer = ChessRecognizer(classifiers_folder)
    # Export on CPU to avoid device propagation issues with torch.export (PyTorch 2.6+)
    recognizer._occupancy_model = recognizer._occupancy_model.cpu()
    recognizer._pieces_model = recognizer._pieces_model.cpu()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Occupancy classifier: input (64, 3, 100, 100) from chesscog config ---
    occ_cfg = recognizer._occupancy_cfg
    occ_transforms = recognizer._occupancy_transforms
    # Typical config: RESIZE [100, 100], CENTER_CROP [100, 100]
    try:
        resize = list(occ_cfg.DATASET.TRANSFORMS.RESIZE) if hasattr(occ_cfg.DATASET.TRANSFORMS, "RESIZE") else [100, 100]
    except Exception:
        resize = [100, 100]
    occ_h, occ_w = resize[0], resize[1]
    batch_occ = 64
    dummy_occ = torch.randn(batch_occ, 3, occ_h, occ_w, device="cpu")

    occ_onnx = OUT_DIR / "occupancy.onnx"
    torch.onnx.export(
        recognizer._occupancy_model,
        dummy_occ,
        str(occ_onnx),
        input_names=["squares"],
        output_names=["logits"],
        dynamic_axes=None,
        opset_version=14,
    )
    print(f"Exported {occ_onnx}")

    # --- Piece classifier: input (N, 3, H, W); get H,W from config or dummy run ---
    piece_cfg = recognizer._pieces_cfg
    piece_transforms = recognizer._pieces_transforms
    try:
        piece_resize = list(piece_cfg.DATASET.TRANSFORMS.RESIZE) if hasattr(piece_cfg.DATASET.TRANSFORMS, "RESIZE") else [224, 224]
    except Exception:
        piece_resize = [224, 224]
    piece_h, piece_w = piece_resize[0], piece_resize[1]
    dummy_piece = torch.randn(1, 3, piece_h, piece_w, device="cpu")

    piece_onnx = OUT_DIR / "piece.onnx"
    torch.onnx.export(
        recognizer._pieces_model,
        dummy_piece,
        str(piece_onnx),
        input_names=["pieces"],
        output_names=["logits"],
        dynamic_axes={"pieces": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=14,
    )
    print(f"Exported {piece_onnx}")

    # Class names for occupancy (empty, occupied) and pieces (e.g. white pawn, black king)
    try:
        occ_classes = list(occ_cfg.DATASET.CLASSES)
    except Exception:
        occ_classes = ["empty", "occupied"]
    try:
        piece_classes = list(piece_cfg.DATASET.CLASSES)
    except Exception:
        piece_classes = []

    # Normalization: chesscog often uses ImageNet-style; we store for the ONNX runner
    try:
        mean = list(piece_cfg.DATASET.TRANSFORMS.NORMALISE.MEAN) if hasattr(piece_cfg.DATASET.TRANSFORMS, "NORMALISE") else [0.485, 0.456, 0.406]
        std = list(piece_cfg.DATASET.TRANSFORMS.NORMALISE.STD) if hasattr(piece_cfg.DATASET.TRANSFORMS, "NORMALISE") else [0.229, 0.224, 0.225]
    except Exception:
        mean = [0.485, 0.456, 0.406]
        std = [0.229, 0.224, 0.225]

    metadata = {
        "occupancy": {
            "input_shape": [batch_occ, 3, occ_h, occ_w],
            "height": occ_h,
            "width": occ_w,
            "classes": occ_classes,
            "occupied_class_index": occ_classes.index("occupied") if "occupied" in occ_classes else 1,
        },
        "piece": {
            "input_shape": [1, 3, piece_h, piece_w],
            "height": piece_h,
            "width": piece_w,
            "classes": piece_classes,
            "mean": mean,
            "std": std,
        },
    }
    meta_path = OUT_DIR / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Wrote {meta_path}")

    print("Done. Copy the onnx_models/ folder into your project for local ONNX-only vision.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
