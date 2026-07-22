"""Thread-safe counters for plate detection fail-capture observability."""

from __future__ import annotations

import threading
from typing import Dict


class FailMetrics:
    """In-process counters for detection fail categories."""

    KEYS = (
        "plate_bbox_hits",
        "ocr_empty",
        "ocr_invalid_format",
        "ocr_valid_emitted",
        "operator_confirmed_miss",
        "operator_corrected_plate",
        "operator_marked_not_plate",
        "duplicate_fail_skipped",
        "fail_capture_rate_limited",
        "transient_retry_success",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Dict[str, int] = {k: 0 for k in self.KEYS}

    def inc(self, key: str, amount: int = 1) -> None:
        if key not in self._counts:
            return
        with self._lock:
            self._counts[key] += amount

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def reset(self) -> None:
        with self._lock:
            for key in self._counts:
                self._counts[key] = 0


fail_metrics = FailMetrics()
