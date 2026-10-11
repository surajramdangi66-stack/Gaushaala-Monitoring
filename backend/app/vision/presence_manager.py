import time
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime

class EntitySession:
    def __init__(
        self,
        session_id: str,
        entity_type: str,  # "worker" | "animal"
        entity_id: str,    # e.g. "WRK-01" or "COW-104"
        label: str,        # e.g. "Worker (Gaushala Staff)" or "Gir Cow"
        breed: str,        # e.g. "Gir", "Sahiwal", "Worker"
        camera_id: str,
        camera_name: str,
        entry_time_epoch: float,
        posture: str = "standing",
        bbox: Optional[List[float]] = None
    ):
        self.session_id = session_id
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.label = label
        self.breed = breed
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.entry_time_epoch = entry_time_epoch
        self.entry_time = datetime.fromtimestamp(entry_time_epoch).strftime("%Y-%m-%d %H:%M:%S")
        self.last_seen_epoch = entry_time_epoch
        self.last_seen_time = self.entry_time
        self.exit_time_epoch: Optional[float] = None
        self.exit_time: Optional[str] = None
        self.status = "INSIDE"  # "INSIDE" or "EXITED"
        self.duration_seconds = 0.0
        self.posture = posture
        self.bbox = bbox or []

    def update_presence(self, camera_id: str, camera_name: str, posture: str = "standing", bbox: Optional[List[float]] = None):
        now = time.time()
        self.last_seen_epoch = now
        self.last_seen_time = datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S")
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.posture = posture
        if bbox:
            self.bbox = bbox
        self.duration_seconds = round(now - self.entry_time_epoch, 1)

    def mark_exited(self, exit_epoch: Optional[float] = None):
        if self.status == "EXITED":
            return
        exit_time_val = exit_epoch or self.last_seen_epoch
        self.exit_time_epoch = exit_time_val
        self.exit_time = datetime.fromtimestamp(exit_time_val).strftime("%Y-%m-%d %H:%M:%S")
        self.status = "EXITED"
        self.duration_seconds = max(1.0, round(exit_time_val - self.entry_time_epoch, 1))

    def to_dict(self) -> Dict[str, Any]:
        duration_fmt = self._format_duration(self.duration_seconds)
        return {
            "session_id": self.session_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "label": self.label,
            "breed": self.breed,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "entry_time": self.entry_time,
            "last_seen_time": self.last_seen_time,
            "exit_time": self.exit_time or "Present (Inside)",
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "duration_formatted": duration_fmt,
            "posture": self.posture,
            "bbox": self.bbox
        }

    @staticmethod
    def _format_duration(sec: float) -> str:
        s = int(sec)
        if s < 60:
            return f"{s}s"
        m = s // 60
        rem_s = s % 60
        if m < 60:
            return f"{m}m {rem_s}s"
        h = m // 60
        rem_m = m % 60
        return f"{h}h {rem_m}m"


