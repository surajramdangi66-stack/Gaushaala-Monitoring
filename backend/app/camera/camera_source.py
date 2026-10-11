import cv2
import time
import math
import random
import threading
import numpy as np
from typing import Optional, Tuple, Dict, Any, List

class SimulatedCattleEntity:
    def __init__(self, id_num: int, start_x: float, start_y: float, breed: str = "gir", behavior: str = "wander"):
        self.id_num = id_num
        self.x = start_x
        self.y = start_y
        self.vx = random.uniform(-0.8, 0.8)
        self.vy = random.uniform(-0.6, 0.6)
        self.breed = breed  # "gir" (reddish/brown with hump), "holstein" (white with black patches), "sahiwal" (light brown)
        self.behavior = behavior  # "wander", "feeder", "resting", "escaper"
        self.w = random.uniform(85, 110)
        self.h = random.uniform(55, 75)
        self.angle = random.uniform(0, 360)
        self.leg_phase = random.uniform(0, 6.28)
        self.tail_phase = random.uniform(0, 6.28)
        self.rest_duration = 0.0
        self.is_lying = (behavior == "resting")

    def update(self, bounds: Tuple[int, int, int, int], feeder_bounds: Tuple[int, int, int, int], dt: float = 0.05):
        self.tail_phase += dt * 3.0
        min_x, min_y, max_x, max_y = bounds

        if self.behavior == "resting":
            self.is_lying = True
            self.rest_duration += dt
            # Subtle breathing movement
            self.w = 95 + 2 * math.sin(self.tail_phase * 0.8)
            self.h = 55 + 1.5 * math.cos(self.tail_phase * 0.8)
            return

        self.is_lying = False
        self.leg_phase += dt * 4.0

        if self.behavior == "feeder":
            # Move towards feeder and stay feeding
            fx_min, fy_min, fx_max, fy_max = feeder_bounds
            target_x = fx_min + (self.id_num * 65) % (fx_max - fx_min - 30) + 15
            target_y = (fy_min + fy_max) / 2.0 + random.uniform(-10, 10)
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.hypot(dx, dy)
            if dist > 8:
                self.x += (dx / dist) * 1.2
                self.y += (dy / dist) * 0.8
            else:
                # Eating animation: head bobbing
                self.x += random.uniform(-0.2, 0.2)
                self.y += random.uniform(-0.2, 0.2)
            return

        if self.behavior == "escaper":
            # Slowly moves past boundary to demonstrate geofence alert!
            self.x += 1.1 * dt * 25
            self.y += 0.3 * dt * 25
            if self.x > max_x + 50:
                self.x = min_x + 60
                self.y = min_y + 120
            return

        # "wander" behavior: roam inside pen
        self.x += self.vx
        self.y += self.vy

        if self.x - self.w / 2 < min_x:
            self.x = min_x + self.w / 2
            self.vx = abs(self.vx)
        elif self.x + self.w / 2 > max_x:
            self.x = max_x - self.w / 2
            self.vx = -abs(self.vx)

        if self.y - self.h / 2 < min_y:
            self.y = min_y + self.h / 2
            self.vy = abs(self.vy)
        elif self.y + self.h / 2 > max_y:
            self.y = max_y - self.h / 2
            self.vy = -abs(self.vy)

        if random.random() < 0.02:
            self.vx = random.uniform(-1.0, 1.0)
            self.vy = random.uniform(-0.8, 0.8)

    def get_bbox(self) -> List[float]:
        return [
            round(self.x - self.w / 2, 1),
            round(self.y - self.h / 2, 1),
            round(self.x + self.w / 2, 1),
            round(self.y + self.h / 2, 1)
        ]

