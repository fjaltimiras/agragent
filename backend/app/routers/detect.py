"""
Grape cluster detection endpoint using YOLO26 fine-tuned on WGISD.

POST /api/detect
  - Accepts image upload (jpg/png)
  - Runs YOLO26 inference
  - Returns bounding boxes, confidence scores, and cluster count

Requires: ultralytics, Pillow
Model: models/wgisd_yolo26m.pt (trained with yolo/train_yolo26_wgisd.py).
Test-set performance of that checkpoint is recorded in yolo/yolo26_metrics.json
(mAP50 0.880, mAP50-95 0.581, P 0.866, R 0.805) and is what the manuscript reports.

The endpoint reports the checkpoint it actually loaded, so the UI never claims YOLO26
while serving something else.
"""

import logging
from pathlib import Path
from io import BytesIO
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Model resolution, most specific first: the WGISD-fine-tuned YOLO26m checkpoint is what
# the manuscript evaluates. The COCO-pretrained fallbacks only keep the endpoint alive when
# no fine-tuned weights are deployed; they do NOT reproduce the reported metrics.
MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
WGISD_MODEL = MODEL_DIR / "wgisd_yolo26m.pt"
FALLBACK_MODEL = "yolo26n.pt"  # Pre-trained on COCO (auto-downloads)

_model = None
_model_name = None      # what actually got loaded, surfaced in every response
_model_is_wgisd = False  # True only for the fine-tuned grape-cluster checkpoint


def get_model():
    """Load YOLO model (lazy singleton)."""
    global _model, _model_name, _model_is_wgisd
    if _model is not None:
        return _model

    try:
        from ultralytics import YOLO
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="ultralytics not installed. Run: pip install ultralytics"
        )

    if WGISD_MODEL.exists():
        logger.info(f"Loading WGISD fine-tuned model: {WGISD_MODEL}")
        _model = YOLO(str(WGISD_MODEL))
        _model_name = "YOLO26m-WGISD"
        _model_is_wgisd = True
    else:
        logger.warning(
            f"WGISD checkpoint not found at {WGISD_MODEL}; falling back to COCO-pretrained "
            f"{FALLBACK_MODEL}. Detections will NOT match the reported WGISD metrics."
        )
        logger.info("To train on WGISD: python yolo/train_yolo26_wgisd.py")
        MODEL_DIR.mkdir(exist_ok=True)
        _model = YOLO(FALLBACK_MODEL)
        _model_name = "YOLO26n-COCO (fallback)"
        _model_is_wgisd = False

    return _model


@router.post("/")
async def detect_grapes(
    image: UploadFile = File(..., description="Vineyard image (jpg/png)"),
    conf: float = 0.25,
    iou: float = 0.45,
):
    """
    Detect grape clusters in an uploaded image.

    Returns:
        - boxes: list of {x1, y1, x2, y2, confidence, class_name}
        - count: number of clusters detected
        - berries_est: estimated berry count
        - image_size: {width, height}
        - model: model name used
    """
    # Validate file type
    if image.content_type not in ("image/jpeg", "image/png", "image/tiff"):
        raise HTTPException(400, f"Unsupported format: {image.content_type}. Use jpg/png/tiff.")

    # Read image bytes
    contents = await image.read()
    if len(contents) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(413, "Image too large. Max 50MB.")

    try:
        from PIL import Image
        img = Image.open(BytesIO(contents))
        img_w, img_h = img.size
    except Exception as e:
        raise HTTPException(400, f"Could not read image: {e}")

    # Run inference
    model = get_model()

    try:
        results = model.predict(
            source=img,
            conf=conf,
            iou=iou,
            imgsz=640,
            verbose=False,
        )
    except Exception as e:
        logger.error(f"Inference error: {e}")
        raise HTTPException(500, f"Detection failed: {e}")

    # Parse results
    boxes = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = model.names.get(cls_id, f"class_{cls_id}")

            boxes.append({
                "x1": round(x1, 1),
                "y1": round(y1, 1),
                "x2": round(x2, 1),
                "y2": round(y2, 1),
                "confidence": round(confidence, 3),
                "class_name": cls_name,
                # Normalized YOLO format for canvas drawing
                "cx": round(((x1 + x2) / 2) / img_w, 5),
                "cy": round(((y1 + y2) / 2) / img_h, 5),
                "w": round((x2 - x1) / img_w, 5),
                "h": round((y2 - y1) / img_h, 5),
            })

    # Estimate berries (avg ~42 berries per cluster for wine grapes)
    cluster_count = len(boxes)
    berries_est = round(cluster_count * 42) if cluster_count > 0 else 0

    logger.info(f"Detection: {cluster_count} clusters in {image.filename} ({img_w}x{img_h})")

    return JSONResponse({
        "boxes": boxes,
        "count": cluster_count,
        "berries_est": berries_est,
        "image_size": {"width": img_w, "height": img_h},
        "model": _model_name or "unknown",
        "fine_tuned_on_wgisd": _model_is_wgisd,
        "confidence_threshold": conf,
    })


