"""
FastAPI Bridge for Parkinox Plate Detection System
Modern API bridge between Flutter UI and YOLOv5 Core
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional
import io

# FFmpeg RTSP options must be set before OpenCV loads its FFmpeg backend.
# err_detect;ignore_err recovers from minor H.264 bitstream glitches common on IP cameras.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    (
        "rtsp_transport;tcp|"
        "fflags;nobuffer|"
        "flags;low_delay|"
        "max_delay;0|"
        "reorder_queue_size;0|"
        "err_detect;ignore_err"
    ),
)

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel, Field
import cv2
import numpy as np
import uvicorn

from plate_detector import PlateDetector
from camera_stream_service import CameraManager
from fail_capture import (
    FAIL_TYPE_OCR_EMPTY,
    FAIL_TYPE_OCR_INVALID,
    FailCaptureStore,
    django_ingest_callback_factory,
    get_fail_capture_store,
)
from fail_metrics import fail_metrics
from test_plate_tools import (
    CAMERA_IDS,
    FREE_ZONES,
    build_plate_detected_payload,
    make_random_payload,
    normalize_to_standard,
)
import fail_capture as fail_capture_mod

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
    fail_captured: bool = False
    fail_capture_id: Optional[str] = None
    fail_type: Optional[str] = None


def _capture_upload_detection_fail(
    img: np.ndarray,
    confidence: float,
    metadata: Optional[dict],
    camera_id: str = "entry_camera",
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Persist Type A/B fails from POST /detect into FailCaptureStore (immediate write).

    Returns (captured, capture_id, fail_type).
    """
    if img is None or metadata is None:
        return False, None, None

    store = get_fail_capture_store()
    cam = (camera_id or "entry_camera").strip() or "entry_camera"
    bbox = metadata.get("bbox")

    if metadata.get("rejected") or metadata.get("fail_type") == FAIL_TYPE_OCR_INVALID:
        out = store.submit(
            fail_type=FAIL_TYPE_OCR_INVALID,
            frame=img,
            camera_id=cam,
            raw_ocr=metadata.get("raw_ocr") or metadata.get("raw_text"),
            validation_error=metadata.get("validation_error"),
            plate_confidence=float(confidence or 0.0),
            char_confidence=float(metadata.get("char_confidence") or 0.0),
            bbox=bbox,
            immediate=True,
        )
        capture_id = out.name if out is not None else None
        return out is not None, capture_id, FAIL_TYPE_OCR_INVALID

    if metadata.get("fail_type") == FAIL_TYPE_OCR_EMPTY:
        out = store.submit(
            fail_type=FAIL_TYPE_OCR_EMPTY,
            frame=img,
            camera_id=cam,
            raw_ocr=metadata.get("raw_ocr") or "",
            validation_error=metadata.get("validation_error")
            or "Empty or below-threshold OCR",
            plate_confidence=float(confidence or 0.0),
            char_confidence=float(metadata.get("char_confidence") or 0.0),
            bbox=bbox,
            immediate=True,
        )
        capture_id = out.name if out is not None else None
        return out is not None, capture_id, FAIL_TYPE_OCR_EMPTY

    return False, None, None


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


class InjectPlateRequest(BaseModel):
    """Inject a validated plate_detected event for Flutter testing."""
    plate: str = Field(..., description="Any accepted Iranian plate format")
    camera_id: str = Field(
        "entry_camera",
        description="entry_camera or exit_camera",
    )
    confidence: float = Field(0.95, ge=0.0, le=1.0)
    char_confidence: float = Field(0.92, ge=0.0, le=1.0)


class RandomPlateRequest(BaseModel):
    """Generate a random valid national or free-zone plate and push to Flutter."""
    kind: str = Field(
        "national",
        description="national or free_zone",
    )
    camera_id: str = Field("entry_camera")
    free_zone: Optional[str] = Field(
        None,
        description="Optional free-zone name when kind=free_zone",
    )
    confidence: float = Field(0.95, ge=0.0, le=1.0)


