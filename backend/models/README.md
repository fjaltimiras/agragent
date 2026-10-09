# Model weights

The fine-tuned detector `wgisd_yolo26m.pt` is not committed here (44 MB binary).
Reproduce it with `yolo/train_yolo26_wgisd.py`, which fine-tunes YOLO26m on the
official WGISD train/test split (see the manuscript, Supplementary Material
Methods S2), or place your own
checkpoint at `backend/models/wgisd_yolo26m.pt`. The detection endpoint falls
back to COCO weights when it is absent.
