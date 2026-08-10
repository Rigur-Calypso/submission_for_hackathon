#!/usr/bin/env python3
"""
currency.py — Indian currency normalizer.

Handles all representations found in the document estate:
  - "INR 33.38 Cr"       → 333800000
  - "Rs. 1403.00 Lakh"   → 140300000
  - "Rs. 11.23 Crore"    → 112300000
  - "33,38,00,000"        → 333800000  (Indian digit grouping)
  - "₹ 33.38 crore"      → 333800000
  - "INR 200.00 Cr"      → 2000000000
  - "Rs. -1,03,75,31,068" → -1037531068
  - "Rs. 18.26 Crore"    → 182600000
"""
import re

from word2number import w2n

# ── Multiplier map ──────────────────────────────────────────────────
MULTIPLIERS = {
    'cr': 1_00_00_000,
    'crore': 1_00_00_000,
    'crores': 1_00_00_000,
    'lakh': 1_00_000,
    'lakhs': 1_00_000,
    'lac': 1_00_000,
    'lacs': 1_00_000,
    'thousand': 1_000,
    'k': 1_000,
}


def parse_indian_money(text: str) -> int | None:
    """
    Parse an Indian currency string to integer rupees.
    
    Returns None if no currency amount can be found.
    """
    if not text:
        return None
    
    text = text.strip()
    
    # Try multiple patterns in priority order
    
    # 1. Number with explicit multiplier: "INR 33.38 Cr", "Rs. 1403.00 Lakh"
    pattern_multiplier = re.compile(
        r'(?:INR|₹|Rs\.?)\s*'
        r'(-?\s*[\d,]+\.?\d*)\s*'
        r'(Cr(?:ore)?s?|Lakh?s?|Lac?s?|Thousand|K)\b',
        re.IGNORECASE
    )
    m = pattern_multiplier.search(text)
    if m:
        num_str = m.group(1).replace(',', '').replace(' ', '')
        mult_key = m.group(2).lower().rstrip('s')
        if mult_key == 'lak':
            mult_key = 'lakh'
        mult = MULTIPLIERS.get(mult_key, 1)
        
        from decimal import Decimal
        return int(Decimal(num_str) * Decimal(mult))
    
    # 2. Number with multiplier but no currency prefix: "200.00 Cr", "33.38 Crore"
    pattern_mult_no_prefix = re.compile(
        r'(-?[\d,]+\.?\d*)\s*'
        r'(Cr(?:ore)?s?|Lakh?s?|Lac?s?)\b',
        re.IGNORECASE
    )
    m = pattern_mult_no_prefix.search(text)
    if m:
        num_str = m.group(1).replace(',', '').replace(' ', '')
        mult_key = m.group(2).lower().rstrip('s')
        if mult_key == 'lak':
            mult_key = 'lakh'
        mult = MULTIPLIERS.get(mult_key, 1)
        from decimal import Decimal
        return int(Decimal(num_str) * Decimal(mult))
    
    # 3. Indian digit grouping with currency prefix: "Rs. 33,38,00,000" or "₹ 1,03,75,31,068"
    pattern_indian = re.compile(
        r'(?:INR|₹|Rs\.?)\s*(-?\s*\d{1,2}(?:,\d{2})*,\d{3}(?:\.\d+)?)'
    )
    m = pattern_indian.search(text)
    if m:
        num_str = m.group(1).replace(',', '').replace(' ', '')
        from decimal import Decimal
        return int(Decimal(num_str))
    
    # 4. Plain number with currency prefix: "INR 333800000", "₹ 24850000"
    pattern_plain = re.compile(
        r'(?:INR|₹|Rs\.?)\s*(-?\s*[\d,]+(?:\.\d+)?)\b'
    )
    m = pattern_plain.search(text)
    if m:
        num_str = m.group(1).replace(',', '').replace(' ', '')
        try:
            from decimal import Decimal
            return int(Decimal(num_str))
        except ValueError:
            pass
    
    # 5. Standalone number (no prefix, no multiplier) — used as fallback
    pattern_standalone = re.compile(r'^(-?[\d,]+(?:\.\d+)?)\s*$')
    m = pattern_standalone.match(text.strip())
    if m:
        num_str = m.group(1).replace(',', '')
        try:
            from decimal import Decimal
            return int(Decimal(num_str))
        except ValueError:
            pass
    
    return None