class EntityPresenceManager:
    """
    Cross-Camera Entity Presence & Session Manager.
    - Prevents duplicate detection logs while an entity remains in view across CCTV feeds.
    - Tracks exact Entry Time and Exit Time for Workers and Animals.
    - Closes sessions only after complete departure from all CCTV cameras.
    - Re-detects with a fresh entry time when the entity re-enters later.
    """
    _instance = None

    def __init__(self, exit_timeout_seconds: float = 6.0):
        self.exit_timeout_seconds = exit_timeout_seconds
        self.lock = threading.Lock()
        
        # Key: (camera_id, entity_type, track_id) -> EntitySession
        self.active_sessions: Dict[str, EntitySession] = {}
        
        # Completed sessions log (ordered newest first, up to 200 items)
        self.history_sessions: List[EntitySession] = []
        
        self.total_entries_today = 0
        self.session_counter = 1000

    @classmethod
    def get_instance(cls) -> "EntityPresenceManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _generate_entity_id(self, entity_type: str, track_id: int) -> str:
        prefix = "WRK" if entity_type == "worker" else "COW"
        return f"{prefix}-{track_id}"

    def register_or_update(
        self,
        camera_id: str,
        camera_name: str,
        entity_type: str,     # "worker" | "animal"
        track_id: int,
        label: str,
        breed: str = "",
        posture: str = "standing",
        bbox: Optional[List[float]] = None
    ) -> EntitySession:
        """
        Idempotent detection registration:
        - If already visible in this camera or transitioning across cameras: update timestamp without duplicating.
        - If new or returning after exit: register brand new session with current entry time.
        """
        now = time.time()
        track_key = f"{camera_id}:{entity_type}:{track_id}"
        
        with self.lock:
            # 1. Check if active session already exists for this track in this camera
            if track_key in self.active_sessions:
                session = self.active_sessions[track_key]
                session.update_presence(camera_id, camera_name, posture, bbox)
                return session

            # 2. Check cross-camera migration: same entity type & track appearing in adjacent camera within 3 seconds
            for k, existing in list(self.active_sessions.items()):
                if existing.entity_type == entity_type and existing.entity_id == self._generate_entity_id(entity_type, track_id):
                    if (now - existing.last_seen_epoch) < 4.0:
                        # Migrate existing session to new camera
                        del self.active_sessions[k]
                        existing.update_presence(camera_id, camera_name, posture, bbox)
                        self.active_sessions[track_key] = existing
                        return existing

            # 3. New Entry detected! Create fresh session
            self.session_counter += 1
            session_id = f"SES-{self.session_counter}"
            entity_id = self._generate_entity_id(entity_type, track_id)
            
            clean_label = label or ("Worker (Staff)" if entity_type == "worker" else "Indigenous Cattle")
            clean_breed = breed or ("Worker" if entity_type == "worker" else "Desi Breed")

            new_session = EntitySession(
                session_id=session_id,
                entity_type=entity_type,
                entity_id=entity_id,
                label=clean_label,
                breed=clean_breed,
                camera_id=camera_id,
                camera_name=camera_name,
                entry_time_epoch=now,
                posture=posture,
                bbox=bbox
            )

            self.active_sessions[track_key] = new_session
            self.total_entries_today += 1
            return new_session

    def reap_exited_sessions(self) -> List[EntitySession]:
        """
        Identifies entities that have completely disappeared from CCTV cameras (> exit_timeout_seconds).
        Marks them as EXITED and moves them to history.
        """
        now = time.time()
        exited: List[EntitySession] = []

        with self.lock:
            dead_keys = []
            for k, session in self.active_sessions.items():
                if (now - session.last_seen_epoch) > self.exit_timeout_seconds:
                    session.mark_exited(session.last_seen_epoch)
                    exited.append(session)
                    dead_keys.append(k)

            for k in dead_keys:
                session = self.active_sessions.pop(k)
                self.history_sessions.insert(0, session)

            # Cap history at 200 records
            if len(self.history_sessions) > 200:
                self.history_sessions = self.history_sessions[:200]

        return exited

    def get_live_data(self) -> Dict[str, Any]:
        """Returns consolidated real-time detection telemetry for Home Quick Access."""
        self.reap_exited_sessions()

        with self.lock:
            inside_list = [s.to_dict() for s in self.active_sessions.values()]
            history_list = [s.to_dict() for s in self.history_sessions[:50]]

            active_workers = sum(1 for s in self.active_sessions.values() if s.entity_type == "worker")
            active_animals = sum(1 for s in self.active_sessions.values() if s.entity_type == "animal")

            # Recent detections: active ones first, followed by recent exits
            all_recent = inside_list + history_list[:30]

            return {
                "active_count": len(inside_list),
                "active_workers": active_workers,
                "active_animals": active_animals,
                "total_entries_today": self.total_entries_today,
                "inside": inside_list,
                "recent_events": all_recent[:40]
            }

    def clear_history(self):
        with self.lock:
            self.history_sessions.clear()
            self.total_entries_today = len(self.active_sessions)


def get_presence_manager() -> EntityPresenceManager:
    return EntityPresenceManager.get_instance()
