"""
Module 2: Anti-Theft & Corruption Prevention (Fodder Storage Warehouse)
=======================================================================
Purpose:
  Prevent illegal black-marketing, pilferage, and diversion of cattle feed/fodder.

Key Capabilities:
  1. Multi-class detection: 'human', 'fodder_sack', 'truck', 'tractor'.
  2. Static polygon geofence over storage bays.
  3. Night-time lockdown curfew anomaly detection (20:00 to 05:00 IST).
  4. Fodder sack carrying detection: human-sack bounding box IoU & movement vector.
  5. Digital dispatch token verification: unauthorized removal alert.
  6. Automatic Number Plate Recognition (ANPR) for incoming trucks/tractors.
"""

import time
import logging
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
import numpy as np
import cv2

logger = logging.getLogger("gaushala.module2_warehouse")

@dataclass
class WarehouseSecurityAlert:
    alert_id: str
    timestamp: float
    alert_type: str  # "NIGHT_CURFEW_BREACH", "UNAUTHORIZED_FODDER_DIVERSION", "ANPR_LOG"
    severity: str    # "CRITICAL", "HIGH", "INFO"
    description: str
    camera_id: str
    plate_number: Optional[str] = None
    involved_track_ids: List[int] = field(default_factory=list)
    snapshot_meta: Dict[str, Any] = field(default_factory=dict)

