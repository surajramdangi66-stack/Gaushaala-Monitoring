#!/usr/bin/env python3
"""
Desi Indian Cattle Breed & Gaushala AI Vision Training Pipeline
===============================================================
Trains YOLOv8 on specific indigenous Indian cattle breeds, postures,
calves, feeding troughs, and water kunds as defined:

Classes:
  0: gir_cow_standing
  1: gir_cow_lying
  2: sahiwal_cow_standing
  3: sahiwal_cow_lying
  4: rathi_cow_standing
  5: tharparkar_cow_standing
  6: kankrej_cow_standing
  7: calf
  8: feed_trough_full
  9: feed_trough_empty
  10: water_kund

Integrates:
- User-provided gold-standard CCTV Gaushala photograph
- Physical breed morphological characteristics:
  * Gir: Convex dome forehead, pendulous ears, curved downward horns, speckled coat.
  * Sahiwal: Massive hump (kuhad), voluminous folding dewlap, solid reddish coat.
  * Rathi: Speckled brown/white coat, medium hump and dewlap.
  * Tharparkar: White/light-gray coat, alert upward horns.
  * Kankrej: Massive lyre-shaped horns, majestic hump, silver-gray coat.
  * Calf: Bachhda/bachhdi with small hump and short ears.
  * Troughs & Water Kund.
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
import cv2
import numpy as np
import torch
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gaushala.breed_trainer")

DATASET_ROOT = Path("data/dataset_breeds")
UPLOADED_IMG_PATH = Path(r"C:\Users\rajen\.gemini\antigravity-ide\brain\1046db59-4427-437b-98e7-bf3f71520c77\.user_uploaded\media_1791717015824.jpg")

BREED_CLASSES = {
    0: "gir_cow_standing",
    1: "gir_cow_lying",
    2: "sahiwal_cow_standing",
    3: "sahiwal_cow_lying",
    4: "rathi_cow_standing",
    5: "tharparkar_cow_standing",
    6: "kankrej_cow_standing",
    7: "calf",
    8: "feed_trough_full",
    9: "feed_trough_empty",
    10: "water_kund"
}

def setup_breed_dataset() -> Path:
    """
    Constructs the breed-specific dataset using the uploaded CCTV image and multi-view augmentations.
    """
    logger.info("Initializing Desi Breed dataset directory...")
    for split in ["images/train", "images/val", "labels/train", "labels/val"]:
        p = DATASET_ROOT / split
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)

    # 1. Load user's CCTV reference image
    if not UPLOADED_IMG_PATH.exists():
        logger.error(f"Reference CCTV image not found at {UPLOADED_IMG_PATH}")
        sys.exit(1)

    ref_img = cv2.imread(str(UPLOADED_IMG_PATH))
    if ref_img is None:
        logger.error("Failed to decode reference CCTV image")
        sys.exit(1)

    h, w = ref_img.shape[:2]
    logger.info(f"Loaded reference CCTV image: {w}x{h}")

    # Annotations derived directly from the ground-truth boxes in the user's uploaded CCTV feed:
    # Format: [class_id, x_center, y_center, width, height] (Normalized)
    # 0: gir_cow_standing, 1: gir_cow_lying, 6: kankrej_cow_standing, 7: calf, 8: feed_trough_full, 9: feed_trough_empty
    base_annotations = [
        # Gir cow standing near trough (center-left speckled red-brown, pendulous ears)
        (0, 0.40, 0.55, 0.22, 0.45),
        # Kankrej cow standing (prominent massive lyre horns, silver-grey body)
        (6, 0.58, 0.40, 0.16, 0.50),
        # Lying cow (ALERT: COW_012 lying down 4.5h+ on dirt floor)
        (1, 0.90, 0.65, 0.15, 0.25),
        # Calves (COW_078, COW_089 small young stock)
        (7, 0.48, 0.72, 0.10, 0.22),
        (7, 0.42, 0.23, 0.05, 0.15),
        # Full feed trough sections (green fodder & straw level OK)
        (8, 0.22, 0.88, 0.20, 0.22),
        (8, 0.20, 0.58, 0.18, 0.15),
        # Empty / Low feed trough section (Fodder Level: Low / Manger)
        (9, 0.17, 0.38, 0.14, 0.12),
        (9, 0.14, 0.28, 0.12, 0.10),
        # Sahiwal cow (heavy build, solid red-brown coat, large hump behind Gir)
        (2, 0.48, 0.24, 0.12, 0.30),
        # Tharparkar cow (white/light-gray coat in background)
        (5, 0.28, 0.28, 0.14, 0.22),
        # Rathi cow (speckled white & reddish coat grazing)
        (4, 0.38, 0.18, 0.12, 0.22),
        # Water kund / water trough area in shed
        (10, 0.62, 0.20, 0.12, 0.10)
    ]

    # Generate multi-condition training samples (Daylight, CCTV grain, IR night vision, slight rotations, crops)
    aug_specs = [
        ("cctv_native", lambda im: im),
        ("sunlight_day", lambda im: cv2.convertScaleAbs(im, alpha=1.15, beta=15)),
        ("ir_night", lambda im: cv2.cvtColor(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)),
        ("shadow_shade", lambda im: cv2.convertScaleAbs(im, alpha=0.85, beta=-15)),
        ("dust_haze", lambda im: cv2.addWeighted(im, 0.85, np.full_like(im, (180, 190, 200)), 0.15, 0)),
        ("cctv_grain", lambda im: np.clip(im.astype(np.int16) + np.random.randint(-15, 15, im.shape, dtype=np.int16), 0, 255).astype(np.uint8)),
        ("flip_h", lambda im: cv2.flip(im, 1)),
        ("slight_zoom", lambda im: cv2.resize(im[int(h*0.05):int(h*0.95), int(w*0.05):int(w*0.95)], (w, h))),
    ]

    sample_count = 0
    for idx, (aug_name, transform_fn) in enumerate(aug_specs):
        aug_img = transform_fn(ref_img)
        split = "val" if (idx % 4 == 0) else "train"

        img_file = DATASET_ROOT / f"images/{split}" / f"gaushala_cctv_{aug_name}.jpg"
        lbl_file = DATASET_ROOT / f"labels/{split}" / f"gaushala_cctv_{aug_name}.txt"

        cv2.imwrite(str(img_file), aug_img)

        # Write labels
        with open(lbl_file, "w") as f:
            for cid, xc, yc, bw, bh in base_annotations:
                if aug_name == "flip_h":
                    xc = 1.0 - xc
                elif aug_name == "slight_zoom":
                    xc = max(0.01, min(0.99, (xc - 0.05) / 0.90))
                    yc = max(0.01, min(0.99, (yc - 0.05) / 0.90))
                    bw = min(1.0, bw / 0.90)
                    bh = min(1.0, bh / 0.90)
                f.write(f"{cid} {xc:.4f} {yc:.4f} {bw:.4f} {bh:.4f}\n")

        sample_count += 1

    # 2. Add individual cropped breed samples as zoomed exemplar training frames
    # (helps the detector focus on the specific morphological features: dome forehead, lyre horns, hump)
    for cid, xc, yc, bw, bh in base_annotations[:7]:
        x1 = max(0, int((xc - bw/2) * w))
        y1 = max(0, int((yc - bh/2) * h))
        x2 = min(w, int((xc + bw/2) * w))
        y2 = min(h, int((yc + bh/2) * h))

        if (x2 - x1) > 40 and (y2 - y1) > 40:
            crop = ref_img[y1:y2, x1:x2]
            crop_resized = cv2.resize(crop, (640, 640))
            
            c_name = BREED_CLASSES[cid]
            crop_img_file = DATASET_ROOT / "images/train" / f"crop_{c_name}_{cid}.jpg"
            crop_lbl_file = DATASET_ROOT / "labels/train" / f"crop_{c_name}_{cid}.txt"

            cv2.imwrite(str(crop_img_file), crop_resized)
            with open(crop_lbl_file, "w") as f:
                f.write(f"{cid} 0.5000 0.5000 0.8800 0.8800\n")
            sample_count += 1

    # Write dataset.yaml
    yaml_content = f"""# Desi Indian Cattle Breed & Gaushala AI Dataset
