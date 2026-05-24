"""
Unit tests for plate_normalizer module

Tests validate Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 9.1, 9.2, 9.3, 9.4, 9.5
"""

import pytest
from .plate_normalizer import normalize_plate, VALID_LETTERS


class TestDigitConversion:
    """Test digit conversion from Arabic-Indic and Latin to Persian"""
    
    def test_latin_digits_to_persian(self):
        """Requirement 7.2: Convert Latin digits (0-9) to Persian digits (۰-۹)"""
        result = normalize_plate("12ب345-67")
        assert result == "۱۲ب۳۴۵-۶۷"
    
    def test_arabic_indic_digits_to_persian(self):
        """Requirement 7.1: Convert Arabic-Indic digits (٠-٩) to Persian digits (۰-۹)"""
        result = normalize_plate("١٢ب٣٤٥-٦٧")
        assert result == "۱۲ب۳۴۵-۶۷"
    
    def test_mixed_digit_systems(self):
        """Test conversion when multiple digit systems are mixed"""
        result = normalize_plate("1٢ب3٤5-6٧")
        assert result == "۱۲ب۳۴۵-۶۷"
    
    def test_all_latin_digits(self):
        """Test all Latin digits 0-9 convert correctly"""
        result = normalize_plate("01ب234-56")
        assert result == "۰۱ب۲۳۴-۵۶"
        
        result = normalize_plate("78ب901-23")
        assert result == "۷۸ب۹۰۱-۲۳"
    
    def test_all_arabic_indic_digits(self):
        """Test all Arabic-Indic digits ٠-٩ convert correctly"""
        result = normalize_plate("٠١ب٢٣٤-٥٦")
        assert result == "۰۱ب۲۳۴-۵۶"
        
        result = normalize_plate("٧٨ب٩٠١-٢٣")
        assert result == "۷۸ب۹۰۱-۲۳"


class TestWhitespaceRemoval:
    """Test whitespace and underscore removal"""
    
    def test_space_removal(self):
        """Requirement 7.3: Remove all whitespace characters"""
        result = normalize_plate("12 ب 345 - 67")
        assert result == "۱۲ب۳۴۵-۶۷"
    
    def test_underscore_removal(self):
        """Requirement 7.3: Remove underscore characters"""
        result = normalize_plate("12_ب_345_-_67")
        assert result == "۱۲ب۳۴۵-۶۷"
    
    def test_tab_removal(self):
        """Test tab character removal"""
        result = normalize_plate("12\tب\t345\t-\t67")
        assert result == "۱۲ب۳۴۵-۶۷"
    
    def test_newline_removal(self):
        """Test newline character removal"""
        result = normalize_plate("12\nب\n345\n-\n67")
        assert result == "۱۲ب۳۴۵-۶۷"
    
    def test_mixed_whitespace_removal(self):
        """Test removal of mixed whitespace types"""
        result = normalize_plate("12 \t\n\rب 345 - 67")
        assert result == "۱۲ب۳۴۵-۶۷"

    def test_compact_format_without_hyphen(self):
        """OCR/compact plates missing hyphen are normalized."""
        result = normalize_plate("13ب43570")
        assert result == "۱۳ب۴۳۵-۷۰"

    def test_api_format_13B435IR70(self):
        result = normalize_plate("13B435IR70")
        assert result == "۱۳ب۴۳۵-۷۰"


class TestFormatValidation:
    """Test Iranian plate format validation"""
    
    def test_valid_format(self):
        """Requirement 7.4: Validate correct format [۰-۹]{2}[letter][۰-۹]{3}-[۰-۹]{2}"""
        result = normalize_plate("۱۲ب۳۴۵-۶۷")
        assert result == "۱۲ب۳۴۵-۶۷"
    
    def test_missing_dash(self):
        """Requirement 9.3: Reject plates missing dash separator"""
        with pytest.raises(ValueError, match="Invalid plate format"):
            normalize_plate("۱۲ب۳۴۵۶۷")
    
    def test_incorrect_first_digit_group_length(self):
        """Requirement 9.4: Reject plates with incorrect digit group lengths"""
        with pytest.raises(ValueError, match="Invalid plate format"):
            normalize_plate("۱ب۳۴۵-۶۷")  # Only 1 digit instead of 2
        
        with pytest.raises(ValueError, match="Invalid plate format"):
            normalize_plate("۱۲۳ب۳۴۵-۶۷")  # 3 digits instead of 2
    
    def test_incorrect_middle_digit_group_length(self):
        """Requirement 9.4: Reject plates with incorrect middle digit group"""
        with pytest.raises(ValueError, match="Invalid plate format"):
            normalize_plate("۱۲ب۳۴-۶۷")  # Only 2 digits instead of 3
        
        with pytest.raises(ValueError, match="Invalid plate format"):
            normalize_plate("۱۲ب۳۴۵۶-۶۷")  # 4 digits instead of 3
    
    def test_incorrect_last_digit_group_length(self):
        """Requirement 9.4: Reject plates with incorrect last digit group"""
        with pytest.raises(ValueError, match="Invalid plate format"):
            normalize_plate("۱۲ب۳۴۵-۶")  # Only 1 digit instead of 2
        
        with pytest.raises(ValueError, match="Invalid plate format"):
            normalize_plate("۱۲ب۳۴۵-۶۷۸")  # 3 digits instead of 2
    
    def test_empty_plate(self):
        """Test empty plate string raises error"""
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_plate("")
    
    def test_no_letter(self):
        """Test plate without letter raises error"""
        with pytest.raises(ValueError, match="Invalid plate format"):
            normalize_plate("۱۲۳۴۵-۶۷")


