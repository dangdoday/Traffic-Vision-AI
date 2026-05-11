"""
Video Thread - Xử lý video và detection trong background thread
"""
import cv2
import numpy as np
import time
import importlib
import re
from threading import Lock
from collections import defaultdict
from PyQt5.QtCore import QThread, pyqtSignal

try:
    from .vehicle_tracker import VehicleTracker
    from .violation_detector import ViolationDetector
    from .stopline_manager import StopLineManager
    from .traffic_light_manager import TrafficLightManager
except ImportError:
    from core import VehicleTracker, ViolationDetector, StopLineManager, TrafficLightManager

# OCR backends are imported lazily to keep the module importable in tests.
PADDLE_OCR_AVAILABLE = importlib.util.find_spec("paddleocr") is not None
EASYOCR_AVAILABLE = importlib.util.find_spec("easyocr") is not None

# Common province/city plate prefixes in Vietnam (civilian plates).
VALID_PROVINCE_CODES = {
    "11", "12", "14", "15", "16", "17", "18", "19",
    "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
    "30", "31", "32", "33", "34", "35", "36", "37", "38",
    "40", "41", "43", "47", "48", "49",
    "50", "51", "52", "53", "54", "55", "56", "57", "58", "59",
    "60", "61", "62", "63", "64", "65", "66", "67", "68", "69",
    "70", "71", "72", "73", "74", "75", "76", "77", "78", "79",
    "80", "81", "82", "83", "84", "85", "86", "88", "89",
    "90", "92", "93", "94", "95", "97", "98", "99"
}

# OCR confusions for numeric positions.
TO_DIGIT_MAP = {
    "O": "0", "Q": "0", "D": "0",
    "I": "1", "L": "1", "T": "7",
    "Z": "2",
    "S": "5",
    "G": "6",
    "B": "8"
}

# Common same-shape swaps for numeric slots. Used with small penalty only.
DIGIT_AMBIGUOUS_SWAP = {
    "1": "7",
    "7": "1",
}

# OCR confusions for series letter positions.
TO_SERIES_MAP = {
    "0": "O", "1": "I", "2": "Z", "3": "B", "4": "A", "5": "S", "6": "G", "7": "T", "8": "B"
}

# Series letters I/O/Q are forbidden in Vietnamese civilian plates.
SERIES_SAFE_REMAP = {
    "I": "T",
    "O": "D",
    "Q": "D",
}

# Series letters in VN plates exclude I, O, Q.
FORBIDDEN_SERIES = {"I", "O", "Q"}
SERIES_REGEX = r"[A-HJ-NPR-Z]{1,2}"
SERIES_LETTER_DIGIT_REGEX = r"[A-HJ-NPR-Z]\d"


def _sanitize_ocr_text(text):
    if not text:
        return ""
    return re.sub(r'[^A-Z0-9]', '', text.upper())


def _unique_min_cost_candidates(candidates):
    best = {}
    for token, cost in candidates:
        if not token:
            continue
        prev = best.get(token)
        if prev is None or cost < prev:
            best[token] = cost
    return sorted(best.items(), key=lambda item: (item[1], item[0]))


def _digit_candidates(ch, allow_17_swap=False):
    """Return possible digit interpretations with edit costs."""
    raw = str(ch).upper()
    candidates = []

    if raw.isdigit():
        candidates.append((raw, 0))

    mapped = TO_DIGIT_MAP.get(raw)
    if mapped:
        candidates.append((mapped, 0 if mapped == raw else 1))

    base = _unique_min_cost_candidates(candidates)
    if not allow_17_swap or not base:
        return base

    expanded = list(base)
    for digit, cost in base:
        swapped = DIGIT_AMBIGUOUS_SWAP.get(digit)
        if swapped:
            expanded.append((swapped, cost + 1))

    return _unique_min_cost_candidates(expanded)


def _to_digit(ch):
    candidates = _digit_candidates(ch, allow_17_swap=False)
    if not candidates:
        return None
    return candidates[0][0]


def _series_letter_candidates(ch):
    """Return possible series-letter interpretations with edit costs."""
    raw = str(ch).upper()
    candidates = []

    if raw.isalpha():
        candidates.append((raw, 0))

    mapped = TO_SERIES_MAP.get(raw)
    if mapped:
        candidates.append((mapped, 0 if mapped == raw else 1))

    normalized = []
    for letter, cost in candidates:
        if letter in FORBIDDEN_SERIES:
            safe = SERIES_SAFE_REMAP.get(letter)
            if not safe:
                continue
            normalized.append((safe, cost + 1))
        else:
            normalized.append((letter, cost))

    return _unique_min_cost_candidates(normalized)


def _to_series_letter(ch):
    candidates = _series_letter_candidates(ch)
    if not candidates:
        return None
    return candidates[0][0]


def _build_plate_candidates(cleaned_text):
    """Build candidate canonical plates from noisy OCR text.

    Canonical forms (without separators):
      Cars (ô tô, 1 letter only):
      - XX + L + N4      (e.g. 30A1234)
      - XX + L + N5      (e.g. 30A12345)
      - XX + L + N6      (e.g. 61D206617, two-line display: 61D2-066.17)
      Motorcycles (xe máy):
      - XX + L + N + N4  (e.g. 30A11234, 1 letter + 1 digit + 4 digits)
      - XX + LL + N4     (e.g. 30AB1234, 2 letters + 4 digits)
    """
    candidates = []
    if len(cleaned_text) < 8:
        return candidates

    def _parse_tail_digits(tail_src, tail_len):
        if len(tail_src) < tail_len:
            return None

        digits = []
        total_cost = 0
        # Enforce contiguous numeric slots after series to avoid letter leakage.
        for ch in tail_src[:tail_len]:
            digit_options = _digit_candidates(ch, allow_17_swap=False)
            if not digit_options:
                return None
            digit, digit_cost = digit_options[0]
            digits.append(digit)
            total_cost += digit_cost

        return ''.join(digits), total_cost

    def add_motorcycle_candidates(segment):
        """Add candidates for motorcycle format: XX + L + N + N4 (e.g., 30A11234)."""
        if len(segment) < 8:
            return
        
        # Parse province (XX)
        p0_options = _digit_candidates(segment[0], allow_17_swap=True)
        p1_options = _digit_candidates(segment[1], allow_17_swap=True)
        if not p0_options or not p1_options:
            return
        
        # Parse series letter (L)
        series_options = _series_letter_candidates(segment[2])
        if not series_options:
            return
        
        # Parse mid digit (N)
        mid_options = _digit_candidates(segment[3], allow_17_swap=False)
        if not mid_options:
            return
        
        # Parse tail digits (NNNN)
        tail_options = []
        tail_cost = 0
        for ch in segment[4:8]:
            digit_opts = _digit_candidates(ch, allow_17_swap=False)
            if not digit_opts:
                return
            digit, cost = digit_opts[0]
            tail_options.append(digit)
            tail_cost += cost
        
        if len(tail_options) < 4:
            return
        
        # Generate all combinations
        for p0, p0_cost in p0_options[:2]:
            for p1, p1_cost in p1_options[:2]:
                province = f"{p0}{p1}"
                province_valid = province in VALID_PROVINCE_CODES
                province_cost = p0_cost + p1_cost
                province_penalty = 0 if province_valid else 3
                
                for series, series_cost in series_options[:2]:
                    for mid_digit, mid_cost in mid_options[:2]:
                        tail_digits = ''.join(tail_options[:4])
                        canonical = f"{province}{series}{mid_digit}{tail_digits}"
                        score = province_cost + series_cost + mid_cost + tail_cost + province_penalty + 0.5
                        candidates.append((score, canonical, province_valid))

    def add_candidates_from_segment(segment, start_penalty=0):
        if len(segment) < 8:
            return

        p0_options = _digit_candidates(segment[0], allow_17_swap=True)
        p1_options = _digit_candidates(segment[1], allow_17_swap=True)
        if not p0_options or not p1_options:
            return

        province_options = {}
        for p0, p0_cost in p0_options[:2]:
            for p1, p1_cost in p1_options[:2]:
                province = f"{p0}{p1}"
                total_cost = p0_cost + p1_cost
                prev = province_options.get(province)
                if prev is None or total_cost < prev:
                    province_options[province] = total_cost

        for province, province_cost in sorted(province_options.items(), key=lambda item: item[1]):
            province_valid = province in VALID_PROVINCE_CODES
            province_penalty = 0 if province_valid else 3

            for series_len in (1, 2):
                if len(segment) < 2 + series_len + 5:
                    continue

                series_chars = segment[2:2 + series_len]
                series_out = []
                series_cost = 0
                series_ok = True

                for ch in series_chars:
                    mapped_options = _series_letter_candidates(ch)
                    if not mapped_options:
                        series_ok = False
                        break
                    mapped, mapped_cost = mapped_options[0]
                    series_out.append(mapped)
                    series_cost += mapped_cost

                if not series_ok:
                    continue

                tail_src = segment[2 + series_len:]
                # Cars (1 letter): XX + L + N4/N5/N6; Motorcycles (2 letters): XX + LL + N4
                tail_lengths = (4,) if series_len == 2 else (6, 5, 4)
                pattern_penalty = 1 if series_len == 2 else 0

                for tail_len in tail_lengths:
                    parsed_tail = _parse_tail_digits(tail_src, tail_len)
                    if not parsed_tail:
                        continue

                    tail_digits, tail_cost = parsed_tail
                    expected_len = 2 + series_len + tail_len
                    length_penalty = abs(len(segment) - expected_len)

                    canonical = f"{province}{''.join(series_out)}{tail_digits}"
                    score = (
                        province_cost + province_penalty + series_cost + tail_cost
                        + length_penalty + pattern_penalty + start_penalty
                    )
                    candidates.append((score, canonical, province_valid))

    # Primary parse: assume useful characters start near the beginning.
    add_candidates_from_segment(cleaned_text)
    add_motorcycle_candidates(cleaned_text)

    # For long/noisy strings (often merged 2-line OCR), also scan short windows.
    if len(cleaned_text) > 10:
        max_start = min(4, len(cleaned_text) - 8)
        for start in range(1, max_start + 1):
            add_candidates_from_segment(cleaned_text[start:start + 12], start_penalty=start)
            add_motorcycle_candidates(cleaned_text[start:start + 8])

    return candidates


def _recover_two_line_merged(cleaned_text):
    """Heuristic recovery for merged 2-line OCR text.

    Example target style: XXS(S)-NNN.NN(N), canonicalized as XXSSNNNNN(N).
    """
    if len(cleaned_text) < 11:
        return ""

    candidates = []
    max_split = min(6, len(cleaned_text) - 5)
    for split in range(3, max_split + 1):
        head = cleaned_text[:split]
        tail = cleaned_text[split:]
        if len(head) < 3:
            continue

        p0_options = _digit_candidates(head[0], allow_17_swap=True)
        p1_options = _digit_candidates(head[1], allow_17_swap=True)
        if not p0_options or not p1_options:
            continue

        province_options = {}
        for p0, p0_cost in p0_options[:2]:
            for p1, p1_cost in p1_options[:2]:
                province = f"{p0}{p1}"
                total_cost = p0_cost + p1_cost
                prev = province_options.get(province)
                if prev is None or total_cost < prev:
                    province_options[province] = total_cost

        for province, province_cost in sorted(province_options.items(), key=lambda item: item[1]):
            province_valid = province in VALID_PROVINCE_CODES
            province_penalty = 0 if province_valid else 3

            for series_len in (1, 2):
                if len(head) < 2 + series_len:
                    continue
                series_src = head[2:2 + series_len]
                series_out = []
                series_cost = 0
                ok = True
                for ch in series_src:
                    mapped_options = _series_letter_candidates(ch)
                    if not mapped_options:
                        ok = False
                        break
                    mapped, mapped_cost = mapped_options[0]
                    series_out.append(mapped)
                    series_cost += mapped_cost
                if not ok:
                    continue

                digit_stream = []
                for ch in tail:
                    digit_options = _digit_candidates(ch, allow_17_swap=False)
                    if not digit_options:
                        continue
                    digit, digit_cost = digit_options[0]
                    digit_stream.append((digit, digit_cost))

                tail_lengths = (4,) if series_len == 2 else (6, 5, 4)
                for tail_len in tail_lengths:
                    if len(digit_stream) < tail_len:
                        continue
                    # Prefer first N digits, but also allow last N digits for merged/noisy tails.
                    for pick_last in (False, True):
                        pool = digit_stream[-tail_len:] if pick_last else digit_stream[:tail_len]
                        tail_digits = ''.join(d for d, _ in pool)
                        tail_cost = sum(cost for _, cost in pool)
                        split_penalty = abs(split - (2 + series_len))
                        series_penalty = 1 if series_len == 2 else 0
                        score = province_cost + series_cost + tail_cost + split_penalty + province_penalty + series_penalty
                        canonical = f"{province}{''.join(series_out)}{tail_digits}"
                        candidates.append((score, canonical, province_valid))

    if not candidates:
        return ""

    best = min(candidates, key=lambda item: (item[0], 0 if item[2] else 1))
    return best[1]


