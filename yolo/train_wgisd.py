"""
Train YOLOv11 on the WGISD (Wine Grape Instance Segmentation Dataset) from Embrapa.

Usage:
    pip install ultralytics gitpython
    python train_wgisd.py

This script:
1. Clones the WGISD dataset from GitHub
2. Prepares the data in YOLO format (already in YOLO format)
3. Creates train/val split
4. Trains YOLOv11n (nano) for grape cluster detection
5. Exports the best model to ONNX format

Output:
    - runs/detect/wgisd/weights/best.pt   (PyTorch model)
    - runs/detect/wgisd/weights/best.onnx  (ONNX for deployment)

Reference:
    Santos, T.T. et al. "Grape detection, segmentation, and tracking using deep
    neural networks and three-dimensional association." Computers and Electronics
    in Agriculture, 2020.
"""

import os
import shutil
import random
from pathlib import Path

def setup_dataset():
    """Clone WGISD and prepare train/val split."""
    base = Path("wgisd_dataset")

    # Clone if not exists
    if not (base / "wgisd").exists():
        print("Cloning WGISD dataset from GitHub...")
        os.system(f"git clone https://github.com/thsant/wgisd.git {base / 'wgisd'}")

    data_dir = base / "wgisd" / "data"

    # Collect all image-annotation pairs
    images = sorted(data_dir.glob("*.jpg"))
    pairs = []
    for img in images:
        txt = img.with_suffix(".txt")
        if txt.exists() and txt.stat().st_size > 0:
            pairs.append((img, txt))

    print(f"Found {len(pairs)} image-annotation pairs")

    # Create YOLO dataset structure
    for split in ["train", "val"]:
        (base / "images" / split).mkdir(parents=True, exist_ok=True)
        (base / "labels" / split).mkdir(parents=True, exist_ok=True)

    # 80/20 split
    random.seed(42)
    random.shuffle(pairs)
    split_idx = int(len(pairs) * 0.8)
    train_pairs = pairs[:split_idx]
    val_pairs = pairs[split_idx:]

    for split_name, split_pairs in [("train", train_pairs), ("val", val_pairs)]:
        for img_path, txt_path in split_pairs:
            shutil.copy2(img_path, base / "images" / split_name / img_path.name)
            shutil.copy2(txt_path, base / "labels" / split_name / txt_path.name)
        print(f"  {split_name}: {len(split_pairs)} images")

    # Create dataset YAML
    yaml_content = f"""# WGISD - Wine Grape Instance Segmentation Dataset
# Embrapa · Santos et al. 2020
# Trained for agragent platform

path: {base.resolve()}
train: images/train
val: images/val

nc: 1
names:
  0: grape_cluster
"""
    yaml_path = base / "wgisd.yaml"
    yaml_path.write_text(yaml_content)
    print(f"Dataset YAML: {yaml_path}")

    return str(yaml_path)


def train(yaml_path):
    """Train YOLOv11 on WGISD dataset."""
    from ultralytics import YOLO

    # Load YOLOv11n (nano - fastest, suitable for web deployment)
    model = YOLO("yolo11n.pt")

    print("\nStarting YOLOv11n training on WGISD...")
    print("=" * 60)

    results = model.train(
        data=yaml_path,
        epochs=100,
        imgsz=640,
        batch=16,
        name="wgisd",
        patience=15,          # Early stopping
        save=True,
        plots=True,
        device="mps",         # Apple Silicon GPU (use "0" for NVIDIA, "cpu" for CPU)
        workers=4,
        lr0=0.01,
        lrf=0.01,
        mosaic=1.0,
        flipud=0.5,
        fliplr=0.5,
        degrees=10,
        translate=0.1,
        scale=0.5,
    )

    print("\nTraining complete!")
    print(f"Best model: runs/detect/wgisd/weights/best.pt")

    return results


def export_onnx():
    """Export trained model to ONNX for web/API deployment."""
    from ultralytics import YOLO

    best_pt = Path("runs/detect/wgisd/weights/best.pt")
    if not best_pt.exists():
        print("No trained model found. Run training first.")
        return

    model = YOLO(str(best_pt))

    print("\nExporting to ONNX...")
    model.export(format="onnx", imgsz=640, simplify=True)

    onnx_path = best_pt.with_suffix(".onnx")
    print(f"ONNX model: {onnx_path}")
    print(f"Model size: {onnx_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Copy to agro-agent for API deployment
    deploy_dir = Path.home() / "agro-agent" / "models"
    deploy_dir.mkdir(exist_ok=True)
    shutil.copy2(onnx_path, deploy_dir / "wgisd_yolo11n.onnx")
    shutil.copy2(best_pt, deploy_dir / "wgisd_yolo11n.pt")
    print(f"Models copied to: {deploy_dir}")


if __name__ == "__main__":
    yaml_path = setup_dataset()
    train(yaml_path)
    export_onnx()

    print("\n" + "=" * 60)
    print("DONE! Next steps:")
    print("1. Copy model to agro-agent/models/wgisd_yolo11n.pt")
    print("2. Start the API: cd ~/agro-agent && uvicorn app.main:app --reload")
    print("3. Upload vineyard images in agragent app")
    print("=" * 60)