@router.post("/train")
async def train_wgisd():
    """
    Train YOLO26 on the WGISD dataset (runs on server).
    Downloads dataset, trains for 30 epochs, saves best model.

    Note: this in-server run is a convenience path on CPU with a smaller backbone. The
    checkpoint the manuscript evaluates was produced offline by yolo/train_yolo26_wgisd.py
    (YOLO26m, 100 epochs, official WGISD split).
    """
    import os, shutil, random, subprocess
    from pathlib import Path

    global _model, _model_name, _model_is_wgisd

    try:
        from ultralytics import YOLO
    except ImportError:
        raise HTTPException(503, "ultralytics not installed")

    base = Path("/tmp/wgisd_dataset")

    # Clone WGISD if needed
    if not (base / "wgisd").exists():
        logger.info("Cloning WGISD dataset...")
        result = subprocess.run(
            ["git", "clone", "--depth=1", "https://github.com/thsant/wgisd.git", str(base / "wgisd")],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise HTTPException(500, f"Git clone failed: {result.stderr}")

    # Collect pairs
    data_dir = base / "wgisd" / "data"
    images = sorted(data_dir.glob("*.jpg"))
    pairs = [(img, img.with_suffix(".txt")) for img in images
             if img.with_suffix(".txt").exists() and img.with_suffix(".txt").stat().st_size > 0]

    if len(pairs) == 0:
        raise HTTPException(500, "No image-annotation pairs found in WGISD")

    # Create train/val split
    for split in ["train", "val"]:
        (base / "images" / split).mkdir(parents=True, exist_ok=True)
        (base / "labels" / split).mkdir(parents=True, exist_ok=True)

    random.seed(42)
    random.shuffle(pairs)
    split_idx = int(len(pairs) * 0.8)

    for split_name, split_pairs in [("train", pairs[:split_idx]), ("val", pairs[split_idx:])]:
        for img_path, txt_path in split_pairs:
            shutil.copy2(img_path, base / "images" / split_name / img_path.name)
            shutil.copy2(txt_path, base / "labels" / split_name / txt_path.name)

    # Write dataset YAML
    yaml_path = base / "wgisd.yaml"
    yaml_path.write_text(f"path: {base}\ntrain: images/train\nval: images/val\nnc: 1\nnames:\n  0: grape_cluster\n")

    # Train
    logger.info(f"Starting training: {len(pairs)} images, 30 epochs")
    model = YOLO("yolo26n.pt")
    results = model.train(
        data=str(yaml_path),
        epochs=30,
        imgsz=640,
        batch=4,
        name="wgisd_server",
        patience=10,
        save=True,
        device="cpu",
        workers=0,
    )

    # Copy best model
    best_pt = Path("runs/detect/wgisd_server/weights/best.pt")
    if best_pt.exists():
        MODEL_DIR.mkdir(exist_ok=True)
        shutil.copy2(best_pt, WGISD_MODEL)
        _model = None  # Force reload on next request
        _model_name, _model_is_wgisd = None, False
        logger.info(f"Training complete! Model saved to {WGISD_MODEL}")
        return JSONResponse({
            "status": "ok",
            "message": f"Training complete. {len(pairs)} images, model saved.",
            "model_path": str(WGISD_MODEL),
            "metrics": {
                "mAP50": round(results.results_dict.get("metrics/mAP50(B)", 0), 4),
                "mAP50-95": round(results.results_dict.get("metrics/mAP50-95(B)", 0), 4),
            }
        })
    else:
        raise HTTPException(500, "Training completed but no best.pt found")