def correct_plate_characters(plate_text):
    """Return the best corrected canonical VN plate from noisy OCR text.

    Output is canonical without separators (e.g. 59A12345, 30G123456).
    """
    cleaned = _sanitize_ocr_text(plate_text)
    if not cleaned:
        return ""

    # Long strings are often merged lines/noise. Try dedicated recovery first.
    if len(cleaned) > 12:
        # Reject very noisy long strings early to avoid false positives.
        alpha_count = sum(ch.isalpha() for ch in cleaned)
        digit_like_count = sum(1 for ch in cleaned if ch.isdigit() or ch in TO_DIGIT_MAP)
        has_early_province = any(
            _to_digit(cleaned[i]) and _to_digit(cleaned[i + 1])
            for i in range(0, min(3, len(cleaned) - 1))
        )
        if alpha_count > 4 or digit_like_count < 8 or not has_early_province:
            return ""

        recovered = _recover_two_line_merged(cleaned)
        if recovered:
            return recovered
        # If 2-line heuristic fails, still try generic candidate extraction.
        candidates = _build_plate_candidates(cleaned)
        if candidates:
            best = min(candidates, key=lambda item: (item[0], 0 if item[2] else 1))
            return best[1]
        return ""

    candidates = _build_plate_candidates(cleaned)
    if candidates:
        # Lower score is better; when tied, prefer valid province code.
        best = min(candidates, key=lambda item: (item[0], 0 if item[2] else 1))
        return best[1]

    # Avoid trusting long garbage directly.
    if len(cleaned) > 10:
        return ""

    # Fallback best-effort for short strings.
    return cleaned


def validate_license_plate(plate_text, vehicle_class):
    """Validate canonical VN plate text after correction.

    Accepts data with/without separators, normalizes internally, then validates:
      - province: 2 digits and in known province list
      - Supported canonical families for cars (ô tô):
            1) XX + L + N4  (e.g., 30A1234)
            2) XX + L + N5  (e.g., 30A12345)
            3) XX + L + N6  (e.g., 61D206617, two-line display: 61D2-066.17)
      - Supported canonical families for motorcycles (xe máy):
            4) XX + L + N + N4  (e.g., 30A11234, 1 letter + 1 digit + 4 digits)
            5) XX + LL + N4     (e.g., 30AB1234, 2 letters + 4 digits)
    """
    if not plate_text:
        return (False, "")

    canonical = _sanitize_ocr_text(plate_text)
    
    # Car plates (1 letter only)
    m_one_letter_4 = re.match(r'^(\d{2})([A-HJ-NPR-Z])(\d{4})$', canonical)
    m_one_letter_5 = re.match(r'^(\d{2})([A-HJ-NPR-Z])(\d{5})$', canonical)
    m_one_letter_6 = re.match(r'^(\d{2})([A-HJ-NPR-Z])(\d{6})$', canonical)
    
    # Motorcycle plates
    m_motorcycle_1L1D = re.match(r'^(\d{2})([A-HJ-NPR-Z])(\d)(\d{4})$', canonical)
    m_motorcycle_2L = re.match(r'^(\d{2})([A-HJ-NPR-Z]{2})(\d{4})$', canonical)
    
    m = (m_one_letter_4 or m_one_letter_5 or m_one_letter_6 or 
         m_motorcycle_1L1D or m_motorcycle_2L)
    
    if m is None:
        return (False, canonical)

    province = m.group(1)
    if province not in VALID_PROVINCE_CODES:
        return (False, canonical)

    return (True, canonical)


def format_vietnamese_plate(plate_text, vehicle_class=0):
    """Format cleaned plate text into a common Vietnamese display style.

    Args:
        plate_text: Canonical plate (A-Z0-9 only)
        vehicle_class: YOLO class ID (0=car, 3=motorcycle, others=car)
                      Used to disambiguate 8-char formats that could be either.

    Vietnamese plate display formats:
    - 6-digit cars (2-line): XX L F1 / F2...F5 (e.g., 61D206617 -> 61D2 / 06617)
    - 5-digit cars (1-line): XX L - XXX.XX (e.g., 29A12345 -> 29A - 123.45)
    - 4-digit cars (1-line): XX L - XX.XX (e.g., 29B1234 -> 29B - 12.34)
    - Motorcycle 2-letter: XX LL - X.XXX (e.g., 30AB1234 -> 30AB - 1.234)
    - Motorcycle 1L+1D: XX L - D.XXXX (e.g., 30A11234 -> 30A - 1.1234)
    """
    if not plate_text:
        return ""

    cleaned = _sanitize_ocr_text(plate_text)
    is_motorcycle = vehicle_class == 3  # YOLO class 3 = motorcycle
    
    # 6-digit cars (2-line): displayed as XX L F1 / F2...F5
    # Example: 61D206617 -> 61D2 / 06617
    m_one_letter_6 = re.match(r'^(\d{2})([A-HJ-NPR-Z])(\d{6})$', cleaned)
    if m_one_letter_6:
        province = m_one_letter_6.group(1)
        letter = m_one_letter_6.group(2)
        tail6 = m_one_letter_6.group(3)
        line1 = f"{province}{letter}{tail6[0]}"
        line2 = tail6[1:]
        return f"{line1} / {line2}"

    # Standard: 1 letter or 2 letters + 4-5 digits
    m_standard = re.match(r'^(\d{2})([A-HJ-NPR-Z]{1,2})(\d{4,5})$', cleaned)
    if m_standard:
        province = m_standard.group(1)
        series = m_standard.group(2)
        tail = m_standard.group(3)
        
        # Check for motorcycle 1L+1D pattern: tail must be 5 digits, series 1 letter
        if len(tail) == 5 and len(series) == 1 and is_motorcycle:
            # Try to interpret as motorcycle: XX + L + D + NNNN
            # This means: first digit of tail is the mid_digit, rest is tail
            mid_digit = tail[0]
            tail4 = tail[1:]
            return f"{province}{series} - {mid_digit}.{tail4}"
        
        # 5-digit: format as XX... - XXX.XX
        if len(tail) == 5:
            return f"{province}{series} - {tail[:3]}.{tail[3:]}"
        # 4-digit:
        # - Cars (1 letter): format as XX L - XX.XX
        # - Motorcycles (2 letters): format as XX LL - X.XXX
        else:
            if len(series) == 1:
                # Car: split as XX.XX
                return f"{province}{series} - {tail[:2]}.{tail[2:]}"
            else:
                # Motorcycle: split as X.XXX
                return f"{province}{series} - {tail[0]}.{tail[1:]}"
    
    return cleaned


