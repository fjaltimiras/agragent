#!/usr/bin/env python3
"""
Fine-tune YOLO26m on WGISD (grape-cluster detection) and evaluate on the
official WGISD test split. Produces real mAP/precision/recall for the manuscript.

Split: official WGISD train.txt (242) / test.txt (58). A deterministic 20% of the
official train images is held out as validation; the official 58-image test set is
the untouched test partition on which final metrics are reported.

Usage (from the yolo/ dir, inside the venv):
  .venv_yolo26/bin/python train_yolo26_wgisd.py --epochs 100
  .venv_yolo26/bin/python train_yolo26_wgisd.py --epochs 2 --smoke   # quick pipeline test
"""
import argparse, json, os, random, shutil, warnings
from pathlib import Path
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
WGISD = ROOT / "wgisd_dataset" / "wgisd"
DATA = WGISD / "data"
OUT = ROOT / "wgisd26"          # prepared dataset root
YAML = ROOT / "wgisd26.yaml"


def read_ids(txt):
    return [l.strip() for l in (WGISD / txt).read_text().splitlines() if l.strip()]


def prepare():
    train_ids = read_ids("train.txt")
    test_ids = read_ids("test.txt")
    # deterministic val carve-out from official train (~20%)
    rng = random.Random(42)
    tr = train_ids[:]
    rng.shuffle(tr)
    n_val = round(len(tr) * 0.20)
    val_ids = sorted(tr[:n_val])
    trn_ids = sorted(tr[n_val:])

    for split, ids in [("train", trn_ids), ("val", val_ids), ("test", test_ids)]:
        (OUT / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT / "labels" / split).mkdir(parents=True, exist_ok=True)
        kept = 0
        for i in ids:
            jpg, txt = DATA / f"{i}.jpg", DATA / f"{i}.txt"
            if jpg.exists() and txt.exists() and txt.stat().st_size > 0:
                shutil.copy2(jpg, OUT / "images" / split / jpg.name)
                shutil.copy2(txt, OUT / "labels" / split / txt.name)
                kept += 1
        print(f"  {split}: {kept} images")

    YAML.write_text(
        f"path: {OUT}\ntrain: images/train\nval: images/val\ntest: images/test\n"
        f"nc: 1\nnames:\n  0: grape_cluster\n"
    )
    return len(trn_ids), len(val_ids), len(test_ids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--model", default="yolo26m.pt")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    print("Preparing WGISD (official split)...")
    ntr, nval, nte = prepare()

    from ultralytics import YOLO
    model = YOLO(args.model)
    name = f"wgisd_yolo26m_e{args.epochs}" + ("_smoke" if args.smoke else "")
    print(f"Training {args.model} — {args.epochs} epochs, imgsz {args.imgsz}, device {args.device}")
    model.train(
        data=str(YAML), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        device=args.device, seed=0, deterministic=True, project=str(ROOT / "runs26"),
        name=name, exist_ok=True, verbose=True, patience=max(20, args.epochs // 3),
        plots=True,
    )

    # Evaluate on the untouched official test split
    print("Evaluating on official WGISD test split (58 images)...")
    metrics = model.val(data=str(YAML), split="test", imgsz=args.imgsz,
                        device=args.device, project=str(ROOT / "runs26"),
                        name=name + "_test", exist_ok=True, verbose=False)
    box = metrics.box
    speed = metrics.speed  # dict: preprocess/inference/postprocess ms
    out = {
        "model": args.model, "epochs": args.epochs, "imgsz": args.imgsz,
        "n_train": ntr, "n_val": nval, "n_test": nte,
        "map50": round(float(box.map50), 4),
        "map50_95": round(float(box.map), 4),
        "precision": round(float(box.mp), 4),
        "recall": round(float(box.mr), 4),
        "f1": round(float(2 * box.mp * box.mr / (box.mp + box.mr)) if (box.mp + box.mr) else 0.0, 4),
        "inference_ms_per_image": round(float(speed.get("inference", 0.0)), 2),
        "speed_ms": {k: round(float(v), 2) for k, v in speed.items()},
        "device": args.device,
    }
    (ROOT / "yolo26_metrics.json").write_text(json.dumps(out, indent=2))
    print("\n===== YOLO26m WGISD TEST METRICS =====")
    for k, v in out.items():
        print(f"  {k}: {v}")
    print(f"\nWrote {ROOT / 'yolo26_metrics.json'}")


if __name__ == "__main__":
    main()
