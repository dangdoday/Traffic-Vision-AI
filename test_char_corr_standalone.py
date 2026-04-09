"""Quick regression checks for OCR correction in src/core/video_thread.py."""

from src.core.video_thread import (
    correct_plate_characters,
    validate_license_plate,
    format_vietnamese_plate,
)


def run_case(raw_text, expected_valid=True):
    corrected = correct_plate_characters(raw_text)
    is_valid, canonical = validate_license_plate(corrected, 0)
    formatted = format_vietnamese_plate(canonical) if is_valid else ""
    return corrected, is_valid, canonical, formatted


def main():
    cases = [
        # raw, expected_canonical, expected_format
        ("29B12345", "29B12345", "29B-123.45"),
        ("3OB12345", "30B12345", "30B-123.45"),
        ("61D206617", "61D206617", "61D2-066.17"),
        # Position-aware confusion fixes (O/0, D/O, 1/7)
        ("30012345", "30D12345", "30D-123.45"),
        ("3ODI2345", "30D12345", "30D-123.45"),
        ("1OB12345", "70B12345", "70B-123.45"),
        ("29H12O456", "29H120456", "29H1-204.56"),
        # Merged/noisy style from 2-line plate OCR (should still produce plausible canonical)
        ("674021066177", None, None),
        # Very long nonsense should be rejected
        ("ABCD1234567890XYZ", "", ""),
    ]

    print("=" * 80)
    print("OCR CORRECTION REGRESSION")
    print("=" * 80)

    failed = 0
    for raw, expected_canonical, expected_format in cases:
        corrected, is_valid, canonical, formatted = run_case(raw)

        case_ok = True
        if expected_canonical is not None and canonical != expected_canonical:
            case_ok = False
        if expected_format is not None and formatted != expected_format:
            case_ok = False
        if raw == "674021066177" and corrected:
            # Relaxed check: long merged input should still map to plausible VN shape.
            case_ok = is_valid

        status = "PASS" if case_ok else "FAIL"
        if not case_ok:
            failed += 1

        print(f"\n[{status}] raw='{raw}'")
        print(f"  corrected='{corrected}'")
        print(f"  valid={is_valid} canonical='{canonical}'")
        print(f"  formatted='{formatted}'")

    print("\n" + "=" * 80)
    print(f"TOTAL FAILED: {failed}")
    print("=" * 80)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
