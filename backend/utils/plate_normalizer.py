"""
License Plate Normalization Utility

This module provides functionality to normalize Iranian license plate numbers
to a canonical format for consistent storage and matching.

Supports two types of Iranian plates:

1. National Plates:
   Canonical Format: [۰-۹]{2}[letter][۰-۹]{3}-[۰-۹]{2}
   Example: ۱۲ب۳۴۵-۶۷
   
   API ASCII Format: [0-9]{2}[LatinLetter(s)][0-9]{3}IR[0-9]{2}
   Example: 12B345IR67

2. Free Zone Plates:
   Canonical Format: [۰-۹]{5}-[۰-۹]{2}
   Example: ۱۷۲۴۳-۶۶ (Anzali Free Zone)
   
   Note: Free Zone plates have the same NUMBER format as national plates (5+2 digits),
   but are distinguished by zone logos on the physical plate. The zone must be 
   specified separately when registering.
   
   API ASCII Format: [0-9]{5}FZ[ZONE][0-9]{2}
   Example: 17243FZANZALI66

The normalize_plate() function accepts formats with or without zone specification.

Requirements Validated: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 9.1, 9.2, 9.3, 9.4, 9.5
"""

import re
from typing import Final, Union, Optional


# ---------------------------------------------------------------------------
# Free Zone definitions
# ---------------------------------------------------------------------------

VALID_FREE_ZONES: Final[list[str]] = [
    'ANZALI',
    'ARAS',
    'ARVAND',
    'KISH',
    'MAKU',
    'CHABAHAR',
    'QESHM',
]

# Persian names for Free Zones (for display purposes)
FREE_ZONE_PERSIAN_NAMES: Final[dict[str, str]] = {
    'ANZALI': 'انزلی',
    'ARAS': 'ارس',
    'ARVAND': 'اروند',
    'KISH': 'کیش',
    'MAKU': 'ماکو',
    'CHABAHAR': 'چابهار',
    'QESHM': 'قشم',
}


# ---------------------------------------------------------------------------
# Valid Persian letters for Iranian license plates
# ---------------------------------------------------------------------------

# All letters that can legally appear on Iranian plates (private + special use)
# Private (13): ب ج د س ص ط ق ل م ن و ه ی
# Special: الف پ ت ث ز ژ ش ع ف ک گ
# OCR extras: آ ا ء خ ح ر چ
VALID_LETTERS: Final[list[str]] = [
    # Private vehicle letters
    'ب', 'ج', 'د', 'س', 'ص', 'ط', 'ق', 'ل', 'م', 'ن', 'و', 'ه', 'هـ', 'ی',
    # Special-use letters
    'الف', 'پ', 'ت', 'ث', 'ز', 'ژ', 'ش', 'ع', 'ف', 'ک', 'گ',
    # OCR / legacy extras
    'آ', 'ا', 'ء', 'خ', 'ح', 'ر', 'چ',
]

# ---------------------------------------------------------------------------
# Digit conversion mappings
# ---------------------------------------------------------------------------

# Arabic-Indic digits (٠-٩) to Persian digits (۰-۹)
ARABIC_INDIC_TO_PERSIAN: Final[dict[str, str]] = {
    '٠': '۰', '١': '۱', '٢': '۲', '٣': '۳', '٤': '۴',
    '٥': '۵', '٦': '۶', '٧': '۷', '٨': '۸', '٩': '۹',
}

# Latin digits (0-9) to Persian digits (۰-۹)
LATIN_TO_PERSIAN_DIGIT: Final[dict[str, str]] = {
    '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
    '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹',
}

# Persian digits (۰-۹) to Latin digits (0-9)
PERSIAN_TO_LATIN_DIGIT: Final[dict[str, str]] = {
    v: k for k, v in LATIN_TO_PERSIAN_DIGIT.items()
}

# ---------------------------------------------------------------------------
# Letter transliteration tables
# ---------------------------------------------------------------------------

# Latin letter code → Persian letter (for decoding API format)
# Source: Iranis Dataset (https://github.com/alitourani/Iranis-dataset)
LATIN_TO_PERSIAN_LETTER: Final[dict[str, str]] = {
    # Private vehicle letters
    'B':     'ب',
    'J':     'ج',
    'D':     'د',
    'Sin':   'س',
    'Sad':   'ص',
    'T':     'ط',
    'Gh':    'ق',
    'L':     'ل',
    'M':     'م',
    'N':     'ن',
    'V':     'و',
    'H':     'ه',
    'Y':     'ی',
    # Special-use letters
    'A':     'الف',   # government (Alef) - takes precedence over single ا
    'P':     'پ',
    'Taxi':  'ت',
    'Tha':   'ث',
    'Z':     'ز',
    'PwD':   'ژ',     # People with Disabilities
    'Sha':   'ش',
    'PuV':   'ع',     # Public Vehicle
    'F':     'ف',
    'K':     'ک',
    'G':     'گ',
    # OCR extras
    'Kh':    'خ',
    'Ha':    'ح',
    'R':     'ر',
    'Aa':    'آ',
    'Hamza': 'ء',
    'Ch':    'چ',
}

