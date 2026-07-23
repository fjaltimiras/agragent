# Model weights

The fine-tuned detector `wgisd_yolo26m.pt` is not committed here (44 MB binary).
Reproduce it with the YOLO26 training script in the project's `yolo/` directory
(see the manuscript, Supplementary Material Methods S2), or place your own
checkpoint at `backend/models/wgisd_yolo26m.pt`. The detection endpoint falls
back to COCO weights when it is absent.
