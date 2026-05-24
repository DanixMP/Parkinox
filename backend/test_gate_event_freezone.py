"""
Test the gate event Free Zone detection.
"""

import os
import sys
import django

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from utils.plate_normalizer import normalize_plate, VALID_FREE_ZONES

def normalize_plate_strict_test(raw):
    """Test version of normalize_plate_strict."""
    if not raw or not str(raw).strip():
        return None
    
    raw_str = str(raw).strip()
    
    try:
        result = normalize_plate(raw_str, free_zone=None)
        # If it's a tuple (Free Zone plate), return just the normalized plate
        if isinstance(result, tuple):
            return result[0]
        return result
    except ValueError as e:
        error_msg = str(e)
        # If it's an ambiguity error, try Free Zone detection
        if 'Ambiguous plate format' in error_msg:
            # Try each Free Zone
            for zone in VALID_FREE_ZONES:
                try:
                    result = normalize_plate(raw_str, free_zone=zone)
                    if isinstance(result, tuple):
                        # Successfully detected as Free Zone plate
                        return result[0]
                except ValueError:
                    continue
            
            # If we get here, Free Zone detection failed
            raise ValueError(f"Ambiguous plate format: '{raw_str}'. Could not detect Free Zone.")
        else:
            # Re-raise other errors
            raise

# Test with Persian digits (the actual format received from operator panel)
test_plates = [
    '۱۷۲۳۶-۶۵',  # Persian with dash
    '17236-65',   # Latin with dash
    '1723665',    # Compact 7 digits
    '17 236 65',  # Space-separated
]

print("=" * 80)
print("Testing Gate Event Free Zone Detection")
print("=" * 80)

for plate in test_plates:
    print(f"\nInput: '{plate}'")
    try:
        result = normalize_plate_strict_test(plate)
        print(f"✓ SUCCESS: Normalized to '{result}'")
    except ValueError as e:
        print(f"✗ FAILED: {str(e)}")

print("\n" + "=" * 80)
