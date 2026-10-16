import time
import json
import logging
from typing import Dict, Any, Optional, Set
from datetime import datetime, timezone
import numpy as np

from backend.app.db.database import SessionLocal
from backend.app.db.models import CattleModel, CensusRecordModel, CensusSettingModel
from backend.app.camera.stream_manager import get_stream_manager
from backend.app.alerts.alert_engine import get_alert_engine

logger = logging.getLogger("gaushala.census")

class CensusResult:
    def __init__(
        self,
        session_id: str,
        camera_id: str,
        enclosure_name: str,
        census_type: str,
        scheduled_time: str,
        executed_at: str,
        expected_count: int,
        detected_count: Optional[int],
        difference: Optional[int],
        status: str,
        camera_online: bool,
        frames_analyzed: int,
        unique_tracks_count: int,
        diagnostic_details: Dict[str, Any]
    ):
        self.session_id = session_id
        self.camera_id = camera_id
        self.enclosure_name = enclosure_name
        self.census_type = census_type
        self.scheduled_time = scheduled_time
        self.executed_at = executed_at
        self.expected_count = expected_count
        self.detected_count = detected_count
        self.difference = difference
        self.status = status
        self.camera_online = camera_online
        self.frames_analyzed = frames_analyzed
        self.unique_tracks_count = unique_tracks_count
        self.diagnostic_details = diagnostic_details

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "camera_id": self.camera_id,
            "enclosure_name": self.enclosure_name,
            "census_type": self.census_type,
            "scheduled_time": self.scheduled_time,
            "executed_at": self.executed_at,
            "expected_count": self.expected_count,
            "detected_count": self.detected_count,
            "difference": self.difference,
            "status": self.status,
            "camera_online": self.camera_online,
            "frames_analyzed": self.frames_analyzed,
            "unique_tracks_count": self.unique_tracks_count,
            "diagnostic_details": self.diagnostic_details
        }

