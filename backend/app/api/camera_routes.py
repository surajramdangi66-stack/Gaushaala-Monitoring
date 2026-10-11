from fastapi import APIRouter, HTTPException, Depends, Response, Query, Security
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.app.auth import get_current_user, get_user_from_token, security
from backend.app.camera.stream_manager import get_stream_manager

router = APIRouter(prefix="/api/cameras", tags=["Cameras"])

class CameraConfigPayload(BaseModel):
    id: Optional[str] = None
    name: str
    location: Optional[str] = "Main Barn"
    rtsp_url: str
    is_simulated: Optional[bool] = False
    fps: Optional[int] = 25

class ProbeRequest(BaseModel):
    rtsp_url: str

@router.post("/probe")
async def probe_camera_stream(payload: ProbeRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    url = payload.rtsp_url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Stream URL or device index cannot be empty")
    
    if url.startswith("rtsp://simulation"):
        return {"online": True, "resolution": "1920x1080", "fps": 25, "message": "Simulation stream verified"}
    
    import cv2
    target = int(url) if url.isdigit() else url
    cap = cv2.VideoCapture(target)
    if not cap.isOpened():
        return {"online": False, "message": f"Could not connect to stream: {url}"}
    
    ret, frame = cap.read()
    if not ret or frame is None:
        cap.release()
        return {"online": False, "message": "Connected to socket but no video frame returned"}
    
    h, w = frame.shape[:2]
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    cap.release()
    return {
        "online": True,
        "resolution": f"{w}x{h}",
        "fps": round(fps, 1),
        "message": f"Stream online ({w}x{h} @ {fps:.0f} FPS)"
    }

@router.get("", response_model=List[Dict[str, Any]])
async def list_cameras(current_user: Dict[str, Any] = Depends(get_current_user)):
    manager = get_stream_manager()
    return manager.get_all_summaries()

@router.get("/{camera_id}")
async def get_camera_detail(camera_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    manager = get_stream_manager()
    pipeline = manager.get_pipeline(camera_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Camera not found")
    return pipeline.get_summary()

@router.post("")
async def create_or_update_camera(payload: CameraConfigPayload, current_user: Dict[str, Any] = Depends(get_current_user)):
    manager = get_stream_manager()
    cfg = payload.model_dump()
    if not cfg.get("id"):
        cfg["id"] = f"cam-{len(manager.pipelines) + 1:02d}"
    pipeline = manager.add_or_update_camera(cfg)
    return {"message": "Camera configured successfully", "camera": pipeline.get_summary()}

@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(
    camera_id: str,
    overlay: bool = True,
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
):
    user = None
    if credentials:
        user = get_user_from_token(credentials.credentials)
    elif token:
        user = get_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    manager = get_stream_manager()
    pipeline = manager.get_pipeline(camera_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Camera not found")
    jpeg_bytes = pipeline.get_jpeg_frame(overlay=overlay, quality=90)
    if not jpeg_bytes:
        raise HTTPException(status_code=503, detail="Frame not available yet")
    return Response(content=jpeg_bytes, media_type="image/jpeg")

@router.post("/{camera_id}/toggle-yolo")
async def toggle_camera_yolo(camera_id: str, enabled: bool, current_user: Dict[str, Any] = Depends(get_current_user)):
    manager = get_stream_manager()
    pipeline = manager.get_pipeline(camera_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Camera not found")
    pipeline.use_yolo_model = enabled
    return {"message": f"YOLO inference {'enabled' if enabled else 'disabled'} for {camera_id}"}
