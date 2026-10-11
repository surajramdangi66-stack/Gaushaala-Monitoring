import cv2
import time
import base64
import threading
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from backend.app.config import DEFAULT_CAMERAS
from backend.app.camera.camera_source import CameraSource
from backend.app.vision.analytics import CameraAnalyticsEngine, FrameAnalysisResult
from backend.app.alerts.alert_engine import get_alert_engine

class CameraPipeline:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.camera_id = config["id"]
        self.name = config["name"]
        self.source = CameraSource(
            camera_id=self.camera_id,
            name=self.name,
            rtsp_url=config.get("rtsp_url", ""),
            fps=config.get("fps", 25)
        )
        self.analytics = CameraAnalyticsEngine(
            camera_id=self.camera_id,
            camera_name=self.name,
            zones_config=config.get("zones", {})
        )
        self.alert_engine = get_alert_engine()
        self.latest_result: Optional[FrameAnalysisResult] = None
        self.latest_processed_frame: Optional[np.ndarray] = None
        self.latest_raw_frame: Optional[np.ndarray] = None
        self.lock = threading.Lock()
        self.is_running = False
        self.worker_thread: Optional[threading.Thread] = None

    def start(self):
        self.source.start()
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._processing_loop, daemon=True, name=f"Pipeline-{self.camera_id}")
        self.worker_thread.start()

    def stop(self):
        self.is_running = False
        self.source.stop()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)

    def _processing_loop(self):
        while self.is_running:
            raw_frame = self.source.get_latest_frame()
            if raw_frame is None:
                time.sleep(0.04)
                continue

            # Process real incoming video frame with YOLOv8
            result = self.analytics.process_frame(raw_frame)

            # Check for Alerts
            # 1. Geofence breach
            for breached_cow in result.breaches_detected:
                self.alert_engine.trigger_alert(
                    camera_id=self.camera_id,
                    zone_name=self.name,
                    alert_type="GEOFENCE_BREACH",
                    severity="CRITICAL",
                    message=f"Cattle #{breached_cow.track_id} breached pen boundary perimeter!",
                    frame=raw_frame,
                    highlight_box=breached_cow.bbox,
                    entity_id=str(breached_cow.track_id),
                    details={"track_id": breached_cow.track_id, "zone": breached_cow.current_zone}
                )

            # 2. Prolonged Inactivity / Prostration
            for prostrated_cow in result.prostrations_detected:
                self.alert_engine.trigger_alert(
                    camera_id=self.camera_id,
                    zone_name=self.name,
                    alert_type="PROSTRATION_DISTRESS",
                    severity="CRITICAL",
                    message=f"Cattle #{prostrated_cow.track_id} prostrated motionless for {int(prostrated_cow.inactivity_duration)}s - check for distress/colic!",
                    frame=raw_frame,
                    highlight_box=prostrated_cow.bbox,
                    entity_id=str(prostrated_cow.track_id),
                    details={"track_id": prostrated_cow.track_id, "duration": prostrated_cow.inactivity_duration}
                )

            # 3. Overcrowding in feed trough
            if result.overcrowding_detected:
                feeder_zone = self.analytics.spatial.feeder_zone
                max_cap = feeder_zone.max_capacity if feeder_zone else 4
                self.alert_engine.trigger_alert(
                    camera_id=self.camera_id,
                    zone_name=self.name,
                    alert_type="FEEDER_OVERCROWDING",
                    severity="WARNING",
                    message=f"Feed trough density alert: {result.feeder_count} cattle crowding (limit: {max_cap})",
                    frame=raw_frame,
                    entity_id="feeder",
                    details={"count": result.feeder_count, "capacity": max_cap}
                )

            # Render frame with overlays
            processed = self._render_overlay_frame(raw_frame, result)

            with self.lock:
                self.latest_raw_frame = raw_frame
                self.latest_processed_frame = processed
                self.latest_result = result

            time.sleep(0.035)

    def _render_overlay_frame(self, frame: np.ndarray, result: FrameAnalysisResult) -> np.ndarray:
        overlay_frame = frame.copy()
        h, w = overlay_frame.shape[:2]

        # 1. Draw Zones (ROIs) with polygon shading
        overlay = overlay_frame.copy()
        for zone in self.analytics.spatial.zones.values():
            pts = np.array(zone.polygon_coords, np.int32).reshape((-1, 1, 2))
            # Convert hex to BGR
            hex_col = zone.color.lstrip('#')
            bgr = tuple(int(hex_col[i:i+2], 16) for i in (4, 2, 0))

            cv2.fillPoly(overlay, [pts], bgr)
            cv2.polylines(overlay_frame, [pts], True, bgr, 2, cv2.LINE_AA)

            # Label zone centroid
            moments = cv2.moments(pts)
            if moments["m00"] != 0:
                zx = int(moments["m10"] / moments["m00"])
                zy = int(moments["m01"] / moments["m00"])
                cv2.putText(overlay_frame, zone.name, (zx - 40, zy), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

        # Blend polygon fill
        cv2.addWeighted(overlay, 0.15, overlay_frame, 0.85, 0, overlay_frame)

        # 2. Draw Cattle Tracks (Bounding Boxes, Tracking IDs, Centroids)
        for track in result.tracks:
            x1, y1, x2, y2 = [int(v) for v in track.bbox]

            # Choose bounding box color:
            # Red if breached, Orange if prostrated, Emerald if active, Blue if resting
            if track.is_breached:
                box_color = (40, 40, 240)    # Critical Red
                status_txt = "BREACH"
            elif track.is_prostrated:
                box_color = (0, 140, 255)    # Orange Caution
                status_txt = f"PROSTRATED ({int(track.inactivity_duration)}s)"
            elif track.activity_state == "resting":
                box_color = (235, 145, 50)   # Sky Blue
                status_txt = f"RESTING ({int(track.inactivity_duration)}s)"
            else:
                box_color = (80, 210, 110)   # Emerald Active
                status_txt = "ACTIVE"

            # Bounding box
            cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), box_color, 2)

            # Centroid point
            cx, cy = int(track.cx), int(track.cy)
            cv2.circle(overlay_frame, (cx, cy), 4, (255, 255, 255), -1)
            cv2.circle(overlay_frame, (cx, cy), 5, box_color, 1)

            # Motion history trail
            if len(track.centroid_history) > 1:
                pts = np.array([(int(p[0]), int(p[1])) for p in track.centroid_history[-10:]], np.int32).reshape((-1, 1, 2))
                cv2.polylines(overlay_frame, [pts], False, box_color, 1, cv2.LINE_AA)

            # Tag label background banner
            label = f"#{track.track_id} {status_txt}"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
            bg_y1 = max(34, y1 - lh - 8)
            cv2.rectangle(overlay_frame, (x1, bg_y1), (x1 + lw + 12, bg_y1 + lh + 8), (15, 18, 22), -1)
            cv2.rectangle(overlay_frame, (x1, bg_y1), (x1 + lw + 12, bg_y1 + lh + 8), box_color, 1)
            cv2.putText(overlay_frame, label, (x1 + 6, bg_y1 + lh + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (240, 240, 240), 1, cv2.LINE_AA)

        # 3. Live HUD stats in corner
        hud_txt = f"CATTLE: {result.total_count} | ACT: {result.active_count} | REST: {result.resting_count}"
        cv2.rectangle(overlay_frame, (w - 280, h - 35), (w - 10, h - 10), (12, 16, 20), -1)
        cv2.rectangle(overlay_frame, (w - 280, h - 35), (w - 10, h - 10), (50, 70, 90), 1)
        cv2.putText(overlay_frame, hud_txt, (w - 270, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 220, 160), 1, cv2.LINE_AA)

        return overlay_frame

    def get_jpeg_frame(self, overlay: bool = True, quality: int = 70) -> Optional[bytes]:
        with self.lock:
            frame = self.latest_processed_frame if overlay else self.latest_raw_frame
            if frame is None:
                return None
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            ret, buf = cv2.imencode('.jpg', frame, encode_param)
            if not ret:
                return None
            return buf.tobytes()

    def get_summary(self) -> Dict[str, Any]:
        with self.lock:
            is_on = self.source.is_online
            total = self.latest_result.total_count if (self.latest_result and is_on) else 0
            active = self.latest_result.active_count if (self.latest_result and is_on) else 0
            resting = self.latest_result.resting_count if (self.latest_result and is_on) else 0
            feeder = self.latest_result.feeder_count if (self.latest_result and is_on) else 0
            has_breach = (len(self.latest_result.breaches_detected) > 0) if (self.latest_result and is_on) else False
            has_prostration = (len(self.latest_result.prostrations_detected) > 0) if (self.latest_result and is_on) else False

            tracks_payload = []
            if self.latest_result and is_on:
                for t in self.latest_result.tracks:
                    tracks_payload.append({
                        "id": t.track_id,
                        "bbox": t.bbox,
                        "cx": round(t.cx, 1),
                        "cy": round(t.cy, 1),
                        "state": t.activity_state,
                        "zone": t.current_zone,
                        "inactivity_sec": round(t.inactivity_duration, 1),
                        "is_prostrated": t.is_prostrated,
                        "is_breached": t.is_breached
                    })

            return {
                "id": self.camera_id,
                "name": self.name,
                "location": self.config.get("location", ""),
                "status": "online" if is_on else "offline",
                "fps": round(self.source.actual_fps, 1),
                "resolution": f"{self.source.width}x{self.source.height}",
                "rtsp_url": self.config.get("rtsp_url", ""),
                "total_cattle": total,
                "active_cattle": active,
                "resting_cattle": resting,
                "feeder_cattle": feeder,
                "has_breach": has_breach,
                "has_prostration": has_prostration,
                "tracks": tracks_payload
            }

class StreamManager:
    _instance = None

    def __init__(self):
        self.pipelines: Dict[str, CameraPipeline] = {}
        for cam_cfg in DEFAULT_CAMERAS:
            pipeline = CameraPipeline(cam_cfg)
            self.pipelines[cam_cfg["id"]] = pipeline

    def start_all(self):
        for p in self.pipelines.values():
            p.start()

    def stop_all(self):
        for p in self.pipelines.values():
            p.stop()

    def get_pipeline(self, camera_id: str) -> Optional[CameraPipeline]:
        return self.pipelines.get(camera_id)

    def add_or_update_camera(self, config: Dict[str, Any]) -> CameraPipeline:
        cam_id = config.get("id")
        if not cam_id:
            cam_id = f"cam-{len(self.pipelines) + 1:02d}"
            config["id"] = cam_id

        if cam_id in self.pipelines:
            self.pipelines[cam_id].stop()

        pipeline = CameraPipeline(config)
        pipeline.start()
        self.pipelines[cam_id] = pipeline
        return pipeline

    def get_all_summaries(self) -> List[Dict[str, Any]]:
        return [p.get_summary() for p in self.pipelines.values()]

    def get_system_metrics(self) -> Dict[str, Any]:
        summaries = self.get_all_summaries()
        total_cattle = sum(s["total_cattle"] for s in summaries)
        total_active = sum(s["active_cattle"] for s in summaries)
        total_resting = sum(s["resting_cattle"] for s in summaries)
        cams_online = sum(1 for s in summaries if s["status"] == "online")
        cams_total = len(summaries)

        zone_breakdown = []
        for s in summaries:
            zone_breakdown.append({
                "camera_id": s["id"],
                "name": s["name"],
                "total": s["total_cattle"],
                "active": s["active_cattle"],
                "resting": s["resting_cattle"],
                "feeder": s["feeder_cattle"],
                "status": s["status"],
                "health": "Alert" if (s["has_breach"] or s["has_prostration"]) else "Normal"
            })

        return {
            "total_cattle": total_cattle,
            "active_cattle": total_active,
            "resting_cattle": total_resting,
            "cameras_online": cams_online,
            "cameras_total": cams_total,
            "system_status": "Optimal" if (cams_online == cams_total) else "Degraded",
            "zones": zone_breakdown,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

_global_stream_manager = None

def get_stream_manager() -> StreamManager:
    global _global_stream_manager
    if _global_stream_manager is None:
        _global_stream_manager = StreamManager()
    return _global_stream_manager
