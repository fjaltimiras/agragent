"""
Train YOLOv11n-seg on solar panel aerial images.

Run this OFFLINE on a machine with GPU — never on Railway.
Output: backend/models/solar_panel_yolo11n-seg.pt

Usage:
  # Modo 1: descargar dataset de Roboflow con segmentación
  python train_solar_seg.py --mode roboflow --key <ROBOFLOW_API_KEY> --epochs 100

  # Modo 2: convertir labels bbox existentes a polígono de 4 puntos (punto de partida rápido)
  python train_solar_seg.py --mode bbox-convert --labels ./labels/ --images ./images/ --epochs 100

  # Solo entrenar si ya tienes el dataset listo en /tmp/solar_seg_dataset/
  python train_solar_seg.py --mode train-only --data /tmp/solar_seg_dataset/solar_seg.yaml --epochs 100
"""

import argparse
import shutil
import os
from pathlib import Path

# ─── Dataset YAML template ────────────────────────────────────────────────────
DATASET_YAML = """\
path: {data_dir}
train: images/train
val: images/val
nc: 1
names:
  0: solar_panel
"""

OUTPUT_MODEL = Path(__file__).resolve().parent.parent / "models" / "solar_panel_yolo11n-seg.pt"


# ─── Roboflow download ────────────────────────────────────────────────────────
def download_roboflow(api_key: str, data_dir: Path):
    """
    Download solar panel segmentation dataset from Roboflow Universe.
    Requires: pip install roboflow
    Dataset: search for "Solar Panel Segmentation" or "aerial solar panels" on
             https://universe.roboflow.com — pick one with YOLOv8-seg format.
    """
    try:
        from roboflow import Roboflow
    except ImportError:
        raise RuntimeError("Run: pip install roboflow")

    print("Connecting to Roboflow...")
    rf = Roboflow(api_key=api_key)

    # Adjust workspace/project/version to match the dataset you choose on Roboflow Universe
    # Example: rf.workspace("solar-panels").project("solar-panel-detection").version(3)
    project = rf.workspace("YOUR_WORKSPACE").project("YOUR_PROJECT").version(1)
    dataset = project.download("yolov8-seg", location=str(data_dir))

    yaml_path = data_dir / "data.yaml"
    if not yaml_path.exists():
        # Write our own YAML pointing to the downloaded structure
        (data_dir / "solar_seg.yaml").write_text(DATASET_YAML.format(data_dir=str(data_dir)))
        yaml_path = data_dir / "solar_seg.yaml"

    return yaml_path


# ─── BBox → Polygon label conversion ─────────────────────────────────────────
def convert_bbox_to_seg(labels_dir: Path, images_dir: Path, out_dir: Path):
    """
    Convert YOLO bbox labels (cx cy w h) to 4-point segmentation labels (x1y1 x2y1 x2y2 x1y2).
    Produces approximate masks — good enough as a fine-tuning starting point.
    """
    (out_dir / "images" / "train").mkdir(parents=True, exist_ok=True)
    (out_dir / "images" / "val").mkdir(parents=True, exist_ok=True)
    (out_dir / "labels" / "train").mkdir(parents=True, exist_ok=True)
    (out_dir / "labels" / "val").mkdir(parents=True, exist_ok=True)

    label_files = sorted(Path(labels_dir).glob("*.txt"))
    split_idx   = int(len(label_files) * 0.8)

    for i, lf in enumerate(label_files):
        split   = "train" if i < split_idx else "val"
        img_src = Path(images_dir) / lf.stem
        for ext in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]:
            if img_src.with_suffix(ext).exists():
                shutil.copy(img_src.with_suffix(ext), out_dir / "images" / split / img_src.with_suffix(ext).name)
                break

        lines = lf.read_text().strip().splitlines()
        seg_lines = []
        for line in lines:
            parts = line.split()
            if len(parts) != 5:
                # Already in seg format (> 5 values) — keep as-is
                seg_lines.append(line)
                continue
            cls, cx, cy, w, h = parts
            cx, cy, w, h = float(cx), float(cy), float(w), float(h)
            x1, y1 = cx - w/2, cy - h/2
            x2, y2 = cx + w/2, cy + h/2
            # 4-point polygon: top-left → top-right → bottom-right → bottom-left
            seg_lines.append(f"{cls} {x1:.6f} {y1:.6f} {x2:.6f} {y1:.6f} {x2:.6f} {y2:.6f} {x1:.6f} {y2:.6f}")

        (out_dir / "labels" / split / lf.name).write_text("\n".join(seg_lines))

    print(f"Converted {len(label_files)} labels → {out_dir} ({split_idx} train / {len(label_files)-split_idx} val)")

    yaml_path = out_dir / "solar_seg.yaml"
    yaml_path.write_text(DATASET_YAML.format(data_dir=str(out_dir)))
    return yaml_path


