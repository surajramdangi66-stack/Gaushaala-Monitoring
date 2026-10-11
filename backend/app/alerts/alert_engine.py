import os
import cv2
import time
import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import numpy as np
from pathlib import Path

from backend.app.config import SNAPSHOT_DIR, ALERT_THROTTLE_SECONDS
from backend.app.db.database import SessionLocal
from backend.app.db.models import AlertModel

logger = logging.getLogger("gaushala.alerts")

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
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        resolved: bool = False,
        resolved_at: Optional[str] = None
    ):
        self.id = alert_id
        self.camera_id = camera_id
        self.zone_name = zone_name
        self.alert_type = alert_type  # "GEOFENCE_BREACH", "PROSTRATION_DISTRESS", "FEEDER_OVERCROWDING", "CENSUS_SHORTFALL", "CENSUS_EXCESS", "FEEDING_MISSED", "CAMERA_OFFLINE"
        self.severity = severity      # "CRITICAL", "WARNING", "INFO"
        self.message = message
        self.snapshot_filename = snapshot_filename
        self.details = details or {}
        self.session_id = session_id
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.resolved = resolved
        self.resolved_at = resolved_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
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
        self.subscribers = []
        self._load_persisted_alerts()

    def _load_persisted_alerts(self):
        """Loads alerts from database to maintain state across application restarts."""
        try:
            db = SessionLocal()
            try:
                db_alerts = db.query(AlertModel).order_by(AlertModel.timestamp.desc()).limit(100).all()
                loaded = []
                for a in db_alerts:
                    details = {}
                    if a.details_json:
                        try:
                            details = json.loads(a.details_json)
                        except Exception:
                            pass
                    loaded.append(AlertEvent(
                        alert_id=a.id,
                        camera_id=a.camera_id,
                        zone_name=a.zone_name,
                        alert_type=a.alert_type,
                        severity=a.severity,
                        message=a.message,
                        snapshot_filename=a.snapshot_filename,
                        details=details,
                        session_id=a.session_id,
                        timestamp=a.timestamp,
                        resolved=a.resolved,
                        resolved_at=a.resolved_at
                    ))
                self.alerts = loaded
                logger.info(f"Loaded {len(self.alerts)} persisted alerts from database.")
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Database alerts table not yet created or error reading: {e}")

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
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Optional[AlertEvent]:
        # Session-level deduplication: If session_id provided, ensure only one alert of this type exists
        if session_id:
            for a in self.alerts:
                if a.session_id == session_id and a.alert_type == alert_type:
                    return a

        throttle_key = f"{camera_id}:{alert_type}:{entity_id or 'all'}"
        if not session_id and self._should_throttle(throttle_key):
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
            details=details,
            session_id=session_id
        )

        self.alerts.insert(0, alert)
        if len(self.alerts) > 200:
            self.alerts = self.alerts[:200]

        # Persist alert to database
        try:
            db = SessionLocal()
            try:
                db_record = AlertModel(
                    id=alert.id,
                    session_id=session_id,
                    camera_id=camera_id,
                    zone_name=zone_name,
                    alert_type=alert_type,
                    severity=severity,
                    message=message,
                    snapshot_filename=snapshot_filename,
                    details_json=json.dumps(details) if details else None,
                    timestamp=alert.timestamp,
                    resolved=False
                )
                db.add(db_record)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Failed to persist alert to database: {e}")

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
        resolved_time = datetime.now(timezone.utc).isoformat()
        found = False
        for a in self.alerts:
            if a.id == alert_id:
                a.resolved = True
                a.resolved_at = resolved_time
                found = True
                break

        # Persist resolution to database
        try:
            db = SessionLocal()
            try:
                record = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
                if record:
                    record.resolved = True
                    record.resolved_at = resolved_time
                    db.commit()
                    found = True
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Failed to persist alert resolution to database: {e}")

        return found

    def clear_all(self):
        self.alerts.clear()
        try:
            db = SessionLocal()
            try:
                db.query(AlertModel).delete()
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Failed to clear alerts in database: {e}")

_global_alert_engine = None

def get_alert_engine() -> AlertEngine:
    global _global_alert_engine
    if _global_alert_engine is None:
        _global_alert_engine = AlertEngine()
    return _global_alert_engine
