#!/usr/bin/env python3
"""Quick test for updated license plate validation supporting car & motorcycle formats."""

import sys
sys.path.insert(0, 'src/core')

from video_thread import validate_license_plate, format_vietnamese_plate

# Test cases
test_cases = [
    # (plate_text, vehicle_class, expected_valid, description)
    # Car: 2 digits + 1 letter + 5 digits (existing)
    ("30A12345", 0, True, "Car: XX + L + N5"),
    # Car: 2 digits + 1 letter + 4 digits (new)
    ("30A1234", 0, True, "Car: XX + L + N4"),
    # Car: 2 digits + 2 letters + 5 digits (existing)
    ("30AB12345", 0, True, "Car: XX + LL + N5"),
    # Car: 2 digits + 2 letters + 4 digits (new)
    ("30AB1234", 0, True, "Car: XX + LL + N4"),
    # Motorcycle: 2 digits + 1 letter + 1 digit + 4 digits (new)
    ("30A11234", 1, True, "Motorcycle: XX + L + N + N4"),
    # Car: 2 digits + 1 letter + 6 digits (existing, 2-line style)
    ("61D206617", 0, True, "Car: XX + L + N6 (2-line)"),
    # Invalid: wrong province code
    ("99A12345", 0, False, "Invalid: Unknown province code 99"),
    # Invalid: too few digits
    ("30AB123", 0, False, "Invalid: Too few digits"),
]

print("=" * 80)
print("Testing updated license plate validation")
print("=" * 80)

passed = 0
failed = 0

for plate, veh_class, expected_valid, description in test_cases:
    is_valid, canonical = validate_license_plate(plate, veh_class)
    status = "✓ PASS" if is_valid == expected_valid else "✗ FAIL"
    
    if is_valid == expected_valid:
        passed += 1
    else:
        failed += 1
    
    formatted = format_vietnamese_plate(canonical) if is_valid else "(invalid)"
    
    print(f"\n{status}: {description}")
    print(f"  Input: {plate} (vehicle_class={veh_class})")
    print(f"  Valid: {is_valid} (expected {expected_valid})")
    print(f"  Canonical: {canonical}")
    if is_valid:
        print(f"  Formatted: {formatted}")

print("\n" + "=" * 80)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 80)

sys.exit(0 if failed == 0 else 1)