# ─── Training ─────────────────────────────────────────────────────────────────
def train(yaml_path: Path, epochs: int, device: str = "0"):
    from ultralytics import YOLO

    print(f"\nTraining yolo11n-seg on {yaml_path} for {epochs} epochs (device={device})")
    model = YOLO("yolo11n-seg.pt")   # start from COCO seg pretrained
    results = model.train(
        data=str(yaml_path),
        epochs=epochs,
        imgsz=640,
        batch=8,             # lower to 4 if OOM on small GPU
        name="solar_seg",
        patience=20,
        save=True,
        device=device,
        workers=4,
        lr0=0.01,
        augment=True,
        mosaic=1.0,
        degrees=15.0,        # panels appear at various angles in aerial views
        flipud=0.5,
        fliplr=0.5,
        hsv_h=0.01,          # subtle hue shift for lighting conditions
        hsv_s=0.4,
        hsv_v=0.3,
    )

    best_pt = Path(results.save_dir) / "weights" / "best.pt"
    if best_pt.exists():
        OUTPUT_MODEL.parent.mkdir(exist_ok=True)
        shutil.copy(best_pt, OUTPUT_MODEL)
        print(f"\nModel saved → {OUTPUT_MODEL}")
        print("Deploy to Railway: copy this file to backend/models/ and restart the service.")
    else:
        print(f"WARNING: best.pt not found at {best_pt}")

    return results


# ─── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Train YOLO11n-seg for solar panel detection")
    parser.add_argument("--mode", choices=["roboflow", "bbox-convert", "train-only"], required=True)
    parser.add_argument("--key",     help="Roboflow API key (mode=roboflow)")
    parser.add_argument("--labels",  help="Path to existing YOLO bbox labels dir (mode=bbox-convert)")
    parser.add_argument("--images",  help="Path to images dir (mode=bbox-convert)")
    parser.add_argument("--data",    help="Path to YAML (mode=train-only)")
    parser.add_argument("--epochs",  type=int, default=100)
    parser.add_argument("--device",  default="0", help="GPU device id or 'cpu'")
    parser.add_argument("--out",     default="/tmp/solar_seg_dataset", help="Dataset output dir")
    args = parser.parse_args()

    data_dir = Path(args.out)

    if args.mode == "roboflow":
        if not args.key:
            parser.error("--key required for mode=roboflow")
        yaml_path = download_roboflow(args.key, data_dir)

    elif args.mode == "bbox-convert":
        if not args.labels or not args.images:
            parser.error("--labels and --images required for mode=bbox-convert")
        yaml_path = convert_bbox_to_seg(Path(args.labels), Path(args.images), data_dir)

    elif args.mode == "train-only":
        if not args.data:
            parser.error("--data required for mode=train-only")
        yaml_path = Path(args.data)

    train(yaml_path, epochs=args.epochs, device=args.device)


if __name__ == "__main__":
    main()
