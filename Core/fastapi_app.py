"""
FastAPI Bridge for Parkinox Plate Detection System
Modern API bridge between Flutter UI and YOLOv5 Core
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
import io

from fastapi import FastAPI, File, UploadFile, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import cv2
import numpy as np
import uvicorn

from plate_detector import PlateDetector
from camera_stream_service import CameraManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Parkinox Plate Detection API",
    description="FastAPI bridge for Iranian license plate detection using YOLOv5",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for Flutter
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify Flutter app origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global detector instance
detector: Optional[PlateDetector] = None
camera_manager: Optional[CameraManager] = None


# Pydantic models for request/response
class DetectionResponse(BaseModel):
    """Response model for plate detection"""
    success: bool
    plate: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    char_confidence: float = Field(0.0, ge=0.0, le=1.0)
    num_characters: int = 0
    bbox: list[int] = Field(default_factory=list)
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    models_loaded: bool
    device: Optional[str] = None
    version: str = "1.0.0"


class FilePathRequest(BaseModel):
    """Request model for file path detection"""
    path: str = Field(..., description="Absolute path to image file")


class CameraConfigRequest(BaseModel):
    """IP camera configuration pushed from Flutter settings."""
    entry_enabled: bool = False
    exit_enabled: bool = False
    entry_url: Optional[str] = None
    exit_url: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str
    detail: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Initialize detector on startup"""
    global detector, camera_manager
    try:
        logger.info("="*60)
        logger.info("Parkinox FastAPI - Starting up...")
        logger.info("="*60)
        logger.info("Initializing plate detector...")
        detector = PlateDetector()
        camera_manager = CameraManager(detector)
        camera_manager.set_event_loop(asyncio.get_running_loop())
        logger.info(f"✓ Plate detector initialized on device: {detector.device}")
        logger.info("✓ FastAPI server ready")
    except Exception as e:
        logger.error(f"Failed to initialize detector: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Parkinox FastAPI...")
    if camera_manager is not None:
        camera_manager.shutdown()


@app.get("/", tags=["General"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Parkinox Plate Detection API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """
    Health check endpoint
    
    Returns system status and model loading state
    """
    return HealthResponse(
        status="ok" if detector is not None else "error",
        models_loaded=detector is not None,
        device=detector.device if detector else None
    )


@app.post("/detect", response_model=DetectionResponse, tags=["Detection"])
async def detect_plate(
    image: UploadFile = File(..., description="Image file containing license plate")
):
    """
    Detect Iranian license plate from uploaded image
    
    **Supported formats:** JPG, JPEG, PNG, BMP, WEBP
    
    **Process:**
    1. Detects plate region using plateYolo model
    2. Recognizes characters using CharsYolo model
    3. Formats plate text to standard Iranian format
    
    **Returns:**
    - `success`: Detection status
    - `plate`: Formatted plate text (e.g., "۱۲ ب ۳۴۵ ۶۷")
    - `confidence`: Plate detection confidence (0-1)
    - `char_confidence`: Character recognition confidence (0-1)
    - `num_characters`: Number of detected characters
    - `bbox`: Bounding box coordinates [x1, y1, x2, y2]
    """
    if detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Detector not initialized"
        )
    
    try:
        # Validate file type
        if not image.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type: {image.content_type}. Expected image file."
            )
        
        # Read image bytes
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not decode image. Please upload a valid image file."
            )
        
        logger.info(f"Processing image: {img.shape[1]}x{img.shape[0]} from {image.filename}")
        
        # Detect plate
        plate_text, confidence, metadata = detector.detect(img)
        
        if plate_text:
            response = DetectionResponse(
                success=True,
                plate=plate_text,
                confidence=round(confidence, 3),
                char_confidence=round(metadata.get('char_confidence', 0), 3) if metadata else 0,
                num_characters=len(plate_text.replace(' ', '')),
                bbox=metadata.get('bbox', []) if metadata else [],
                message="Plate detected successfully"
            )
            logger.info(f"✓ Detection successful: {plate_text} (conf: {confidence:.3f})")
            return response
        else:
            response = DetectionResponse(
                success=False,
                message="No plate detected in image"
            )
            logger.info("No plate detected")
            return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during detection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection error: {str(e)}"
        )


