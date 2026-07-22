"""
Plate Detector Module - YOLOv5-based license plate detection
Extracted from legacy code for standalone use
"""
import sys
import re
import logging
from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np
import torch

from plate_validator import validate_detection_plate, to_operator_display

logger = logging.getLogger(__name__)

# Downscale large RTSP frames before YOLO — main stream (101) is often 1080p+.
MAX_INFERENCE_EDGE = 1280
CHAR_PLATE_SIZE = (320, 80)

# Add yolov5 to path
YOLOV5_PATH = Path(__file__).parent.parent / "yolov5"
if YOLOV5_PATH.exists() and str(YOLOV5_PATH) not in sys.path:
    sys.path.insert(0, str(YOLOV5_PATH))


class PlateDetector:
    """
    License plate detection using YOLOv5 models.
    
    Uses two-stage detection:
    1. plateYolo.pt - Detects plate region in full image
    2. CharsYolo.pt - Recognizes characters in cropped plate
    
    Example:
        detector = PlateDetector()
        plate_text, confidence = detector.detect("image.jpg")
        print(f"Plate: {plate_text}, Confidence: {confidence:.2f}")
    """
    
    def __init__(
        self,
        plate_model_path: Optional[str] = None,
        char_model_path: Optional[str] = None,
        device: str = "auto",
        conf_threshold: float = 0.5,
    ):
        """
        Initialize plate detector.
        
        Args:
            plate_model_path: Path to plateYolo.pt (default: ../operator_panel/models/plateYolo.pt)
            char_model_path: Path to CharsYolo.pt (default: ../operator_panel/models/CharsYolo.pt)
            device: Device to use - "auto", "cuda", or "cpu"
            conf_threshold: Minimum confidence for detections
        """
        # Set device
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        # Set model paths (check local models dir first, then operator_panel)
        local_models = Path(__file__).parent / "models"
        operator_models = Path(__file__).parent.parent / "operator_panel" / "models"
        
        if not plate_model_path:
            if (local_models / "plateYolo.pt").exists():
                self.plate_model_path = local_models / "plateYolo.pt"
            else:
                self.plate_model_path = operator_models / "plateYolo.pt"
        else:
            self.plate_model_path = Path(plate_model_path)
        
        if not char_model_path:
            if (local_models / "CharsYolo.pt").exists():
                self.char_model_path = local_models / "CharsYolo.pt"
            else:
                self.char_model_path = operator_models / "CharsYolo.pt"
        else:
            self.char_model_path = Path(char_model_path)
        
        self.conf_threshold = conf_threshold
        self.plate_model = None
        self.char_model = None
        
        # Load models
        self._load_models()
    
    def _load_models(self):
        """Load YOLO models using legacy approach"""
        try:
            logger.info(f"Loading plate detection model from: {self.plate_model_path}")
            self.plate_model = torch.hub.load(
                str(YOLOV5_PATH),
                "custom",
                path=str(self.plate_model_path),
                source="local",
            )
            self.plate_model.to(self.device)
            self.plate_model.eval()
            if self.device == "cuda":
                self.plate_model.half()
            logger.info("✓ Plate model loaded")
            
            logger.info(f"Loading character recognition model from: {self.char_model_path}")
            self.char_model = torch.hub.load(
                str(YOLOV5_PATH),
                "custom",
                path=str(self.char_model_path),
                source="local",
            )
            self.char_model.to(self.device)
            self.char_model.eval()
            if self.device == "cuda":
                self.char_model.half()
            logger.info("✓ Character model loaded")
            
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            raise
    
    @staticmethod
    def _normalize_char(ch: str) -> str:
        """Normalize Persian characters"""
        if ch == "ه‌":
            ch = "ه"
        if ch.startswith("ژ"):
            ch = "ژ"
        return ch
    
    @staticmethod
    def _clean_text(txt: str) -> str:
        """Remove non-digits and non-Persian letters"""
        return re.sub(r"[^0-9آ-ی]", "", txt)
    
    @staticmethod
    def format_plate(txt: str) -> str:
        """
        Format plate text to standard format.
        
        Supports:
        - National plate: 2 digits + letter + 3 digits + 2 digits
        - Free zone: 5 digits + 2 digits
        
        Args:
            txt: Raw plate text
        
        Returns:
            Formatted plate string
        """
        s = PlateDetector._clean_text(txt)
        
        # National plate: ۲۲ب۳۳۳۴۴ format
        m1 = re.match(r"^(\d{2})([آ-ی])(\d{3})(\d{2})$", s)
        if m1:
            a, b, c, d = m1.groups()
            return f"{a} {b} {c} {d}"
        
        # Free zone plate: ۵ digits + 2 digits
        m2 = re.match(r"^(\d{5})(\d{2})$", s)
        if m2:
            serial, region = m2.groups()
            return f"{serial} {region}"
        
        return s
    
    @staticmethod
    def _prepare_inference_frame(image: np.ndarray) -> tuple[np.ndarray, float]:
        """Resize oversized frames and return (frame, scale) for bbox remap."""
        h, w = image.shape[:2]
        longest = max(h, w)
        if longest <= MAX_INFERENCE_EDGE:
            return image, 1.0
        scale = MAX_INFERENCE_EDGE / float(longest)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return resized, scale

    @staticmethod
    def _scale_bbox(bbox: list[int], scale: float) -> list[int]:
        if scale == 1.0:
            return bbox
        inv = 1.0 / scale
        return [int(v * inv) for v in bbox]

    def _run_plate_model(self, image: np.ndarray):
        if self.device == "cuda":
            with torch.inference_mode(), torch.amp.autocast("cuda"):
                return self.plate_model(image)
        with torch.inference_mode():
            return self.plate_model(image)

    def _run_char_model(self, plate_resized: np.ndarray):
        if self.device == "cuda":
            with torch.inference_mode(), torch.amp.autocast("cuda"):
                return self.char_model(plate_resized)
        with torch.inference_mode():
            return self.char_model(plate_resized)
    
    def _decode_plate(self, plate_crop: np.ndarray) -> Tuple[str, float]:
        """
        Detect and decode characters in cropped plate image.
        
        Args:
            plate_crop: Cropped plate image (BGR format)
        
        Returns:
            Tuple of (formatted_plate_text, average_confidence)
        """
        # Resize plate to standard size (from legacy code)
        plate_resized = cv2.resize(plate_crop, CHAR_PLATE_SIZE)
        
        # Detect characters
        results = self._run_char_model(plate_resized)
        detections = results.xyxy[0].cpu().numpy()
        
        if len(detections) == 0:
            return "", 0.0
        
        # Filter by confidence
        filtered = [d for d in detections if d[4] >= self.conf_threshold]
        
        if not filtered:
            return "", 0.0
        
        # Sort by x coordinate (left to right)
        filtered.sort(key=lambda x: x[0])
        
        # Get character names
        names = self.char_model.names
        chars = [self._normalize_char(names[int(d[5])]) for d in filtered]
        
        # Calculate average confidence
        avg_conf = float(np.mean([d[4] for d in filtered]))
        
        # Assemble and format
        raw_text = "".join(chars)
        formatted = self.format_plate(raw_text)
        
        return formatted, avg_conf
    
    def _finalize_detection(
        self,
        formatted: str,
        conf: float,
        char_conf: float,
        bbox: list[int],
    ) -> Tuple[Optional[str], float, Optional[dict]]:
        """Apply Django plate rules; reject invalid OCR immediately."""
        canonical, err = validate_detection_plate(formatted)
        if not canonical:
            logger.info("Rejected invalid plate OCR %r: %s", formatted, err)
            return None, float(conf), {
                "rejected": True,
                "raw_ocr": formatted,
                "validation_error": err,
                "char_confidence": char_conf,
                "bbox": bbox,
            }

        display = to_operator_display(canonical)
        return display, float(conf), {
            "plate_canonical": canonical,
            "char_confidence": char_conf,
            "bbox": bbox,
            "raw_text": formatted,
        }
    
    def detect(
        self,
        image: np.ndarray,
        return_all: bool = False
    ) -> Tuple[Optional[str], float, Optional[dict]]:
        """
        Detect license plate in image.
        
        Args:
            image: Input image (BGR format) or path to image file
            return_all: If True, return all detections; else return only best
        
        Returns:
            Tuple of (plate_text, confidence, metadata_dict)
            - plate_text: Formatted plate string or None if not detected
            - confidence: Detection confidence (0.0 to 1.0)
            - metadata: Dict with bbox, char_confidence, raw_text, etc.
        """
        # Load image if path provided
        if isinstance(image, (str, Path)):
            image = cv2.imread(str(image))
            if image is None:
                logger.error(f"Could not load image: {image}")
                return None, 0.0, None
        
        if image is None or image.size == 0:
            logger.error("Invalid image")
            return None, 0.0, None
        
        infer_image, scale = self._prepare_inference_frame(image)
        h, w = image.shape[:2]
        
        # Step 1: Detect plate regions
        results = self._run_plate_model(infer_image)
        detections = results.xyxy[0].cpu().numpy()
        
        if len(detections) == 0:
            logger.debug("No plate regions detected")
            return None, 0.0, None
        
        # Process detections
        all_results = []
        best_result = None
        best_conf = 0.0
        
        for *xyxy, conf, cls in detections:
            if conf < self.conf_threshold:
                continue
            
            x1, y1, x2, y2 = map(int, xyxy)
            if scale != 1.0:
                x1, y1, x2, y2 = self._scale_bbox([x1, y1, x2, y2], scale)
            
            # Crop plate region with padding
            pad = 10
            x1p = max(0, x1 - pad)
            y1p = max(0, y1 - pad)
            x2p = min(w, x2 + pad)
            y2p = min(h, y2 + pad)
            
            plate_crop = image[y1p:y2p, x1p:x2p]
            
            if plate_crop.size == 0:
                continue
            
            # Step 2: Decode characters
            plate_text, char_conf = self._decode_plate(plate_crop)
            
            if not plate_text:
                # Type B observability only — does not change YOLO/validation.
                # Prefer a valid/rejected OCR candidate over empty OCR when ranking.
                empty_meta = {
                    "plate": None,
                    "confidence": float(conf),
                    "char_confidence": float(char_conf),
                    "bbox": [x1, y1, x2, y2],
                    "raw_text": "",
                    "raw_ocr": "",
                    "fail_type": "ocr_empty",
                    "rejected": False,
                }
                if best_result is None or (
                    best_result.get("fail_type") == "ocr_empty"
                    and conf > best_conf
                ):
                    best_conf = float(conf)
                    best_result = empty_meta
                continue
            
            finalized = self._finalize_detection(
                plate_text, float(conf), char_conf, [x1, y1, x2, y2]
            )
            plate_out, conf_out, meta = finalized
            
            if meta and meta.get("rejected"):
                # Keep best rejected candidate for retry signalling upstream.
                if conf > best_conf or (
                    best_result is not None
                    and best_result.get("fail_type") == "ocr_empty"
                ):
                    best_conf = conf
                    best_result = {
                        "plate": None,
                        "confidence": conf_out,
                        "char_confidence": char_conf,
                        "bbox": [x1, y1, x2, y2],
                        "raw_text": plate_text,
                        "fail_type": "ocr_invalid_format",
                        **meta,
                    }
                continue

            result = {
                "plate": plate_out,
                "confidence": conf_out,
                "char_confidence": char_conf,
                "bbox": [x1, y1, x2, y2],
                "raw_text": plate_text,
                **(meta or {}),
            }
            
            all_results.append(result)
            
            # Track best result
            if conf_out > best_conf:
                best_conf = conf_out
                best_result = result
        
        if return_all:
            return all_results
        
        if best_result:
            if best_result.get("rejected") or best_result.get("fail_type") == "ocr_empty":
                return (
                    None,
                    best_result["confidence"],
                    best_result,
                )
            return (
                best_result["plate"],
                best_result["confidence"],
                best_result,
            )
        
        return None, 0.0, None
    
    def detect_from_file(self, image_path: str) -> Tuple[Optional[str], float, Optional[dict]]:
        """
        Detect license plate from image file.
        
        Args:
            image_path: Path to image file
        
        Returns:
            Same as detect()
        """
        return self.detect(image_path)


