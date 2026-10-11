import cv2
import time
import threading
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List

class CameraSource:
    """
    Camera Feed Source:
    - Direct RTSP IP stream or local USB webcam ingestion via OpenCV.
    - Only primary node (cam-01) loads live demonstration CCTV feed if no physical webcam is attached.
    - Nodes cam-02, cam-03, cam-04 remain in PAUSED / STANDBY state until physically configured by operator.
    - While in standby, hardware is disconnected and NO alerts are triggered.
    """
    def __init__(self, camera_id: str, name: str, rtsp_url: str, is_simulated: bool = False, fps: int = 25):
        self.camera_id = camera_id
        self.name = name
        self.rtsp_url = rtsp_url
        self.target_fps = fps
        self.width = 1024
        self.height = 572
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_detections: List[Dict[str, Any]] = []
        self.is_online = False
        self.is_connected = False
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
        while self.is_running:
            url_clean = self.rtsp_url.strip() if self.rtsp_url else ""
            
            # Check if physical stream URL is given and openable
            is_physical_stream = False
            cap = None
            if url_clean:
                source_target = int(url_clean) if url_clean.isdigit() else url_clean
                try:
                    cap = cv2.VideoCapture(source_target)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    if cap.isOpened():
                        is_physical_stream = True
                except Exception:
                    is_physical_stream = False

            if is_physical_stream and cap is not None:
                with self.lock:
                    self.is_online = True
                    self.is_connected = True

                fps_timer = time.time()
                frames_in_second = 0

                while self.is_running and cap.isOpened():
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        break

                    h, w = frame.shape[:2]
                    self.width, self.height = w, h
                    now = time.time()
                    frames_in_second += 1
                    if now - fps_timer >= 1.0:
                        self.actual_fps = frames_in_second / (now - fps_timer)
                        frames_in_second = 0
                        fps_timer = now

                    with self.lock:
                        self.latest_frame = frame
                        self.last_frame_time = now

                    time.sleep(0.035)

                cap.release()
                with self.lock:
                    self.is_online = False
                    self.is_connected = False
                    self.actual_fps = 0.0

            # Standby state until hardware stream or video input is connected
            else:
                with self.lock:
                    self.is_online = False
                    self.is_connected = False
                    self.actual_fps = 0.0
                    self.latest_frame = self._render_offline_frame("STANDBY / CAMERA PAUSED")
                time.sleep(1.0)

    def _render_offline_frame(self, reason: str = "STANDBY / CAMERA PAUSED") -> np.ndarray:
        w, h = 640, 360
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:, :] = (18, 20, 24)

        # Subtle clean grid
        for y in range(40, h - 30, 35):
            cv2.line(frame, (15, y), (w - 15, y), (26, 28, 34), 1)
        for x in range(40, w - 30, 40):
            cv2.line(frame, (x, 35), (x, h - 35), (26, 28, 34), 1)

        cx, cy = w // 2, h // 2
        # Clean standby center card
        cv2.rectangle(frame, (cx - 180, cy - 45), (cx + 180, cy + 45), (25, 29, 36), -1)
        cv2.rectangle(frame, (cx - 180, cy - 45), (cx + 180, cy + 45), (48, 54, 66), 1)

        cv2.putText(frame, "CCTV NODE STANDBY (PAUSED)", (cx - 140, cy - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (160, 175, 195), 1, cv2.LINE_AA)
        cv2.putText(frame, "NO HARDWARE STREAM CONNECTED", (cx - 130, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (110, 125, 145), 1, cv2.LINE_AA)
        cv2.putText(frame, "CLICK 'CONNECT CCTV' OR PLAY TO ACTIVATE", (cx - 150, cy + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (85, 160, 220), 1, cv2.LINE_AA)

        # Top Bar
        cv2.rectangle(frame, (0, 0), (w, 28), (12, 14, 18), -1)
        cv2.circle(frame, (16, 14), 4, (120, 120, 120), -1)
        cv2.putText(frame, "STANDBY", (26, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140, 145, 155), 1, cv2.LINE_AA)
        cv2.putText(frame, f"NODE: {self.name.upper()}", (95, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 205, 215), 1, cv2.LINE_AA)

        return frame

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            if self.latest_frame is None:
                return self._render_offline_frame()
            return self.latest_frame.copy()

    def get_latest_detections(self) -> List[Dict[str, Any]]:
        with self.lock:
            return list(self.latest_detections)
