import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np
import cv2

logger = logging.getLogger("gaushala.feed_detector")

class FeedInspectionResult:
    def __init__(
        self,
        status: str,  # "FEED_VISIBLE", "MISSED_FEEDING", "NOT_VERIFIED"
        is_verified: bool,
        fodder_detected: Optional[bool],
        confidence: float,
        reason: str,
        trough_bbox: Optional[List[int]] = None
    ):
        self.status = status
        self.is_verified = is_verified
        self.fodder_detected = fodder_detected
        self.confidence = confidence
        self.reason = reason
        self.trough_bbox = trough_bbox

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "is_verified": self.is_verified,
            "fodder_detected": self.fodder_detected,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "trough_bbox": self.trough_bbox
        }

class FeedDetector:
    """
    Pluggable Fodder & Trough Vision Detector.
    
    Standard COCO YOLOv8 models do not contain a dedicated 'cattle fodder' class.
    This detector provides a rigorous integration interface:
    1. If FEED_MODEL_PATH is configured with custom trained weights, it loads the model
       and evaluates the trough ROI.
    2. If no trained fodder model is configured, or if the camera is offline, it produces
       NOT_VERIFIED rather than falsely declaring the trough empty or full.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or os.getenv("FEED_MODEL_PATH", "").strip()
        self.model = None
        self._load_model()

    def _load_model(self):
        if not self.model_path:
            logger.info("No custom FEED_MODEL_PATH specified. Feed compliance will produce NOT_VERIFIED.")
            return

        p = Path(self.model_path)
        if not p.exists():
            logger.warning(f"FEED_MODEL_PATH '{self.model_path}' not found on filesystem.")
            return

        try:
            from ultralytics import YOLO
            self.model = YOLO(str(p))
            logger.info(f"Custom Feed/Fodder detector successfully initialized from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load custom feed detector model: {e}")
            self.model = None

    def inspect_feeder(
        self,
        frame: Optional[np.ndarray],
        polygon: List[List[int]],
        conf_threshold: float = 0.40
    ) -> FeedInspectionResult:
        """
        Inspects the feeder trough region inside the given polygon coordinates.
        """
        if frame is None or frame.size == 0:
            return FeedInspectionResult(
                status="NOT_VERIFIED",
                is_verified=False,
                fodder_detected=None,
                confidence=0.0,
                reason="Camera offline or invalid video frame"
            )

        if not polygon or len(polygon) < 3:
            return FeedInspectionResult(
                status="NOT_VERIFIED",
                is_verified=False,
                fodder_detected=None,
                confidence=0.0,
                reason="Feeder trough polygon is not configured"
            )

        # If no model configured, gracefully produce NOT_VERIFIED without false alarms
        if self.model is None:
            return FeedInspectionResult(
                status="NOT_VERIFIED",
                is_verified=False,
                fodder_detected=None,
                confidence=0.0,
                reason="Fodder recognition model not configured (requires trained feed-classification weights)"
            )

        # Crop trough ROI for targeted inference
        try:
            pts = np.array(polygon, np.int32)
            x, y, w, h = cv2.boundingRect(pts)
            fh, fw = frame.shape[:2]
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(fw, x + w)
            y2 = min(fh, y + h)

            if x2 <= x1 or y2 <= y1:
                return FeedInspectionResult(
                    status="NOT_VERIFIED",
                    is_verified=False,
                    fodder_detected=None,
                    confidence=0.0,
                    reason="Invalid feeder polygon bounding box"
                )

            roi = frame[y1:y2, x1:x2]
            results = self.model.predict(source=roi, conf=conf_threshold, verbose=False)
            
            feed_boxes = []
            if results and len(results) > 0:
                for b in results[0].boxes:
                    conf = float(b.conf[0].item())
                    if conf >= conf_threshold:
                        feed_boxes.append(conf)

            if len(feed_boxes) > 0:
                highest_conf = max(feed_boxes)
                return FeedInspectionResult(
                    status="FEED_VISIBLE",
                    is_verified=True,
                    fodder_detected=True,
                    confidence=highest_conf,
                    reason=f"Fodder presence confirmed ({len(feed_boxes)} detections, max conf: {highest_conf:.2f})",
                    trough_bbox=[x1, y1, x2, y2]
                )
            else:
                return FeedInspectionResult(
                    status="MISSED_FEEDING",
                    is_verified=True,
                    fodder_detected=False,
                    confidence=0.0,
                    reason="No fodder detected in trough after deadline",
                    trough_bbox=[x1, y1, x2, y2]
                )
        except Exception as e:
            logger.error(f"Error during feed trough inference: {e}")
            return FeedInspectionResult(
                status="NOT_VERIFIED",
                is_verified=False,
                fodder_detected=None,
                confidence=0.0,
                reason=f"Inference error: {str(e)}"
            )

_feed_detector_instance: Optional[FeedDetector] = None

def get_feed_detector() -> FeedDetector:
    global _feed_detector_instance
    if _feed_detector_instance is None:
        _feed_detector_instance = FeedDetector()
    return _feed_detector_instance
