import os
from pathlib import Path
from pydantic import BaseModel
from typing import List, Dict, Any
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

SNAPSHOT_DIR = BASE_DIR / "data" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Groq AI Automation Settings
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

# JWT Settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "gaushala_smart_cctv_ai_secret_key_2026_secured")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Default Admin User
DEFAULT_USERS = {
    "admin": {
        "username": "admin",
        "full_name": "Gaushala Chief Veterinarian & Supervisor",
        # Default password: gaushala2026
        "password_hash": "gaushala2026",
        "role": "admin"
    },
    "operator": {
        "username": "operator",
        "full_name": "CCTV Control Room Operator",
        "password_hash": "operator123",
        "role": "operator"
    }
}

# Pre-configured Gaushala Camera Feeds
DEFAULT_CAMERAS: List[Dict[str, Any]] = [
    {
        "id": "cam-01",
        "name": "Main Enclosure - North Pen",
        "location": "North Wing, Barn 1",
        "rtsp_url": "0",  # Default USB/Local CCTV Camera 0
        "status": "offline",
        "resolution": "1280x720",
        "fps": 25,
        "zones": {
            "feeder": {
                "name": "Feeder Trough A",
                "polygon": [[80, 280], [560, 280], [560, 420], [80, 420]],
                "max_capacity": 4,
                "color": "#10b981"
            },
            "boundary": {
                "name": "Pen Geofence",
                "polygon": [[40, 60], [600, 60], [600, 450], [40, 450]],
                "color": "#ef4444"
            },
            "resting": {
                "name": "Resting Bay 1",
                "polygon": [[50, 70], [320, 70], [320, 260], [50, 260]],
                "color": "#3b82f6"
            }
        }
    },
    {
        "id": "cam-02",
        "name": "Shed B - Feeder Bay",
        "location": "East Wing, Barn 2",
        "rtsp_url": "",
        "status": "offline",
        "resolution": "1920x1080",
        "fps": 25,
        "zones": {
            "feeder": {
                "name": "Feeder Trough B",
                "polygon": [[100, 240], [540, 240], [540, 400], [100, 400]],
                "max_capacity": 5,
                "color": "#10b981"
            },
            "boundary": {
                "name": "Pen Geofence",
                "polygon": [[30, 40], [610, 40], [610, 450], [30, 450]],
                "color": "#ef4444"
            }
        }
    },
    {
        "id": "cam-03",
        "name": "Open Paddock / Yard",
        "location": "South Yard Grazing Area",
        "rtsp_url": "",
        "status": "offline",
        "resolution": "1920x1080",
        "fps": 25,
        "zones": {
            "feeder": {
                "name": "Water Trough & Salt Lick",
                "polygon": [[180, 300], [460, 300], [460, 430], [180, 430]],
                "max_capacity": 3,
                "color": "#10b981"
            },
            "boundary": {
                "name": "Paddock Perimeter Fence",
                "polygon": [[40, 50], [600, 50], [600, 440], [40, 440]],
                "color": "#ef4444"
            }
        }
    },
    {
        "id": "cam-04",
        "name": "Calving & Medical Bay",
        "location": "Quarantine & Care Center",
        "rtsp_url": "",
        "status": "offline",
        "resolution": "1920x1080",
        "fps": 25,
        "zones": {
            "resting": {
                "name": "Medical Observation Bed",
                "polygon": [[120, 140], [520, 140], [520, 380], [120, 380]],
                "color": "#3b82f6"
            },
            "boundary": {
                "name": "Sanitary Quarantine Perimeter",
                "polygon": [[50, 60], [590, 60], [590, 430], [50, 430]],
                "color": "#ef4444"
            }
        }
    }
]

# AI Detection Parameters
YOLO_MODEL_PATH = str(BASE_DIR / "yolov8n.pt")
COCO_COW_CLASS_ID = 19
DETECTION_CONF_THRESHOLD = 0.35
IOU_TRACKER_THRESHOLD = 0.45

# Alert Engine Constraints
PROLONGED_INACTIVITY_THRESHOLD_SECONDS = 18.0  # Demonstrable prostration threshold in demo/runtime
OVERCROWDING_THRESHOLD_DEFAULT = 4
ALERT_THROTTLE_SECONDS = 8.0  # Prevent duplicate alert spamming for same event
