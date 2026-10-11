import asyncio
import json
import base64
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.app.auth import decode_token
from backend.app.camera.stream_manager import get_stream_manager
from backend.app.alerts.alert_engine import get_alert_engine
from backend.app.vision.presence_manager import get_presence_manager

logger = logging.getLogger("gaushala.websocket")
router = APIRouter(tags=["WebSockets"])

# Connected telemetry clients
telemetry_clients: Set[WebSocket] = set()

@router.websocket("/ws/stream/{camera_id}")
async def websocket_camera_stream(
    websocket: WebSocket,
    camera_id: str,
    token: str = Query(None)
):
    # Authenticate token if provided
    if token:
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    manager = get_stream_manager()
    pipeline = manager.get_pipeline(camera_id)

    if not pipeline:
        await websocket.send_json({"error": f"Camera {camera_id} not found"})
        await websocket.close(code=1000)
        return

    overlay_enabled = True
    frame_quality = 65

    # Task to handle incoming control messages from client
    async def listen_controls():
        nonlocal overlay_enabled, frame_quality
        try:
            while True:
                msg_text = await websocket.receive_text()
                try:
                    data = json.loads(msg_text)
                    if "overlay" in data:
                        overlay_enabled = bool(data["overlay"])
                    if "quality" in data:
                        frame_quality = max(30, min(95, int(data["quality"])))
                except Exception:
                    pass
        except Exception:
            pass

    control_task = asyncio.create_task(listen_controls())

    try:
        while True:
            # Send latest JPEG frame at ~18-20 FPS (every 50ms)
            jpeg_bytes = pipeline.get_jpeg_frame(overlay=overlay_enabled, quality=frame_quality)
            if jpeg_bytes:
                b64_frame = base64.b64encode(jpeg_bytes).decode('utf-8')
                summary = pipeline.get_summary()

                payload = {
                    "camera_id": camera_id,
                    "frame": f"data:image/jpeg;base64,{b64_frame}",
                    "overlay": overlay_enabled,
                    "fps": summary["fps"],
                    "total": summary["total_cattle"],
                    "active": summary["active_cattle"],
                    "resting": summary["resting_cattle"],
                    "tracks": summary["tracks"],
                    "status": summary["status"]
                }
                await websocket.send_json(payload)

            await asyncio.sleep(0.048)  # ~20 FPS streaming rate
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"Stream WS error for {camera_id}: {e}")
    finally:
        control_task.cancel()

@router.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket, token: str = Query(None)):
    if token:
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    telemetry_clients.add(websocket)
    manager = get_stream_manager()
    alert_engine = get_alert_engine()
    last_alert_id = None

    try:
        while True:
            metrics = manager.get_system_metrics()

            # Check for latest alert to push immediately
            latest_alerts = alert_engine.get_alerts(limit=5)
            new_alert = None
            if latest_alerts:
                current_top_id = latest_alerts[0]["id"]
                if current_top_id != last_alert_id:
                    new_alert = latest_alerts[0]
                    last_alert_id = current_top_id

            # Fetch latest census record & active herd count
            census_summary = None
            try:
                from backend.app.db.database import SessionLocal
                from backend.app.db.models import CensusRecordModel, CattleModel
                db = SessionLocal()
                try:
                    latest_rec = db.query(CensusRecordModel).order_by(CensusRecordModel.executed_at.desc()).first()
                    active_cattle_count = db.query(CattleModel).filter(CattleModel.status == "active").count()
                    census_summary = {
                        "registered_herd": active_cattle_count,
                        "latest_status": latest_rec.status if latest_rec else "PENDING",
                        "expected_count": latest_rec.expected_count if latest_rec else active_cattle_count,
                        "detected_count": latest_rec.detected_count if latest_rec else None,
                        "difference": latest_rec.difference if latest_rec else 0,
                        "last_executed_at": latest_rec.executed_at if latest_rec else None,
                        "scheduled_time": latest_rec.scheduled_time if latest_rec else None
                    }
                finally:
                    db.close()
            except Exception:
                pass

            payload = {
                "type": "telemetry",
                "metrics": metrics,
                "latest_alert": new_alert,
                "census": census_summary,
                "detections": get_presence_manager().get_live_data()
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1.0)  # Telemetry pulse every 1 second
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"Telemetry WS error: {e}")
    finally:
        telemetry_clients.discard(websocket)
