import cv2
import time
import base64
import threading
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

import json
import logging
from backend.app.config import DEFAULT_CAMERAS, ZONES_CONFIG_FILE
from backend.app.camera.camera_source import CameraSource
from backend.app.vision.analytics import CameraAnalyticsEngine, FrameAnalysisResult
from backend.app.vision.presence_manager import get_presence_manager
from backend.app.alerts.alert_engine import get_alert_engine

logger = logging.getLogger("gaushala.stream_manager")


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
        self.presence_mgr = get_presence_manager()
        self.latest_result: Optional[FrameAnalysisResult] = None
        self.latest_processed_frame: Optional[np.ndarray] = None
        self.latest_raw_frame: Optional[np.ndarray] = None
        self.latest_jpeg_bytes: Optional[bytes] = None
        self.lock = threading.Lock()
        self.is_running = False
        self.worker_thread: Optional[threading.Thread] = None
        self._loop_counter = 0

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

    def update_zones(self, new_zones: Dict[str, Any]):
        """Dynamically updates spatial zones on the live pipeline without interrupting stream."""
        with self.lock:
            self.config["zones"] = new_zones
            from backend.app.vision.spatial import SpatialAnalytics
            self.analytics.spatial = SpatialAnalytics(new_zones)
            self.analytics.zones_config = new_zones
        logger.info(f"Updated live spatial zones for {self.camera_id}: {list(new_zones.keys())}")

    def get_zones(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.config.get("zones", {}))

    def _processing_loop(self):
        while self.is_running:
            try:
                # 1. Check if hardware is connected to this camera
                # If camera is paused or disconnected from hardware:
                # DO NOT run analytics, DO NOT trigger any alerts, and DO NOT register phantom presence!
                if not self.source.is_connected or not self.source.is_online:
                    raw_frame = self.source.get_latest_frame()
                    with self.lock:
                        self.latest_raw_frame = raw_frame
                        self.latest_processed_frame = raw_frame
                        self.latest_jpeg_bytes = None
                        self.latest_result = None
                    time.sleep(0.5)
                    continue

                raw_frame = self.source.get_latest_frame()
                if raw_frame is None:
                    time.sleep(0.03)
                    continue

                self._loop_counter += 1

                # Process real incoming video frame with YOLOv8 (detecting animals & workers)
                result = self.analytics.process_frame(raw_frame)

                # Sync detections with Cross-Camera Entity Presence Manager
                for track in result.tracks:
                    self.presence_mgr.register_or_update(
                        camera_id=self.camera_id,
                        camera_name=self.name,
                        entity_type=track.entity_type,
                        track_id=track.track_id,
                        label=track.label,
                        breed=track.breed,
                        posture=track.activity_state if not track.is_worker else "standing",
                        bbox=track.bbox
                    )

                # Periodic exit check across cameras (every ~15 frames)
                if self._loop_counter % 15 == 0:
                    self.presence_mgr.reap_exited_sessions()

                # Alerts evaluation (Only triggered when camera has active hardware stream!)
                for breached_cow in result.breaches_detected:
                    self.alert_engine.trigger_alert(
                        camera_id=self.camera_id,
                        zone_name=self.name,
                        alert_type="GEOFENCE_BREACH",
                        severity="CRITICAL",
                        message=f"Cattle #{breached_cow.track_id} ({breached_cow.label}) breached perimeter!",
                        frame=raw_frame,
                        highlight_box=breached_cow.bbox,
                        entity_id=str(breached_cow.track_id),
                        details={"track_id": breached_cow.track_id, "zone": breached_cow.current_zone}
                    )

                for prostrated_cow in result.prostrations_detected:
                    self.alert_engine.trigger_alert(
                        camera_id=self.camera_id,
                        zone_name=self.name,
                        alert_type="PROSTRATION_DISTRESS",
                        severity="CRITICAL",
                        message=f"Cattle #{prostrated_cow.track_id} ({prostrated_cow.label}) motionless for {int(prostrated_cow.inactivity_duration)}s!",
                        frame=raw_frame,
                        highlight_box=prostrated_cow.bbox,
                        entity_id=str(prostrated_cow.track_id),
                        details={"track_id": prostrated_cow.track_id, "duration": prostrated_cow.inactivity_duration}
                    )

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

                # Render frame with clean, professional, uncluttered overlays
                processed = self._render_overlay_frame(raw_frame, result)

                # Pre-encode JPEG once for all WebSocket clients, avoiding repetitive encoding & lock contention
                h, w = processed.shape[:2]
                if w > 960:
                    scale = 960.0 / w
                    stream_frame = cv2.resize(processed, (960, int(h * scale)), interpolation=cv2.INTER_LINEAR)
                else:
                    stream_frame = processed

                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 65]
                ret, buf = cv2.imencode('.jpg', stream_frame, encode_param)
                encoded_bytes = buf.tobytes() if ret else None

                with self.lock:
                    self.latest_raw_frame = raw_frame
                    self.latest_processed_frame = processed
                    self.latest_jpeg_bytes = encoded_bytes
                    self.latest_result = result

            except Exception as e:
                logger.error(f"Error in {self.camera_id} processing loop: {e}", exc_info=True)

            time.sleep(0.035)

    def _render_overlay_frame(self, frame: np.ndarray, result: FrameAnalysisResult) -> np.ndarray:
        """
        Renders a clean, uncluttered, professional security CCTV overlay:
        - NO noisy polygon mesh shading or permanent static trough boxes covering the screen.
        - Only renders clean bounding boxes when an animal or worker is present.
        - Worker: Sleek golden/amber box '[WORKER] Staff #ID'.
        - Animal: Sleek mint/emerald box '[COW] Breed #ID'.
        - Distress: High-visibility red box '[ALERT] #ID'.
        """
        overlay_frame = frame.copy()
        h, w = overlay_frame.shape[:2]

        # Draw detected entities with sleek corner styling
        for track in result.tracks:
            x1, y1, x2, y2 = [int(v) for v in track.bbox]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w - 1, x2), min(h - 1, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            # Classify styling & label
            if track.is_worker or track.entity_type == "worker":
                box_color = (30, 185, 245)      # Warm Golden / Amber (BGR)
                badge_bg = (18, 30, 42)
                badge_txt = f"WORKER #{track.track_id}"
            elif track.is_breached:
                box_color = (40, 40, 240)       # Critical Red
                badge_bg = (15, 15, 45)
                badge_txt = f"ALERT #{track.track_id} (BREACH)"
            elif track.is_prostrated:
                box_color = (0, 140, 255)       # Caution Orange
                badge_bg = (15, 25, 45)
                badge_txt = f"DISTRESS #{track.track_id} ({int(track.inactivity_duration)}s)"
            elif track.activity_state == "resting":
                box_color = (235, 145, 50)      # Sky Blue
                badge_bg = (35, 25, 15)
                badge_txt = f"{track.label} #{track.track_id} (REST)"
            else:
                box_color = (80, 215, 110)      # Crisp Mint Emerald
                badge_bg = (15, 30, 20)
                badge_txt = f"{track.label} #{track.track_id}"

            # 1. Sleek thin bounding box (thickness: 2)
            cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), box_color, 2, cv2.LINE_AA)

            # 2. Corner bracket accents for modern high-tech CCTV look
            corner_len = min(16, (x2 - x1) // 4, (y2 - y1) // 4)
            if corner_len > 4:
                cv2.line(overlay_frame, (x1, y1), (x1 + corner_len, y1), box_color, 3, cv2.LINE_AA)
                cv2.line(overlay_frame, (x1, y1), (x1, y1 + corner_len), box_color, 3, cv2.LINE_AA)
                cv2.line(overlay_frame, (x2, y1), (x2 - corner_len, y1), box_color, 3, cv2.LINE_AA)
                cv2.line(overlay_frame, (x2, y1), (x2, y1 + corner_len), box_color, 3, cv2.LINE_AA)
                cv2.line(overlay_frame, (x1, y2), (x1 + corner_len, y2), box_color, 3, cv2.LINE_AA)
                cv2.line(overlay_frame, (x1, y2), (x1, y2 - corner_len), box_color, 3, cv2.LINE_AA)
                cv2.line(overlay_frame, (x2, y2), (x2 - corner_len, y2), box_color, 3, cv2.LINE_AA)
                cv2.line(overlay_frame, (x2, y2), (x2, y2 - corner_len), box_color, 3, cv2.LINE_AA)

            # 3. Compact pill banner above entity
            (lw, lh), _ = cv2.getTextSize(badge_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
            bg_y1 = max(18, y1 - lh - 7)
            bg_y2 = bg_y1 + lh + 6
            bg_x2 = min(w - 2, x1 + lw + 14)

            cv2.rectangle(overlay_frame, (x1, bg_y1), (bg_x2, bg_y2), badge_bg, -1)
            cv2.rectangle(overlay_frame, (x1, bg_y1), (bg_x2, bg_y2), box_color, 1, cv2.LINE_AA)
            cv2.putText(
                overlay_frame,
                badge_txt,
                (x1 + 6, bg_y1 + lh + 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.44,
                (245, 245, 245),
                1,
                cv2.LINE_AA
            )

        # 4. Top-left Live Entity Count HUD Banner (Cow & Worker counts)
        hud_cow = f"CATTLE: {result.cattle_count}"
        hud_worker = f"WORKERS: {result.worker_count}"
        (cw, ch), _ = cv2.getTextSize(hud_cow, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
        (ww, wh), _ = cv2.getTextSize(hud_worker, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
        badge_w = cw + ww + 40
        badge_h = max(ch, wh) + 14

        cv2.rectangle(overlay_frame, (12, 10), (12 + badge_w, 10 + badge_h), (18, 26, 36), -1)
        cv2.rectangle(overlay_frame, (12, 10), (12 + badge_w, 10 + badge_h), (60, 90, 115), 1, cv2.LINE_AA)

        cv2.putText(overlay_frame, hud_cow, (20, 10 + badge_h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (80, 230, 140), 1, cv2.LINE_AA)
        cv2.putText(overlay_frame, "|", (20 + cw + 8, 10 + badge_h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (140, 160, 180), 1, cv2.LINE_AA)
        cv2.putText(overlay_frame, hud_worker, (20 + cw + 20, 10 + badge_h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (40, 195, 250), 1, cv2.LINE_AA)

        # 5. Minimal discreet top-right watermark
        time_str = time.strftime("%H:%M:%S")
        watermark_txt = f"{self.name} // {time_str}"
        cv2.putText(overlay_frame, watermark_txt, (w - 240, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (170, 185, 200), 1, cv2.LINE_AA)

        return overlay_frame

    def get_jpeg_frame(self, overlay: bool = True, quality: int = 65) -> Optional[bytes]:
        with self.lock:
            if overlay and self.latest_jpeg_bytes is not None:
                return self.latest_jpeg_bytes
            frame = self.latest_processed_frame if overlay else self.latest_raw_frame
            if frame is None:
                return None
            frame_copy = frame.copy()

        h, w = frame_copy.shape[:2]
        if w > 960:
            scale = 960.0 / w
            frame_copy = cv2.resize(frame_copy, (960, int(h * scale)), interpolation=cv2.INTER_LINEAR)
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        ret, buf = cv2.imencode('.jpg', frame_copy, encode_param)
        return buf.tobytes() if ret else None

    def get_summary(self) -> Dict[str, Any]:
        with self.lock:
            is_connected = self.source.is_connected and self.source.is_online
            total = self.latest_result.cattle_count if (self.latest_result and is_connected) else 0
            workers = self.latest_result.worker_count if (self.latest_result and is_connected) else 0
            active = self.latest_result.active_count if (self.latest_result and is_connected) else 0
            resting = self.latest_result.resting_count if (self.latest_result and is_connected) else 0
            feeder = self.latest_result.feeder_count if (self.latest_result and is_connected) else 0
            has_breach = (len(self.latest_result.breaches_detected) > 0) if (self.latest_result and is_connected) else False
            has_prostration = (len(self.latest_result.prostrations_detected) > 0) if (self.latest_result and is_connected) else False

            tracks_payload = []
            if self.latest_result and is_connected:
                for t in self.latest_result.tracks:
                    tracks_payload.append({
                        "id": t.track_id,
                        "type": t.entity_type,
                        "label": t.label,
                        "breed": t.breed,
                        "bbox": t.bbox,
                        "cx": round(t.cx, 1),
                        "cy": round(t.cy, 1),
                        "state": t.activity_state,
                        "zone": t.current_zone,
                        "inactivity_sec": round(t.inactivity_duration, 1),
                        "is_prostrated": t.is_prostrated,
                        "is_breached": t.is_breached,
                        "is_worker": t.is_worker
                    })

            return {
                "id": self.camera_id,
                "name": self.name,
                "location": self.config.get("location", ""),
                "status": "online" if is_connected else "standby",
                "fps": round(self.source.actual_fps, 1) if is_connected else 0.0,
                "resolution": f"{self.source.width}x{self.source.height}",
                "rtsp_url": self.config.get("rtsp_url", ""),
                "total_cattle": total,
                "total_workers": workers,
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
        self.load_persisted_zones()

    def load_persisted_zones(self):
        """Loads custom saved camera zones from disk if present."""
        if ZONES_CONFIG_FILE.exists():
            try:
                with open(ZONES_CONFIG_FILE, "r") as f:
                    data = json.load(f)
                for cam_id, zones in data.items():
                    if cam_id in self.pipelines:
                        self.pipelines[cam_id].update_zones(zones)
                logger.info("Loaded custom camera polygon zones from disk.")
            except Exception as e:
                logger.error(f"Failed to load persisted zones: {e}")

    def save_camera_zones(self, camera_id: str, zones: Dict[str, Any]) -> bool:
        pipeline = self.get_pipeline(camera_id)
        if not pipeline:
            return False
        pipeline.update_zones(zones)
        try:
            current_data = {}
            if ZONES_CONFIG_FILE.exists():
                with open(ZONES_CONFIG_FILE, "r") as f:
                    current_data = json.load(f)
            current_data[camera_id] = zones
            ZONES_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(ZONES_CONFIG_FILE, "w") as f:
                json.dump(current_data, f, indent=2)
            logger.info(f"Successfully saved and persisted polygon zones for {camera_id}.")
            return True
        except Exception as e:
            logger.error(f"Failed to persist camera zones for {camera_id}: {e}")
            return False

    def reset_camera_zones(self, camera_id: str) -> bool:
        default_cfg = next((c for c in DEFAULT_CAMERAS if c["id"] == camera_id), None)
        if not default_cfg:
            return False
        default_zones = default_cfg.get("zones", {})
        return self.save_camera_zones(camera_id, default_zones)

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
        total_workers = sum(s.get("total_workers", 0) for s in summaries)
        total_active = sum(s["active_cattle"] for s in summaries)
        total_resting = sum(s["resting_cattle"] for s in summaries)
        cams_online = sum(1 for s in summaries if s["status"] == "online")
        cams_total = len(summaries)

        zone_breakdown = []
        for s in summaries:
            is_active = (s["status"] == "online")
            zone_breakdown.append({
                "camera_id": s["id"],
                "name": s["name"],
                "total": s["total_cattle"],
                "workers": s.get("total_workers", 0),
                "active": s["active_cattle"],
                "resting": s["resting_cattle"],
                "feeder": s["feeder_cattle"],
                "status": s["status"],
                "health": "Alert" if (s["has_breach"] or s["has_prostration"]) else ("Normal" if is_active else "Standby")
            })

        return {
            "total_cattle": total_cattle,
            "total_workers": total_workers,
            "active_cattle": total_active,
            "resting_cattle": total_resting,
            "cameras_online": cams_online,
            "cameras_total": cams_total,
            "system_status": "Optimal" if (cams_online > 0) else "Standby",
            "zones": zone_breakdown,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }


_global_stream_manager = None

def get_stream_manager() -> StreamManager:
    global _global_stream_manager
    if _global_stream_manager is None:
        _global_stream_manager = StreamManager()
    return _global_stream_manager
