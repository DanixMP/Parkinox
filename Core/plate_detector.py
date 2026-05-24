"""
Plate Detector Module - YOLOv5-based license plate detection
Extracted from legacy code for standalone use
"""
import sys
import re
import logging
from pathlib import Path
from typing import Tuple, Optional
import cv2
import numpy as np
import torch

logger = logging.getLogger(__name__)

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
    
    def _decode_plate(self, plate_crop: np.ndarray) -> Tuple[str, float]:
        """
        Detect and decode characters in cropped plate image.
        
        Args:
            plate_crop: Cropped plate image (BGR format)
        
        Returns:
            Tuple of (formatted_plate_text, average_confidence)
        """
        # Resize plate to standard size (from legacy code)
        plate_resized = cv2.resize(plate_crop, (320, 80))
        
        # Detect characters
        results = self.char_model(plate_resized)
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
        
        h, w = image.shape[:2]
        
        # Step 1: Detect plate regions
        results = self.plate_model(image)
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
                continue
            
            result = {
                'plate': plate_text,
                'confidence': float(conf),
                'char_confidence': char_conf,
                'bbox': [x1, y1, x2, y2],
                'raw_text': plate_text,
            }
            
            all_results.append(result)
            
            # Track best result
            if conf > best_conf:
                best_conf = conf
                best_result = result
        
        if return_all:
            return all_results
        
        if best_result:
            return (
                best_result['plate'],
                best_result['confidence'],
                best_result
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