class TestValidLetters:
    """Test valid Persian letter enforcement"""
    
    def test_all_valid_letters(self):
        """Requirement 7.6: Accept all 25 valid Persian letters"""
        # Test a sample of valid letters
        valid_samples = [
            ("۱۲آ۳۴۵-۶۷", "۱۲آ۳۴۵-۶۷"),
            ("۱۲ا۳۴۵-۶۷", "۱۲ا۳۴۵-۶۷"),
            ("۱۲ب۳۴۵-۶۷", "۱۲ب۳۴۵-۶۷"),
            ("۱۲پ۳۴۵-۶۷", "۱۲پ۳۴۵-۶۷"),
            ("۱۲ت۳۴۵-۶۷", "۱۲ت۳۴۵-۶۷"),
            ("۱۲ج۳۴۵-۶۷", "۱۲ج۳۴۵-۶۷"),
            ("۱۲د۳۴۵-۶۷", "۱۲د۳۴۵-۶۷"),
            ("۱۲س۳۴۵-۶۷", "۱۲س۳۴۵-۶۷"),
            ("۱۲ع۳۴۵-۶۷", "۱۲ع۳۴۵-۶۷"),
            ("۱۲ل۳۴۵-۶۷", "۱۲ل۳۴۵-۶۷"),
            ("۱۲م۳۴۵-۶۷", "۱۲م۳۴۵-۶۷"),
            ("۱۲ن۳۴۵-۶۷", "۱۲ن۳۴۵-۶۷"),
            ("۱۲ه۳۴۵-۶۷", "۱۲ه۳۴۵-۶۷"),
            ("۱۲ی۳۴۵-۶۷", "۱۲ی۳۴۵-۶۷"),
        ]
        
        for input_plate, expected in valid_samples:
            result = normalize_plate(input_plate)
            assert result == expected
    
    def test_invalid_letters_rejected(self):
        """Requirement 7.6, 9.2: Reject plates with invalid letters (ذ، ژ، ص، ط، ظ، غ، ف، ق)"""
        invalid_letters = ['ذ', 'ژ', 'ص', 'ط', 'ظ', 'غ', 'ف', 'ق']
        
        for letter in invalid_letters:
            with pytest.raises(ValueError, match=f"Invalid letter '{letter}'"):
                normalize_plate(f"۱۲{letter}۳۴۵-۶۷")
    
    def test_valid_letters_constant(self):
        """Verify VALID_LETTERS contains exactly 25 letters"""
        assert len(VALID_LETTERS) == 25
        
        # Verify excluded letters are not in the list
        excluded = ['ذ', 'ژ', 'ص', 'ط', 'ظ', 'غ', 'ف', 'ق']
        for letter in excluded:
            assert letter not in VALID_LETTERS


