import cv2
import time
import threading
import numpy as np
from typing import Optional, Dict, Any, List

class CameraSource:
    """
    Production Camera Feed Source:
    Directly ingests RTSP IP streams, HTTP video feeds, or local USB webcams via OpenCV.
    Provides non-blocking threaded frame extraction and auto-reconnect handling.
    Renders an authentic CCTV signal-loss diagnostic screen when a physical feed is offline.
    """
    def __init__(self, camera_id: str, name: str, rtsp_url: str, is_simulated: bool = False, fps: int = 25):
        self.camera_id = camera_id
        self.name = name
        self.rtsp_url = rtsp_url
        self.target_fps = fps
        self.width = 640
        self.height = 480
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_detections: List[Dict[str, Any]] = []
        self.is_online = False
        self.actual_fps = 0.0
        self.last_frame_time = time.time()
        self.frame_count = 0

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True, name=f"CamThread-{self.camera_id}")
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def _capture_loop(self):
        reconnect_delay = 2.0
        while self.is_running:
            url_clean = self.rtsp_url.strip() if self.rtsp_url else ""
            if not url_clean:
                with self.lock:
                    self.is_online = False
                    self.latest_frame = self._render_offline_frame("NO STREAM URL CONFIGURED")
                time.sleep(1.0)
                continue

            source_target = int(url_clean) if url_clean.isdigit() else url_clean
            cap = cv2.VideoCapture(source_target)

            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            if not cap.isOpened():
                with self.lock:
                    self.is_online = False
                    self.actual_fps = 0.0
                    self.latest_frame = self._render_offline_frame("CONNECTING / FEED OFFLINE")
                time.sleep(reconnect_delay)
                reconnect_delay = min(10.0, reconnect_delay * 1.5)
                continue

            # Stream opened successfully
            reconnect_delay = 2.0
            with self.lock:
                self.is_online = True

            fps_timer = time.time()
            frames_in_second = 0

            while self.is_running and cap.isOpened():
                grabbed = cap.grab()
                if not grabbed:
                    break
                ret, frame = cap.retrieve()
                if not ret or frame is None:
                    break

                # Update resolution dynamically
                h, w = frame.shape[:2]
                self.width = w
                self.height = h

                now = time.time()
                frames_in_second += 1
                if now - fps_timer >= 1.0:
                    self.actual_fps = frames_in_second / (now - fps_timer)
                    frames_in_second = 0
                    fps_timer = now

                with self.lock:
                    self.latest_frame = frame
                    self.last_frame_time = now

            cap.release()
            with self.lock:
                self.is_online = False
                self.actual_fps = 0.0
                self.latest_frame = self._render_offline_frame("SIGNAL LOST / RECONNECTING")
            time.sleep(1.0)

    def _render_offline_frame(self, reason: str = "FEED DISCONNECTED") -> np.ndarray:
        """Renders an authentic CCTV signal loss / test pattern display."""
        w, h = 640, 480
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        # Subtle dark grid CCTV background
        frame[:, :] = (20, 22, 26)
        for y in range(40, h - 40, 30):
            cv2.line(frame, (20, y), (w - 20, y), (28, 30, 36), 1)
        for x in range(40, w - 40, 40):
            cv2.line(frame, (x, 40), (x, h - 40), (28, 30, 36), 1)

        # Central Diagnostic Box
        cx, cy = w // 2, h // 2
        cv2.rectangle(frame, (cx - 190, cy - 55), (cx + 190, cy + 55), (32, 36, 44), -1)
        cv2.rectangle(frame, (cx - 190, cy - 55), (cx + 190, cy + 55), (60, 70, 85), 1)

        # Warning icon/text
        cv2.putText(frame, "CCTV VIDEO LOSS / NO SIGNAL", (cx - 150, cy - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 100, 240), 2, cv2.LINE_AA)
        cv2.putText(frame, f"STATUS: {reason}", (cx - 130, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 190, 205), 1, cv2.LINE_AA)
        cv2.putText(frame, f"TARGET: {self.rtsp_url}", (cx - 130, cy + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (120, 130, 145), 1, cv2.LINE_AA)

        # Top Header Banner
        cv2.rectangle(frame, (0, 0), (w, 32), (12, 14, 18), -1)
        cv2.circle(frame, (18, 16), 5, (50, 50, 180), -1)
        cv2.putText(frame, "OFFLINE", (28, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (140, 140, 160), 1, cv2.LINE_AA)
        cv2.putText(frame, f"NODE: {self.name.upper()}", (95, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)

        time_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, time_str, (w - 180, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 175, 190), 1, cv2.LINE_AA)

        # Bottom Bar
        cv2.putText(frame, "AI PIPELINE STANDBY | CHECK NETWORK / RTSP SETTINGS", (15, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (100, 110, 125), 1, cv2.LINE_AA)

        return frame

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            if self.latest_frame is None:
                return self._render_offline_frame("INITIALIZING")
            return self.latest_frame.copy()

    def get_latest_detections(self) -> List[Dict[str, Any]]:
        with self.lock:
            return list(self.latest_detections)