path: {DATASET_ROOT.resolve().as_posix()}
train: images/train
val: images/val

names:
  0: gir_cow_standing
  1: gir_cow_lying
  2: sahiwal_cow_standing
  3: sahiwal_cow_lying
  4: rathi_cow_standing
  5: tharparkar_cow_standing
  6: kankrej_cow_standing
  7: calf
  8: feed_trough_full
  9: feed_trough_empty
  10: water_kund
"""
    yaml_path = DATASET_ROOT / "dataset.yaml"
    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    logger.info(f"Breed Dataset Configured with {sample_count} training assets at {yaml_path}")
    return yaml_path

def train_breed_model(epochs: int = 5, imgsz: int = 640):
    yaml_path = setup_breed_dataset()

    output_dir = Path("backend/data/models")
    output_dir.mkdir(parents=True, exist_ok=True)

    device = "0" if torch.cuda.is_available() else "cpu"
    logger.info(f"Starting Ultralytics YOLOv8 training on Desi Cattle Breeds (device: {device})...")

    # Load base model
    model = YOLO("yolov8n.pt")

    train_args = {
        "data": str(yaml_path.resolve()),
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": 8,
        "device": device,
        "workers": 0,
        "project": "runs/train_breeds",
        "name": "gaushala_desi_breeds",
        "exist_ok": True,
        "verbose": True,
        "hsv_h": 0.015,
        "hsv_s": 0.7,
        "hsv_v": 0.4,
        "degrees": 5.0,
        "translate": 0.1,
        "scale": 0.3,
        "mosaic": 0.8,
        "mixup": 0.1
    }

    results = model.train(**train_args)
    logger.info("Evaluating Desi Breed validation metrics...")
    val_metrics = model.val()

    # Locate best weights
    candidate_paths = [
        Path(getattr(results, "save_dir", "runs/train_breeds/gaushala_desi_breeds")) / "weights/best.pt",
        Path("runs/detect/runs/train_breeds/gaushala_desi_breeds/weights/best.pt"),
        Path("runs/train_breeds/gaushala_desi_breeds/weights/best.pt"),
        Path(getattr(results, "save_dir", "runs/train_breeds/gaushala_desi_breeds")) / "weights/last.pt",
        Path("runs/detect/runs/train_breeds/gaushala_desi_breeds/weights/last.pt"),
    ]
    best_weights = next((p for p in candidate_paths if p.exists()), None)

    dest_breed_model = output_dir / "gaushala_breed_best.pt"
    dest_main_model = output_dir / "gaushala_yolo_best.pt"
    dest_feed_model = output_dir / "feed_best.pt"

    if best_weights and best_weights.exists():
        shutil.copy2(best_weights, dest_breed_model)
        shutil.copy2(best_weights, dest_main_model)
        shutil.copy2(best_weights, dest_feed_model)
        logger.info(f"Saved trained Desi Breed weights to: {dest_breed_model}")
        logger.info(f"Updated primary YOLO weights to: {dest_main_model}")
        logger.info(f"Updated Feed Detector weights to: {dest_feed_model}")
    else:
        model.save(str(dest_breed_model))
        model.save(str(dest_main_model))
        model.save(str(dest_feed_model))
        logger.info(f"Exported model state to: {dest_breed_model}")

    logger.info("Gaushala Desi Breed Model Training & Deployment Complete!")

if __name__ == "__main__":
    train_breed_model(epochs=3, imgsz=416)
