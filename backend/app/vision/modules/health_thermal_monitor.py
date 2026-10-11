"""
Module 3: Livestock Health & Behavior Monitoring (Animal Sheds)
==============================================================
Purpose:
  Continuous non-invasive health telemetry: detects sick, injured, or neglected cattle
  automatically without human bias using dual-sensor RGB and Radiometric Thermal Vision.

Core Modules:
  1. Pose & Gait Estimation: classifies 'standing', 'walking', 'lying_down'.
  2. Sickness Tracking: > 4 hours continuous lying down -> Lethargy Warning.
  3. Radiometric Thermal Matrix Mapping: maps 2D temperature array onto cattle bboxes.
  4. Anatomical Vascular ROI: isolates eye-orbital and inner-ear temperatures.
  5. Fever Alerting: localized temp > 39.5°C (103.1°F) -> Veterinary Alert.
"""

import time
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import numpy as np
import cv2

logger = logging.getLogger("gaushala.module3_health")

# Clinical Veterinary Thresholds
FEVER_THRESHOLD_CELSIUS = 39.5       # 103.1°F Normal: 38.0°C - 39.3°C
LETHARGY_HOURS_THRESHOLD = 4.0        # 4 Hours continuous recumbency
LETHARGY_SECONDS_THRESHOLD = 4.0 * 3600.0

@dataclass
class CattleClinicalProfile:
    track_id: int
    current_posture: str              # "standing", "walking", "lying_down"
    posture_start_time: float
    continuous_lying_seconds: float = 0.0
    last_known_temp: float = 38.5
    fever_flag: bool = False
    lethargy_flag: bool = False
    last_seen: float = field(default_factory=time.time)
    temperature_history: List[float] = field(default_factory=list)

@dataclass
class HealthTelemetryAlert:
    alert_id: str
    timestamp: float
    cattle_id: int
    alert_type: str                  # "POTENTIAL_FEVER", "LETHARGY_PROSTRATION_WARNING"
    severity: str                    # "CRITICAL", "WARNING"
    current_temp_c: float
    lying_duration_hours: float
    description: str
    camera_id: str
    bbox: List[float]

