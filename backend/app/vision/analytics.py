import time
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from backend.app.vision.tracker import CattleTracker, TrackedCattle
from backend.app.vision.spatial import SpatialAnalytics
from backend.app.vision.detector import get_detector
from backend.app.config import PROLONGED_INACTIVITY_THRESHOLD_SECONDS
from backend.app.vision.shed_ai_zone import ShedAIZoneManager

class FrameAnalysisResult:
    def __init__(self):
        self.tracks: List[TrackedCattle] = []
        self.total_count: int = 0
        self.cattle_count: int = 0
        self.worker_count: int = 0
        self.active_count: int = 0
        self.resting_count: int = 0
        self.feeder_count: int = 0
        self.quarantine_count: int = 0
        self.overcrowding_detected: bool = False
        self.breaches_detected: List[TrackedCattle] = []
        self.prostrations_detected: List[TrackedCattle] = []
        self.quarantine_breaches: List[Dict[str, Any]] = []
        self.zone_breakdown: Dict[str, Dict[str, int]] = {}
        self.trough_metrics: Dict[str, Any] = {}
        self.feeding_summary: Dict[str, Any] = {}
        self.rumination_summary: Dict[str, Any] = {}
        self.ndlm_mappings: List[Dict[str, Any]] = []

class CameraAnalyticsEngine:
    def __init__(self, camera_id: str, camera_name: str, zones_config: Dict[str, Any]):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.spatial = SpatialAnalytics(zones_config)
        self.tracker = CattleTracker(iou_threshold=0.20, max_age=75)
        self.detector = get_detector()
        self.shed_manager = ShedAIZoneManager.get_instance(camera_id, camera_name, self.spatial)
        self._frame_count = 0
        self._cached_detections = []
        self._last_subsidy_sample = 0.0

    def process_frame(
        self,
        frame: np.ndarray,
        alert_engine: Optional[Any] = None
    ) -> FrameAnalysisResult:
        result = FrameAnalysisResult()

        if frame is None or frame.size == 0:
            return result

        now = time.time()
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
        quarantine_cattle = 0
        worker_count = 0
        cattle_count = 0
        cows_count = 0
        bulls_count = 0
        calves_count = 0
        max_feeder_cap = self.spatial.feeder_zone.max_capacity if self.spatial.feeder_zone else 4

        for track in tracks:
            # Check entity type
            if track.is_worker or track.entity_type == "worker":
                worker_count += 1
                continue

            # Cattle entity
            cattle_count += 1
            if getattr(track, "is_calf", False):
                calves_count += 1
            elif "bull" in getattr(track, "label", "").lower():
                bulls_count += 1
            else:
                cows_count += 1

            # Spatial assignment
            track.current_zone = self.spatial.get_zone_name_for_point(track.cx, track.cy, lang="hi")

            # Feeder check
            in_feeder = self.spatial.is_in_feeder(track.cx, track.cy)
            if in_feeder:
                feeder_cattle += 1

            # Quarantine check
            in_quarantine = self.spatial.is_in_quarantine(track.cx, track.cy)
            if in_quarantine:
                quarantine_cattle += 1

            # Activity count
            if track.activity_state == "resting":
                resting += 1
            else:
                active += 1

            # Geofence breach check (outside pen perimeter)
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
        result.quarantine_count = quarantine_cattle
        result.overcrowding_detected = (feeder_cattle > max_feeder_cap)

        # 1. Feeder Trough Monitoring & Feeding Duration Analytics
        feeding_data = self.shed_manager.process_feeder_attendance(tracks, frame, now)
        result.feeding_summary = feeding_data
        result.trough_metrics = feeding_data.get("trough_metrics", {})

        # 2. Quarantine Ward Virtual Tripwire Breach Monitoring
        quarantine_breaches = self.shed_manager.check_quarantine_tripwire_breaches(tracks, frame, alert_engine)
        result.quarantine_breaches = quarantine_breaches

        # 3. Resting & Rumination Analytics
        rumination_data = self.shed_manager.process_resting_and_rumination(tracks, now)
        result.rumination_summary = rumination_data

        # 4. NDLM Ear-Tag to Zone OCR Mapping
        ndlm_maps = self.shed_manager.update_tag_zone_mappings(tracks, frame)
        result.ndlm_mappings = ndlm_maps

        # 5. Fodder Subsidy sample recording (every ~10 seconds)
        if now - self._last_subsidy_sample >= 10.0:
            self.shed_manager.record_attendance_sample(
                total_cattle=cattle_count,
                cows=cows_count,
                bulls=bulls_count,
                calves=calves_count,
                sick=quarantine_cattle
            )
            self._last_subsidy_sample = now

        # Zone stats breakdown
        result.zone_breakdown = {
            self.camera_name: {
                "total": cattle_count,
                "workers": worker_count,
                "active": result.active_count,
                "resting": result.resting_count,
                "feeder": result.feeder_count,
                "quarantine": result.quarantine_count
            }
        }

        return result
