import logging
from typing import List, Dict, Any, Optional
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from backend.app.config import YOLO_MODEL_PATH, COCO_COW_CLASS_ID, DETECTION_CONF_THRESHOLD

logger = logging.getLogger("gaushala.detector")

class CattleDetector:
    _instance = None

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or YOLO_MODEL_PATH
        self.model = None
        self.device = "cpu"
        self._load_model()

    def _load_model(self):
        try:
            p = Path(self.model_path)
            if not p.exists():
                logger.info(f"Model path {self.model_path} not found directly, passing name to YOLO...")
                self.model = YOLO("yolov8n.pt")
            else:
                self.model = YOLO(str(p))
            logger.info("YOLOv8 cattle detector initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize YOLO model: {e}")
            self.model = None

    def detect(self, frame: np.ndarray, conf_threshold: float = DETECTION_CONF_THRESHOLD) -> List[Dict[str, Any]]:
        """
        Runs YOLOv8 detection on an image frame (BGR format from cv2).
        Returns bounding boxes filtered for livestock / cattle.
        """
        if self.model is None or frame is None or frame.size == 0:
            return []

        try:
            # We filter classes for cow (19), sheep (18), horse (17), dog (16)
            # COCO: 19 = cow, 18 = sheep, 17 = horse
            results = self.model.predict(
                source=frame,
                classes=[19, 18, 17],
                conf=conf_threshold,
                verbose=False,
                imgsz=640
            )

            detections = []
            if results and len(results) > 0:
                boxes = results[0].boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    xyxy = box.xyxy[0].tolist()

                    detections.append({
                        "bbox": [round(float(c), 1) for c in xyxy],
                        "conf": round(conf, 2),
                        "class_id": cls_id,
                        "class_name": "cattle" if cls_id == 19 else "livestock"
                    })
            return detections
        except Exception as e:
            logger.error(f"Error during YOLO inference: {e}")
            return []

# Singleton instance
_global_detector: Optional[CattleDetector] = None

def get_detector() -> CattleDetector:
    global _global_detector
    if _global_detector is None:
        _global_detector = CattleDetector()
    return _global_detector