class CensusEngine:
    _instance = None

    def __init__(self):
        self.stream_manager = get_stream_manager()
        self.alert_engine = get_alert_engine()

    def run_census(
        self,
        camera_id: Optional[str] = None,
        census_type: str = "MANUAL_DIAGNOSTIC",
        scheduled_time: str = "MANUAL",
        capture_window_seconds: Optional[float] = None
    ) -> CensusResult:
        """
        Executes a multi-frame verified herd census:
        1. Queries active registered cattle from SQLite/PostgreSQL to establish baseline expected count.
        2. Probes camera online connectivity: if disconnected, immediately records NOT_VERIFIED.
        3. Aggregates stable unique track IDs across the capture window to avoid frame duplication.
        4. Calculates MATCH, SHORTFALL, or EXCESS status.
        5. Emits at most one session-deduplicated alert on discrepancy.
        6. Persists audit record in CensusRecordModel.
        """
        db = SessionLocal()
        try:
            # 1. Fetch settings if not specified
            settings = db.query(CensusSettingModel).first()
            if not camera_id:
                camera_id = settings.primary_camera_id if settings else "cam-01"
            if capture_window_seconds is None:
                capture_window_seconds = settings.capture_window_seconds if settings else 5.0

            pipeline = self.stream_manager.get_pipeline(camera_id)
            enclosure_name = pipeline.name if pipeline else f"Pen {camera_id}"
            executed_at = datetime.now(timezone.utc).isoformat()
            timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            session_id = f"census_{timestamp_slug}_{camera_id}"

            # 2. Derive expected count from active registered cattle
            # We match cattle registered specifically for this enclosure,
            # or if global census on primary camera, all active registered cattle.
            active_cattle_query = db.query(CattleModel).filter(CattleModel.status == "active")
            enclosure_cattle_count = active_cattle_query.filter(CattleModel.enclosure_id == camera_id).count()

            # If no cattle assigned specifically to this camera ID, use total active herd count
            expected_count = enclosure_cattle_count if enclosure_cattle_count > 0 else db.query(CattleModel).filter(CattleModel.status == "active").count()

            # 3. Check physical camera status
            if pipeline is None or not pipeline.source.is_online:
                logger.warning(f"Census aborted for {camera_id}: Camera is disconnected/offline.")
                diag = {
                    "reason": "Camera stream is offline or disconnected",
                    "camera_id": camera_id,
                    "pipeline_loaded": pipeline is not None
                }
                record = CensusRecordModel(
                    session_id=session_id,
                    camera_id=camera_id,
                    enclosure_name=enclosure_name,
                    census_type=census_type,
                    scheduled_time=scheduled_time,
                    executed_at=executed_at,
                    expected_count=expected_count,
                    detected_count=None,
                    difference=None,
                    status="NOT_VERIFIED",
                    camera_online=False,
                    frames_analyzed=0,
                    unique_tracks_count=0,
                    diagnostic_details=json.dumps(diag)
                )
                db.add(record)
                db.commit()

                # Trigger offline alert if scheduled
                if census_type != "MANUAL_DIAGNOSTIC":
                    self.alert_engine.trigger_alert(
                        camera_id=camera_id,
                        zone_name=enclosure_name,
                        alert_type="CAMERA_OFFLINE",
                        severity="WARNING",
                        message=f"Scheduled {census_type} census for {enclosure_name} failed: Camera is offline/disconnected.",
                        entity_id=session_id,
                        details={"session_id": session_id, "expected_count": expected_count}
                    )

                return CensusResult(
                    session_id=session_id,
                    camera_id=camera_id,
                    enclosure_name=enclosure_name,
                    census_type=census_type,
                    scheduled_time=scheduled_time,
                    executed_at=executed_at,
                    expected_count=expected_count,
                    detected_count=None,
                    difference=None,
                    status="NOT_VERIFIED",
                    camera_online=False,
                    frames_analyzed=0,
                    unique_tracks_count=0,
                    diagnostic_details=diag
                )

            # 4. Multi-frame census capture window
            unique_tracks: Set[int] = set()
            frame_detections_history = []
            frames_count = 0
            start_time = time.time()
            capture_duration = max(1.0, float(capture_window_seconds))

            # Sample frames over capture window
            while time.time() - start_time < capture_duration:
                raw_frame = pipeline.source.get_latest_frame()
                if raw_frame is not None and pipeline.source.is_online:
                    # Run cow-only detection
                    detections = pipeline.analytics.detector.detect(raw_frame, cow_only=True)
                    # Update tracker
                    tracks = pipeline.analytics.tracker.update(detections)
                    frames_count += 1
                    current_frame_track_ids = [t.track_id for t in tracks]
                    for tid in current_frame_track_ids:
                        unique_tracks.add(tid)
                    frame_detections_history.append(len(current_frame_track_ids))
                time.sleep(0.08)  # ~12 FPS sampling

            # Stable verified detected count
            if frame_detections_history:
                # Use max concurrent stable detection or unique tracks bounded by max active frame count
                # to prevent track ID fragmentation from inflating the headcount
                max_instantaneous = max(frame_detections_history) if frame_detections_history else 0
                avg_instantaneous = int(round(sum(frame_detections_history) / max(1, len(frame_detections_history))))
                # Bounded unique tracks
                detected_count = max(max_instantaneous, min(len(unique_tracks), max_instantaneous + 1))
            else:
                detected_count = 0

            # 5. Evaluate MATCH / SHORTFALL / EXCESS
            difference = detected_count - expected_count
            if detected_count == expected_count:
                status = "MATCH"
            elif detected_count < expected_count:
                status = "SHORTFALL"
            else:
                status = "EXCESS"

            diag = {
                "unique_track_ids": list(unique_tracks),
                "frames_analyzed": frames_count,
                "capture_duration_sec": round(time.time() - start_time, 2),
                "instantaneous_counts": frame_detections_history,
                "difference": difference
            }

            # 6. Save persistent record
            record = CensusRecordModel(
                session_id=session_id,
                camera_id=camera_id,
                enclosure_name=enclosure_name,
                census_type=census_type,
                scheduled_time=scheduled_time,
                executed_at=executed_at,
                expected_count=expected_count,
                detected_count=detected_count,
                difference=difference,
                status=status,
                camera_online=True,
                frames_analyzed=frames_count,
                unique_tracks_count=len(unique_tracks),
                diagnostic_details=json.dumps(diag)
            )
            db.add(record)
            db.commit()

            # 7. Generate at most ONE session-deduplicated alert on shortfall or excess
            if status == "SHORTFALL":
                missing = abs(difference)
                self.alert_engine.trigger_alert(
                    camera_id=camera_id,
                    zone_name=enclosure_name,
                    alert_type="CENSUS_SHORTFALL",
                    severity="CRITICAL",
                    message=f"HERD CENSUS SHORTFALL ({census_type}): Expected {expected_count} cows, verified {detected_count} ({missing} missing)!",
                    entity_id=session_id,
                    details={"session_id": session_id, "expected": expected_count, "detected": detected_count, "missing": missing}
                )
            elif status == "EXCESS":
                excess = difference
                self.alert_engine.trigger_alert(
                    camera_id=camera_id,
                    zone_name=enclosure_name,
                    alert_type="CENSUS_EXCESS",
                    severity="WARNING",
                    message=f"HERD CENSUS EXCESS ({census_type}): Expected {expected_count} cows, detected {detected_count} (+{excess} untagged/unregistered)!",
                    entity_id=session_id,
                    details={"session_id": session_id, "expected": expected_count, "detected": detected_count, "excess": excess}
                )

            return CensusResult(
                session_id=session_id,
                camera_id=camera_id,
                enclosure_name=enclosure_name,
                census_type=census_type,
                scheduled_time=scheduled_time,
                executed_at=executed_at,
                expected_count=expected_count,
                detected_count=detected_count,
                difference=difference,
                status=status,
                camera_online=True,
                frames_analyzed=frames_count,
                unique_tracks_count=len(unique_tracks),
                diagnostic_details=diag
            )
        except Exception as e:
            logger.error(f"Error during census execution: {e}", exc_info=True)
            db.rollback()
            raise
        finally:
            db.close()

    async def execute_census(
        self,
        camera_id: Optional[str] = None,
        census_type: str = "MANUAL_DIAGNOSTIC",
        scheduled_time: str = "MANUAL",
        capture_window_seconds: Optional[float] = None
    ) -> CensusResult:
        """Async compatibility wrapper for run_census."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.run_census(
                camera_id=camera_id,
                census_type=census_type,
                scheduled_time=scheduled_time,
                capture_window_seconds=capture_window_seconds
            )
        )


_census_engine_instance: Optional[CensusEngine] = None

def get_census_engine() -> CensusEngine:
    global _census_engine_instance
    if _census_engine_instance is None:
        _census_engine_instance = CensusEngine()
    return _census_engine_instance