@app.post("/detect/file", response_model=DetectionResponse, tags=["Detection"])
async def detect_plate_from_file(request: FilePathRequest):
    """
    Detect plate from file path (for testing/debugging)
    
    **Note:** This endpoint is primarily for server-side testing.
    Flutter apps should use the `/detect` endpoint with file upload.
    
    **Request body:**
    ```json
    {
        "path": "/path/to/image.jpg"
    }
    ```
    """
    if detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Detector not initialized"
        )
    
    try:
        image_path = Path(request.path)
        
        if not image_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.path}"
            )
        
        if not image_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Path is not a file: {request.path}"
            )
        
        logger.info(f"Processing file: {image_path}")
        
        # Detect plate
        plate_text, confidence, metadata = detector.detect_from_file(str(image_path))
        
        if plate_text:
            response = DetectionResponse(
                success=True,
                plate=plate_text,
                confidence=round(confidence, 3),
                char_confidence=round(metadata.get('char_confidence', 0), 3) if metadata else 0,
                num_characters=len(plate_text.replace(' ', '')),
                bbox=metadata.get('bbox', []) if metadata else [],
                message="Plate detected successfully"
            )
            logger.info(f"✓ Detection successful: {plate_text} (conf: {confidence:.3f})")
            return response
        else:
            response = DetectionResponse(
                success=False,
                message="No plate detected in image"
            )
            logger.info("No plate detected")
            return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during detection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection error: {str(e)}"
        )


@app.get("/models/info", tags=["Models"])
async def get_models_info():
    """
    Get information about loaded models
    
    Returns model paths, device, and configuration
    """
    if detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Detector not initialized"
        )
    
    return {
        "plate_model": str(detector.plate_model_path),
        "char_model": str(detector.char_model_path),
        "device": detector.device,
        "conf_threshold": detector.conf_threshold,
        "models_loaded": True
    }


@app.post("/cameras/config", tags=["Cameras"])
async def update_camera_config(config: CameraConfigRequest):
    """Apply entry/exit IP camera RTSP URLs from Flutter settings."""
    if camera_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera manager not initialized",
        )

    camera_manager.apply_config(config.model_dump())
    logger.info(
        "Camera config updated: entry=%s exit=%s",
        config.entry_enabled,
        config.exit_enabled,
    )
    return {"success": True, "status": camera_manager.status()}


@app.get("/cameras/status", tags=["Cameras"])
async def get_camera_status():
    """Current IP camera connection state."""
    if camera_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera manager not initialized",
        )
    return camera_manager.status()


async def _mjpeg_generator(slot: str):
    boundary = b"--frame"
    if camera_manager is None:
        return

    stream = camera_manager.stream_for(slot)
    while stream.enabled:
        jpeg = stream.get_latest_jpeg()
        if jpeg:
            yield (
                boundary
                + b"\r\nContent-Type: image/jpeg\r\n\r\n"
                + jpeg
                + b"\r\n"
            )
        await asyncio.sleep(0.05)


@app.get("/cameras/{slot}/mjpeg", tags=["Cameras"])
async def camera_mjpeg(slot: str):
    """MJPEG preview stream for Flutter operator UI."""
    if slot not in ("entry", "exit"):
        raise HTTPException(status_code=404, detail="Unknown camera slot")
    if camera_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera manager not initialized",
        )

    stream = camera_manager.stream_for(slot)
    if not stream.enabled:
        raise HTTPException(status_code=404, detail="Camera not enabled")

    return StreamingResponse(
        _mjpeg_generator(slot),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Push plate_detected events to Flutter; accept ping/pong."""
    if camera_manager is None:
        await websocket.close(code=1013)
        return

    await camera_manager.add_client(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_text('{"type":"pong"}')
            elif msg_type == "camera_config":
                camera_manager.apply_config(data.get("data", {}))
    except WebSocketDisconnect:
        pass
    finally:
        camera_manager.remove_client(websocket)


if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Parkinox FastAPI - Plate Detection Bridge")
    logger.info("="*60)
    
    # Run with uvicorn
    uvicorn.run(
        "fastapi_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes (disable in production)
        log_level="info"
    )