class TestNormalizationIdempotence:
    """Test normalization idempotence property"""
    
    def test_idempotence(self):
        """Requirement 7.7: normalize(normalize(x)) = normalize(x)"""
        test_cases = [
            "12ب345-67",
            "١٢ب٣٤٥-٦٧",
            "12 ب 345 - 67",
            "۱۲ب۳۴۵-۶۷",
        ]
        
        for plate in test_cases:
            first_pass = normalize_plate(plate)
            second_pass = normalize_plate(first_pass)
            assert first_pass == second_pass, \
                f"Normalization not idempotent for '{plate}': {first_pass} != {second_pass}"
    
    def test_already_normalized_unchanged(self):
        """Test that already normalized plates remain unchanged"""
        normalized = "۱۲ب۳۴۵-۶۷"
        result = normalize_plate(normalized)
        assert result == normalized


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_descriptive_error_messages(self):
        """Requirement 9.5: Return descriptive error messages"""
        # Invalid format
        try:
            normalize_plate("invalid")
        except ValueError as e:
            assert "Invalid plate format" in str(e)
            assert "Expected format" in str(e)
        
        # Invalid letter
        try:
            normalize_plate("۱۲ذ۳۴۵-۶۷")
        except ValueError as e:
            assert "Invalid letter" in str(e)
            assert "ذ" in str(e)
    
    def test_combined_transformations(self):
        """Test all transformations applied together"""
        # Latin digits + spaces + underscores
        result = normalize_plate("12 _ ب _ 345 _ - _ 67")
        assert result == "۱۲ب۳۴۵-۶۷"
        
        # Arabic-Indic digits + tabs + spaces
        result = normalize_plate("٠١\tب\t٢٣٤ - ٥٦")
        assert result == "۰۱ب۲۳۴-۵۶"
        
        # Mixed digits + mixed whitespace
        result = normalize_plate("1٢ \n ب \t 3٤5 - 6٧")
        assert result == "۱۲ب۳۴۵-۶۷"


# Property-Based Tests using Hypothesis
from hypothesis import given, strategies as st, settings


class TestPropertyDigitNormalization:
    """Property-based tests for digit normalization
    
    **Validates: Requirements 7.1, 7.2**
    """
    
    @given(st.text(alphabet='٠١٢٣٤٥٦٧٨٩0123456789آابپتثجچحخدرزسشعکگلمنوهیء-', min_size=10, max_size=10))
    @settings(max_examples=10)
    def test_property_digit_normalization_completeness(self, input_string):
        """
        Property 1: Digit Normalization Completeness
        
        **Validates: Requirements 7.1, 7.2**
        
        For any string containing Arabic-Indic digits (٠-٩) or Latin digits (0-9),
        applying plate normalization SHALL convert all such digits to Persian digits (۰-۹).
        
        This property test generates random strings containing:
        - Arabic-Indic digits (٠-٩)
        - Latin digits (0-9)
        - Valid Persian letters
        - Dash separator
        
        And verifies that after normalization (if successful), no Arabic-Indic or Latin
        digits remain in the output.
        """
        # Define the digit sets
        arabic_indic_digits = set('٠١٢٣٤٥٦٧٨٩')
        latin_digits = set('0123456789')
        persian_digits = set('۰۱۲۳۴۵۶۷۸۹')
        
        try:
            # Attempt to normalize the input
            result = normalize_plate(input_string)
            
            # Property: The result should NOT contain any Arabic-Indic digits
            for char in result:
                assert char not in arabic_indic_digits, \
                    f"Arabic-Indic digit '{char}' found in normalized result: {result}"
            
            # Property: The result should NOT contain any Latin digits
            for char in result:
                assert char not in latin_digits, \
                    f"Latin digit '{char}' found in normalized result: {result}"
            
            # Property: All digits in the result should be Persian digits (if any digits exist)
            result_digits = [char for char in result if char in persian_digits or 
                           char in arabic_indic_digits or char in latin_digits]
            for digit in result_digits:
                assert digit in persian_digits, \
                    f"Non-Persian digit '{digit}' found in normalized result: {result}"
                    
        except ValueError:
            # If normalization fails due to invalid format or invalid letters,
            # that's acceptable - the property only applies to successfully normalized plates
            pass


class TestPropertyWhitespaceRemoval:
    """Property-based tests for whitespace removal
    
    **Validates: Requirements 7.3**
    """
    
    @given(st.text(alphabet='۰۱۲۳۴۵۶۷۸۹آابپتثجچحخدرزسشعکگلمنوهیء- \t\n\r_', min_size=10, max_size=20))
    @settings(max_examples=10)
    def test_property_whitespace_removal(self, input_string):
        """
        Property 2: Whitespace Removal
        
        **Validates: Requirements 7.3**
        
        For any plate string containing whitespace or underscore characters,
        applying plate normalization SHALL remove all such characters from the result.
        
        This property test generates random strings containing:
        - Persian digits (۰-۹)
        - Valid Persian letters
        - Dash separator
        - Whitespace characters (space, tab, newline, carriage return)
        - Underscore characters
        
        And verifies that after normalization (if successful), no whitespace or
        underscore characters remain in the output.
        """
        # Define the whitespace and underscore characters that should be removed
        whitespace_chars = set(' \t\n\r_')
        
        try:
            # Attempt to normalize the input
            result = normalize_plate(input_string)
            
            # Property: The result should NOT contain any whitespace characters
            for char in result:
                assert char not in whitespace_chars, \
                    f"Whitespace/underscore character '{repr(char)}' found in normalized result: {result}"
            
            # Additional check: Verify no spaces
            assert ' ' not in result, f"Space character found in normalized result: {result}"
            
            # Additional check: Verify no underscores
            assert '_' not in result, f"Underscore character found in normalized result: {result}"
            
            # Additional check: Verify no tabs
            assert '\t' not in result, f"Tab character found in normalized result: {result}"
            
            # Additional check: Verify no newlines
            assert '\n' not in result, f"Newline character found in normalized result: {result}"
            
            # Additional check: Verify no carriage returns
            assert '\r' not in result, f"Carriage return character found in normalized result: {result}"
                    
        except ValueError:
            # If normalization fails due to invalid format or invalid letters,
            # that's acceptable - the property only applies to successfully normalized plates
            pass