def parse_threshold_words(text: str) -> int | None:
    """
    Parse a monetary threshold expressed in words.
    
    Handles:
      - "seventy-three crore"  → 730000000
      - "six crore"            → 60000000
      - "twenty crore"         → 200000000
      - "INR 20 Cr"            → 200000000
    """
    if not text:
        return None
    
    # First try parsing as a numeric amount
    result = parse_indian_money(text)
    if result is not None:
        return result
    
    text_lower = text.lower()
    pattern = re.compile(r'([\w\s-]+?)\s+(crore|cr|lakh|lac)\b', re.IGNORECASE)
    matches = pattern.findall(text_lower)
    
    if not matches:
        return None
        
    total = 0
    for num_words, mult_word in matches:
        mult_val = 1_00_00_000 if mult_word in ('crore', 'cr') else 1_00_000
        word_part = num_words.strip()
        # Remove common prefixes
        word_part = re.sub(r'^(?:the|a|an|about|around|over|approximately|crossing|hitting|reaching|above|past|beyond)\s+(?:the\s+)?', '', word_part)
        word_part = re.sub(r'^and\s+', '', word_part)
        try:
            num = w2n.word_to_num(word_part)
            total += int(num * mult_val)
        except ValueError:
            return None
            
    return total if total > 0 else None


# ── Self-test ───────────────────────────────────────────────────────
if __name__ == '__main__':
    tests = [
        # (input, expected_output)
        ("INR 33.38 Cr", 333800000),
        ("Rs. 1403.00 Lakh", 140300000),
        ("Rs. 11.23 Crore", 112300000),
        ("INR 200.00 Cr", 2000000000),
        ("INR 24.85 Cr", 248500000),
        ("Rs. 18.26 Crore", 182600000),
        ("INR 24.31 Cr", 243100000),
        ("Rs. 24.05 Crore", 240500000),
        ("Rs. 11.32 Crore", 113200000),
        ("INR 2.33 Cr", 23300000),
        ("INR 1.06 Cr", 10600000),
        ("INR 127.78 Cr", 1277800000),
        ("Rs. 26642.31 Lakh", 2664231000),
        ("Rs. -1,03,75,31,068", -1037531068),
        ("333800000", 333800000),
        ("INR 97.72 Cr", 977200000),
        ("INR 73.02 Cr", 730200000),
        # Values from sample question reasoning steps
        ("134000000", 134000000),
        ("23300000", 23300000),
    ]
    
    print("Currency Parser Self-Test")
    print("=" * 60)
    passed = 0
    failed = 0
    for inp, expected in tests:
        result = parse_indian_money(inp)
        status = "✅" if result == expected else "❌"
        if result != expected:
            print(f"  {status} parse_indian_money('{inp}')")
            print(f"       Expected: {expected:>15,}")
            print(f"       Got:      {result:>15,}")
            failed += 1
        else:
            print(f"  {status} '{inp}' → {result:,}")
            passed += 1
    
    print(f"\n{passed}/{passed+failed} tests passed")
    
    # Threshold parser tests
    print("\nThreshold Parser Self-Test")
    print("=" * 60)
    threshold_tests = [
        ("seventy-three crore", 730000000),
        ("six crore", 60000000),
        ("twenty crore", 200000000),
        ("INR 20 Cr", 200000000),
        ("one hundred crore", 1000000000),
        ("one crore twenty lakh", 12000000),
        ("above the one crore twenty lakh mark", 12000000),
    ]
    for inp, expected in threshold_tests:
        result = parse_threshold_words(inp)
        status = "✅" if result == expected else "❌"
        if result != expected:
            print(f"  {status} parse_threshold_words('{inp}')")
            print(f"       Expected: {expected:>15,}")
            print(f"       Got:      {result}")
            failed += 1
        else:
            print(f"  {status} '{inp}' → {result:,}")
            passed += 1
    
    print(f"\nFinal: {passed}/{passed+failed} tests passed")
