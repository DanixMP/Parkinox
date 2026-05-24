"""
Test script for PlateDetector module
"""
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

from plate_detector import PlateDetector

def test_detector():
    """Test plate detector with sample images"""
    print("="*60)
    print("Plate Detector Test")
    print("="*60)
    
    # Initialize detector
    print("\n1. Initializing detector...")
    detector = PlateDetector()
    print("   ✓ Detector initialized")
    
    # Test with sample images
    samples_dir = Path(__file__).parent.parent / "operator_panel" / "samples" / "plates"
    
    if not samples_dir.exists():
        print(f"   ✗ Samples directory not found: {samples_dir}")
        return
    
    sample_images = list(samples_dir.glob("*.png")) + list(samples_dir.glob("*.jpg"))
    print(f"\n2. Found {len(sample_images)} sample images")
    
    print("\n3. Testing detection on first 5 images:")
    print("-" * 60)
    
    for i, img_path in enumerate(sample_images[:5], 1):
        print(f"\n[{i}] {img_path.name}")
        
        plate, conf, meta = detector.detect_from_file(str(img_path))
        
        if plate:
            print(f"    ✓ Plate: {plate}")
            print(f"      Confidence: {conf:.3f}")
            if meta:
                print(f"      Char Confidence: {meta['char_confidence']:.3f}")
                if meta.get('bbox'):
                    print(f"      BBox: {meta['bbox']}")
        else:
            print(f"    ✗ No plate detected")
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60)

if __name__ == "__main__":
    try:
        test_detector()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
