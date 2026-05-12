import re

VALID_PROVINCE_CODES = {"30", "29", "61", "59", "51", "34", "33", "52", "58", "24", "23", "22", "21", "20", "74", "75", "76", "77", "78", "79", "80", "81", "82", "83", "84", "85", "86", "87", "88", "89", "90", "91", "92", "93", "94", "95", "96", "97"}

def validate_plate(plate_text, vehicle_class="car"):
    canonical = plate_text.replace("-", "").replace(".", "").upper().strip()
    
    # Updated main regex to allow 2 letters for motorcycles
    if not re.match(r"^\d{2}[A-HJ-NPR-Z]{1,2}\d{4,6}$", canonical):
        return False, "Format mismatch"
    
    province = canonical[:2]
    if province not in VALID_PROVINCE_CODES:
        return False, f"Invalid province {province}"
    
    if vehicle_class == "car":
        m_car = re.match(r"^(\d{2})([A-HJ-NPR-Z])(\d{4,6})$", canonical)
        if m_car:
            return True, "Valid car plate"
        return False, "Car must have 1 letter only and 4-6 digits"
    else:
        # Motorcycle patterns
        m_motorcycle_2L = re.match(r"^(\d{2})([A-HJ-NPR-Z]{2})(\d{4})$", canonical)
        m_motorcycle_1L1D = re.match(r"^(\d{2})([A-HJ-NPR-Z])(\d)(\d{4})$", canonical)
        if m_motorcycle_2L or m_motorcycle_1L1D:
            return True, "Valid motorcycle plate"
        return False, "Invalid motorcycle format"

# Test cases
test_cases = [
    ("30A12345", "car", True, "5-digit car"),
    ("30A1234", "car", True, "4-digit car"),
    ("61D206617", "car", True, "6-digit car"),
    ("30AB1234", "motorcycle", True, "2-letter motorcycle"),
    ("30A11234", "motorcycle", True, "1L+1D+4D motorcycle"),
    ("99A12345", "car", False, "Invalid province"),
    ("30AA1234", "car", False, "Car with 2 letters"),
]

for plate, vclass, expected, desc in test_cases:
    valid, msg = validate_plate(plate, vclass)
    status = "v" if valid == expected else "x"
    print(f"{status} {desc}: {plate} ({vclass}) -> {valid} ({msg})")
