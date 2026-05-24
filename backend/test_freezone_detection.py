"""
Test script to verify Free Zone plate detection works correctly.
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from utils.plate_normalizer import normalize_plate, VALID_FREE_ZONES

def test_free_zone_detection():
    """Test Free Zone plate detection with various formats."""
    
    test_cases = [
        # (input, expected_output, description)
        ("1724366", "Free Zone", "7-digit format"),
        ("17243-66", "Free Zone", "Persian format with dash"),
        ("17 243 66", "Free Zone", "Space-separated format"),
        ("17243FZKISH66", "Free Zone", "API format with zone"),
        ("12B345IR67", "National", "National plate API format"),
        ("12ب345-67", "National", "National plate Persian format"),
    ]
    
    print("=" * 80)
    print("Testing Free Zone Plate Detection")
    print("=" * 80)
    
    for raw_plate, expected_type, description in test_cases:
        print(f"\nTest: {description}")
        print(f"Input: '{raw_plate}'")
        print(f"Expected: {expected_type}")
        
        # Try without zone first
        try:
            result = normalize_plate(raw_plate, free_zone=None)
            if isinstance(result, tuple):
                print(f"✓ Detected as Free Zone: {result[0]}, zone: {result[1]}")
            else:
                print(f"✓ Detected as National: {result}")
        except ValueError as e:
            error_msg = str(e)
            if 'Ambiguous' in error_msg:
                print(f"⚠ Ambiguous format detected")
                # Try with each zone
                detected = False
                for zone in VALID_FREE_ZONES:
                    try:
                        result = normalize_plate(raw_plate, free_zone=zone)
                        if isinstance(result, tuple):
                            print(f"✓ Successfully detected with zone {zone}: {result[0]}")
                            detected = True
                            break
                    except ValueError:
                        continue
                if not detected:
                    print(f"✗ Failed to detect with any zone")
            else:
                print(f"✗ Error: {error_msg}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_free_zone_detection()