class VideoThread(QThread):
    """Thread xử lý video và YOLO detection"""
    
    change_pixmap_signal = pyqtSignal(np.ndarray)
    error_signal = pyqtSignal(str)
    playback_info_signal = pyqtSignal(dict)
    
    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self._run_flag = True
        self.model = None
        self.detection_enabled = False
        self.model_loaded = False
        self.fps = 0
        self.frame_count = 0
        self.display_count = 0
        self.fps_start_time = None
        self.realtime_mode = True  # Toggle realtime sync
        self.target_display_fps = 30  # Limit display FPS to reduce CPU usage
        self.stable_display_mode = True
        self.stable_display_fps = 20
        self.repeat_last_frame_for_smoothness = True
        self.enable_runtime_fps_logs = True
        self.runtime_fps_log_interval_sec = 1.0

        # Playback control state (pause/seek/timeline).
        self.playback_paused = False
        self.video_fps = 30.0
        self.video_total_frames = 0
        self.video_duration_sec = 0.0
        self.current_playback_sec = 0.0
        self._pending_seek_target_sec = None
        self._last_playback_emit_time = 0.0
        self._playback_lock = Lock()
        
        # Model config (will be set by MainWindow)
        self.model_config = None
        
        # Detailed FPS tracking
        self.processed_fps = 0  # Frames actually processed (with detection)
        self.processed_count = 0
        self.skipped_frames = 0  # Frames skipped in realtime mode
        
        # Initialize OOP modules
        self.vehicle_tracker = VehicleTracker(time_window=1.0, min_distance=20.0)
        self.violation_detector = ViolationDetector()
        self.stopline_manager = StopLineManager()
        self.traffic_light_manager = TrafficLightManager()
        
        # License plate relative position tracking
        # Format: {vehicle_track_id: {'x_ratio': float, 'y_ratio': float, 'abs_w': int, 'abs_h': int, 'conf': float, 'last_updated_frame': int, 'ocr_text': str}}
        # Note: x_ratio, y_ratio are relative (0.0-1.0), but abs_w, abs_h are absolute pixels to keep plate size constant
        self.vehicle_plate_positions = {}
        self.update_interval = 30  # Update relative position every 30 frames
        self.current_frame_count = 0
        self.use_plate_relative_tracking = False  # Toggle between YOLO direct vs relative tracking (Default: YOLO Direct)
        
        # YOLO Direct mode: Store OCR text for each vehicle
        # Format: {vehicle_track_id: 'plate_text'}
        self.vehicle_ocr_texts = {}

        # Stable plate text actually shown/used per vehicle.
        self.vehicle_stable_plates = {}

        # Candidate smoothing state per vehicle.
        # Format: {veh_id: {'candidate': str, 'streak': int, 'last_frame': int}}
        self.vehicle_plate_smoothing = {}

        # Temporal smoothing thresholds.
        self.plate_initial_confirm_frames = 3
        self.plate_switch_confirm_frames = 4

        # OCR voting across frames to stabilize low-quality readings.
        # Format: {vehicle_track_id: {plate_text: {'count': int, 'last_frame': int}}}
        self.vehicle_ocr_votes = {}
        self.vehicle_ocr_history = {}
        self.max_ocr_history_per_vehicle = 10

        # OCR throttling state (per vehicle) to reduce lag from repeated OCR retries.
        self.vehicle_ocr_attempts = {}
        self.vehicle_last_ocr_frame = {}
        self.ocr_retry_interval_frames = 12
        self.ocr_process_every_n_frames = 3
        self.ocr_bootstrap_every_n_frames = 3
        self.ocr_bootstrap_retry_interval_frames = 3
        self.max_ocr_attempts_per_vehicle = 45
        self.max_ocr_jobs_per_frame = 2
        self.max_ocr_jobs_per_frame_low_traffic = 3
        self.max_ocr_jobs_per_frame_high_traffic = 1
        self.ocr_medium_traffic_vehicle_threshold = 3
        self.ocr_high_traffic_vehicle_threshold = 6
        self._ocr_frame_budget = self.max_ocr_jobs_per_frame
        self._ocr_jobs_this_frame = 0
        self.ocr_heavy_until_attempt = 2
        self.ocr_heavy_pass_period = 6
        self.max_paddle_candidates_quick = 3
        self.max_paddle_candidates_heavy = 8
        self.min_ocr_plate_width = 40
        self.min_ocr_plate_height = 14
        self.ocr_priority_heavy_threshold = 0.70
        self.ocr_signature_size = (24, 12)
        self.ocr_signature_diff_threshold = 8.5
        self.ocr_positive_cache_ttl_frames = 45
        self.ocr_negative_cache_ttl_frames = 8
        self.enable_ocr_debug_logs = False
        self.enable_perf_logs = False

        # Per-vehicle OCR reuse cache to avoid repeating expensive OCR on near-identical crops.
        # Format: {veh_id: {'sig': np.ndarray, 'text': str, 'frame': int, 'heavy_frame': int}}
        self.vehicle_ocr_signature_cache = {}

        # GPU-first execution knobs for realtime inference.
        self.cuda_available = False
        self.yolo_device = 'cpu'
        self.yolo_half = False
        try:
            import torch
            self.cuda_available = torch.cuda.is_available()
            if self.cuda_available:
                torch.backends.cudnn.benchmark = True
                self.yolo_device = 0
                self.yolo_half = True
        except Exception:
            self.cuda_available = False
            self.yolo_device = 'cpu'
            self.yolo_half = False
        
        # YOLO Direct mode: Map vehicle track_id to plate track_id
        # Format: {vehicle_track_id: plate_track_id}
        self.vehicle_to_plate_map = {}
        
        # Violator trajectory tracking
        # Format: {track_id: [(x, y), (x, y), ...]}
        self.violator_trajectories = {}
        self.show_violator_trajectories = True  # Toggle to show/hide trajectories
        
        # Initialize PaddleOCR
        self.ocr = None
        self.enable_ocr = True  # Toggle OCR on/off
        self.easyocr_reader = None
        if self.enable_ocr_debug_logs:
            print(f"🧪 OCR debug mode: ON | Paddle module: {PADDLE_OCR_AVAILABLE} | EasyOCR module: {EASYOCR_AVAILABLE}")
        if PADDLE_OCR_AVAILABLE and self.enable_ocr:
            try:
                PaddleOCR = importlib.import_module("paddleocr").PaddleOCR
                # Suppress minor warnings during PaddleOCR initialization
                import sys
                import io
                old_stderr = sys.stderr
                sys.stderr = io.StringIO()  # Temporarily redirect stderr
                
                # use_textline_orientation=True: detect rotated text
                # lang='en': English (use 'ch' for Chinese, 'latin' for Latin scripts)
                try:
                    self.ocr = PaddleOCR(use_textline_orientation=True, lang='en', use_gpu=self.cuda_available)
                except Exception:
                    # Fallback to CPU when paddle GPU runtime is unavailable/misconfigured.
                    self.ocr = PaddleOCR(use_textline_orientation=True, lang='en', use_gpu=False)
                
                # Restore stderr
                sys.stderr = old_stderr
                print("✅ PaddleOCR initialized for license plate recognition")
            except Exception as e:
                sys.stderr = old_stderr  # Restore stderr on error too
                print(f"⚠️ Failed to initialize PaddleOCR: {e}")
                self.ocr = None

            # Do not initialize EasyOCR eagerly to avoid startup delay.
            # It will be created only if PaddleOCR cannot read text.
        
        # Reference to global state (will be set externally)
        self.globals_ref = None
    
    def set_globals_reference(self, globals_dict):
        """Set reference to global state dictionary"""
        self.globals_ref = globals_dict
    def preprocess_plate(self, img):
        """Advanced preprocessing for better OCR - from Traffic-Vision-AI reference"""
        # 1. Resize to height 100px
        h, w = img.shape[:2]
        if h < 100:
            scale = 100 / h
            img = cv2.resize(img, (int(w * scale), 100), interpolation=cv2.INTER_CUBIC)
        
        # 2. Grayscale
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 3. CLAHE contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        img = clahe.apply(img)
        
        # 4. Bilateral filter (noise reduction while preserving edges)
        img = cv2.bilateralFilter(img, 5, 75, 75)
        
        # 5. Sharpen
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        img = cv2.filter2D(img, -1, kernel)
        
        return img

    def _extract_texts_from_paddle_result(self, result, min_conf=0.35):
        """Extract (text, confidence) pairs from PaddleOCR outputs across versions."""
        extracted = []

        if not result:
            return extracted

        # Format A (classic): [[ [bbox, (text, conf)], ... ]]
        if isinstance(result, list) and result and isinstance(result[0], list):
            for line in result[0]:
                # Format A1 (rec-only): (text, conf) or [text, conf]
                if isinstance(line, (list, tuple)) and len(line) == 2 and isinstance(line[0], str):
                    text = str(line[0]).strip()
                    try:
                        conf = float(line[1])
                    except Exception:
                        conf = 0.0
                    if text and conf >= min_conf:
                        extracted.append((text, conf))
                    continue

                if isinstance(line, (list, tuple)) and len(line) >= 2:
                    text_info = line[1]

                    # Format A2 (rec-only nested): line[1] is confidence scalar, line[0] is text
                    if isinstance(line[0], str) and isinstance(text_info, (int, float)):
                        text = str(line[0]).strip()
                        try:
                            conf = float(text_info)
                        except Exception:
                            conf = 0.0
                        if text and conf >= min_conf:
                            extracted.append((text, conf))
                        continue

                    if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                        text = str(text_info[0]).strip()
                        try:
                            conf = float(text_info[1])
                        except Exception:
                            conf = 0.0
                        if text and conf >= min_conf:
                            extracted.append((text, conf))

        # Format B (dict-like from newer wrappers): {'rec_texts': [...], 'rec_scores': [...]}
        elif isinstance(result, dict):
            rec_texts = result.get('rec_texts', [])
            rec_scores = result.get('rec_scores', [])
            for i, text in enumerate(rec_texts):
                try:
                    conf = float(rec_scores[i]) if i < len(rec_scores) else 0.0
                except Exception:
                    conf = 0.0
                text = str(text).strip()
                if text and conf >= min_conf:
                    extracted.append((text, conf))

        # Format C (list of dicts)
        elif isinstance(result, list):
            for item in result:
                # Format C1: direct tuple/list pair (text, conf)
                if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], str):
                    text = str(item[0]).strip()
                    try:
                        conf = float(item[1])
                    except Exception:
                        conf = 0.0
                    if text and conf >= min_conf:
                        extracted.append((text, conf))
                    continue

                if isinstance(item, dict):
                    rec_texts = item.get('rec_texts', [])
                    rec_scores = item.get('rec_scores', [])
                    for i, text in enumerate(rec_texts):
                        try:
                            conf = float(rec_scores[i]) if i < len(rec_scores) else 0.0
                        except Exception:
                            conf = 0.0
                        text = str(text).strip()
                        if text and conf >= min_conf:
                            extracted.append((text, conf))

        return extracted

    def _normalize_plate_text(self, text):
        """Normalize OCR text for Vietnamese plate matching."""
        if not text:
            return ""
        return re.sub(r'[^A-Z0-9]', '', text.upper())

    def _compute_plate_priority(self, plate_w, plate_h, plate_conf=0.5):
        """Compute OCR priority score from plate geometry and detector confidence."""
        area = max(1.0, float(plate_w) * float(plate_h))
        area_score = min(1.0, area / 7200.0)  # ~120x60 is considered ideal quality.

        aspect = float(plate_w) / max(1.0, float(plate_h))
        aspect_score = 1.0 - min(1.0, abs(aspect - 3.0) / 3.0)

        conf_norm = max(0.0, min(1.0, (float(plate_conf) - 0.2) / 0.65))
        return 0.5 * area_score + 0.3 * aspect_score + 0.2 * conf_norm

    def _should_use_heavy_ocr(self, attempt_no, plate_priority):
        """Decide whether a heavy OCR pass is worth running on this attempt."""
        base_heavy = attempt_no <= self.ocr_heavy_until_attempt or (attempt_no % self.ocr_heavy_pass_period == 0)
        if not base_heavy:
            return False

        # In crowded scenes, keep heavy OCR only for better-quality crops.
        if self._ocr_frame_budget <= self.max_ocr_jobs_per_frame_high_traffic and plate_priority < self.ocr_priority_heavy_threshold:
            return False

        # Very low-quality crops are expensive with little gain: do sparse heavy retries.
        if plate_priority < 0.35 and (attempt_no % (self.ocr_heavy_pass_period * 2) != 0):
            return False

        return True

    def _compute_plate_signature(self, plate_img):
        """Create a tiny grayscale signature for cheap OCR-cache similarity checks."""
        try:
            if plate_img is None or getattr(plate_img, 'size', 0) == 0:
                return None
            gray = plate_img if len(plate_img.shape) == 2 else cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
            sig = cv2.resize(gray, self.ocr_signature_size, interpolation=cv2.INTER_AREA)
            return sig.astype(np.int16)
        except Exception:
            return None

    def _try_reuse_recent_ocr(self, veh_track_id, plate_img, heavy_mode=False):
        """Reuse OCR result when the current crop is near-identical to recent frames."""
        if veh_track_id is None:
            return None, False

        cache_entry = self.vehicle_ocr_signature_cache.get(veh_track_id)
        if not cache_entry:
            return None, False

        sig_now = self._compute_plate_signature(plate_img)
        sig_prev = cache_entry.get('sig')
        if sig_now is None or sig_prev is None:
            return None, False

        frame_gap = self.current_frame_count - int(cache_entry.get('frame', -10**9))
        diff = float(np.mean(np.abs(sig_now - sig_prev)))
        if diff > self.ocr_signature_diff_threshold:
            return None, False

        cached_text = cache_entry.get('text', '')
        if cached_text and frame_gap <= self.ocr_positive_cache_ttl_frames:
            return cached_text, True

        if (not cached_text) and (not heavy_mode) and frame_gap <= self.ocr_negative_cache_ttl_frames:
            return "", True

        return None, False

    def _finalize_ocr_result(self, veh_track_id, plate_img, text, heavy_mode=False):
        """Store OCR cache metadata and return text unchanged."""
        if veh_track_id is None:
            return text

        sig_now = self._compute_plate_signature(plate_img)
        if sig_now is None:
            return text

        cache_entry = {
            'sig': sig_now,
            'text': text or '',
            'frame': self.current_frame_count,
            'heavy_frame': self.current_frame_count if heavy_mode else self.current_frame_count,
        }
        self.vehicle_ocr_signature_cache[veh_track_id] = cache_entry
        return text

    def _deskew_plate_image(self, plate_img):
        """Try a light deskew to recover slanted plate text."""
        try:
            bgr = plate_img if len(plate_img.shape) == 3 else cv2.cvtColor(plate_img, cv2.COLOR_GRAY2BGR)
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            coords = cv2.findNonZero(255 - binary)
            if coords is None or len(coords) < 10:
                return bgr

            rect = cv2.minAreaRect(coords)
            angle = rect[-1]
            if angle < -45:
                angle = 90 + angle

            if abs(angle) < 1.5:
                return bgr

            h, w = bgr.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(bgr, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            return rotated
        except Exception:
            return plate_img

    def _order_quad_points(self, pts):
        """Order four points as top-left, top-right, bottom-right, bottom-left."""
        pts = np.array(pts, dtype=np.float32)
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1)

        ordered = np.zeros((4, 2), dtype=np.float32)
        ordered[0] = pts[np.argmin(s)]
        ordered[2] = pts[np.argmax(s)]
        ordered[1] = pts[np.argmin(diff)]
        ordered[3] = pts[np.argmax(diff)]
        return ordered

    def _rectify_plate_perspective(self, plate_img):
        """Rectify perspective for oblique plates using contour quad detection."""
        try:
            bgr = plate_img if len(plate_img.shape) == 3 else cv2.cvtColor(plate_img, cv2.COLOR_GRAY2BGR)
            h, w = bgr.shape[:2]
            if h < 14 or w < 40:
                return bgr

            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blur, 60, 180)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            edges = cv2.dilate(edges, kernel, iterations=1)

            contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return bgr

            img_area = float(h * w)
            for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
                area = cv2.contourArea(cnt)
                if area < img_area * 0.18:
                    continue

                peri = cv2.arcLength(cnt, True)
                if peri <= 0:
                    continue

                approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
                if len(approx) != 4:
                    continue

                quad = self._order_quad_points(approx.reshape(4, 2))
                tl, tr, br, bl = quad

                width_top = np.linalg.norm(tr - tl)
                width_bottom = np.linalg.norm(br - bl)
                max_width = int(max(width_top, width_bottom))

                height_left = np.linalg.norm(bl - tl)
                height_right = np.linalg.norm(br - tr)
                max_height = int(max(height_left, height_right))

                if max_width < 40 or max_height < 12:
                    continue

                aspect = max_width / max(1, max_height)
                if aspect < 1.4 or aspect > 7.5:
                    continue

                dst = np.array([
                    [0, 0],
                    [max_width - 1, 0],
                    [max_width - 1, max_height - 1],
                    [0, max_height - 1],
                ], dtype=np.float32)

                matrix = cv2.getPerspectiveTransform(quad, dst)
                warped = cv2.warpPerspective(
                    bgr,
                    matrix,
                    (max_width, max_height),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE,
                )

                if warped is not None and getattr(warped, 'size', 0) > 0:
                    return warped

            # Fallback: use minAreaRect when contour approximation misses 4-point quad.
            coords = cv2.findNonZero(edges)
            if coords is not None and len(coords) >= 12:
                rect = cv2.minAreaRect(coords)
                box = cv2.boxPoints(rect)
                quad = self._order_quad_points(box)

                tl, tr, br, bl = quad
                width_top = np.linalg.norm(tr - tl)
                width_bottom = np.linalg.norm(br - bl)
                max_width = int(max(width_top, width_bottom))

                height_left = np.linalg.norm(bl - tl)
                height_right = np.linalg.norm(br - tr)
                max_height = int(max(height_left, height_right))

                if max_width >= 40 and max_height >= 12:
                    dst = np.array([
                        [0, 0],
                        [max_width - 1, 0],
                        [max_width - 1, max_height - 1],
                        [0, max_height - 1],
                    ], dtype=np.float32)
                    matrix = cv2.getPerspectiveTransform(quad, dst)
                    warped = cv2.warpPerspective(
                        bgr,
                        matrix,
                        (max_width, max_height),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE,
                    )
                    if warped is not None and getattr(warped, 'size', 0) > 0:
                        return warped

            return bgr
        except Exception:
            return plate_img

    def _enhance_plate_for_readability(self, plate_img, fast_mode=False):
        """Enhance plate readability with upscale + contrast + sharpening."""
        try:
            bgr = plate_img if len(plate_img.shape) == 3 else cv2.cvtColor(plate_img, cv2.COLOR_GRAY2BGR)
            h, w = bgr.shape[:2]
            if h < 8 or w < 20:
                return bgr

            # Upscale small crops so OCR can separate close characters.
            target_h = 72
            if h < target_h:
                scale = min(4.0, target_h / max(1, float(h)))
                bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            if fast_mode:
                den = cv2.GaussianBlur(gray, (3, 3), 0)
                clahe = cv2.createCLAHE(clipLimit=2.6, tileGridSize=(8, 8)).apply(den)
            else:
                den = cv2.bilateralFilter(gray, d=7, sigmaColor=40, sigmaSpace=40)
                # Increase local contrast for low-light and side-angle plates.
                clahe = cv2.createCLAHE(clipLimit=3.2, tileGridSize=(8, 8)).apply(den)
            norm = cv2.normalize(clahe, None, 0, 255, cv2.NORM_MINMAX)

            blur = cv2.GaussianBlur(norm, (0, 0), 1.0)
            sharp = cv2.addWeighted(norm, 1.65, blur, -0.65, 0)

            return cv2.cvtColor(sharp, cv2.COLOR_GRAY2BGR)
        except Exception:
            return plate_img

    def _add_safe_plate_border(self, plate_img, border_ratio=0.08):
        """Add replicated border so edge characters are not clipped during OCR."""
        try:
            bgr = plate_img if len(plate_img.shape) == 3 else cv2.cvtColor(plate_img, cv2.COLOR_GRAY2BGR)
            h, w = bgr.shape[:2]
            if h < 2 or w < 2:
                return bgr

            by = max(2, int(h * border_ratio))
            bx = max(2, int(w * border_ratio))
            return cv2.copyMakeBorder(bgr, by, by, bx, bx, borderType=cv2.BORDER_REPLICATE)
        except Exception:
            return plate_img

    def _crop_plate_roi(self, frame_original, plate_bbox, pad_x_ratio, pad_y_ratio):
        """Crop plate ROI with configurable padding ratios."""
        try:
            x1, y1, x2, y2 = plate_bbox
            plate_w = max(1, x2 - x1)
            plate_h = max(1, y2 - y1)

            pad_x = int(plate_w * pad_x_ratio)
            pad_y = int(plate_h * pad_y_ratio)

            cx1 = x1 - pad_x
            cy1 = y1 - pad_y
            cx2 = x2 + pad_x
            cy2 = y2 + pad_y

            h, w = frame_original.shape[:2]
            cx1 = max(0, min(cx1, w - 1))
            cy1 = max(0, min(cy1, h - 1))
            cx2 = max(cx1 + 1, min(cx2, w))
            cy2 = max(cy1 + 1, min(cy2, h))

            roi = frame_original[cy1:cy2, cx1:cx2]
            if roi is None or getattr(roi, 'size', 0) == 0:
                return None
            return roi
        except Exception:
            return None

    def _build_plate_rois(self, frame_original, plate_bbox, heavy_mode=False):
        """Create multiple padded crops to avoid tight-box OCR failures."""
        roi_specs = [('base', 0.20, 0.32)]
        if heavy_mode:
            roi_specs.extend([
                ('wide', 0.32, 0.44),
                ('xwide', 0.45, 0.55),
                ('tall', 0.28, 0.65),
            ])

        rois = []
        for name, px, py in roi_specs:
            roi = self._crop_plate_roi(frame_original, plate_bbox, px, py)
            if roi is not None and getattr(roi, 'size', 0) > 0:
                rois.append((name, roi))

        # Fallback to original bbox crop if padded extraction failed.
        if not rois:
            fallback = self._crop_plate_roi(frame_original, plate_bbox, 0.0, 0.0)
            if fallback is not None and getattr(fallback, 'size', 0) > 0:
                rois.append(('fallback', fallback))

        return rois

    def _split_plate_lines(self, plate_img):
        """Split likely 2-line plate into top and bottom crops."""
        h, w = plate_img.shape[:2]
        if h < 24:
            return []

        # 2-line plates are usually taller relative to width.
        if (w / max(1, h)) > 2.2:
            return []

        split_y = int(h * 0.5)
        pad = max(1, int(h * 0.06))
        top = plate_img[0:max(1, split_y + pad), :]
        bottom = plate_img[max(0, split_y - pad):h, :]

        lines = []
        if getattr(top, 'size', 0) > 0:
            lines.append(('line_top', top))
        if getattr(bottom, 'size', 0) > 0:
            lines.append(('line_bottom', bottom))
        return lines

    def _recognize_from_candidates(self, candidates, heavy_mode=False):
        """Try OCR backends over candidate images and return first good text."""
        for variant_name, candidate in candidates:
            easy_text = self._recognize_with_easyocr(candidate)
            if easy_text:
                if self.enable_ocr_debug_logs:
                    print(f"✅ EasyOCR raw ({variant_name}): '{easy_text}'")
                return easy_text

        if self.ocr is not None:
            paddle_limit = self.max_paddle_candidates_heavy if heavy_mode else self.max_paddle_candidates_quick
            for variant_name, candidate in candidates[:paddle_limit]:
                try:
                    result = self.ocr.ocr(candidate)
                except Exception:
                    continue

                if result:
                    extracted = self._extract_texts_from_paddle_result(result, min_conf=0.35)
                    if extracted:
                        texts = [t for t, _ in extracted]
                        final_text = self._normalize_plate_text("".join(texts))
                        if final_text:
                            if self.enable_ocr_debug_logs:
                                print(f"✅ PaddleOCR raw ({variant_name}): '{final_text}'")
                            return final_text

        return ""

    def _select_ocr_candidates(self, candidates, heavy_mode=False):
        """Select a lightweight or full OCR variant set for this attempt."""
        if heavy_mode:
            return candidates[:28]

        quick_names = {'original', 'gray', 'clahe', 'otsu', 'adaptive'}
        selected = []
        for item in candidates:
            name = item[0]
            base_name = name.split('|', 1)[-1] if '|' in name else name
            if base_name in quick_names:
                selected.append(item)

        if selected:
            return selected[:8]
        return candidates[:4]

    def _recognize_with_easyocr(self, bgr_image):
        """Primary OCR method using EasyOCR for plate recognition."""
        if not EASYOCR_AVAILABLE:
            return ""

        try:
            easyocr = importlib.import_module("easyocr")
            if self.easyocr_reader is None:
                import torch
                self.easyocr_reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available(), verbose=False)

            result = self.easyocr_reader.readtext(
                bgr_image,
                detail=1,
                paragraph=False,
                allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'  # License plate chars
            )

            if not result:
                return ""

            texts = []
            for item in result:
                # Expected: (bbox, text, confidence)
                if isinstance(item, (list, tuple)) and len(item) >= 3:
                    text = str(item[1]).strip()
                    try:
                        conf = float(item[2])
                    except Exception:
                        conf = 0.0
                    # Use lower threshold (0.2) to catch more potential plates, validate format later
                    if text and conf >= 0.2:
                        texts.append(text)

            if not texts:
                return ""

            normalized = self._normalize_plate_text("".join(texts))
            return normalized
        except Exception as e:
            # Silently fail to avoid disrupting main flow
            return ""
    
    def recognize_plate_text(self, frame_original, plate_bbox, heavy_mode=False, veh_track_id=None):
        """Run OCR on license plate region from original frame - Primary: EasyOCR, Fallback: PaddleOCR
        
        Args:
            frame_original: Original full-size frame
            plate_bbox: (x1, y1, x2, y2) of plate in original coordinates
            
        Returns:
            str: Recognized text or empty string
        """
        if not EASYOCR_AVAILABLE and self.ocr is None:
            return ""
        
        try:
            rois = self._build_plate_rois(frame_original, plate_bbox, heavy_mode=heavy_mode)
            if self.enable_ocr_debug_logs:
                x1, y1, x2, y2 = plate_bbox
                print(f"🔎 OCR input bbox: ({x1},{y1},{x2},{y2}), roi_count={len(rois)}")

            if not rois:
                return ""

            cache_seed_img = rois[0][1]
            reused_text, reused = self._try_reuse_recent_ocr(veh_track_id, cache_seed_img, heavy_mode=heavy_mode)
            if reused:
                if self.enable_ocr_debug_logs:
                    cache_state = "hit_text" if reused_text else "hit_empty"
                    print(f"🧠 OCR cache {cache_state} for Vehicle ID:{veh_track_id}")
                return reused_text

            # In heavy traffic, keep heavy OCR on top ROIs only.
            if heavy_mode and self._ocr_frame_budget <= self.max_ocr_jobs_per_frame_high_traffic:
                rois = rois[:2]

            quick_mode = not heavy_mode
            for roi_name, plate_img in rois:
                bordered = self._add_safe_plate_border(plate_img)
                # Keep quick pass cheap: rectify only the base ROI.
                if heavy_mode or roi_name == 'base':
                    rectified = self._rectify_plate_perspective(bordered)
                else:
                    rectified = bordered
                enhanced_raw = self._enhance_plate_for_readability(bordered, fast_mode=quick_mode)
                enhanced_rect = self._enhance_plate_for_readability(rectified, fast_mode=quick_mode)

                # Pipeline: crop -> border -> perspective rectify -> readability enhancement -> OCR variants.
                seed_plan = [
                    (f"{roi_name}_rect_enh", enhanced_rect),
                    (f"{roi_name}_raw_enh", enhanced_raw),
                ]
                if heavy_mode:
                    if self._ocr_frame_budget > self.max_ocr_jobs_per_frame_high_traffic:
                        seed_plan.extend([
                            (f"{roi_name}_rect", rectified),
                            (f"{roi_name}_raw", bordered),
                        ])

                roi_candidates = []
                for seed_name, seed_img in seed_plan:
                    if seed_img is None or getattr(seed_img, 'size', 0) == 0:
                        continue
                    seed_candidates = self._build_ocr_variants(seed_img, quick_mode=quick_mode)
                    roi_candidates.extend((f"{seed_name}|{name}", img) for name, img in seed_candidates)

                pass_candidates = self._select_ocr_candidates(roi_candidates, heavy_mode=heavy_mode)
                if self.enable_ocr_debug_logs:
                    variant_names = [name for name, _ in pass_candidates]
                    mode_name = "heavy" if heavy_mode else "quick"
                    print(f"🧩 OCR variants ({mode_name}, {roi_name}): {variant_names}")

                text = self._recognize_from_candidates(pass_candidates, heavy_mode=heavy_mode)
                if text:
                    return self._finalize_ocr_result(veh_track_id, cache_seed_img, text, heavy_mode=heavy_mode)

                # In quick mode, try only base ROI and exit fast.
                if quick_mode:
                    break

            # In quick mode, stop early to keep realtime FPS stable.
            if not heavy_mode:
                return self._finalize_ocr_result(veh_track_id, cache_seed_img, "", heavy_mode=heavy_mode)

            # Rescue path for hard cases: deskew + enhance + 2-line split OCR.
            rescue_seed = self._enhance_plate_for_readability(self._add_safe_plate_border(rois[0][1]), fast_mode=False)
            rescued = self._deskew_plate_image(rescue_seed)
            rescued_enh = self._enhance_plate_for_readability(rescued, fast_mode=False)

            rescue_candidates = []
            rescue_candidates.extend((f"rescue_enh|{name}", img) for name, img in self._build_ocr_variants(rescued_enh))
            rescue_candidates.extend((f"rescue|{name}", img) for name, img in self._build_ocr_variants(rescued))
            text = self._recognize_from_candidates(rescue_candidates, heavy_mode=True)
            if text:
                return self._finalize_ocr_result(veh_track_id, cache_seed_img, text, heavy_mode=heavy_mode)

            # Final fallback: OCR line-by-line for possible 2-line plates.
            lines = self._split_plate_lines(rescued_enh)
            if lines:
                top_text = ""
                bottom_text = ""
                for line_name, line_img in lines:
                    line_enh = self._enhance_plate_for_readability(line_img, fast_mode=False)
                    line_candidates = self._build_ocr_variants(line_enh)
                    line_text = self._recognize_from_candidates(line_candidates, heavy_mode=True)
                    if line_name == 'line_top':
                        top_text = line_text
                    else:
                        bottom_text = line_text

                merged = self._normalize_plate_text(f"{top_text}{bottom_text}")
                if merged:
                    if self.enable_ocr_debug_logs:
                        print(f"✅ OCR rescue merged lines: '{merged}'")
                    return self._finalize_ocr_result(veh_track_id, cache_seed_img, merged, heavy_mode=heavy_mode)

            if self.enable_ocr_debug_logs:
                print("⚠️ OCR result: no readable text")
            return self._finalize_ocr_result(veh_track_id, cache_seed_img, "", heavy_mode=heavy_mode)
            
        except Exception as e:
            # Silently fail OCR errors to not disrupt detection
            return ""
    
    def set_reference_angle(self, ref_angle: float):
        """Update reference angle for direction detection
        
        Args:
            ref_angle: Reference angle in degrees (-180 to 180) for straight direction
        """
        self.vehicle_tracker.set_ref_angle(ref_angle)
        print(f"🧭 VideoThread: Reference angle set to {ref_angle:.1f}°")

    def set_paused(self, paused):
        """Pause or resume playback without stopping the processing thread."""
        with self._playback_lock:
            self.playback_paused = bool(paused)

    def toggle_paused(self):
        """Toggle pause state and return the new state."""
        with self._playback_lock:
            self.playback_paused = not self.playback_paused
            return self.playback_paused

    def request_seek_to_seconds(self, target_sec):
        """Request an absolute seek target in seconds."""
        safe_target = max(0.0, float(target_sec))
        with self._playback_lock:
            if self.video_duration_sec > 0:
                safe_target = min(safe_target, self.video_duration_sec)
            self._pending_seek_target_sec = safe_target

    def request_seek_relative(self, delta_sec):
        """Request seek relative to current playback position."""
        with self._playback_lock:
            target = self.current_playback_sec + float(delta_sec)
            if self.video_duration_sec > 0:
                target = min(max(0.0, target), self.video_duration_sec)
            else:
                target = max(0.0, target)
            self._pending_seek_target_sec = target

    def _consume_playback_commands(self):
        """Fetch latest pause/seek commands atomically."""
        with self._playback_lock:
            paused = self.playback_paused
            seek_target = self._pending_seek_target_sec
            self._pending_seek_target_sec = None
        return paused, seek_target

    def _emit_playback_info(self, cap, force=False):
        """Emit playback metadata for UI timeline/labels."""
        now = time.time()
        if not force and (now - self._last_playback_emit_time) < 0.08:
            return

        pos_msec = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
        if pos_msec > 0:
            current_sec = pos_msec / 1000.0
        else:
            frame_idx = float(cap.get(cv2.CAP_PROP_POS_FRAMES) or 0.0)
            fps_safe = max(1e-6, self.video_fps)
            current_sec = frame_idx / fps_safe

        with self._playback_lock:
            self.current_playback_sec = max(0.0, current_sec)
            paused = self.playback_paused

        info = {
            'current_sec': self.current_playback_sec,
            'duration_sec': max(0.0, self.video_duration_sec),
            'fps': self.video_fps,
            'paused': paused,
        }
        self.playback_info_signal.emit(info)
        self._last_playback_emit_time = now

    def _apply_seek_request(self, cap, target_sec):
        """Seek capture and return the fetched frame at the requested position."""
        fps_safe = max(1e-6, self.video_fps)
        if self.video_total_frames > 0:
            target_frame = int(round(target_sec * fps_safe))
            target_frame = min(max(0, target_frame), self.video_total_frames - 1)
        else:
            target_frame = max(0, int(round(target_sec * fps_safe)))

        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        if not ret:
            return None

        self.current_playback_sec = target_frame / fps_safe
        return frame
    
    def run(self):
        """Main video processing loop"""
        cap = cv2.VideoCapture(self.video_path)
        self.fps_start_time = time.time()
        
        # Get video FPS
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps == 0:
            video_fps = 30

        self.video_fps = float(video_fps)
        self.video_total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if self.video_total_frames > 0 and self.video_fps > 0:
            self.video_duration_sec = self.video_total_frames / self.video_fps
        else:
            self.video_duration_sec = 0.0
        self.current_playback_sec = 0.0
        self._last_playback_emit_time = 0.0
        self._emit_playback_info(cap, force=True)
        
        frame_interval = 1.0 / video_fps
        next_frame_time = time.time()

        # Render loop runs at a stable and usually lower FPS than detection.
        effective_display_fps = max(1, self.target_display_fps)
        if self.stable_display_mode:
            effective_display_fps = min(effective_display_fps, max(1, self.stable_display_fps))
        display_interval = 1.0 / effective_display_fps
        next_display_time = time.time()
        last_render_frame = None
        
        print(f"📹 Video FPS: {video_fps}, Frame interval: {frame_interval:.4f}s")
        print(f"⏱️ Realtime mode: {'ON (may skip frames)' if self.realtime_mode else 'OFF (process all frames)'}")
        print(f"🎯 Display FPS: target={self.target_display_fps}, render={effective_display_fps}")
        
        while self._run_flag:
            current_time = time.time()

            # Track FPS on a fixed interval (display and detection are measured separately).
            elapsed = current_time - self.fps_start_time
            if elapsed >= self.runtime_fps_log_interval_sec:
                self.fps = int(round(self.display_count / max(elapsed, 1e-6)))
                self.processed_fps = int(round(self.processed_count / max(elapsed, 1e-6)))
                if self.enable_runtime_fps_logs:
                    if self.realtime_mode:
                        print(f"📊 Display FPS: {self.fps} | Detection FPS: {self.processed_fps} | Skipped: {self.skipped_frames}")
                    else:
                        print(f"📊 Display FPS: {self.fps} | Detection FPS: {self.processed_fps}")
                self.frame_count = 0
                self.display_count = 0
                self.processed_count = 0
                self.skipped_frames = 0
                self.fps_start_time = current_time

            paused, seek_target_sec = self._consume_playback_commands()
            if seek_target_sec is not None:
                seek_frame = self._apply_seek_request(cap, seek_target_sec)
                if seek_frame is not None:
                    if self.detection_enabled and self.model is not None and self.model_loaded:
                        try:
                            seek_frame = self.process_detection(seek_frame)
                            self.processed_count += 1
                        except Exception as e:
                            print(f"⚠️ Detection error during seek: {e}")
                            self.error_signal.emit(str(e))
                            self.detection_enabled = False

                    last_render_frame = seek_frame
                    self.change_pixmap_signal.emit(last_render_frame)
                    self.display_count += 1

                now = time.time()
                next_frame_time = now + frame_interval
                next_display_time = now + display_interval
                self._emit_playback_info(cap, force=True)

            if paused:
                if (self.repeat_last_frame_for_smoothness and
                    last_render_frame is not None and
                    current_time >= next_display_time):
                    self.change_pixmap_signal.emit(last_render_frame)
                    self.display_count += 1
                    next_display_time += display_interval
                    if next_display_time < current_time - display_interval:
                        next_display_time = current_time + display_interval

                self._emit_playback_info(cap)
                self.msleep(12)
                continue
            
            if self.realtime_mode:
                # REALTIME MODE: Skip frames to match real-time
                if current_time >= next_frame_time:
                    ret, frame = cap.read()
                    if ret:
                        self.frame_count += 1
                        
                        if self.detection_enabled and self.model is not None and self.model_loaded:
                            try:
                                frame = self.process_detection(frame)
                                self.processed_count += 1  # Count actual detections
                            except Exception as e:
                                print(f"⚠️ Detection error: {e}")
                                self.error_signal.emit(str(e))
                                self.detection_enabled = False

                        # Stable render cadence: detection can run fast/slow independently.
                        last_render_frame = frame
                        if current_time >= next_display_time:
                            self.change_pixmap_signal.emit(last_render_frame)
                            self.display_count += 1
                            next_display_time += display_interval
                            if next_display_time < current_time - display_interval:
                                next_display_time = current_time + display_interval
                        self._emit_playback_info(cap)
                        
                        next_frame_time += frame_interval
                        
                        # If falling behind, reset
                        if next_frame_time < current_time:
                            next_frame_time = current_time + frame_interval
                    else:
                        # Video ended, loop back
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        self._clear_all_state()
                        next_frame_time = time.time()
                        next_display_time = next_frame_time
                        self.current_playback_sec = 0.0
                        self._emit_playback_info(cap, force=True)
                else:
                    self.skipped_frames += 1  # Count skipped frames

                    # Keep UI smooth by replaying the latest rendered frame at fixed cadence.
                    if (self.repeat_last_frame_for_smoothness and
                        last_render_frame is not None and
                        current_time >= next_display_time):
                        self.change_pixmap_signal.emit(last_render_frame)
                        self.display_count += 1
                        next_display_time += display_interval
                        if next_display_time < current_time - display_interval:
                            next_display_time = current_time + display_interval
                        self._emit_playback_info(cap)
                    else:
                        # Short sleep reduces spin while preserving realtime responsiveness.
                        self.msleep(6)
            else:
                # FULL PROCESSING MODE: Process every frame (no skip)
                ret, frame = cap.read()
                if ret:
                    self.frame_count += 1
                    
                    if self.detection_enabled and self.model is not None and self.model_loaded:
                        try:
                            frame = self.process_detection(frame)
                            self.processed_count += 1  # Count actual detections
                        except Exception as e:
                            print(f"⚠️ Detection error: {e}")
                            self.error_signal.emit(str(e))
                            self.detection_enabled = False

                    last_render_frame = frame
                    if current_time >= next_display_time:
                        self.change_pixmap_signal.emit(last_render_frame)
                        self.display_count += 1
                        next_display_time += display_interval
                        if next_display_time < current_time - display_interval:
                            next_display_time = current_time + display_interval
                    self._emit_playback_info(cap)
                    
                    # ⚠️ PERFORMANCE: Small sleep to yield CPU
                    self.msleep(5)
                else:
                    # Video ended, loop back
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self._clear_all_state()
                    next_display_time = time.time()
                    self.current_playback_sec = 0.0
                    self._emit_playback_info(cap, force=True)
            
        cap.release()
    
    def _clear_all_state(self):
        """Clear all tracking and violation state"""
        # Clear OOP modules
        self.vehicle_tracker.clear()
        self.violation_detector.clear()
        
        # Clear license plate positions
        self.vehicle_plate_positions.clear()
        self.vehicle_ocr_texts.clear()
        self.vehicle_stable_plates.clear()
        self.vehicle_plate_smoothing.clear()
        self.vehicle_ocr_votes.clear()
        self.vehicle_ocr_history.clear()
        self.vehicle_to_plate_map.clear()
        self.vehicle_ocr_attempts.clear()
        self.vehicle_last_ocr_frame.clear()
        self.vehicle_ocr_signature_cache.clear()
        self._ocr_jobs_this_frame = 0
        self._ocr_frame_budget = self.max_ocr_jobs_per_frame
        self.current_frame_count = 0
        
        # Also clear global sets for backward compatibility
        if self.globals_ref:
            self.globals_ref['VIOLATOR_TRACK_IDS'].clear()
            self.globals_ref['RED_LIGHT_VIOLATORS'].clear()
            self.globals_ref['LANE_VIOLATORS'].clear()
            self.globals_ref['PASSED_VEHICLES'].clear()
            self.globals_ref['MOTORBIKE_COUNT'].clear()
            self.globals_ref['CAR_COUNT'].clear()

    def _update_ocr_frame_budget(self, vehicle_count, plate_count):
        """Adapt per-frame OCR budget to scene load to avoid frame-time spikes."""
        if not self.enable_ocr:
            self._ocr_frame_budget = 0
            return

        load_count = max(vehicle_count, plate_count)
        if load_count >= self.ocr_high_traffic_vehicle_threshold:
            self._ocr_frame_budget = self.max_ocr_jobs_per_frame_high_traffic
        elif load_count >= self.ocr_medium_traffic_vehicle_threshold:
            self._ocr_frame_budget = self.max_ocr_jobs_per_frame
        else:
            self._ocr_frame_budget = self.max_ocr_jobs_per_frame_low_traffic

    def _should_attempt_ocr(self, veh_track_id, plate_w, plate_h):
        """Return True when OCR should run for this vehicle in current frame."""
        if not self.enable_ocr:
            return False

        if plate_w < self.min_ocr_plate_width or plate_h < self.min_ocr_plate_height:
            return False

        if self._ocr_jobs_this_frame >= self._ocr_frame_budget:
            return False

        has_stable_plate = bool(self.vehicle_stable_plates.get(veh_track_id))
        every_n_frames = self.ocr_process_every_n_frames if has_stable_plate else self.ocr_bootstrap_every_n_frames
        retry_interval = self.ocr_retry_interval_frames if has_stable_plate else self.ocr_bootstrap_retry_interval_frames

        # Spread OCR calls over frames to reduce spikes.
        slot = veh_track_id % every_n_frames
        if (self.current_frame_count % every_n_frames) != slot:
            return False

        attempts = self.vehicle_ocr_attempts.get(veh_track_id, 0)
        if attempts >= self.max_ocr_attempts_per_vehicle:
            return False

        last_frame = self.vehicle_last_ocr_frame.get(veh_track_id, -10**9)
        return (self.current_frame_count - last_frame) >= retry_interval

    def _get_ocr_skip_reason(self, veh_track_id, plate_w, plate_h):
        """Return human-readable reason when OCR is skipped."""
        if not self.enable_ocr:
            return "OCR disabled"

        if plate_w < self.min_ocr_plate_width or plate_h < self.min_ocr_plate_height:
            return f"plate too small ({plate_w}x{plate_h})"

        if self._ocr_jobs_this_frame >= self._ocr_frame_budget:
            return f"frame OCR budget reached ({self._ocr_frame_budget})"

        has_stable_plate = bool(self.vehicle_stable_plates.get(veh_track_id))
        every_n_frames = self.ocr_process_every_n_frames if has_stable_plate else self.ocr_bootstrap_every_n_frames
        retry_interval = self.ocr_retry_interval_frames if has_stable_plate else self.ocr_bootstrap_retry_interval_frames

        slot = veh_track_id % every_n_frames
        if (self.current_frame_count % every_n_frames) != slot:
            return f"frame slot skip (every {every_n_frames} frames)"

        attempts = self.vehicle_ocr_attempts.get(veh_track_id, 0)
        if attempts >= self.max_ocr_attempts_per_vehicle:
            return f"max attempts reached ({attempts})"

        last_frame = self.vehicle_last_ocr_frame.get(veh_track_id, -10**9)
        wait_left = retry_interval - (self.current_frame_count - last_frame)
        if wait_left > 0:
            return f"retry cooldown ({wait_left} frames left)"

        return "unknown"

    def _is_loose_ocr_candidate(self, plate_text):
        """Allow near-valid OCR strings to be stabilized when strict parser fails."""
        cleaned = _sanitize_ocr_text(plate_text)
        if len(cleaned) < 8 or len(cleaned) > 10:
            return False
        if not cleaned[:2].isdigit():
            return False
        digit_count = sum(ch.isdigit() for ch in cleaned)
        return digit_count >= 6

    def _register_plate_vote(self, veh_track_id, plate_text):
        """Register a validated plate observation and return the current best vote."""
        if not plate_text:
            return ""

        history = self.vehicle_ocr_history.setdefault(veh_track_id, [])
        history.append(plate_text)
        if len(history) > self.max_ocr_history_per_vehicle:
            del history[0]

        vehicle_votes = self.vehicle_ocr_votes.setdefault(veh_track_id, {})
        vote_entry = vehicle_votes.get(plate_text, {'count': 0, 'last_frame': 0})
        vote_entry['count'] += 1
        vote_entry['last_frame'] = self.current_frame_count
        vehicle_votes[plate_text] = vote_entry

        # Recompute soft vote from recent history only (bounded memory).
        recent_scores = defaultdict(float)
        for idx, candidate in enumerate(history):
            # Recent observations get slightly higher weight.
            recent_scores[candidate] += 1.0 + (idx / max(1, len(history))) * 0.2

        best_plate = max(recent_scores.items(), key=lambda item: (item[1], -history[::-1].index(item[0])))[0]
        return best_plate

    def _update_stable_plate(self, veh_track_id, canonical_plate):
        """Update stable per-vehicle plate only after consecutive-frame confirmation.

        Returns the stable plate if one exists; otherwise returns an empty string.
        """
        if not canonical_plate:
            return self.vehicle_stable_plates.get(veh_track_id, '')

        best_plate = self._register_plate_vote(veh_track_id, canonical_plate)

        smoothing = self.vehicle_plate_smoothing.get(veh_track_id, {
            'candidate': '',
            'streak': 0,
            'last_frame': -10**9,
        })

        if smoothing['candidate'] == best_plate:
            smoothing['streak'] += 1
        else:
            smoothing['candidate'] = best_plate
            smoothing['streak'] = 1

        smoothing['last_frame'] = self.current_frame_count
        self.vehicle_plate_smoothing[veh_track_id] = smoothing

        stable_plate = self.vehicle_stable_plates.get(veh_track_id, '')
        if not stable_plate:
            if smoothing['streak'] >= self.plate_initial_confirm_frames:
                self.vehicle_stable_plates[veh_track_id] = best_plate
                return best_plate
            return ''

        if best_plate == stable_plate:
            return stable_plate

        if smoothing['streak'] >= self.plate_switch_confirm_frames:
            self.vehicle_stable_plates[veh_track_id] = best_plate
            return best_plate

        return stable_plate

    def _build_ocr_variants(self, plate_img, quick_mode=False):
        """Create several OCR-ready image variants from a plate crop."""
        variants = []

        def add_variant(name, img):
            if img is not None and getattr(img, 'size', 0) > 0:
                variants.append((name, img))

        original_bgr = plate_img if len(plate_img.shape) == 3 else cv2.cvtColor(plate_img, cv2.COLOR_GRAY2BGR)
        add_variant('original', original_bgr)

        # Basic grayscale / equalization / sharpening family.
        gray = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2GRAY)
        add_variant('gray', cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))

        if quick_mode:
            clahe_fast = cv2.createCLAHE(clipLimit=2.6, tileGridSize=(8, 8)).apply(gray)
            add_variant('clahe', cv2.cvtColor(clahe_fast, cv2.COLOR_GRAY2BGR))

            otsu_fast = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            add_variant('otsu', cv2.cvtColor(otsu_fast, cv2.COLOR_GRAY2BGR))

            ph, pw = original_bgr.shape[:2]
            if ph < 44 or pw < 140:
                scaled = cv2.resize(original_bgr, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                add_variant('original_x2', scaled)

            return variants

        eq = cv2.equalizeHist(gray)
        add_variant('equalized', cv2.cvtColor(eq, cv2.COLOR_GRAY2BGR))

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
        add_variant('clahe', cv2.cvtColor(clahe, cv2.COLOR_GRAY2BGR))

        denoised = cv2.fastNlMeansDenoising(gray, None, 15, 7, 21)
        add_variant('denoised', cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR))

        sharpen_kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(gray, -1, sharpen_kernel)
        add_variant('sharpened', cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR))

        # Threshold variants help with glare / low contrast frames.
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 31, 7)
        add_variant('adaptive', cv2.cvtColor(adaptive, cv2.COLOR_GRAY2BGR))

        otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        add_variant('otsu', cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR))

        # Keep the default path lightweight; heavy upscaling only for tiny crops.
        ph, pw = original_bgr.shape[:2]
        if ph < 50 or pw < 160:
            for scale in (2.0, 4.0):
                scaled_original = cv2.resize(original_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                add_variant(f'original_x{int(scale)}', scaled_original)

                scaled_gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                scaled_clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(scaled_gray)
                add_variant(f'clahe_x{int(scale)}', cv2.cvtColor(scaled_clahe, cv2.COLOR_GRAY2BGR))

                scaled_sharp = cv2.filter2D(scaled_gray, -1, sharpen_kernel)
                add_variant(f'sharpened_x{int(scale)}', cv2.cvtColor(scaled_sharp, cv2.COLOR_GRAY2BGR))
        else:
            # For normal-size crops, keep a medium set for better OCR quality.
            variants = [v for v in variants if v[0] in {'original', 'gray', 'clahe', 'otsu', 'adaptive', 'sharpened'}]

        return variants
    
    def set_model(self, model):
        """Set pre-loaded model from main thread"""
        self.model = model
        self.model_loaded = True
        print("✅ Model set in thread")
    
    def process_detection(self, frame):
        """Process YOLO detection on original frame
        
        Args:
            frame: Original full-size frame
        
        Returns:
            frame: Frame with drawings (same as input)
        """
        if not self.globals_ref:
            print("⚠️ globals_ref is None!")
            return frame
        
        # Keep original frame size for display and OCR
        frame_original = frame
        orig_h, orig_w = frame.shape[:2]
        
        # Debug: First call
        if not hasattr(self, '_debug_first_detection'):
            self._debug_first_detection = True
            if self.enable_perf_logs:
                print(f"✅ First detection call - Frame size: {orig_w}x{orig_h}")
                print(f"   Model config: {self.model_config}")
        
        # Get global state references
        ALLOWED_VEHICLE_IDS = self.globals_ref['ALLOWED_VEHICLE_IDS']
        VEHICLE_CLASSES = self.globals_ref['VEHICLE_CLASSES']
        LANE_CONFIGS = self.globals_ref['LANE_CONFIGS']
        TL_ROIS = self.globals_ref['TL_ROIS']
        DIRECTION_ROIS = self.globals_ref.get('DIRECTION_ROIS', [])
        # Don't cache _show_all_boxes - read it fresh each time to get latest value
        is_on_stop_line = self.globals_ref['is_on_stop_line']
        check_tl_violation = self.globals_ref['check_tl_violation']
        point_in_polygon = self.globals_ref['point_in_polygon']
        
        # Backward compat globals
        VIOLATOR_TRACK_IDS = self.globals_ref['VIOLATOR_TRACK_IDS']
        RED_LIGHT_VIOLATORS = self.globals_ref['RED_LIGHT_VIOLATORS']
        LANE_VIOLATORS = self.globals_ref['LANE_VIOLATORS']
        DIRECTION_VIOLATORS = self.globals_ref.get('DIRECTION_VIOLATORS', set())
        PASSED_VEHICLES = self.globals_ref['PASSED_VEHICLES']
        MOTORBIKE_COUNT = self.globals_ref['MOTORBIKE_COUNT']
        CAR_COUNT = self.globals_ref['CAR_COUNT']
        
        # Get model config or use defaults
        imgsz = 640
        conf = 0.3
        classes = [0, 1, 3, 4]
        
        if self.model_config:
            imgsz = self.model_config.get('default_imgsz', 640)
            conf = self.model_config.get('default_conf', 0.3)
            classes = self.model_config.get('classes', [0, 1, 3, 4])
        
        # Run YOLO tracking with dynamic config
        # YOLO will resize image internally according to imgsz
        results = self.model.track(
            frame,
            tracker="bytetrack.yaml",
            persist=True,
            classes=classes,
            verbose=False,
            imgsz=imgsz,
            conf=conf,
            device=self.yolo_device,
            half=self.yolo_half
        )
        
        # Calculate scale factors from YOLO resized size back to original
        # YOLO returns bbox in original coordinates already? Let's check
        # If bbox looks wrong, we need to scale it
        
        vehicles = []
        license_plates = []
        
        if results[0].boxes is not None:
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                conf_val = float(box.conf[0])
                # YOLO bbox is already in original frame coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                if cls_id in ALLOWED_VEHICLE_IDS:
                    track_id = int(box.id[0]) if box.id is not None else -1
                    
                    if cls_id == 5:  # License plate
                        # Always separate plates for mapping to vehicles
                        license_plates.append({
                            "track_id": track_id,
                            "box": (x1, y1, x2, y2),
                            "conf": conf_val
                        })
                    else:  # Vehicle (not plate)
                        vehicles.append({
                            "track_id": track_id,
                            "cls_id": cls_id,
                            "box": (x1, y1, x2, y2),
                            "conf": conf_val
                        })
        
        # === MAP LICENSE PLATES TO VEHICLES ===
        # Works for both YOLO Direct and Relative Tracking modes
        self.current_frame_count += 1
        self._ocr_jobs_this_frame = 0
        self._update_ocr_frame_budget(len(vehicles), len(license_plates))
        
        # Debug: Log detections periodically
        if self.enable_perf_logs:
            if not hasattr(self, '_debug_frame_count'):
                self._debug_frame_count = 0
            self._debug_frame_count += 1
            if self._debug_frame_count % 30 == 0:  # Every 30 frames
                print(
                    f"📊 Detection stats: {len(vehicles)} vehicles, {len(license_plates)} plates, "
                    f"ocr budget={self._ocr_frame_budget}, used={self._ocr_jobs_this_frame}"
                )
        
        current_vehicle_ids = set()
        for veh in vehicles:
            if veh["track_id"] != -1:
                current_vehicle_ids.add(veh["track_id"])

        # Prioritize clearer/bigger plate detections so limited OCR budget is spent effectively.
        license_plates.sort(
            key=lambda p: (
                self._compute_plate_priority(
                    p["box"][2] - p["box"][0],
                    p["box"][3] - p["box"][1],
                    p.get("conf", 0.0),
                ),
                p.get("conf", 0.0),
            ),
            reverse=True,
        )
        
        # Check each detected plate
        for plate in license_plates:
            plate_x1, plate_y1, plate_x2, plate_y2 = plate["box"]
            plate_cx = (plate_x1 + plate_x2) / 2.0
            plate_cy = (plate_y1 + plate_y2) / 2.0
            plate_w = plate_x2 - plate_x1
            plate_h = plate_y2 - plate_y1
            
            # Find vehicle candidates that fully contain this plate.
            # If multiple vehicles contain it, keep mapping stable by preferring
            # previous mapping for this plate track; otherwise use tightest bbox.
            best_match = None
            candidate_matches = []
            
            for veh in vehicles:
                veh_x1, veh_y1, veh_x2, veh_y2 = veh["box"]
                veh_track_id = veh["track_id"]
                
                if veh_track_id == -1:
                    continue
                
                # ✅ STRICT CHECK: Plate must be 100% inside vehicle bbox
                # All 4 corners of plate must be within vehicle bounds
                if (plate_x1 >= veh_x1 and plate_x2 <= veh_x2 and 
                    plate_y1 >= veh_y1 and plate_y2 <= veh_y2):
                    veh_area = max(1, (veh_x2 - veh_x1) * (veh_y2 - veh_y1))
                    candidate_matches.append((veh_area, veh))

            if candidate_matches:
                plate_track_id = plate["track_id"]

                # 1) Prefer old vehicle-id mapping for this same plate track id.
                preferred_vehicle_id = None
                for mapped_veh_id, mapped_plate_id in self.vehicle_to_plate_map.items():
                    if mapped_plate_id == plate_track_id and mapped_veh_id in current_vehicle_ids:
                        preferred_vehicle_id = mapped_veh_id
                        break

                if preferred_vehicle_id is not None:
                    for _, veh in candidate_matches:
                        if veh["track_id"] == preferred_vehicle_id:
                            best_match = veh
                            break

                # 2) Fallback: choose tightest vehicle bbox around plate.
                if best_match is None:
                    best_match = min(candidate_matches, key=lambda item: item[0])[1]
            
            # If found matching vehicle (plate 100% inside)
            if best_match:
                veh_track_id = best_match["track_id"]
                veh_cls_id = best_match["cls_id"]  # Get vehicle class for plate validation
                veh_x1, veh_y1, veh_x2, veh_y2 = best_match["box"]
                
                veh_w = veh_x2 - veh_x1
                veh_h = veh_y2 - veh_y1
                
                if veh_w > 0 and veh_h > 0:
                    # === YOLO DIRECT MODE: Just run OCR and store text ===
                    if not self.use_plate_relative_tracking:
                        # Map vehicle to plate track_id
                        plate_track_id = plate["track_id"]
                        self.vehicle_to_plate_map[veh_track_id] = plate_track_id
                        
                        if self.enable_ocr_debug_logs:
                            print(f"📍 Mapped Plate ID:{plate_track_id} → Vehicle ID:{veh_track_id}")
                        
                        # Check if vehicle already has VALID OCR text (not empty string)
                        existing_plate = self.vehicle_ocr_texts.get(veh_track_id)
                        if existing_plate and existing_plate != "":
                            # Already have valid plate, skip OCR
                            pass
                        else:
                            should_ocr = self._should_attempt_ocr(veh_track_id, plate_w, plate_h)
                            if should_ocr:
                                self.vehicle_last_ocr_frame[veh_track_id] = self.current_frame_count
                                self.vehicle_ocr_attempts[veh_track_id] = self.vehicle_ocr_attempts.get(veh_track_id, 0) + 1
                                self._ocr_jobs_this_frame += 1

                                attempt_no = self.vehicle_ocr_attempts[veh_track_id]
                                plate_priority = self._compute_plate_priority(plate_w, plate_h, plate.get("conf", 0.0))
                                heavy_mode = self._should_use_heavy_ocr(attempt_no, plate_priority)

                                if self.enable_ocr_debug_logs:
                                    print(
                                        f"🔍 Attempting OCR for Vehicle ID:{veh_track_id} "
                                        f"(attempt={attempt_no}, heavy={heavy_mode}, priority={plate_priority:.2f})"
                                    )

                                plate_bbox = (int(plate_x1), int(plate_y1), int(plate_x2), int(plate_y2))
                                ocr_text = self.recognize_plate_text(
                                    frame_original,
                                    plate_bbox,
                                    heavy_mode=heavy_mode,
                                    veh_track_id=veh_track_id,
                                )
                                if ocr_text:
                                    # Step 1: Correct character confusion (0↔O, 1↔I, 8↔B, etc.)
                                    corrected_text = correct_plate_characters(ocr_text)
                                    # Step 2: Validate plate format based on vehicle class
                                    is_valid, cleaned_plate = validate_license_plate(corrected_text, veh_cls_id)
                                    if is_valid:
                                        stable_plate = self._update_stable_plate(veh_track_id, cleaned_plate)
                                        if stable_plate:
                                            formatted_plate = format_vietnamese_plate(stable_plate, veh_cls_id)
                                            self.vehicle_ocr_texts[veh_track_id] = formatted_plate
                                            if self.enable_perf_logs:
                                                if corrected_text != ocr_text:
                                                    print(f"✅ OCR [CORRECTED] Vehicle ID:{veh_track_id} → '{ocr_text}' → '{formatted_plate}'")
                                                else:
                                                    print(f"✅ OCR [VALID] Vehicle ID:{veh_track_id} → '{formatted_plate}'")
                                        elif self.enable_ocr_debug_logs:
                                            print(f"⏳ OCR [WAIT STABLE] Vehicle ID:{veh_track_id} → '{cleaned_plate}'")
                                        if stable_plate:
                                            formatted_plate = format_vietnamese_plate(stable_plate, veh_cls_id)
                                            self.vehicle_ocr_texts[veh_track_id] = formatted_plate
                                            if self.enable_ocr_debug_logs:
                                                print(f"🟡 OCR [LOOSE ACCEPT] Vehicle ID:{veh_track_id} → '{formatted_plate}'")
                                    elif self.enable_ocr_debug_logs:
                                        print(f"❌ OCR [INVALID FORMAT] Vehicle ID:{veh_track_id} → '{ocr_text}' → '{corrected_text}' (cleaned: '{cleaned_plate}')")
                            elif self.enable_ocr_debug_logs:
                                reason = self._get_ocr_skip_reason(veh_track_id, plate_w, plate_h)
                                print(f"⏭️ OCR skipped Vehicle ID:{veh_track_id}: {reason}")
                    
                    # === RELATIVE TRACKING MODE: Calculate position and run OCR ===
                    else:
                        # Check if we should update (first time OR 30 frames passed)
                        should_update = False
                        if veh_track_id not in self.vehicle_plate_positions:
                            should_update = True  # First detection
                        else:
                            last_updated = self.vehicle_plate_positions[veh_track_id].get('last_updated_frame', 0)
                            frames_since_update = self.current_frame_count - last_updated
                            if frames_since_update >= self.update_interval:
                                should_update = True  # Time to refresh
                        
                        if should_update:
                            # Calculate relative position for x,y (0.0 to 1.0)
                            x_ratio = (plate_x1 - veh_x1) / veh_w
                            y_ratio = (plate_y1 - veh_y1) / veh_h
                            
                            # Store ABSOLUTE size (not ratio) to keep plate size constant
                            abs_w = int(plate_w)
                            abs_h = int(plate_h)
                            
                            # Run OCR on plate ONLY if this vehicle doesn't have VALID text yet
                            ocr_text = ""
                            if veh_track_id in self.vehicle_plate_positions:
                                # Keep existing OCR text if available and valid
                                ocr_text = self.vehicle_plate_positions[veh_track_id].get('ocr_text', '')
                            
                            # Only run OCR if no valid text exists yet AND OCR is enabled
                            if not ocr_text and self._should_attempt_ocr(veh_track_id, plate_w, plate_h):
                                self.vehicle_last_ocr_frame[veh_track_id] = self.current_frame_count
                                self.vehicle_ocr_attempts[veh_track_id] = self.vehicle_ocr_attempts.get(veh_track_id, 0) + 1
                                self._ocr_jobs_this_frame += 1
                                attempt_no = self.vehicle_ocr_attempts[veh_track_id]
                                plate_priority = self._compute_plate_priority(plate_w, plate_h, plate.get("conf", 0.0))
                                heavy_mode = self._should_use_heavy_ocr(attempt_no, plate_priority)
                                plate_bbox = (int(plate_x1), int(plate_y1), int(plate_x2), int(plate_y2))
                                raw_ocr_text = self.recognize_plate_text(
                                    frame_original,
                                    plate_bbox,
                                    heavy_mode=heavy_mode,
                                    veh_track_id=veh_track_id,
                                )
                                if raw_ocr_text:
                                    # Step 1: Correct character confusion
                                    corrected_text = correct_plate_characters(raw_ocr_text)
                                    # Step 2: Validate plate format based on vehicle class
                                    is_valid, cleaned_plate = validate_license_plate(corrected_text, veh_cls_id)
                                    if is_valid:
                                        stable_plate = self._update_stable_plate(veh_track_id, cleaned_plate)
                                        if stable_plate:
                                            ocr_text = format_vietnamese_plate(stable_plate, veh_cls_id)
                                            if self.enable_perf_logs:
                                                if corrected_text != raw_ocr_text:
                                                    print(f"✅ OCR [Relative CORRECTED] Vehicle ID:{veh_track_id} → '{raw_ocr_text}' → '{ocr_text}'")
                                                else:
                                                    print(f"✅ OCR [Relative VALID] Vehicle ID:{veh_track_id} → '{ocr_text}'")
                                        elif self.enable_ocr_debug_logs:
                                            print(f"⏳ OCR [Relative WAIT STABLE] Vehicle ID:{veh_track_id} → '{cleaned_plate}'")
                                    elif self._is_loose_ocr_candidate(cleaned_plate):
                                        stable_plate = self._update_stable_plate(veh_track_id, cleaned_plate)
                                        if stable_plate:
                                            ocr_text = format_vietnamese_plate(stable_plate, veh_cls_id)
                                            if self.enable_ocr_debug_logs:
                                                print(f"🟡 OCR [Relative LOOSE ACCEPT] Vehicle ID:{veh_track_id} → '{ocr_text}'")
                                    elif self.enable_ocr_debug_logs:
                                        print(f"❌ OCR [Relative INVALID] Vehicle ID:{veh_track_id} → '{raw_ocr_text}' → '{corrected_text}' (retry next frame)")
                            elif not ocr_text and self.enable_ocr_debug_logs:
                                reason = self._get_ocr_skip_reason(veh_track_id, plate_w, plate_h)
                                print(f"⏭️ OCR [Relative] skipped Vehicle ID:{veh_track_id}: {reason}")
                            
                            # Store or update relative position
                            self.vehicle_plate_positions[veh_track_id] = {
                                'x_ratio': x_ratio,
                                'y_ratio': y_ratio,
                                'abs_w': abs_w,  # Absolute width (pixels)
                                'abs_h': abs_h,  # Absolute height (pixels)
                                'conf': plate["conf"],
                                'last_updated_frame': self.current_frame_count,
                                'ocr_text': ocr_text  # OCR recognized text (only if valid)
                            }
            elif self.enable_ocr_debug_logs:
                print(f"⚠️ Plate ID:{plate['track_id']} not mapped to vehicle (not fully inside any vehicle bbox)")
        
        # Clean up plates for vehicles that are no longer tracked
        if self.use_plate_relative_tracking:
            for veh_id in list(self.vehicle_plate_positions.keys()):
                if veh_id not in current_vehicle_ids:
                    del self.vehicle_plate_positions[veh_id]
        else:
            # YOLO Direct mode cleanup
            for veh_id in list(self.vehicle_ocr_texts.keys()):
                if veh_id not in current_vehicle_ids:
                    del self.vehicle_ocr_texts[veh_id]
            for veh_id in list(self.vehicle_stable_plates.keys()):
                if veh_id not in current_vehicle_ids:
                    del self.vehicle_stable_plates[veh_id]
            for veh_id in list(self.vehicle_plate_smoothing.keys()):
                if veh_id not in current_vehicle_ids:
                    del self.vehicle_plate_smoothing[veh_id]
            for veh_id in list(self.vehicle_ocr_votes.keys()):
                if veh_id not in current_vehicle_ids:
                    del self.vehicle_ocr_votes[veh_id]
            for veh_id in list(self.vehicle_ocr_history.keys()):
                if veh_id not in current_vehicle_ids:
                    del self.vehicle_ocr_history[veh_id]
            for veh_id in list(self.vehicle_to_plate_map.keys()):
                if veh_id not in current_vehicle_ids:
                    del self.vehicle_to_plate_map[veh_id]
            for veh_id in list(self.vehicle_ocr_attempts.keys()):
                if veh_id not in current_vehicle_ids:
                    del self.vehicle_ocr_attempts[veh_id]
            for veh_id in list(self.vehicle_last_ocr_frame.keys()):
                if veh_id not in current_vehicle_ids:
                    del self.vehicle_last_ocr_frame[veh_id]
        
        # Process vehicles with direction detection
        for veh in vehicles:
            track_id = veh["track_id"]
            cls_id = veh["cls_id"]
            x1, y1, x2, y2 = veh["box"]
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            
            vehicle_label = VEHICLE_CLASSES.get(cls_id, "vehicle")
            
            # Track vehicle position for direction calculation using OOP
            if track_id != -1:
                vehicle_direction = self.vehicle_tracker.update_position(track_id, cx, cy)
                
                # Check if vehicle crossed THE stop line
                if is_on_stop_line(cx, cy, threshold=20):
                    if not self.violation_detector.passed_vehicles.__contains__(track_id):
                        # ⚠️ CRITICAL: Đánh dấu điểm bắt đầu khi xe VỪA qua stopline
                        self.vehicle_tracker.mark_stopline_crossing(track_id, cx, cy)
                        
                        # Mark vehicle as passed and count by type
                        self.violation_detector.mark_vehicle_passed(track_id, cls_id)
                        
                        # Also update global sets for backward compatibility
                        PASSED_VEHICLES.add(track_id)
                        if cls_id in [2, 3]:  # xe đạp, xe máy
                            MOTORBIKE_COUNT.add(track_id)
                        elif cls_id in [0, 1, 4]:  # ô tô, xe bus, xe tải
                            CAR_COUNT.add(track_id)
                        
                        # Debug: Print TL states when vehicle crosses
                        if len(TL_ROIS) > 0:
                            tl_states = [f"{tl_type}:{color}" for _, _, _, _, tl_type, color in TL_ROIS]
                            print(f"🚦 Vehicle crossing: {vehicle_label} (ID={track_id}) Dir={vehicle_direction} | TL states: {tl_states}")
                        
                        # Check for TL violation using direction and OOP
                        is_violation, reason = check_tl_violation(track_id, vehicle_direction)
                        if is_violation:
                            self.violation_detector.add_violation(track_id, 'red_light')
                            # Update globals for backward compatibility
                            RED_LIGHT_VIOLATORS.add(track_id)
                            VIOLATOR_TRACK_IDS.add(track_id)
                            # Get license plate if available
                            plate_text = self.vehicle_ocr_texts.get(track_id, '')
                            plate_info = f" | Bien so: {plate_text}" if plate_text else " | Bien so: Chua doc duoc"
                            print(f"🚨 TL VIOLATION: {vehicle_label} (ID={track_id}) Dir={vehicle_direction}{plate_info} - {reason}")
                        else:
                            print(f"✅ Vehicle passed: {vehicle_label} (ID={track_id}) Dir={vehicle_direction} - {reason}")
                        
                        # ⚠️ CRITICAL: Check direction violation ONCE when crossing stopline
                        # Find which ROI the vehicle is in AT THE MOMENT of crossing
                        if DIRECTION_ROIS and vehicle_direction != 'unknown':
                            for roi_idx, roi in enumerate(DIRECTION_ROIS):
                                roi_points = roi.get('points', [])
                                if not roi_points:
                                    continue
                                
                                if point_in_polygon((cx, cy), roi_points):
                                    # Get allowed directions for this ROI
                                    allowed_dirs = roi.get('allowed_directions', [])
                                    if not allowed_dirs:
                                        # Fallback to legacy format
                                        primary_dir = roi.get('primary_direction', 'straight')
                                        secondary_dirs = roi.get('secondary_directions', [])
                                        allowed_dirs = [primary_dir] + secondary_dirs
                                    
                                    # If allowed_dirs is empty or contains 'all', skip violation check
                                    if not allowed_dirs or 'all' in allowed_dirs:
                                        break
                                    
                                    # Check if vehicle direction is allowed
                                    if vehicle_direction not in allowed_dirs:
                                        self.violation_detector.add_violation(track_id, 'direction')
                                        DIRECTION_VIOLATORS.add(track_id)
                                        VIOLATOR_TRACK_IDS.add(track_id)
                                        plate_text = self.vehicle_ocr_texts.get(track_id, '')
                                        plate_info = f" | Bien so: {plate_text}" if plate_text else " | Bien so: Chua doc duoc"
                                        roi_name = roi.get('name', f'ROI_{roi_idx}')
                                        print(f"🚨 DIRECTION VIOLATION: {vehicle_label} (ID={track_id}) went {vehicle_direction} in {roi_name} (allowed: {allowed_dirs}){plate_info}")
                                    break
            
            # Check lane violation (does NOT require stopline)
            for lane in LANE_CONFIGS:
                poly = lane["poly"]
                # Support both 'allowed_types' (from config) and 'allowed_labels' (legacy)
                allowed = lane.get("allowed_types", lane.get("allowed_labels", []))
                
                if point_in_polygon((cx, cy), poly):
                    # Check if vehicle type is allowed in this lane
                    # If allowed is empty list [] or contains "all", all vehicles are allowed
                    # If allowed has specific types, only those are allowed
                    is_all_allowed = len(allowed) == 0 or "all" in allowed
                    if not is_all_allowed and vehicle_label not in allowed:
                        if track_id not in LANE_VIOLATORS:
                            self.violation_detector.add_violation(track_id, 'lane')
                            # Update globals for backward compatibility
                            LANE_VIOLATORS.add(track_id)
                            VIOLATOR_TRACK_IDS.add(track_id)
                            # Get license plate if available
                            plate_text = self.vehicle_ocr_texts.get(track_id, '')
                            plate_info = f" | Bien so: {plate_text}" if plate_text else " | Bien so: Chua doc duoc"
                            print(f"🚨 LANE VIOLATION: {vehicle_label} (ID={track_id}) not allowed in lane (allowed: {allowed}){plate_info}")
                    break
            
            # Draw vehicle (respect _show_all_boxes flag)
            is_violator = self.violation_detector.is_violator(track_id)
            is_lane_violator = track_id in LANE_VIOLATORS
            is_tl_violator = track_id in RED_LIGHT_VIOLATORS
            is_direction_violator = track_id in DIRECTION_VIOLATORS
            
            # ⚠️ Lane violations show immediately (no stopline needed)
            # ⚠️ TL violations and Direction violations only show after passing stopline
            has_passed_stopline = track_id in PASSED_VEHICLES
            show_as_violator = is_lane_violator or is_direction_violator or (is_tl_violator and has_passed_stopline)
            
            # Track trajectory for violators
            if show_as_violator:
                if track_id not in self.violator_trajectories:
                    self.violator_trajectories[track_id] = []
                self.violator_trajectories[track_id].append((cx, cy))
                # Limit trajectory points to avoid memory issues (keep last 200 points)
                if len(self.violator_trajectories[track_id]) > 200:
                    self.violator_trajectories[track_id] = self.violator_trajectories[track_id][-200:]
            
            # Get real-time _show_all_boxes value via lambda function
            get_show_all_boxes = self.globals_ref.get('get_show_all_boxes')
            _show_all_boxes = get_show_all_boxes() if get_show_all_boxes else True
            
            # Only draw if: _show_all_boxes=True OR vehicle is violator (and passed)
            if _show_all_boxes or show_as_violator:
                box_color = (0, 0, 255) if show_as_violator else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                
                label_text = f"{vehicle_label} ID:{track_id}"
                if show_as_violator:
                    # Build violation type labels in Vietnamese (no diacritics)
                    violation_labels = []
                    if is_tl_violator and has_passed_stopline:
                        violation_labels.append("VUOT DEN DO")
                    if is_lane_violator:
                        violation_labels.append("SAI LAN")
                    if is_direction_violator:
                        violation_labels.append("SAI HUONG")
                    
                    if violation_labels:
                        label_text += f" [{', '.join(violation_labels)}]"
                    else:
                        label_text += " [VI PHAM]"
                
                # === Show OCR text and draw plate for YOLO Direct mode ===
                if not self.use_plate_relative_tracking:
                    # Find plate by track_id in current detections
                    if track_id in self.vehicle_to_plate_map:
                        plate_track_id = self.vehicle_to_plate_map[track_id]
                        # Search for this plate in current license_plates list
                        for plate in license_plates:
                            if plate["track_id"] == plate_track_id:
                                # Found! Use current bbox from YOLO detection
                                plate_x1, plate_y1, plate_x2, plate_y2 = plate["box"]
                                # Draw plate box in green (YOLO Direct)
                                cv2.rectangle(frame, (plate_x1, plate_y1), (plate_x2, plate_y2), (0, 255, 0), 2)
                                
                                # Draw OCR text near plate if available
                                if track_id in self.vehicle_ocr_texts:
                                    ocr_text = self.vehicle_ocr_texts[track_id]
                                    if ocr_text:
                                        cv2.putText(frame, ocr_text, (plate_x1, plate_y1 - 5),
                                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                                break
                    
                    # Add OCR text to vehicle label
                    if track_id in self.vehicle_ocr_texts:
                        ocr_text = self.vehicle_ocr_texts[track_id]
                        if ocr_text:
                            label_text += f" [{ocr_text}]"
                
                # === Draw license plate if we have relative position (Relative Tracking mode only) ===
                elif self.use_plate_relative_tracking and track_id in self.vehicle_plate_positions:
                    plate_info = self.vehicle_plate_positions[track_id]
                    
                    # Calculate absolute position from relative position (x,y move with vehicle)
                    veh_w = x2 - x1
                    veh_h = y2 - y1
                    
                    plate_x1 = int(x1 + plate_info['x_ratio'] * veh_w)
                    plate_y1 = int(y1 + plate_info['y_ratio'] * veh_h)
                    
                    # Use ABSOLUTE size (keep original plate size, don't scale with vehicle)
                    plate_w = plate_info['abs_w']
                    plate_h = plate_info['abs_h']
                    plate_x2 = plate_x1 + plate_w
                    plate_y2 = plate_y1 + plate_h
                    
                    # Draw plate box in yellow/orange
                    plate_color = (0, 255, 255)  # Yellow
                    cv2.rectangle(frame, (plate_x1, plate_y1), (plate_x2, plate_y2), plate_color, 2)
                    
                    # Add OCR text if available
                    ocr_text = plate_info.get('ocr_text', '')
                    if ocr_text:
                        label_text += f" [{ocr_text}]"
                        
                        # Draw OCR text near plate
                        cv2.putText(frame, ocr_text, (plate_x1, plate_y1 - 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    else:
                        label_text += " [PLATE]"
                
                cv2.putText(frame, label_text, (x1, y1-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
        
        # Clean up trajectories for vehicles no longer detected
        current_vehicle_ids = set(veh["track_id"] for veh in vehicles if veh["track_id"] != -1)
        for track_id in list(self.violator_trajectories.keys()):
            if track_id not in current_vehicle_ids:
                del self.violator_trajectories[track_id]
        
        # Draw violator trajectories if enabled
        if self.show_violator_trajectories:
            for track_id, trajectory in self.violator_trajectories.items():
                if len(trajectory) >= 2:
                    # Draw trajectory as polyline
                    points = np.array(trajectory, dtype=np.int32)
                    # Use gradient color from yellow to red based on position
                    for i in range(1, len(points)):
                        # Color gradient: older points more yellow, newer points more red
                        ratio = i / len(points)
                        color = (0, int(255 * (1 - ratio)), 255)  # From yellow (0,255,255) to red (0,0,255)
                        cv2.line(frame, tuple(points[i-1]), tuple(points[i]), color, 2)
                    
                    # Draw starting point (circle)
                    if len(trajectory) > 0:
                        cv2.circle(frame, trajectory[0], 5, (0, 255, 255), -1)  # Yellow start
                    
                    # Draw current position (larger circle)
                    if len(trajectory) > 0:
                        cv2.circle(frame, trajectory[-1], 8, (0, 0, 255), -1)  # Red current
        
        # Draw statistics panel
        frame = self._draw_statistics_panel(frame)
        
        return frame
    
    def _draw_statistics_panel(self, frame):
        """Draw statistics panel on frame"""
        # Panel position - TOP LEFT
        panel_x = 10
        panel_y = 10
        panel_width = 550
        panel_height = 100
        
        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x, panel_y), (panel_x + panel_width, panel_y + panel_height), (50, 50, 50), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Get statistics from OOP module
        stats = self.violation_detector.get_statistics()
        
        # Draw stats in 3 rows
        text_y = panel_y + 28
        
        # Row 1: FPS info
        cv2.putText(frame, f"Render FPS: {self.fps}", (panel_x + 10, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        if self.detection_enabled:
            cv2.putText(frame, f"Detection FPS: {self.processed_fps}", (panel_x + 230, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
        
        # Row 2: Vehicle counts (from OOP)
        text_y += 32
        cv2.putText(frame, f"Xe may: {stats['motorbikes']}", (panel_x + 10, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, f"O to: {stats['cars']}", (panel_x + 150, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, f"Total: {stats['total_vehicles']}", (panel_x + 280, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)
        
        # Row 3: Violations (from OOP)
        text_y += 32
        cv2.putText(frame, f"TL Violations: {stats['red_light_violations']}", (panel_x + 10, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
        cv2.putText(frame, f"Lane Violations: {stats['lane_violations']}", (panel_x + 280, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 165, 255), 2)
        
        return frame
    
    def stop(self):
        """Stop the thread"""
        self._run_flag = False
        with self._playback_lock:
            self.playback_paused = False
            self._pending_seek_target_sec = None
        self.wait()