class TestPropertyPlateFormatValidation:
    """Property-based tests for plate format validation
    
    **Validates: Requirements 7.4, 7.5**
    """
    
    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=10)
    def test_property_format_validation(self, input_string):
        """
        Property 3: Plate Format Validation
        
        **Validates: Requirements 7.4, 7.5**
        
        For any string, after normalization, the string SHALL either match the pattern
        [۰-۹]{2}[valid_letter][۰-۹]{3}-[۰-۹]{2} and be accepted, or fail to match and
        raise a ValueError.
        
        This property test generates arbitrary strings and verifies that:
        1. If normalization succeeds, the result matches the valid Iranian plate format
        2. If normalization fails, it raises a ValueError
        3. There is no third outcome (no silent failures or incorrect acceptances)
        """
        import re
        
        # Define the valid plate pattern
        valid_pattern = re.compile(r'^[۰-۹]{2}[آ-ی]{1,4}[۰-۹]{3}-[۰-۹]{2}$')
        
        try:
            # Attempt to normalize the input
            result = normalize_plate(input_string)
            
            # Property: If normalization succeeds, the result MUST match the valid pattern
            assert valid_pattern.match(result), \
                f"Normalization succeeded but result '{result}' does not match valid pattern [۰-۹]{{2}}[letter][۰-۹]{{3}}-[۰-۹]{{2}}"
            
            # Property: The result must have exactly the correct structure
            # Extract components
            assert len(result) >= 9, f"Normalized plate '{result}' is too short"
            
            # First 2 characters must be Persian digits
            assert result[0] in '۰۱۲۳۴۵۶۷۸۹', f"First character '{result[0]}' is not a Persian digit"
            assert result[1] in '۰۱۲۳۴۵۶۷۸۹', f"Second character '{result[1]}' is not a Persian digit"
            
            # Find the dash position
            dash_pos = result.find('-')
            assert dash_pos != -1, f"No dash found in normalized plate '{result}'"
            
            # Last 2 characters must be Persian digits
            assert result[-2] in '۰۱۲۳۴۵۶۷۸۹', f"Second-to-last character '{result[-2]}' is not a Persian digit"
            assert result[-1] in '۰۱۲۳۴۵۶۷۸۹', f"Last character '{result[-1]}' is not a Persian digit"
            
            # 3 digits before the dash
            assert result[dash_pos-3] in '۰۱۲۳۴۵۶۷۸۹', f"Character at position {dash_pos-3} is not a Persian digit"
            assert result[dash_pos-2] in '۰۱۲۳۴۵۶۷۸۹', f"Character at position {dash_pos-2} is not a Persian digit"
            assert result[dash_pos-1] in '۰۱۲۳۴۵۶۷۸۹', f"Character at position {dash_pos-1} is not a Persian digit"
            
            # The letter portion is between position 2 and dash_pos-3
            letter_portion = result[2:dash_pos-3]
            assert len(letter_portion) >= 1, f"No letter found in normalized plate '{result}'"
            
            # Verify the letter is in the valid set
            assert letter_portion in VALID_LETTERS, \
                f"Letter '{letter_portion}' in normalized plate '{result}' is not in the valid letter set"
            
        except ValueError as e:
            # Property: If normalization fails, it MUST be due to invalid format or invalid letter
            # This is the expected behavior for invalid inputs
            error_message = str(e)
            assert "Invalid plate format" in error_message or "Invalid letter" in error_message or "cannot be empty" in error_message, \
                f"ValueError raised but with unexpected message: {error_message}"


