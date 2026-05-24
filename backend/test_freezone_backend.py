"""
Test the backend Free Zone detection with Persian digits.
"""

import os
import sys
import django

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Now import after Django is set up
from utils.plate_normalizer import normalize_plate, VALID_FREE_ZONES

def test_free_zone_detection_backend(raw_plate):
    """Simulate what _try_detect_free_zone does."""
    print(f"Testing Free Zone detection with: {raw_plate}")
    print("=" * 80)
    
    for zone in VALID_FREE_ZONES:
        try:
            result = normalize_plate(raw_plate, free_zone=zone)
            if isinstance(result, tuple):
                print(f"✓ SUCCESS with zone {zone}")
                print(f"  Normalized plate: {result[0]}")
                print(f"  Zone: {result[1]}")
                return result
        except ValueError as e:
            print(f"  Zone {zone}: Failed - {str(e)[:50]}...")
            continue
    
    print(f"✗ FAILED: Could not detect Free Zone with any zone")
    print(f"  This is why the error is being returned!")
    return None

# Test with Persian digits (the actual format received from frontend)
test_plate = '۱۷۲۳۶-۶۵'
result = test_free_zone_detection_backend(test_plate)

print("=" * 80)
