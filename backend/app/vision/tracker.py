import time
import math
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

def calculate_iou(boxA: List[float], boxB: List[float]) -> float:
    # box format: [x1, y1, x2, y2]
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    unionArea = boxAArea + boxBArea - interArea
    if unionArea <= 0:
        return 0.0
    return interArea / unionArea

class TrackedCattle:
    def __init__(self, track_id: int, bbox: List[float], conf: float = 1.0):
        self.track_id = track_id
        self.bbox = [float(c) for c in bbox]
        self.conf = conf
        self.cx = (self.bbox[0] + self.bbox[2]) / 2.0
        self.cy = (self.bbox[1] + self.bbox[3]) / 2.0
        self.centroid_history: List[Tuple[float, float, float]] = [(self.cx, self.cy, time.time())]
        self.velocity = 0.0
        self.activity_state = "active"  # "active" (standing/walking) or "resting" (lying)
        self.inactivity_start_time = time.time()
        self.inactivity_duration = 0.0
        self.is_prostrated = False
        self.is_breached = False
        self.prostration_alert_triggered = False
        self.geofence_breach_triggered = False
        self.current_zone = "Main Yard"
        self.age = 1
        self.time_since_update = 0

    def update(self, bbox: List[float], conf: float = 1.0):
        new_bbox = [float(c) for c in bbox]
        new_cx = (new_bbox[0] + new_bbox[2]) / 2.0
        new_cy = (new_bbox[1] + new_bbox[3]) / 2.0
        now = time.time()

        # Displacement from previous centroid
        dx = new_cx - self.cx
        dy = new_cy - self.cy
        dist = math.sqrt(dx * dx + dy * dy)
        dt = max(0.001, now - self.centroid_history[-1][2]) if self.centroid_history else 0.05
        current_vel = dist / dt

        # Smooth velocity
        self.velocity = 0.7 * self.velocity + 0.3 * current_vel

        self.bbox = new_bbox
        self.conf = conf
        self.cx = new_cx
        self.cy = new_cy
        self.centroid_history.append((new_cx, new_cy, now))
        if len(self.centroid_history) > 30:
            self.centroid_history.pop(0)

        # Activity State Logic:
        # Bounding box aspect ratio:
        w = max(1.0, self.bbox[2] - self.bbox[0])
        h = max(1.0, self.bbox[3] - self.bbox[1])
        aspect_ratio = w / h  # Resting cattle are typically wider than tall

        # Check movement over last 5 seconds
        recent_displacement = 0.0
        if len(self.centroid_history) >= 2:
            oldest = self.centroid_history[0]
            recent_displacement = math.hypot(self.cx - oldest[0], self.cy - oldest[1])

        # If velocity is very low and aspect ratio indicates lying down or stationary
        if recent_displacement < 25.0 and self.velocity < 12.0 and (aspect_ratio > 1.25 or dist < 2.0):
            self.activity_state = "resting"
            self.inactivity_duration = now - self.inactivity_start_time
        else:
            self.activity_state = "active"
            self.inactivity_start_time = now
            self.inactivity_duration = 0.0
            self.prostration_alert_triggered = False

        self.age += 1
        self.time_since_update = 0

    def mark_missed(self):
        self.time_since_update += 1

class CattleTracker:
    def __init__(self, iou_threshold: float = 0.3, max_age: int = 15):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.tracks: Dict[int, TrackedCattle] = {}
        self.next_id = 101

    def update(self, detections: List[Dict[str, Any]]) -> List[TrackedCattle]:
        """
        detections: list of dicts with 'bbox': [x1, y1, x2, y2], 'conf': float
        """
        matched_track_ids = set()
        matched_det_indices = set()

        existing_track_ids = list(self.tracks.keys())

        if existing_track_ids and detections:
            # Calculate IoU cost matrix
            cost_matrix = []
            for tid in existing_track_ids:
                row = []
                for det in detections:
                    iou = calculate_iou(self.tracks[tid].bbox, det["bbox"])
                    row.append(iou)
                cost_matrix.append(row)

            # Greedy matching for highest IoU
            while True:
                max_iou = 0.0
                best_t_idx = -1
                best_d_idx = -1

                for t_idx, tid in enumerate(existing_track_ids):
                    if tid in matched_track_ids:
                        continue
                    for d_idx in range(len(detections)):
                        if d_idx in matched_det_indices:
                            continue
                        iou = cost_matrix[t_idx][d_idx]
                        if iou > max_iou:
                            max_iou = iou
                            best_t_idx = t_idx
                            best_d_idx = d_idx

                if max_iou >= self.iou_threshold and best_t_idx != -1 and best_d_idx != -1:
                    tid = existing_track_ids[best_t_idx]
                    det = detections[best_d_idx]
                    self.tracks[tid].update(det["bbox"], det.get("conf", 1.0))
                    matched_track_ids.add(tid)
                    matched_det_indices.add(best_d_idx)
                else:
                    break

        # Handle unmatched existing tracks
        for tid in existing_track_ids:
            if tid not in matched_track_ids:
                self.tracks[tid].mark_missed()

        # Remove dead tracks
        dead_tracks = [tid for tid, track in self.tracks.items() if track.time_since_update > self.max_age]
        for tid in dead_tracks:
            del self.tracks[tid]

        # Initialize new tracks for unmatched detections
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_det_indices:
                new_track = TrackedCattle(self.next_id, det["bbox"], det.get("conf", 1.0))
                self.tracks[self.next_id] = new_track
                self.next_id += 1

        return list(self.tracks.values())