class TestPropertyValidLetterSet:
    """Property-based tests for valid letter set enforcement
    
    **Validates: Requirements 7.6**
    """
    
    @given(
        first_digits=st.text(alphabet='۰۱۲۳۴۵۶۷۸۹', min_size=2, max_size=2),
        letter=st.sampled_from(VALID_LETTERS + ['ذ', 'ژ', 'ص', 'ط', 'ظ', 'غ', 'ف', 'ق']),
        middle_digits=st.text(alphabet='۰۱۲۳۴۵۶۷۸۹', min_size=3, max_size=3),
        last_digits=st.text(alphabet='۰۱۲۳۴۵۶۷۸۹', min_size=2, max_size=2)
    )
    @settings(max_examples=10)
    def test_property_valid_letter_set_enforcement(self, first_digits, letter, middle_digits, last_digits):
        """
        Property 4: Valid Letter Set Enforcement
        
        **Validates: Requirements 7.6**
        
        For any plate string in the format [۰-۹]{2}[letter][۰-۹]{3}-[۰-۹]{2},
        the letter SHALL be accepted if and only if it is one of the 25 valid
        Persian letters (excluding ذ، ژ، ص، ط، ظ، غ، ف، ق).
        
        This property test generates plate strings with:
        - 2 Persian digits at the start
        - A letter (either valid or invalid)
        - 3 Persian digits in the middle
        - A dash separator
        - 2 Persian digits at the end
        
        And verifies that:
        1. If the letter is in the valid set, normalization succeeds
        2. If the letter is NOT in the valid set, normalization raises ValueError
        """
        # Construct the plate string in the correct format
        plate_string = f"{first_digits}{letter}{middle_digits}-{last_digits}"
        
        # Define the invalid letters (excluded from Iranian plates)
        invalid_letters = ['ذ', 'ژ', 'ص', 'ط', 'ظ', 'غ', 'ف', 'ق']
        
        if letter in VALID_LETTERS:
            # Property: If the letter is valid, normalization MUST succeed
            try:
                result = normalize_plate(plate_string)
                
                # Verify the result contains the same letter
                assert letter in result, \
                    f"Valid letter '{letter}' not found in normalized result: {result}"
                
                # Verify the result matches the expected format
                assert result == plate_string, \
                    f"Normalized result '{result}' does not match input '{plate_string}' for valid letter"
                    
            except ValueError as e:
                # If a valid letter causes an error, this is a bug
                pytest.fail(
                    f"Valid letter '{letter}' was rejected. "
                    f"Plate: '{plate_string}', Error: {str(e)}"
                )
        else:
            # Property: If the letter is invalid, normalization MUST raise ValueError
            assert letter in invalid_letters, \
                f"Letter '{letter}' is neither valid nor invalid - test logic error"
            
            with pytest.raises(ValueError) as exc_info:
                normalize_plate(plate_string)
            
            # Verify the error message mentions the invalid letter
            error_message = str(exc_info.value)
            assert "Invalid letter" in error_message, \
                f"Error message does not mention 'Invalid letter': {error_message}"
            assert letter in error_message, \
                f"Error message does not mention the invalid letter '{letter}': {error_message}"


class TestPropertyNormalizationIdempotence:
    """Property-based tests for normalization idempotence
    
    **Validates: Requirements 7.7**
    """
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=10)
    def test_property_normalization_idempotence(self, input_string):
        """
        Property 5: Normalization Idempotence
        
        **Validates: Requirements 7.7**
        
        For any plate string, applying normalization twice SHALL produce the same
        result as applying it once: normalize(normalize(x)) = normalize(x).
        
        This property test generates arbitrary strings and verifies that:
        1. If normalization succeeds on the first pass, it also succeeds on the second pass
        2. The result of the first normalization equals the result of the second normalization
        3. This holds true regardless of the input format (Latin digits, Arabic-Indic digits,
           whitespace, etc.)
        
        The idempotence property is crucial for ensuring that:
        - Normalized plates can be safely re-normalized without changing their value
        - The normalization function is stable and predictable
        - Database lookups work correctly even if plates are normalized multiple times
        """
        try:
            # First normalization pass
            first_pass = normalize_plate(input_string)
            
            # Second normalization pass on the already-normalized result
            second_pass = normalize_plate(first_pass)
            
            # Property: normalize(normalize(x)) MUST equal normalize(x)
            assert first_pass == second_pass, \
                f"Normalization is not idempotent for input '{input_string}': " \
                f"first_pass='{first_pass}' != second_pass='{second_pass}'"
            
            # Additional verification: The second pass should not modify the string at all
            # since it's already in canonical format
            assert first_pass == second_pass, \
                f"Second normalization modified the already-normalized plate: " \
                f"'{first_pass}' became '{second_pass}'"
            
        except ValueError:
            # If the first normalization fails, that's acceptable - the property only
            # applies to strings that can be successfully normalized
            # We don't need to test the second pass in this case
            pass
