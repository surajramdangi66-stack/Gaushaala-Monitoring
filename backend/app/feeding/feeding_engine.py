import time
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from backend.app.db.database import SessionLocal
from backend.app.db.models import FeedingScheduleModel, FeedingObservationModel
from backend.app.camera.stream_manager import get_stream_manager
from backend.app.vision.feed_detector import get_feed_detector, FeedInspectionResult
from backend.app.alerts.alert_engine import get_alert_engine

logger = logging.getLogger("gaushala.feeding")

class FeedingEngine:
    _instance = None

    def __init__(self):
        self.stream_manager = get_stream_manager()
        self.feed_detector = get_feed_detector()
        self.alert_engine = get_alert_engine()

    def check_feeding_compliance(
        self,
        schedule_id: Optional[int] = None,
        camera_id: str = "cam-01",
        trough_name: Optional[str] = None,
        session_id_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Conducts an automated feeding observation check:
        1. Confirms physical camera online state.
        2. Inspects trough region using the pluggable FeedDetector.
        3. If model is unconfigured or camera is offline, records NOT_VERIFIED.
        4. If verified absent, generates FEEDING_MISSED alert and snapshot.
        5. Persists observation record in FeedingObservationModel.
        """
        db = SessionLocal()
        try:
            schedule = None
            if schedule_id:
                schedule = db.query(FeedingScheduleModel).filter(FeedingScheduleModel.id == schedule_id).first()
                if schedule:
                    camera_id = schedule.camera_id
                    trough_name = schedule.trough_name

            trough_name = trough_name or "Feeder Trough A"
            pipeline = self.stream_manager.get_pipeline(camera_id)
            timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            session_id = session_id_override or f"feed_{timestamp_slug}_{camera_id}"
            observed_at = datetime.now(timezone.utc).isoformat()

            # 1. Check camera status
            if pipeline is None or not pipeline.source.is_online:
                diag = {"reason": "Camera offline during feeding check", "camera_id": camera_id}
                record = FeedingObservationModel(
                    schedule_id=schedule_id,
                    session_id=session_id,
                    camera_id=camera_id,
                    trough_name=trough_name,
                    observed_at=observed_at,
                    fodder_detected=None,
                    status="NOT_VERIFIED",
                    diagnostic_details=json.dumps(diag),
                    alert_generated=False
                )
                db.add(record)
                db.commit()
                return record.to_dict()

            # 2. Extract trough polygon from spatial engine
            feeder_zone = pipeline.analytics.spatial.feeder_zone
            polygon = feeder_zone.polygon_coords if feeder_zone else [[80, 280], [560, 280], [560, 420], [80, 420]]

            # 3. Capture frame and run FeedDetector
            raw_frame = pipeline.source.get_latest_frame()
            inspection: FeedInspectionResult = self.feed_detector.inspect_feeder(raw_frame, polygon)

            alert_generated = False
            # 4. Trigger alert ONLY when feed is verified absent (not when unverified)
            if inspection.status == "MISSED_FEEDING":
                alert_generated = True
                self.alert_engine.trigger_alert(
                    camera_id=camera_id,
                    zone_name=f"{pipeline.name} - {trough_name}",
                    alert_type="FEEDING_MISSED",
                    severity="WARNING",
                    message=f"MISSED FEEDING ALERT: Trough '{trough_name}' empty past scheduled feeding time!",
                    frame=raw_frame,
                    entity_id=session_id,
                    details={
                        "session_id": session_id,
                        "trough_name": trough_name,
                        "inspection": inspection.to_dict()
                    }
                )

            # 5. Persist record
            diag = {
                "inspection": inspection.to_dict(),
                "polygon": polygon
            }
            record = FeedingObservationModel(
                schedule_id=schedule_id,
                session_id=session_id,
                camera_id=camera_id,
                trough_name=trough_name,
                observed_at=observed_at,
                fodder_detected=inspection.fodder_detected,
                status=inspection.status,
                diagnostic_details=json.dumps(diag),
                alert_generated=alert_generated
            )
            db.add(record)
            db.commit()

            return record.to_dict()
        except Exception as e:
            logger.error(f"Error in feeding compliance inspection: {e}", exc_info=True)
            db.rollback()
            raise
        finally:
            db.close()

_feeding_engine_instance: Optional[FeedingEngine] = None

def get_feeding_engine() -> FeedingEngine:
    global _feeding_engine_instance
    if _feeding_engine_instance is None:
        _feeding_engine_instance = FeedingEngine()
    return _feeding_engine_instance