class InjectPlateResponse(BaseModel):
    success: bool
    plate_number: Optional[str] = None
    plate_canonical: Optional[str] = None
    camera_id: Optional[str] = None
    kind: Optional[str] = None
    free_zone: Optional[str] = None
    payload: Optional[dict] = None
    message: Optional[str] = None
    clients: int = 0


class SuccessCaptureFinalizeRequest(BaseModel):
    event_uuid: str
    camera_id: str
    plate: Optional[str] = ""
    direction: Optional[str] = "entry"
    confidence: Optional[float] = None
    detection_event_id: Optional[str] = None
    session_uuid: Optional[str] = None
    gate_event_id: Optional[int] = None


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
        fail_capture_mod.fail_capture_store = FailCaptureStore(
            ingest_callback=django_ingest_callback_factory()
        )
        camera_manager = CameraManager(detector)
        camera_manager.set_event_loop(asyncio.get_running_loop())
        logger.info(f"✓ Plate detector initialized on device: {detector.device}")
        logger.info("✓ Fail capture store ready")
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


@app.get("/debug", tags=["General"], include_in_schema=False)
async def debug_ui():
    """Simple web UI for testing detection without Flutter."""
    path = Path(__file__).parent / "debug_ui.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="debug_ui.html not found")
    return FileResponse(path, media_type="text/html")


@app.get("/test", tags=["General"], include_in_schema=False)
async def test_ui():
    """HTML tester: upload detect + random plate inject to Flutter WebSocket."""
    path = Path(__file__).parent / "test_ui.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="test_ui.html not found")
    return FileResponse(path, media_type="text/html")


@app.get("/", tags=["General"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Parkinox Plate Detection API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "debug_ui": "/debug",
        "test_ui": "/test",
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
    image: UploadFile = File(..., description="Image file containing license plate"),
    camera_id: str = Query(
        "entry_camera",
        description="Camera id for fail-capture / review (entry_camera or exit_camera)",
    ),
):
    """
    Detect Iranian license plate from uploaded image
    
    **Supported formats:** JPG, JPEG, PNG, BMP, WEBP
    
    **Process:**
    1. Detects plate region using plateYolo model
    2. Recognizes characters using CharsYolo model
    3. Formats plate text to standard Iranian format
    
    On invalid/empty OCR (Type A/B), the frame is saved via FailCaptureStore
    and ingested to Django for the operator review panel.
    
    **Returns:**
    - `success`: Detection status
    - `plate`: Formatted plate text (e.g., "۱۲ ب ۳۴۵ ۶۷")
    - `confidence`: Plate detection confidence (0-1)
    - `char_confidence`: Character recognition confidence (0-1)
    - `num_characters`: Number of detected characters
    - `bbox`: Bounding box coordinates [x1, y1, x2, y2]
    - `fail_captured` / `fail_capture_id`: set when a fail was archived for review
    """
    if detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Detector not initialized"
        )
    
    try:
        # Validate file type
        if not image.content_type or not image.content_type.startswith('image/'):
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

        # Type A: invalid format — capture for operator review
        if metadata and metadata.get("rejected"):
            captured, capture_id, fail_type = _capture_upload_detection_fail(
                img, confidence, metadata, camera_id=camera_id
            )
            msg = (
                f"OCR rejected — invalid Iranian plate format: "
                f"{metadata.get('validation_error', 'unknown')}"
            )
            if captured:
                msg += f" · saved for review ({capture_id})"
            return DetectionResponse(
                success=False,
                confidence=round(confidence, 3),
                char_confidence=round(metadata.get("char_confidence", 0), 3),
                bbox=metadata.get("bbox", []) or [],
                message=msg,
                fail_captured=captured,
                fail_capture_id=capture_id,
                fail_type=fail_type,
            )

        # Type B: empty OCR with bbox — capture for operator review
        if metadata and metadata.get("fail_type") == FAIL_TYPE_OCR_EMPTY:
            captured, capture_id, fail_type = _capture_upload_detection_fail(
                img, confidence, metadata, camera_id=camera_id
            )
            msg = "OCR empty / below threshold"
            if captured:
                msg += f" · saved for review ({capture_id})"
            return DetectionResponse(
                success=False,
                confidence=round(float(confidence or 0.0), 3),
                char_confidence=round(
                    float(metadata.get("char_confidence") or 0.0), 3
                ),
                bbox=metadata.get("bbox", []) or [],
                message=msg,
                fail_captured=captured,
                fail_capture_id=capture_id,
                fail_type=fail_type,
            )

        if plate_text:
            try:
                from success_capture import get_success_capture_store
                import uuid as _uuid

                get_success_capture_store().buffer_detection(
                    detection_event_id=str(_uuid.uuid4()),
                    camera_id=camera_id or "entry_camera",
                    plate=plate_text,
                    confidence=float(confidence or 0.0),
                    frame=img,
                    bbox=(metadata or {}).get("bbox"),
                )
            except Exception:
                logger.debug("success buffer on /detect skipped", exc_info=True)
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

        img = cv2.imread(str(image_path))
        plate_text, confidence, metadata = detector.detect(
            img if img is not None else str(image_path)
        )

        if metadata and (
            metadata.get("rejected")
            or metadata.get("fail_type") == FAIL_TYPE_OCR_EMPTY
        ):
            frame = img if img is not None else cv2.imread(str(image_path))
            captured, capture_id, fail_type = False, None, None
            if frame is not None:
                captured, capture_id, fail_type = _capture_upload_detection_fail(
                    frame,
                    confidence,
                    metadata,
                    camera_id="entry_camera",
                )
            if metadata.get("rejected"):
                msg = (
                    f"OCR rejected — invalid Iranian plate format: "
                    f"{metadata.get('validation_error', 'unknown')}"
                )
            else:
                msg = "OCR empty / below threshold"
            if captured:
                msg += f" · saved for review ({capture_id})"
            return DetectionResponse(
                success=False,
                confidence=round(float(confidence or 0.0), 3),
                char_confidence=round(
                    float(metadata.get("char_confidence") or 0.0), 3
                ),
                bbox=metadata.get("bbox", []) or [],
                message=msg,
                fail_captured=captured,
                fail_capture_id=capture_id,
                fail_type=fail_type,
            )

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


