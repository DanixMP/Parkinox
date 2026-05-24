"""
Diagnostic script to test YOLO models with sample images
"""
import sys
import os
from pathlib import Path
import cv2
import torch
import numpy as np

# Add yolov5 to path
yolov5_path = Path(__file__).parent.parent / "yolov5"
if yolov5_path.exists():
    sys.path.insert(0, str(yolov5_path))
    print(f"✓ Found yolov5 at: {yolov5_path}")
else:
    print(f"✗ yolov5 not found at: {yolov5_path}")
    sys.exit(1)

# Model paths
models_dir = Path(__file__).parent.parent / "operator_panel" / "models"
plate_model_path = models_dir / "plateYolo.pt"
chars_model_path = models_dir / "CharsYolo.pt"

print(f"\nModel paths:")
print(f"  Plate model: {plate_model_path} - {'✓ exists' if plate_model_path.exists() else '✗ NOT FOUND'}")
print(f"  Chars model: {chars_model_path} - {'✓ exists' if chars_model_path.exists() else '✗ NOT FOUND'}")

# Sample images
samples_dir = Path(__file__).parent.parent / "operator_panel" / "samples" / "plates"
print(f"\nSamples directory: {samples_dir}")
if samples_dir.exists():
    sample_images = list(samples_dir.glob("*.png")) + list(samples_dir.glob("*.jpg"))
    print(f"  Found {len(sample_images)} sample images")
else:
    print("  ✗ Samples directory not found")
    sample_images = []

def load_models():
    """Load models using legacy approach"""
    print("\n" + "="*60)
    print("LOADING MODELS")
    print("="*60)
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    
    try:
        # Load plate model
        print("\nLoading plate detection model...")
        plate_model = torch.hub.load(
            str(yolov5_path),
            "custom",
            path=str(plate_model_path),
            source="local",
        )
        plate_model.to(device)
        plate_model.eval()
        print("✓ Plate model loaded")
        
        # Load character model
        print("\nLoading character recognition model...")
        char_model = torch.hub.load(
            str(yolov5_path),
            "custom",
            path=str(chars_model_path),
            source="local",
        )
        char_model.to(device)
        char_model.eval()
        print("✓ Character model loaded")
        
        return plate_model, char_model, device
        
    except Exception as e:
        print(f"✗ Error loading models: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def test_image(img_path, plate_model, char_model, device):
    """Test detection on a single image"""
    print("\n" + "="*60)
    print(f"TESTING: {img_path.name}")
    print("="*60)
    
    # Load image
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"✗ Could not load image: {img_path}")
        return
    
    print(f"Image shape: {img.shape}")
    
    # Step 1: Detect plate regions
    print("\nStep 1: Detecting plate regions...")
    results = plate_model(img)
    detections = results.xyxy[0].cpu().numpy()
    
    print(f"  Detections found: {len(detections)}")
    
    if len(detections) == 0:
        print("  ✗ No plate regions detected!")
        return
    
    # Process each detection
    for idx, (*xyxy, conf, cls) in enumerate(detections):
        print(f"\n  Detection {idx + 1}:")
        print(f"    Confidence: {conf:.3f}")
        print(f"    Class: {int(cls)}")
        
        if conf < 0.5:
            print("    ✗ Confidence too low, skipping")
            continue
        
        x1, y1, x2, y2 = map(int, xyxy)
        print(f"    BBox: ({x1}, {y1}) -> ({x2}, {y2})")
        
        # Crop plate region
        h, w = img.shape[:2]
        pad = 10
        x1p = max(0, x1 - pad)
        y1p = max(0, y1 - pad)
        x2p = min(w, x2 + pad)
        y2p = min(h, y2 + pad)
        
        plate_crop = img[y1p:y2p, x1p:x2p]
        print(f"    Crop shape: {plate_crop.shape}")
        
        if plate_crop.size == 0:
            print("    ✗ Empty crop")
            continue
        
        # Resize for character detection (from legacy code)
        plate_resized = cv2.resize(plate_crop, (320, 80))
        
        # Step 2: Detect characters
        print("\n  Step 2: Detecting characters...")
        char_results = char_model(plate_resized)
        char_dets = char_results.xyxy[0].cpu().numpy()
        
        print(f"    Characters found: {len(char_dets)}")
        
        if len(char_dets) == 0:
            print("    ✗ No characters detected!")
            continue
        
        # Sort by x coordinate (left to right)
        char_dets_filtered = [d for d in char_dets if d[4] >= 0.5]
        char_dets_filtered.sort(key=lambda x: x[0])
        
        print(f"    Valid characters (conf >= 0.5): {len(char_dets_filtered)}")
        
        # Get character names
        names = char_model.names
        chars = []
        for *cxyxy, cconf, ccls in char_dets_filtered:
            char_name = names[int(ccls)]
            chars.append(char_name)
            print(f"      '{char_name}' (conf: {cconf:.3f})")
        
        # Assemble plate string
        raw_text = "".join(chars)
        print(f"\n  Raw plate text: {raw_text}")
        
        # Save debug images
        debug_dir = Path(__file__).parent / "debug"
        debug_dir.mkdir(exist_ok=True)
        
        # Save original with bbox
        debug_img = img.copy()
        cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.imwrite(str(debug_dir / f"{img_path.stem}_bbox.jpg"), debug_img)
        
        # Save plate crop
        cv2.imwrite(str(debug_dir / f"{img_path.stem}_crop.jpg"), plate_crop)
        cv2.imwrite(str(debug_dir / f"{img_path.stem}_resized.jpg"), plate_resized)
        
        print(f"\n  ✓ Debug images saved to: {debug_dir}")

def main():
    # Load models
    plate_model, char_model, device = load_models()
    
    if plate_model is None or char_model is None:
        print("\n✗ Failed to load models")
        return
    
    # Test with sample images
    print("\n" + "="*60)
    print("TESTING SAMPLE IMAGES")
    print("="*60)
    
    # Test first 3 sample images
    for img_path in sample_images[:3]:
        test_image(img_path, plate_model, char_model, device)
    
    print("\n" + "="*60)
    print("DIAGNOSTIC COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()