# Convenience function for quick detection
def detect_plate(image, conf_threshold: float = 0.5) -> Tuple[Optional[str], float]:
    """
    Quick plate detection function.
    
    Args:
        image: Image array or path to image
        conf_threshold: Minimum confidence
    
    Returns:
        Tuple of (plate_text, confidence)
    """
    detector = PlateDetector(conf_threshold=conf_threshold)
    plate, conf, _ = detector.detect(image)
    return plate, conf


if __name__ == "__main__":
    # Test with sample images
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    print("="*60)
    print("Plate Detector Test")
    print("="*60)
    
    # Initialize detector
    detector = PlateDetector()
    
    # Test with sample images
    samples_dir = Path(__file__).parent.parent / "operator_panel" / "samples" / "plates"
    if samples_dir.exists():
        sample_images = list(samples_dir.glob("*.png"))[:3]
        
        for img_path in sample_images:
            print(f"\nTesting: {img_path.name}")
            plate, conf, meta = detector.detect_from_file(str(img_path))
            
            if plate:
                print(f"  ✓ Plate: {plate}")
                print(f"    Confidence: {conf:.3f}")
                if meta:
                    print(f"    Char Confidence: {meta['char_confidence']:.3f}")
            else:
                print(f"  ✗ No plate detected")
    
    print("\n" + "="*60)
    print("Test complete")
    print("="*60)