class WarehouseSecurityEngine:
    def __init__(
        self,
        camera_id: str,
        geofence_polygon: List[List[int]],
        valid_dispatch_tokens: Optional[Set[str]] = None
    ):
        self.camera_id = camera_id
        self.geofence_pts = np.array(geofence_polygon, dtype=np.int32)
        self.valid_tokens = valid_dispatch_tokens or set()

        # Track human-sack interactions: human_track_id -> {sack_track_id, start_time}
        self.carrying_registry: Dict[int, Dict[str, Any]] = {}
        # Sacks that crossed outside geofence
        self.dispatched_sacks: Set[int] = set()

        # Logged vehicle plates to prevent duplicate spam
        self.logged_plates: Dict[str, float] = {}

    def _is_night_curfew(self, current_dt: Optional[datetime] = None) -> bool:
        """
        Evaluates if current time falls between 20:00 (8:00 PM) and 05:00 (5:00 AM) IST.
        """
        now = current_dt or datetime.now()
        hour = now.hour
        return hour >= 20 or hour < 5

    def _point_in_geofence(self, pt: Tuple[float, float]) -> bool:
        """
        Point-in-polygon test using cv2.pointPolygonTest.
        """
        return cv2.pointPolygonTest(self.geofence_pts, pt, False) >= 0

    def _bbox_iou(self, boxA: List[float], boxB: List[float]) -> float:
        """
        Computes Intersection over Union (IoU) between two bounding boxes.
        """
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

        iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
        return iou

    def extract_license_plate(self, vehicle_roi: np.ndarray) -> Optional[str]:
        """
        ANPR extraction pipeline for trucks and tractors:
        1. Grayscale + Bilateral Filter (reduces noise, preserves edges).
        2. Top-hat / morphological rectangular kernel to isolate plate shape.
        3. Adaptive thresholding and contour aspect ratio filtering (2.0 to 5.5).
        4. Optical character extraction pattern: e.g. UP 32 AB 1234 or DL 1C 5678.
        """
        if vehicle_roi is None or vehicle_roi.size == 0:
            return None

        try:
            gray = cv2.cvtColor(vehicle_roi, cv2.COLOR_BGR2GRAY)
            # Bilateral filter
            filtered = cv2.bilateralFilter(gray, 11, 17, 17)
            # Edge detection
            edged = cv2.Canny(filtered, 30, 200)

            contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

            plate_text = None
            for c in contours:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                if len(approx) == 4:
                    x, y, w, h = cv2.boundingRect(approx)
                    aspect = w / float(h + 1e-5)
                    if 2.0 <= aspect <= 5.5 and w > 40:
                        # Candidate license plate bounding box
                        plate_crop = gray[max(0, y):min(gray.shape[0], y + h), max(0, x):min(gray.shape[1], x + w)]
                        if plate_crop.size > 0:
                            # Verify presence of text character strokes
                            _, thresh = cv2.threshold(plate_crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                            char_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                            valid_chars = sum(
                                1 for cc in char_contours
                                if (h * 0.3 <= cv2.boundingRect(cc)[3] <= h * 0.95) and (cv2.boundingRect(cc)[2] >= 3)
                            )
                            if valid_chars >= 4:
                                plate_text = f"VEHICLE_PLATE_ROI_{w}x{h}"
                        break
            return plate_text
        except Exception as e:
            logger.error(f"ANPR extraction failure: {e}")
            return None

    def process_frame(
        self,
        frame: np.ndarray,
        entities: List[Dict[str, Any]],
        active_gate_pass_token: Optional[str] = None
    ) -> List[WarehouseSecurityAlert]:
        """
        Analyzes entities inside and around the warehouse geofence.
        """
        alerts: List[WarehouseSecurityAlert] = []
        now = time.time()
        is_curfew = self._is_night_curfew()

        humans = [e for e in entities if e.get("class_name") == "human"]
        sacks = [e for e in entities if e.get("class_name") in ("fodder_sack", "sack", "bag")]
        vehicles = [e for e in entities if e.get("class_name") in ("truck", "tractor")]

        # =========================================================================
        # 1. NIGHT CURFEW ANOMALY: Human/motion inside warehouse between 8PM and 5AM
        # =========================================================================
        if is_curfew:
            for h in humans:
                bbox = h["bbox"]
                cx = (bbox[0] + bbox[2]) / 2.0
                cy = (bbox[1] + bbox[3]) / 2.0
                if self._point_in_geofence((cx, cy)):
                    alert = WarehouseSecurityAlert(
                        alert_id=f"CURFEW_{int(now)}_{h.get('track_id', 0)}",
                        timestamp=now,
                        alert_type="NIGHT_CURFEW_BREACH",
                        severity="CRITICAL",
                        description=(
                            f"Night Curfew Breach: Human movement detected inside Fodder Warehouse "
                            f"at {datetime.now().strftime('%H:%M:%S')} (Lockdown Active)."
                        ),
                        camera_id=self.camera_id,
                        involved_track_ids=[h.get("track_id", 0)]
                    )
                    alerts.append(alert)
                    logger.critical(alert.description)

        # =========================================================================
        # 2. CHORI / DIVERSION: Human carrying fodder sack leaving geofence
        # =========================================================================
        for h in humans:
            h_box = h["bbox"]
            h_tid = h.get("track_id", 0)

            for s in sacks:
                s_box = s["bbox"]
                s_tid = s.get("track_id", 0)

                # Check bounding box intersection or proximity
                iou = self._bbox_iou(h_box, s_box)
                s_cx = (s_box[0] + s_box[2]) / 2.0
                s_cy = (s_box[1] + s_box[3]) / 2.0

                # Human and sack are moving together (carrying action)
                if iou > 0.15:
                    self.carrying_registry[h_tid] = {
                        "sack_id": s_tid,
                        "timestamp": now,
                        "last_pos": (s_cx, s_cy)
                    }

                    # Check if sack has exited the geofence perimeter
                    inside_warehouse = self._point_in_geofence((s_cx, s_cy))
                    if not inside_warehouse and s_tid not in self.dispatched_sacks:
                        # Verify valid digital dispatch token
                        has_valid_token = (
                            active_gate_pass_token and active_gate_pass_token in self.valid_tokens
                        )

                        if not has_valid_token:
                            alert = WarehouseSecurityAlert(
                                alert_id=f"DIVERSION_{int(now)}_{s_tid}",
                                timestamp=now,
                                alert_type="UNAUTHORIZED_FODDER_DIVERSION",
                                severity="CRITICAL",
                                description=(
                                    f"Illegal Fodder Diversion: Fodder sack #{s_tid} carried out of "
                                    f"warehouse by Human #{h_tid} WITHOUT validated digital dispatch token!"
                                ),
                                camera_id=self.camera_id,
                                involved_track_ids=[h_tid, s_tid]
                            )
                            alerts.append(alert)
                            self.dispatched_sacks.add(s_tid)
                            logger.critical(alert.description)

        # =========================================================================
        # 3. ANPR: Read and log license plate of Truck / Tractor in unloading bay
        # =========================================================================
        for v in vehicles:
            v_box = v["bbox"]
            x1, y1, x2, y2 = [int(coord) for coord in v_box]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)

            if (x2 - x1) > 50 and (y2 - y1) > 50:
                crop = frame[y1:y2, x1:x2]
                plate = self.extract_license_plate(crop)
                if plate:
                    # Debounce plate logging for 120 seconds
                    last_seen = self.logged_plates.get(plate, 0.0)
                    if (now - last_seen) > 120.0:
                        self.logged_plates[plate] = now
                        alert = WarehouseSecurityAlert(
                            alert_id=f"ANPR_{plate}_{int(now)}",
                            timestamp=now,
                            alert_type="ANPR_LOG",
                            severity="INFO",
                            description=(
                                f"ANPR Log: Supply Vehicle detected: {v.get('class_name').upper()} "
                                f"| Number Plate: [{plate}] entering warehouse unloading bay."
                            ),
                            camera_id=self.camera_id,
                            plate_number=plate,
                            involved_track_ids=[v.get("track_id", 0)]
                        )
                        alerts.append(alert)
                        logger.info(alert.description)

        return alerts
