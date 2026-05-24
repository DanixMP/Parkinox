"""
Demonstration script for plate_normalizer module

This script demonstrates the various capabilities of the normalize_plate function.
"""

from plate_normalizer import normalize_plate, VALID_LETTERS


def demo():
    """Demonstrate plate normalization functionality"""
    
    print("=" * 60)
    print("Plate Normalizer Demonstration")
    print("=" * 60)
    print()
    
    # Demo 1: Latin digit conversion
    print("1. Latin Digit Conversion:")
    print(f"   Input:  '12ب345-67'")
    result = normalize_plate("12ب345-67")
    print(f"   Output: '{result}'")
    print()
    
    # Demo 2: Arabic-Indic digit conversion
    print("2. Arabic-Indic Digit Conversion:")
    print(f"   Input:  '١٢ب٣٤٥-٦٧'")
    result = normalize_plate("١٢ب٣٤٥-٦٧")
    print(f"   Output: '{result}'")
    print()
    
    # Demo 3: Whitespace removal
    print("3. Whitespace Removal:")
    print(f"   Input:  '12 ب 345 - 67'")
    result = normalize_plate("12 ب 345 - 67")
    print(f"   Output: '{result}'")
    print()
    
    # Demo 4: Mixed transformations
    print("4. Mixed Transformations (Latin + Arabic-Indic + spaces):")
    print(f"   Input:  '1٢ ب 3٤5 - 6٧'")
    result = normalize_plate("1٢ ب 3٤5 - 6٧")
    print(f"   Output: '{result}'")
    print()
    
    # Demo 5: Idempotence
    print("5. Idempotence (normalizing already normalized plate):")
    print(f"   Input:  '۱۲ب۳۴۵-۶۷'")
    result = normalize_plate("۱۲ب۳۴۵-۶۷")
    print(f"   Output: '{result}'")
    print()
    
    # Demo 6: Valid letters
    print("6. Valid Letters Sample:")
    sample_letters = ['آ', 'ا', 'ب', 'پ', 'ت', 'ج', 'د', 'س', 'ع', 'ل', 'م', 'ن', 'ه', 'ی']
    for letter in sample_letters:
        result = normalize_plate(f"12{letter}345-67")
        print(f"   {letter}: {result}")
    print()
    
    # Demo 7: Invalid letter detection
    print("7. Invalid Letter Detection:")
    invalid_letters = ['ذ', 'ژ', 'ص', 'ط', 'ظ', 'غ', 'ف', 'ق']
    for letter in invalid_letters:
        try:
            normalize_plate(f"۱۲{letter}۳۴۵-۶۷")
            print(f"   {letter}: ERROR - Should have been rejected!")
        except ValueError as e:
            print(f"   {letter}: ✓ Correctly rejected")
    print()
    
    # Demo 8: Format validation
    print("8. Format Validation:")
    invalid_formats = [
        ("۱۲۳۴۵۶۷", "Missing dash"),
        ("۱ب۳۴۵-۶۷", "Too few digits in first group"),
        ("۱۲ب۳۴-۶۷", "Too few digits in middle group"),
        ("۱۲ب۳۴۵-۶", "Too few digits in last group"),
    ]
    for plate, reason in invalid_formats:
        try:
            normalize_plate(plate)
            print(f"   {plate}: ERROR - Should have been rejected!")
        except ValueError:
            print(f"   {plate}: ✓ Correctly rejected ({reason})")
    print()
    
    # Summary
    print("=" * 60)
    print(f"Total valid letters: {len(VALID_LETTERS)}")
    print(f"Valid letters: {', '.join(VALID_LETTERS)}")
    print("=" * 60)


if __name__ == "__main__":
    demo()
