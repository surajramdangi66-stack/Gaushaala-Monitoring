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
        self.cattle_count: int = 0
        self.worker_count: int = 0
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
        self.tracker = CattleTracker(iou_threshold=0.20, max_age=75)
        self.detector = get_detector()
        self._frame_count = 0
        self._cached_detections = []

    def process_frame(
        self,
        frame: np.ndarray
    ) -> FrameAnalysisResult:
        result = FrameAnalysisResult()

        if frame is None or frame.size == 0:
            return result

        self._frame_count += 1

        # High-FPS frame cadence: Run YOLOv8 on every 2nd frame, re-use cached detections on intermediate frames
        if self._frame_count % 2 == 1 and self._cached_detections:
            detections = self._cached_detections
        else:
            detections = self.detector.detect(frame, include_workers=True)
            self._cached_detections = detections

        # Update multi-object tracker
        tracks = self.tracker.update(detections)
        result.tracks = tracks
        result.total_count = len(tracks)

        active = 0
        resting = 0
        feeder_cattle = 0
        worker_count = 0
        cattle_count = 0
        max_feeder_cap = self.spatial.feeder_zone.max_capacity if self.spatial.feeder_zone else 4

        for track in tracks:
            # Check entity type
            if track.is_worker or track.entity_type == "worker":
                worker_count += 1
                continue

            # Cattle entity
            cattle_count += 1

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

            # Prolonged inactivity / prostration check (> 18s in runtime)
            if track.activity_state == "resting" and track.inactivity_duration >= PROLONGED_INACTIVITY_THRESHOLD_SECONDS:
                track.is_prostrated = True
                result.prostrations_detected.append(track)
            else:
                track.is_prostrated = False

        result.cattle_count = cattle_count
        result.worker_count = worker_count
        result.active_count = active
        result.resting_count = resting
        result.feeder_count = feeder_cattle
        result.overcrowding_detected = (feeder_cattle > max_feeder_cap)

        # Zone stats breakdown
        result.zone_breakdown = {
            self.camera_name: {
                "total": cattle_count,
                "workers": worker_count,
                "active": result.active_count,
                "resting": result.resting_count,
                "feeder": result.feeder_count
            }
        }

        return result
