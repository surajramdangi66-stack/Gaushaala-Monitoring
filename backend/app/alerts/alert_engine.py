import os
import cv2
import time
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import numpy as np
from pathlib import Path
from backend.app.config import SNAPSHOT_DIR, ALERT_THROTTLE_SECONDS

class AlertEvent:
    def __init__(
        self,
        alert_id: str,
        camera_id: str,
        zone_name: str,
        alert_type: str,
        severity: str,
        message: str,
        snapshot_filename: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.id = alert_id
        self.camera_id = camera_id
        self.zone_name = zone_name
        self.alert_type = alert_type  # "GEOFENCE_BREACH", "PROSTRATION_DISTRESS", "FEEDER_OVERCROWDING", "CAMERA_OFFLINE"
        self.severity = severity      # "CRITICAL", "WARNING", "INFO"
        self.message = message
        self.snapshot_filename = snapshot_filename
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.resolved = False
        self.resolved_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "zone_name": self.zone_name,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "snapshot_url": f"/api/snapshots/{self.snapshot_filename}" if self.snapshot_filename else None,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "details": self.details
        }

class AlertEngine:
    _instance = None

    def __init__(self):
        self.alerts: List[AlertEvent] = []
        self.last_alert_times: Dict[str, float] = {}  # key: f"{camera_id}:{alert_type}:{entity_id}"
        self.subscribers = []  # WebSocket queues or callbacks

    def _should_throttle(self, key: str) -> bool:
        now = time.time()
        last = self.last_alert_times.get(key, 0)
        if now - last < ALERT_THROTTLE_SECONDS:
            return True
        self.last_alert_times[key] = now
        return False

    def trigger_alert(
        self,
        camera_id: str,
        zone_name: str,
        alert_type: str,
        severity: str,
        message: str,
        frame: Optional[np.ndarray] = None,
        highlight_box: Optional[List[float]] = None,
        entity_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[AlertEvent]:
        throttle_key = f"{camera_id}:{alert_type}:{entity_id or 'all'}"
        if self._should_throttle(throttle_key):
            return None

        alert_id = f"alt_{uuid.uuid4().hex[:8]}"
        snapshot_filename = None

        if frame is not None and frame.size > 0:
            snapshot_filename = f"snap_{alert_id}.jpg"
            snap_path = SNAPSHOT_DIR / snapshot_filename
            snap_frame = frame.copy()

            # Draw alert banner on snapshot
            cv2.rectangle(snap_frame, (0, 0), (snap_frame.shape[1], 40), (20, 20, 24), -1)
            color = (50, 50, 220) if severity == "CRITICAL" else (30, 160, 240) if severity == "WARNING" else (220, 150, 40)
            cv2.putText(
                snap_frame,
                f"[{severity}] {alert_type}: {message}",
                (15, 26),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA
            )

            # Highlight bounding box if available
            if highlight_box and len(highlight_box) == 4:
                x1, y1, x2, y2 = [int(v) for v in highlight_box]
                cv2.rectangle(snap_frame, (x1, y1), (x2, y2), color, 3)
                if entity_id:
                    cv2.putText(
                        snap_frame,
                        f"ID: #{entity_id}",
                        (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        color,
                        2,
                        cv2.LINE_AA
                    )

            cv2.imwrite(str(snap_path), snap_frame)

        alert = AlertEvent(
            alert_id=alert_id,
            camera_id=camera_id,
            zone_name=zone_name,
            alert_type=alert_type,
            severity=severity,
            message=message,
            snapshot_filename=snapshot_filename,
            details=details
        )

        self.alerts.insert(0, alert)
        # Cap alert memory to 200 items
        if len(self.alerts) > 200:
            self.alerts = self.alerts[:200]

        return alert

    def get_alerts(
        self,
        severity: Optional[str] = None,
        camera_id: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        filtered = self.alerts
        if severity:
            sev_upper = severity.upper()
            filtered = [a for a in filtered if a.severity == sev_upper]
        if camera_id:
            filtered = [a for a in filtered if a.camera_id == camera_id]
        if resolved is not None:
            filtered = [a for a in filtered if a.resolved == resolved]
        return [a.to_dict() for a in filtered[:limit]]

    def resolve_alert(self, alert_id: str) -> bool:
        for a in self.alerts:
            if a.id == alert_id:
                a.resolved = True
                a.resolved_at = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def clear_all(self):
        self.alerts.clear()

_global_alert_engine = None

def get_alert_engine() -> AlertEngine:
    global _global_alert_engine
    if _global_alert_engine is None:
        _global_alert_engine = AlertEngine()
    return _global_alert_engine