class CameraSource:
    """
    Unified Camera Feed Source:
    Handles real RTSP streams via OpenCV with buffer-flush threading,
    or generates a realistic high-definition Gaushala CCTV simulation.
    """
    def __init__(self, camera_id: str, name: str, rtsp_url: str, is_simulated: bool = True, fps: int = 25):
        self.camera_id = camera_id
        self.name = name
        self.rtsp_url = rtsp_url
        self.is_simulated = is_simulated or rtsp_url.startswith("rtsp://simulation")
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
        self.occlusion_level = 0.0

        # Simulation entities
        self.cattle_entities: List[SimulatedCattleEntity] = []
        self._init_simulation_entities()

    def _init_simulation_entities(self):
        self.cattle_entities = []
        if self.camera_id == "cam-01":
            # Shed A: Mix of cattle at feeder, resting, and wander
            self.cattle_entities.append(SimulatedCattleEntity(101, 150, 320, breed="gir", behavior="feeder"))
            self.cattle_entities.append(SimulatedCattleEntity(102, 230, 330, breed="sahiwal", behavior="feeder"))
            self.cattle_entities.append(SimulatedCattleEntity(103, 310, 325, breed="holstein", behavior="feeder"))
            self.cattle_entities.append(SimulatedCattleEntity(104, 180, 160, breed="gir", behavior="resting"))
            self.cattle_entities.append(SimulatedCattleEntity(105, 420, 200, breed="sahiwal", behavior="wander"))
            self.cattle_entities.append(SimulatedCattleEntity(106, 500, 360, breed="holstein", behavior="wander"))
        elif self.camera_id == "cam-02":
            # Shed B: Overcrowding simulation at feeder trough!
            self.cattle_entities.append(SimulatedCattleEntity(201, 140, 290, breed="gir", behavior="feeder"))
            self.cattle_entities.append(SimulatedCattleEntity(202, 210, 295, breed="gir", behavior="feeder"))
            self.cattle_entities.append(SimulatedCattleEntity(203, 280, 300, breed="sahiwal", behavior="feeder"))
            self.cattle_entities.append(SimulatedCattleEntity(204, 350, 290, breed="holstein", behavior="feeder"))
            self.cattle_entities.append(SimulatedCattleEntity(205, 420, 295, breed="sahiwal", behavior="feeder"))  # 5 in trough = Overcrowding!
            self.cattle_entities.append(SimulatedCattleEntity(206, 490, 180, breed="gir", behavior="wander"))
        elif self.camera_id == "cam-03":
            # Open Paddock: Escaper entity to demonstrate Geofence Breach!
            self.cattle_entities.append(SimulatedCattleEntity(301, 240, 340, breed="sahiwal", behavior="feeder"))
            self.cattle_entities.append(SimulatedCattleEntity(302, 340, 350, breed="gir", behavior="feeder"))
            self.cattle_entities.append(SimulatedCattleEntity(303, 200, 200, breed="holstein", behavior="wander"))
            self.cattle_entities.append(SimulatedCattleEntity(304, 520, 380, breed="gir", behavior="escaper"))  # Escaper!
        elif self.camera_id == "cam-04":
            # Calving & Medical Bay: Prolonged prostration cow (lying motionless)
            self.cattle_entities.append(SimulatedCattleEntity(401, 280, 220, breed="gir", behavior="resting"))  # Prostrated cow!
            self.cattle_entities.append(SimulatedCattleEntity(402, 440, 240, breed="sahiwal", behavior="wander"))
        else:
            for i in range(4):
                self.cattle_entities.append(SimulatedCattleEntity(500 + i, 150 + i * 90, 250, behavior="wander"))

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
        if not self.is_simulated and not self.rtsp_url.startswith("rtsp://simulation"):
            self._run_rtsp_stream()
        else:
            self._run_simulation_stream()

    def _run_rtsp_stream(self):
        """Buffer-free RTSP / IP Camera / USB Webcam reader with auto-reconnect."""
        reconnect_delay = 2.0
        while self.is_running:
            source_target = int(self.rtsp_url) if self.rtsp_url.strip().isdigit() else self.rtsp_url
            cap = cv2.VideoCapture(source_target)
            # Minimize internal buffer to reduce latency
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            if not cap.isOpened():
                with self.lock:
                    self.is_online = False
                # If simulated fallback is enabled, switch to simulation
                if self.is_simulated:
                    print(f">>> RTSP {self.rtsp_url} offline, fallback to simulation for {self.camera_id}")
                    self._run_simulation_stream()
                    return
                time.sleep(reconnect_delay)
                reconnect_delay = min(15.0, reconnect_delay * 1.5)
                continue

            with self.lock:
                self.is_online = True
            reconnect_delay = 2.0

            fps_timer = time.time()
            frames_in_second = 0

            while self.is_running and cap.isOpened():
                grabbed = cap.grab()
                if not grabbed:
                    break
                ret, frame = cap.retrieve()
                if not ret or frame is None:
                    break

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
            time.sleep(1.0)

    def _run_simulation_stream(self):
        """Generates realistic Gaushala CCTV video frames."""
        with self.lock:
            self.is_online = True

        dt = 1.0 / self.target_fps
        fps_timer = time.time()
        frames_in_second = 0

        while self.is_running:
            frame_start = time.time()

            # Render realistic Gaushala CCTV frame
            frame = self._render_gaushala_frame()

            # Update entities
            pen_bounds = (60, 80, 580, 430)
            feeder_bounds = (90, 260, 550, 410)
            detections = []

            for cow in self.cattle_entities:
                cow.update(pen_bounds, feeder_bounds, dt=dt)
                bbox = cow.get_bbox()
                detections.append({
                    "bbox": bbox,
                    "conf": 0.94,
                    "class_id": 19,
                    "class_name": "cattle",
                    "sim_id": cow.id_num,
                    "behavior": cow.behavior
                })

            frames_in_second += 1
            now = time.time()
            if now - fps_timer >= 1.0:
                self.actual_fps = frames_in_second / (now - fps_timer)
                frames_in_second = 0
                fps_timer = now

            with self.lock:
                self.latest_frame = frame
                self.latest_detections = detections
                self.last_frame_time = now

            elapsed = time.time() - frame_start
            sleep_time = max(0.005, dt - elapsed)
            time.sleep(sleep_time)

    def _render_gaushala_frame(self) -> np.ndarray:
        w, h = self.width, self.height
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        # 1. Base Barn Floor (Warm earth, straw and concrete textures)
        # Deep earthy/straw tone: BGR (75, 95, 115) to (60, 75, 90)
        frame[:, :] = (65, 80, 95)

        # Draw concrete / alley walkways
        cv2.rectangle(frame, (0, 0), (w, 70), (45, 50, 55), -1)
        cv2.rectangle(frame, (0, h - 50), (w, h), (40, 45, 50), -1)

        # Straw bedding texture lines
        for y_line in range(80, h - 60, 24):
            cv2.line(frame, (40, y_line), (w - 40, y_line), (55, 70, 85), 1)

        # Feeder Trough structure (Wooden trough with fresh green fodder/chaff)
        # BGR green fodder: (35, 110, 60), trough rim: (50, 70, 110)
        cv2.rectangle(frame, (80, 275), (560, 415), (40, 65, 90), 3)
        cv2.rectangle(frame, (83, 278), (557, 412), (35, 95, 60), -1)  # Green fodder bed
        cv2.putText(frame, "FEEDER TROUGH BAY", (95, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 210, 150), 1, cv2.LINE_AA)

        # Wooden fence posts along pen border
        for x_post in range(50, w - 40, 90):
            cv2.rectangle(frame, (x_post - 4, 60), (x_post + 4, h - 50), (30, 42, 60), -1)
            cv2.circle(frame, (x_post, 65), 5, (20, 30, 45), -1)

        # Barn structural roof rafters perspective lines
        cv2.line(frame, (0, 0), (140, 70), (30, 35, 40), 4)
        cv2.line(frame, (w, 0), (w - 140, 70), (30, 35, 40), 4)
        cv2.line(frame, (w // 2, 0), (w // 2, 70), (35, 40, 45), 3)

        # 2. Render Each Cattle Figure
        for cow in self.cattle_entities:
            cx, cy = int(cow.x), int(cow.y)
            cw, ch = int(cow.w), int(cow.h)

            # Palette per breed
            if cow.breed == "gir":
                body_color = (45, 75, 155)    # Gir warm reddish-brown
                belly_color = (70, 110, 190)
                horn_color = (200, 215, 225)
            elif cow.breed == "holstein":
                body_color = (230, 235, 240)  # White body
                belly_color = (200, 205, 210)
                horn_color = (120, 120, 120)
            else:
                body_color = (75, 120, 160)   # Sahiwal light caramel
                belly_color = (100, 150, 195)
                horn_color = (180, 190, 200)

            # Drop shadow under cow
            cv2.ellipse(frame, (cx, cy + ch // 2 - 2), (cw // 2 + 6, 12), 0, 0, 360, (20, 25, 30), -1)

            if cow.is_lying:
                # Cattle lying down (compact resting posture)
                cv2.ellipse(frame, (cx, cy), (cw // 2, ch // 2), 0, 0, 360, body_color, -1)
                # Head resting forward
                head_x = cx + int(cw * 0.38)
                head_y = cy - 4
                cv2.ellipse(frame, (head_x, head_y), (14, 11), 15, 0, 360, belly_color, -1)
                # Curved Horns
                cv2.ellipse(frame, (head_x - 2, head_y - 12), (7, 4), -30, 0, 180, horn_color, 2)
            else:
                # Cattle standing / walking
                # Legs
                leg_offset = math.sin(cow.leg_phase) * 6
                # 4 Legs
                cv2.line(frame, (cx - cw // 3, cy + ch // 3), (cx - cw // 3 + int(leg_offset), cy + ch // 2 + 8), (25, 45, 80), 4)
                cv2.line(frame, (cx - cw // 4, cy + ch // 3), (cx - cw // 4 - int(leg_offset), cy + ch // 2 + 8), (25, 45, 80), 4)
                cv2.line(frame, (cx + cw // 4, cy + ch // 3), (cx + cw // 4 - int(leg_offset), cy + ch // 2 + 8), (25, 45, 80), 4)
                cv2.line(frame, (cx + cw // 3, cy + ch // 3), (cx + cw // 3 + int(leg_offset), cy + ch // 2 + 8), (25, 45, 80), 4)

                # Torso Body
                cv2.ellipse(frame, (cx, cy), (cw // 2, ch // 2), 0, 0, 360, body_color, -1)
                # Distinctive Gir Hump (Zebu hump)
                cv2.ellipse(frame, (cx + int(cw * 0.15), cy - int(ch * 0.38)), (14, 10), -10, 0, 360, body_color, -1)

                # Head and Neck
                head_x = cx + int(cw * 0.42)
                head_y = cy - int(ch * 0.15)
                cv2.ellipse(frame, (head_x, head_y), (16, 13), 20, 0, 360, belly_color, -1)
                # Horns
                cv2.ellipse(frame, (head_x - 3, head_y - 14), (8, 5), -20, 0, 180, horn_color, 2)
                cv2.ellipse(frame, (head_x + 5, head_y - 14), (8, 5), 20, 0, 180, horn_color, 2)
                # Drooping Gir Ears
                cv2.ellipse(frame, (head_x - 6, head_y + 4), (10, 4), 60, 0, 360, belly_color, -1)

                # Holstein Black patches if holstein
                if cow.breed == "holstein":
                    cv2.ellipse(frame, (cx - 10, cy - 5), (14, 10), 30, 0, 360, (30, 30, 30), -1)
                    cv2.ellipse(frame, (cx + 15, cy + 6), (12, 8), -20, 0, 360, (30, 30, 30), -1)

                # Swishing tail
                tail_end_x = cx - int(cw * 0.5) - int(math.sin(cow.tail_phase) * 8)
                tail_end_y = cy + int(ch * 0.25)
                cv2.line(frame, (cx - int(cw * 0.45), cy - 2), (tail_end_x, tail_end_y), (35, 45, 60), 2)

        # 3. Authentic CCTV Metadata Overlay Banner
        # Top banner with camera name, live indicator, timestamp
        cv2.rectangle(frame, (0, 0), (w, 32), (10, 14, 18), -1)
        # Blinking REC dot
        if int(time.time() * 2) % 2 == 0:
            cv2.circle(frame, (18, 16), 5, (0, 0, 230), -1)
        cv2.putText(frame, "REC", (28, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.putText(frame, f"CAM: {self.name.upper()}", (75, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (240, 240, 240), 1, cv2.LINE_AA)

        # Real-time ISO Clock
        current_time_str = time.strftime("%Y-%m-%d  %H:%M:%S")
        cv2.putText(frame, current_time_str, (w - 200, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 220, 240), 1, cv2.LINE_AA)

        # Bottom subtle latency & resolution stamp
        cv2.putText(frame, f"FPS: {self.actual_fps:.1f} | 1080p-HQ RTSP", (15, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140, 160, 180), 1, cv2.LINE_AA)

        return frame

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def get_latest_detections(self) -> List[Dict[str, Any]]:
        with self.lock:
            return list(self.latest_detections)