@app.post("/success-capture/finalize", tags=["SuccessCapture"])
async def success_capture_finalize(body: SuccessCaptureFinalizeRequest):
    """
    Finalize buffered success frames into parking_media/<date>/<event_uuid>/.

    Called fire-and-forget from Django after gate confirm. Safe if buffer missed.
    """
    from success_capture import get_success_capture_store

    store = get_success_capture_store()
    meta = await asyncio.to_thread(
        store.finalize,
        event_uuid=body.event_uuid,
        camera_id=body.camera_id,
        plate=body.plate or "",
        direction=body.direction or "entry",
        confidence=body.confidence,
        detection_event_id=body.detection_event_id,
        session_uuid=body.session_uuid,
        gate_event_id=body.gate_event_id,
    )
    return {"success": True, "meta": meta}


async def _mjpeg_generator(slot: str):
    boundary = b"--frame"
    if camera_manager is None:
        return

    stream = camera_manager.stream_for(slot)
    last_sent: Optional[bytes] = None
    target_interval_sec = 1.0 / 15.0
    while stream.enabled:
        jpeg = stream.get_latest_preview_jpeg()
        if jpeg and jpeg != last_sent:
            yield (
                boundary
                + b"\r\nContent-Type: image/jpeg\r\n\r\n"
                + jpeg
                + b"\r\n"
            )
            last_sent = jpeg
        await asyncio.sleep(target_interval_sec)


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


@app.post("/cameras/{slot}/capture-miss", tags=["Cameras"])
async def capture_operator_miss(slot: str):
    """
    Type C: operator reports a visible plate that was not detected (no bbox).
    Saves the latest camera frame under data_fails/ for review/training.
    """
    if slot not in ("entry", "exit"):
        raise HTTPException(status_code=404, detail="Unknown camera slot")
    if camera_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera manager not initialized",
        )
    result = camera_manager.capture_miss(slot)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No camera frame available to capture",
        )
    return {"success": True, **result}


