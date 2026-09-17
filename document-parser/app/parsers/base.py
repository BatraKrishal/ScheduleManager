from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from app.models.canonical import CanonicalSchedule


class ParserError(Exception):
    def __init__(self, message: str, field: Optional[str] = None, details: Any = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.details = details


class BaseParser(ABC):
    @abstractmethod
    def parse(self, content: bytes, filename: str) -> CanonicalSchedule:
        """Parse raw file content into CanonicalSchedule."""
        pass

    @staticmethod
    def parse_datetime(val: Any) -> Optional[datetime]:
        """Safely parse various datetime string and object formats."""
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        s = str(val).strip()
        if not s or s.lower() in ("nan", "none", "nat", "null", ""):
            return None

        # Common formats in P6, ISO, and spreadsheets
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%m/%d/%Y %I:%M:%S %p",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
            "%d-%b-%Y %H:%M",
            "%d-%b-%Y",
            "%d-%b-%y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        # Fallback to dateutil if available
        try:
            import pandas as pd
            ts = pd.to_datetime(s, errors="coerce")
            if pd.notna(ts):
                return ts.to_pydatetime()
        except Exception:
            pass
        return None

    @staticmethod
    def parse_float(val: Any, default: Optional[float] = None) -> Optional[float]:
        """Safely convert numeric string/number to float."""
        if val is None:
            return default
        try:
            s = str(val).replace(",", "").replace("%", "").strip()
            if not s or s.lower() in ("nan", "none", "null"):
                return default
            return float(s)
        except (ValueError, TypeError):
            return default