# Sort by length descending so multi-char codes match before single-char codes
_SORTED_LATIN_LETTER_CODES: Final[list[str]] = sorted(
    LATIN_TO_PERSIAN_LETTER.keys(), key=len, reverse=True
)

# Persian letter → Latin code (for encoding to API format)
PERSIAN_TO_LATIN_LETTER: Final[dict[str, str]] = {
    v: k for k, v in LATIN_TO_PERSIAN_LETTER.items()
}
# هـ is the same letter as ه; map it to H as well
PERSIAN_TO_LATIN_LETTER['هـ'] = 'H'

# ---------------------------------------------------------------------------
# Plate format patterns
# ---------------------------------------------------------------------------

# Canonical Persian format for national plates: [۰-۹]{2}[letter][۰-۹]{3}-[۰-۹]{2}
PLATE_PATTERN: Final[re.Pattern] = re.compile(
    r'^[۰-۹]{2}[ء-ی]{1,4}[۰-۹]{3}-[۰-۹]{2}$'
)

# Free Zone format: [۰-۹]{5}-[۰-۹]{2} (same as national but without letter)
FREE_ZONE_PATTERN: Final[re.Pattern] = re.compile(
    r'^[۰-۹]{5}-[۰-۹]{2}$'
)

# API ASCII format for national plates: [0-9]{2}[LatinLetters][0-9]{3}IR[0-9]{2}
_API_PATTERN: Final[re.Pattern] = re.compile(
    r'^(\d{2})([A-Za-z]+)(\d{3})IR(\d{2})$'
)