@app.get("/metrics/detection-fails", tags=["Metrics"])
async def detection_fail_metrics():
    """In-process counters for fail-capture observability."""
    return {"success": True, "metrics": fail_metrics.snapshot()}


@app.post(
    "/test/inject-plate",
    response_model=InjectPlateResponse,
    tags=["Test"],
)
async def inject_plate(req: InjectPlateRequest):
    """
    Validate an Iranian plate into standard display/canonical form and broadcast
    a ``plate_detected`` WebSocket event so Flutter can exercise the approval UI.
    """
    if camera_manager is None:
        raise HTTPException(status_code=503, detail="Camera manager not ready")
    if req.camera_id not in CAMERA_IDS:
        raise HTTPException(
            status_code=400,
            detail=f"camera_id must be one of {list(CAMERA_IDS)}",
        )
    try:
        display, canonical = normalize_to_standard(req.plate)
        payload = build_plate_detected_payload(
            plate_display=display,
            plate_canonical=canonical,
            camera_id=req.camera_id,
            confidence=req.confidence,
            char_confidence=req.char_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    camera_manager.inject_plate_detected(payload)
    clients = len(getattr(camera_manager, "_ws_clients", set()))
    logger.info(
        "Test inject [%s] %s (%s) → %s WS client(s)",
        req.camera_id,
        display,
        canonical,
        clients,
    )
    return InjectPlateResponse(
        success=True,
        plate_number=display,
        plate_canonical=canonical,
        camera_id=req.camera_id,
        payload=payload,
        message="plate_detected broadcast",
        clients=clients,
    )


@app.post(
    "/test/random-plate",
    response_model=InjectPlateResponse,
    tags=["Test"],
)
async def random_plate(req: RandomPlateRequest):
    """
    Generate a random valid national or free-zone plate (Django standards),
    then push ``plate_detected`` to all WebSocket clients (Flutter).
    """
    if camera_manager is None:
        raise HTTPException(status_code=503, detail="Camera manager not ready")
    if req.camera_id not in CAMERA_IDS:
        raise HTTPException(
            status_code=400,
            detail=f"camera_id must be one of {list(CAMERA_IDS)}",
        )
    kind = (req.kind or "national").strip().lower()
    if kind not in ("national", "free_zone"):
        raise HTTPException(
            status_code=400,
            detail="kind must be 'national' or 'free_zone'",
        )
    try:
        payload = make_random_payload(
            kind,  # type: ignore[arg-type]
            req.camera_id,
            free_zone=req.free_zone,
            confidence=req.confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    camera_manager.inject_plate_detected(payload)
    clients = len(getattr(camera_manager, "_ws_clients", set()))
    logger.info(
        "Test random %s [%s] %s → %s WS client(s)",
        kind,
        req.camera_id,
        payload.get("plate_number"),
        clients,
    )
    return InjectPlateResponse(
        success=True,
        plate_number=payload.get("plate_number"),
        plate_canonical=payload.get("plate_canonical"),
        camera_id=req.camera_id,
        kind=kind,
        free_zone=payload.get("free_zone"),
        payload=payload,
        message="random plate_detected broadcast",
        clients=clients,
    )


@app.get("/test/meta", tags=["Test"])
async def test_meta():
    """Constants for the HTML test UI (letters / free zones / cameras)."""
    return {
        "camera_ids": list(CAMERA_IDS),
        "free_zones": list(FREE_ZONES),
        "formats": {
            "national_display": "۱۲ ب ۳۴۵ ۶۷",
            "national_canonical": "۱۲ب۳۴۵-۶۷",
            "free_zone_display": "۱۷۲۴۳ ۶۶",
            "free_zone_canonical": "۱۷۲۴۳-۶۶",
        },
    }


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
        port=8002,
        reload=True,  # Auto-reload on code changes (disable in production)
        log_level="info"
    )
