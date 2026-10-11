import time
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from backend.app.vision.tracker import CattleTracker, TrackedCattle
from backend.app.vision.spatial import SpatialAnalytics
from backend.app.vision.detector import get_detector
from backend.app.config import PROLONGED_INACTIVITY_THRESHOLD_SECONDS

class FrameAnalysisResult:
    def __init__(self):
        self.tracks: List[TrackedCattle] = []
        self.total_count: int = 0
        self.active_count: int = 0
        self.resting_count: int = 0
        self.feeder_count: int = 0
        self.overcrowding_detected: bool = False
        self.breaches_detected: List[TrackedCattle] = []
        self.prostrations_detected: List[TrackedCattle] = []
        self.zone_breakdown: Dict[str, Dict[str, int]] = {}

class CameraAnalyticsEngine:
    def __init__(self, camera_id: str, camera_name: str, zones_config: Dict[str, Any]):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.spatial = SpatialAnalytics(zones_config)
        self.tracker = CattleTracker(iou_threshold=0.25, max_age=15)
        self.detector = get_detector()

    def process_frame(
        self,
        frame: np.ndarray,
        simulated_detections: Optional[List[Dict[str, Any]]] = None,
        use_yolo: bool = False
    ) -> FrameAnalysisResult:
        result = FrameAnalysisResult()

        if frame is None or frame.size == 0:
            return result

        # Detect cattle: Use real YOLO model if enabled/configured or use simulated ground-truth
        detections = []
        if use_yolo:
            detections = self.detector.detect(frame)
        elif simulated_detections:
            detections = simulated_detections
        else:
            # Fallback to YOLO inference
            detections = self.detector.detect(frame)

        # Update multi-object tracker
        tracks = self.tracker.update(detections)
        result.tracks = tracks
        result.total_count = len(tracks)

        active = 0
        resting = 0
        feeder_cattle = 0
        max_feeder_cap = self.spatial.feeder_zone.max_capacity if self.spatial.feeder_zone else 4

        for track in tracks:
            # Spatial assignment
            track.current_zone = self.spatial.get_zone_name_for_point(track.cx, track.cy)

            # Feeder check
            in_feeder = self.spatial.is_in_feeder(track.cx, track.cy)
            if in_feeder:
                feeder_cattle += 1

            # Activity count
            if track.activity_state == "resting":
                resting += 1
            else:
                active += 1

            # Geofence breach check
            is_breached = self.spatial.check_geofence_breach(track.cx, track.cy)
            track.is_breached = is_breached
            if is_breached:
                result.breaches_detected.append(track)

            # Prolonged inactivity / prostration check
            if track.activity_state == "resting" and track.inactivity_duration >= PROLONGED_INACTIVITY_THRESHOLD_SECONDS:
                track.is_prostrated = True
                result.prostrations_detected.append(track)
            else:
                track.is_prostrated = False

        result.active_count = active
        result.resting_count = resting
        result.feeder_count = feeder_cattle
        result.overcrowding_detected = (feeder_cattle > max_feeder_cap)

        # Zone stats breakdown
        result.zone_breakdown = {
            self.camera_name: {
                "total": result.total_count,
                "active": result.active_count,
                "resting": result.resting_count,
                "feeder": result.feeder_count
            }
        }

        return result