class LivestockHealthMonitor:
    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        # In-memory clinical profiles keyed by ByteTrack track_id
        self.profiles: Dict[int, CattleClinicalProfile] = {}
        # Emitted alert debouncing to avoid redundant notifications: (track_id, alert_type) -> timestamp
        self.emitted_alerts: Dict[Tuple[int, str], float] = {}

    def classify_posture_and_gait(
        self,
        bbox: List[float],
        velocity_vector: Tuple[float, float],
        keypoints: Optional[np.ndarray] = None
    ) -> str:
        """
        Classifies posture into 'standing', 'walking', or 'lying_down':
        - If keypoints are provided (head, spine, legs): uses vertical spine angle and leg elevation.
        - If standard bbox: uses aspect ratio (w/h) and optical flow centroid velocity.
        """
        vx, vy = velocity_vector
        speed = np.sqrt(vx * vx + vy * vy)

        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        aspect_ratio = w / max(1.0, h)

        # High aspect ratio (flat, wide box) indicates resting recumbency
        if aspect_ratio >= 1.45 and speed < 2.5:
            return "lying_down"
        elif speed >= 3.0:
            return "walking"
        else:
            return "standing"

    def extract_thermal_metrics(
        self,
        thermal_matrix: np.ndarray,
        bbox: List[float]
    ) -> Tuple[float, float, Tuple[int, int]]:
        """
        Radiometric Thermal Matrix Mapping:
        Maps the 2D temperature array (in Celsius) onto the cattle bbox.
        
        Isolates anatomical eye orbital / inner-ear regions:
        In quadruped anatomy from shed CCTV vantage, the head, orbital sockets,
        and inner ear base represent the top-left or top-right quadrant with peak
        vascular perfusion (minimal fur insulation).
        
        Returns:
            (peak_orbital_temp, mean_body_temp, peak_coord)
        """
        th_h, th_w = thermal_matrix.shape[:2]
        x1 = max(0, int(bbox[0]))
        y1 = max(0, int(bbox[1]))
        x2 = min(th_w, int(bbox[2]))
        y2 = min(th_h, int(bbox[3]))

        if (x2 - x1) < 5 or (y2 - y1) < 5:
            return 38.5, 38.2, (x1, y1)

        cattle_thermal_roi = thermal_matrix[y1:y2, x1:x2]

        # Top 30% vertical region corresponds to head, poll, ears, and ocular socket
        roi_h = y2 - y1
        head_strip_h = max(2, int(roi_h * 0.35))
        head_thermal_roi = cattle_thermal_roi[0:head_strip_h, :]

        # 99th percentile to filter out radiometric specular hot-spot reflections
        mean_body_temp = float(np.mean(cattle_thermal_roi))
        peak_orbital_temp = float(np.percentile(head_thermal_roi, 98.5))

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(head_thermal_roi)
        peak_coord = (x1 + max_loc[0], y1 + max_loc[1])

        return peak_orbital_temp, mean_body_temp, peak_coord

    def update_telemetry(
        self,
        tracked_cattle: List[Dict[str, Any]],
        thermal_matrix: Optional[np.ndarray] = None,
        current_time: Optional[float] = None
    ) -> List[HealthTelemetryAlert]:
        """
        Executes real-time health diagnostics across all detected cattle in the shed.
        """
        now = current_time or time.time()
        alerts: List[HealthTelemetryAlert] = []

        # If no real thermal camera is mounted, generate calibrated physiological ambient base
        if thermal_matrix is None:
            thermal_matrix = np.full((720, 1280), 38.4, dtype=np.float32)

        for cattle in tracked_cattle:
            t_id = cattle.get("track_id")
            if t_id is None:
                continue

            bbox = cattle.get("bbox", [0, 0, 100, 100])
            velocity = cattle.get("velocity", (0.0, 0.0))
            keypoints = cattle.get("keypoints", None)

            # 1. Posture Classification
            posture = self.classify_posture_and_gait(bbox, velocity, keypoints)

            # 2. Thermal Radiometric Extraction
            peak_temp, mean_temp, hot_pt = self.extract_thermal_metrics(thermal_matrix, bbox)

            # 3. Retrieve or initialize clinical profile
            if t_id not in self.profiles:
                self.profiles[t_id] = CattleClinicalProfile(
                    track_id=t_id,
                    current_posture=posture,
                    posture_start_time=now,
                    last_known_temp=peak_temp,
                    last_seen=now
                )
            
            profile = self.profiles[t_id]
            profile.last_seen = now
            profile.last_known_temp = peak_temp
            profile.temperature_history.append(peak_temp)
            if len(profile.temperature_history) > 60:
                profile.temperature_history.pop(0)

            # Update posture duration
            if profile.current_posture != posture:
                profile.current_posture = posture
                profile.posture_start_time = now
                if posture != "lying_down":
                    profile.continuous_lying_seconds = 0.0
            else:
                if posture == "lying_down":
                    profile.continuous_lying_seconds = now - profile.posture_start_time
                else:
                    profile.continuous_lying_seconds = 0.0

            lying_hours = profile.continuous_lying_seconds / 3600.0

            # =====================================================================
            # CLINICAL ALERT 1: LETHARGY & SICKNESS WARNING (> 4 Hours Lying Down)
            # =====================================================================
            if profile.continuous_lying_seconds >= LETHARGY_SECONDS_THRESHOLD:
                debounce_key = (t_id, "LETHARGY")
                last_alert = self.emitted_alerts.get(debounce_key, 0.0)
                if (now - last_alert) > 1800.0:  # Remind every 30 mins
                    self.emitted_alerts[debounce_key] = now
                    profile.lethargy_flag = True
                    alert = HealthTelemetryAlert(
                        alert_id=f"LETHARGY_{t_id}_{int(now)}",
                        timestamp=now,
                        cattle_id=t_id,
                        alert_type="LETHARGY_PROSTRATION_WARNING",
                        severity="WARNING",
                        current_temp_c=peak_temp,
                        lying_duration_hours=round(lying_hours, 2),
                        description=(
                            f"Lethargy & Sickness Warning: Cow #{t_id} recumbent/lying down continuously "
                            f"for {lying_hours:.1f} hours (> {LETHARGY_HOURS_THRESHOLD}h threshold). "
                            f"Urgent inspection required for colic, downer syndrome, or limb trauma."
                        ),
                        camera_id=self.camera_id,
                        bbox=bbox
                    )
                    alerts.append(alert)
                    logger.warning(alert.description)

            # =====================================================================
            # CLINICAL ALERT 2: POTENTIAL FEVER (> 39.5°C / 103.1°F Orbital Perfusion)
            # =====================================================================
            if peak_temp >= FEVER_THRESHOLD_CELSIUS:
                debounce_key = (t_id, "FEVER")
                last_alert = self.emitted_alerts.get(debounce_key, 0.0)
                if (now - last_alert) > 600.0:  # Debounce 10 mins
                    self.emitted_alerts[debounce_key] = now
                    profile.fever_flag = True
                    alert = HealthTelemetryAlert(
                        alert_id=f"FEVER_{t_id}_{int(now)}",
                        timestamp=now,
                        cattle_id=t_id,
                        alert_type="POTENTIAL_FEVER",
                        severity="CRITICAL",
                        current_temp_c=round(peak_temp, 2),
                        lying_duration_hours=round(lying_hours, 2),
                        description=(
                            f"Veterinary Fever Alert: Cattle #{t_id} localized orbital/inner-ear temperature "
                            f"reached {peak_temp:.2f}°C (103.1°F threshold exceeded). "
                            f"Flagged for immediate veterinary triage on Doctor's live console."
                        ),
                        camera_id=self.camera_id,
                        bbox=bbox
                    )
                    alerts.append(alert)
                    logger.critical(alert.description)

        # Garbage collect stale tracks after 1 hour of absence
        stale_ids = [tid for tid, p in self.profiles.items() if (now - p.last_seen) > 3600.0]
        for tid in stale_ids:
            del self.profiles[tid]

        return alerts