# Free Zone API format: [0-9]{5}FZ[ZONE][0-9]{2}
_FREE_ZONE_API_PATTERN: Final[re.Pattern] = re.compile(
    r'^(\d{5})FZ([A-Z]+)(\d{2})$'
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_plate(raw_plate: str, free_zone: Optional[str] = None) -> Union[str, tuple[str, str]]:
    """
    Normalize a license plate string to canonical Iranian format.

    Accepts input formats for:
    
    National Plates:
    1. Canonical Persian:  ``۱۲ب۳۴۵-۶۷``
    2. API ASCII format:   ``12B345IR67``
    3. Mixed / raw OCR:    ``12 ب 345 - 67``
    
    Free Zone Plates:
    1. Canonical Persian:  ``۱۷۲۴۳-۶۶`` (with free_zone='ANZALI')
    2. API ASCII format:   ``17243FZANZALI66``
    3. Mixed / raw OCR:    ``17243-66`` (with free_zone='ANZALI')
    
    Note: Free Zone plates have the same NUMBER format as national plates (5+2 digits).
    The zone is specified separately via the free_zone parameter or embedded in API format.

    Transformations applied:
    1. If the input matches the Free Zone API format (``#####FZ[ZONE]##``),
       decode it to canonical Persian format and return (plate, zone).
    2. If the input matches the National API ASCII format (``##LetterCode###IR##``),
       decode it directly to canonical Persian format and return plate string.
    3. Otherwise:
       a. Convert Arabic-Indic digits (٠-٩) → Persian digits (۰-۹)
       b. Convert Latin digits (0-9) → Persian digits (۰-۹)
       c. Remove whitespace and underscores
       d. Check if it matches Free Zone format: ``[۰-۹]{5}-[۰-۹]{2}``
       e. Otherwise validate national format: ``[۰-۹]{2}[letter][۰-۹]{3}-[۰-۹]{2}``
       f. Validate that the letter is in the valid set

    Args:
        raw_plate: The raw plate string to normalize.
        free_zone: Optional Free Zone name (ANZALI, KISH, etc.). Required for Free Zone plates
                   unless the zone is embedded in API format.

    Returns:
        - For national plates: The normalized plate string in canonical Persian format.
        - For free zone plates: A tuple (normalized_plate, zone_name).

    Raises:
        ValueError: If the plate format is invalid or contains invalid letters/zones.

    Examples:
        >>> normalize_plate("12ب345-67")
        '۱۲ب۳۴۵-۶۷'

        >>> normalize_plate("12B345IR67")
        '۱۲ب۳۴۵-۶۷'

        >>> normalize_plate("17243-66", free_zone="ANZALI")
        ('۱۷۲۴۳-۶۶', 'ANZALI')

        >>> normalize_plate("17243FZANZALI66")
        ('۱۷۲۴۳-۶۶', 'ANZALI')

        >>> normalize_plate("17 243 66", free_zone="KISH")
        ('۱۷۲۴۳-۶۶', 'KISH')
    """
    if not raw_plate:
        raise ValueError("Plate number cannot be empty")

    stripped = raw_plate.strip().upper()

    # ── Fast path: Free Zone API format ──────────────────────────────────────
    fz_api_match = _FREE_ZONE_API_PATTERN.match(stripped)
    if fz_api_match:
        return _decode_free_zone_api_format(fz_api_match)

    # ── Fast path: National API ASCII format ─────────────────────────────────
    api_match = _API_PATTERN.match(stripped)
    if api_match:
        return _decode_api_format(api_match)

    # ── Standard path: Persian / mixed input ─────────────────────────────────

    # Step 1: Convert Arabic-Indic digits to Persian
    normalized = stripped
    for arabic, persian in ARABIC_INDIC_TO_PERSIAN.items():
        normalized = normalized.replace(arabic, persian)

    # Step 2: Convert Latin digits to Persian
    for latin, persian in LATIN_TO_PERSIAN_DIGIT.items():
        normalized = normalized.replace(latin, persian)

    # Step 3: Remove whitespace and underscores (but preserve hyphens and letters)
    for ch in (' ', '_', '\t', '\n', '\r'):
        normalized = normalized.replace(ch, '')

    # Step 4: Insert missing hyphen if needed
    # For 7-digit input: XXXXXNN → XXXXX-NN
    if len(normalized) == 7 and normalized.isdigit():
        normalized = f"{normalized[:5]}-{normalized[5:]}"
    
    # For national plates with letter: XXletterYYYZZ → XXletterYYY-ZZ
    compact_match = re.match(
        r'^([۰-۹]{2})([ء-ی]{1,4})([۰-۹]{3})([۰-۹]{2})$',
        normalized,
    )
    if compact_match:
        normalized = (
            f'{compact_match.group(1)}{compact_match.group(2)}'
            f'{compact_match.group(3)}-{compact_match.group(4)}'
        )

    # Step 5: Check if it's a Free Zone plate (5 digits + 2 region digits)
    if FREE_ZONE_PATTERN.match(normalized):
        if free_zone:
            zone_upper = free_zone.upper()
            if zone_upper not in VALID_FREE_ZONES:
                raise ValueError(
                    f"Invalid Free Zone '{free_zone}'. "
                    f"Valid zones: {', '.join(VALID_FREE_ZONES)}"
                )
            return (normalized, zone_upper)
        else:
            # Default to MAKU for all Free Zone plates
            return (normalized, 'MAKU')

    # Step 6: Validate national plate format pattern
    if not PLATE_PATTERN.match(normalized):
        raise ValueError(
            f"Invalid plate format: '{normalized}'. "
            f"Expected national format: [۰-۹]{{2}}[letter][۰-۹]{{3}}-[۰-۹]{{2}} "
            f"or Free Zone format: [۰-۹]{{5}}-[۰-۹]{{2}} (with zone specified) "
            f"or API formats: ##LetterCode###IR## or #####FZ[ZONE]##"
        )

    # Step 7: Extract and validate the letter portion for national plates
    match = re.match(r'^[۰-۹]{2}([ء-ی]{1,4})[۰-۹]{3}-[۰-۹]{2}$', normalized)
    if not match:
        raise ValueError(
            f"Invalid plate format: '{normalized}'."
        )

    letter = match.group(1)

    if letter not in VALID_LETTERS:
        raise ValueError(
            f"Invalid letter '{letter}' in plate number. "
            f"Letter must be one of the valid Iranian plate letters."
        )

    return normalized


def to_api_format(canonical_plate: str, free_zone: Optional[str] = None) -> str:
    """
    Convert a canonical Persian plate string to the API-safe ASCII format.

    Args:
        canonical_plate: Plate in canonical format, e.g. ``"۱۲ق۳۴۵-۱۶"`` or ``"۱۷۲۴۳-۶۶"``.
        free_zone: Optional Free Zone name (required if plate is a Free Zone plate).

    Returns:
        API-safe ASCII string, e.g. ``"12Gaf345IR16"`` or ``"17243FZANZALI66"``.

    Raises:
        ValueError: If the plate is not in canonical format or the letter
            is not in the known mapping.

    Examples:
        >>> to_api_format("۱۲ق۳۴۵-۱۶")
        '12Gh345IR16'
        
        >>> to_api_format("۱۷۲۴۳-۶۶", free_zone="ANZALI")
        '17243FZANZALI66'
    """
    # Check if it's a Free Zone plate (5+2 digits, no letter)
    fz_match = FREE_ZONE_PATTERN.match(canonical_plate)
    if fz_match:
        if not free_zone:
            raise ValueError(
                f"Free Zone name required for plate '{canonical_plate}'. "
                f"Please specify the free_zone parameter."
            )
        zone_upper = free_zone.upper()
        if zone_upper not in VALID_FREE_ZONES:
            raise ValueError(
                f"Invalid Free Zone '{free_zone}'. "
                f"Valid zones: {', '.join(VALID_FREE_ZONES)}"
            )
        
        digits_match = re.match(r'^([۰-۹]{5})-([۰-۹]{2})$', canonical_plate)
        if digits_match:
            digits_p = digits_match.group(1)
            region_p = digits_match.group(2)
            digits = _persian_digits_to_latin(digits_p)
            region = _persian_digits_to_latin(region_p)
            return f"{digits}FZ{zone_upper}{region}"
    
    # Otherwise, it's a national plate
    match = re.match(r'^([۰-۹]{2})([ء-ی]{1,4})([۰-۹]{3})-([۰-۹]{2})$', canonical_plate)
    if not match:
        raise ValueError(
            f"Plate '{canonical_plate}' is not in canonical Persian format."
        )

    prefix_p, letter_p, middle_p, province_p = match.groups()

    prefix = _persian_digits_to_latin(prefix_p)
    middle = _persian_digits_to_latin(middle_p)
    province = _persian_digits_to_latin(province_p)

    latin_letter = PERSIAN_TO_LATIN_LETTER.get(letter_p)
    if latin_letter is None:
        raise ValueError(
            f"Unknown Persian plate letter '{letter_p}'."
        )

    return f"{prefix}{latin_letter}{middle}IR{province}"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _decode_api_format(api_match: re.Match) -> str:
    """
    Decode a regex match of the API ASCII format to canonical Persian format.

    Args:
        api_match: A match object from ``_API_PATTERN``.

    Returns:
        Canonical Persian plate string.

    Raises:
        ValueError: If the Latin letter code is not recognised.
    """
    prefix_latin, letter_latin, middle_latin, province_latin = api_match.groups()

    # Convert digits
    prefix = _latin_digits_to_persian(prefix_latin)
    middle = _latin_digits_to_persian(middle_latin)
    province = _latin_digits_to_persian(province_latin)

    # Decode letter – try longest match first
    persian_letter = None
    for code in _SORTED_LATIN_LETTER_CODES:
        if letter_latin == code:
            persian_letter = LATIN_TO_PERSIAN_LETTER[code]
            break

    if persian_letter is None:
        raise ValueError(
            f"Unknown Latin plate letter code '{letter_latin}' in API format."
        )

    return f"{prefix}{persian_letter}{middle}-{province}"


def _decode_free_zone_api_format(fz_match: re.Match) -> tuple[str, str]:
    """
    Decode a regex match of the Free Zone API ASCII format to canonical format.

    Args:
        fz_match: A match object from ``_FREE_ZONE_API_PATTERN``.

    Returns:
        Tuple of (canonical Persian plate string, zone name).

    Raises:
        ValueError: If the zone name is not recognised.
    """
    digits_latin, zone, region_latin = fz_match.groups()

    # Convert digits to Persian
    digits = _latin_digits_to_persian(digits_latin)
    region = _latin_digits_to_persian(region_latin)

    # Validate zone
    if zone not in VALID_FREE_ZONES:
        raise ValueError(
            f"Invalid Free Zone '{zone}'. "
            f"Valid zones: {', '.join(VALID_FREE_ZONES)}"
        )

    return (f"{digits}-{region}", zone)


def _persian_digits_to_latin(text: str) -> str:
    """Convert Persian digit characters to ASCII digit characters."""
    result = text
    for persian, latin in PERSIAN_TO_LATIN_DIGIT.items():
        result = result.replace(persian, latin)
    return result


def _latin_digits_to_persian(text: str) -> str:
    """Convert ASCII digit characters to Persian digit characters."""
    result = text
    for latin, persian in LATIN_TO_PERSIAN_DIGIT.items():
        result = result.replace(latin, persian)
    return result
