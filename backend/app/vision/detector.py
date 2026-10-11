import logging
import threading
from typing import List, Dict, Any, Optional
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from backend.app.config import (
    YOLO_MODEL_PATH,
    CUSTOM_GAUSHALA_MODEL_PATH,
    DETECTION_CONF_THRESHOLD,
)

logger = logging.getLogger("gaushala.detector")

# Clean friendly names for Desi cattle breeds
BREED_MAP = {
    0: "Gir Cow",
    1: "Gir Cow (Lying)",
    2: "Sahiwal Cow",
    3: "Sahiwal Cow (Lying)",
    4: "Rathi Cow",
    5: "Tharparkar Cow",
    6: "Kankrej Cow",
    7: "Desi Calf"
}

class CattleDetector:
    _instance = None

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model_detector = None
        self.model_breed = None
        self._lock = threading.Lock()
        self._load_models()

    def _load_models(self):
        try:
            # 1. Primary High-Accuracy Real-Time Detector (COCO YOLOv8: Class 0 = Person/Worker, Class 19 = Cow)
            coco_p = Path(YOLO_MODEL_PATH)
            if coco_p.exists():
                self.model_detector = YOLO(str(coco_p))
            else:
                self.model_detector = YOLO("yolov8n.pt")
            logger.info("Loaded primary YOLOv8 detector for Worker and Livestock detection.")

            # 2. Desi Breed Classifier Weights (if present)
            custom_p = Path(CUSTOM_GAUSHALA_MODEL_PATH)
            if custom_p.exists():
                try:
                    self.model_breed = YOLO(str(custom_p))
                    logger.info(f"Loaded custom Desi breed classifier from {custom_p}")
                except Exception as ex:
                    logger.warning(f"Could not load custom breed model: {ex}")

            # Warm up detector to eliminate layer fusion race conditions
            dummy = np.zeros((320, 320, 3), dtype=np.uint8)
            with self._lock:
                if self.model_detector is not None:
                    self.model_detector.predict(source=dummy, verbose=False, imgsz=320)
        except Exception as e:
            logger.error(f"Failed to initialize detector models: {e}")

    def _classify_breed(self, crop: np.ndarray, w: float, h: float) -> str:
        """Determines the specific Indian Desi cattle breed from features or crop classifier."""
        area = w * h
        aspect = w / max(1.0, h)
        
        # Check calf first by relative size
        if area < 18500:
            return "Desi Calf"

        if self.model_breed is not None and crop is not None and crop.size > 0:
            try:
                res = self.model_breed.predict(source=crop, conf=0.10, verbose=False)
                if res and len(res[0].boxes) > 0:
                    cls_id = int(res[0].boxes[0].cls[0].item())
                    if cls_id in BREED_MAP:
                        title = BREED_MAP[cls_id].replace(" (Lying)", "")
                        return title
            except Exception:
                pass

        # Intelligent color/texture based breed attribution
        if crop is not None and crop.size > 0:
            try:
                avg_bgr = np.mean(crop, axis=(0, 1))
                b, g, r = float(avg_bgr[0]), float(avg_bgr[1]), float(avg_bgr[2])
                # Reddish-brown hue -> Sahiwal or Gir
                if r > (b + 18) and r > (g + 8):
                    return "Sahiwal Cow" if aspect < 1.3 else "Gir Cow"
                # Grayish / Silver hue with large horns -> Kankrej
                elif abs(r - g) < 12 and abs(g - b) < 12 and (r + g + b) / 3 > 110:
                    return "Kankrej Cow"
                # White / pale coat -> Tharparkar
                elif (r + g + b) / 3 > 155:
                    return "Tharparkar Cow"
            except Exception:
                pass

        return "Indigenous Cattle"

    def detect(
        self,
        frame: np.ndarray,
        conf_threshold: float = 0.30,
        include_workers: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Runs real YOLOv8 detection on incoming CCTV feed:
        - Detects Indian Desi Cattle & Calves with posture and breed tags.
        - Detects Humans as Workers (Gaushala Staff).
        - Excludes static clutter (no boxes for empty troughs, manger boundaries, or tanks).
        """
        if frame is None or frame.size == 0 or self.model_detector is None:
            return []

        target_classes = [0, 19] if include_workers else [19]
        detections: List[Dict[str, Any]] = []

        try:
            with self._lock:
                results = self.model_detector.predict(
                    source=frame,
                    classes=target_classes,
                    conf=conf_threshold,
                    verbose=False,
                    imgsz=640
                )

            if results and len(results) > 0:
                boxes = results[0].boxes
                h_img, w_img = frame.shape[:2]

                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    xyxy = box.xyxy[0].tolist()
                    x1, y1, x2, y2 = [int(v) for v in xyxy]
                    w = max(1, x2 - x1)
                    h = max(1, y2 - y1)

                    if w < 16 or h < 20:
                        continue

                    # Worker detection (Class 0: Person)
                    if cls_id == 0:
                        detections.append({
                            "bbox": [round(float(c), 1) for c in xyxy],
                            "conf": round(conf, 2),
                            "class_id": 0,
                            "class_name": "worker",
                            "entity_type": "worker",
                            "label": "Worker (Staff)",
                            "breed": "Worker",
                            "posture": "standing",
                            "is_lying": False,
                            "is_calf": False,
                            "is_worker": True
                        })
                    # Animal detection (Class 19: Cow)
                    elif cls_id == 19:
                        aspect = w / float(h)
                        is_lying = (aspect > 1.35)
                        is_calf = (w * h < 18500)
                        posture = "lying" if is_lying else ("calf" if is_calf else "standing")

                        # Extract crop for breed determination
                        crop = frame[max(0, y1):min(h_img, y2), max(0, x1):min(w_img, x2)]
                        breed_name = self._classify_breed(crop, w, h)
                        if is_calf:
                            breed_name = "Desi Calf"

                        detections.append({
                            "bbox": [round(float(c), 1) for c in xyxy],
                            "conf": round(conf, 2),
                            "class_id": 19,
                            "class_name": "cattle",
                            "entity_type": "animal",
                            "label": breed_name,
                            "breed": breed_name,
                            "posture": posture,
                            "is_lying": is_lying,
                            "is_calf": is_calf,
                            "is_worker": False
                        })

            return detections
        except Exception as e:
            logger.error(f"Error during entity detection: {e}")
            return []

    def detect_all_entities(self, frame: np.ndarray, conf_threshold: float = 0.30) -> Dict[str, List[Dict[str, Any]]]:
        all_dets = self.detect(frame, conf_threshold=conf_threshold, include_workers=True)
        categorized = {
            "workers": [],
            "cattle_standing": [],
            "cattle_lying": [],
            "calves": []
        }
        for d in all_dets:
            if d.get("is_worker"):
                categorized["workers"].append(d)
            elif d.get("is_calf"):
                categorized["calves"].append(d)
            elif d.get("is_lying"):
                categorized["cattle_lying"].append(d)
            else:
                categorized["cattle_standing"].append(d)
        return categorized


# Singleton instance
_global_detector: Optional[CattleDetector] = None

def get_detector() -> CattleDetector:
    global _global_detector
    if _global_detector is None:
        _global_detector = CattleDetector()
    return _global_detector
