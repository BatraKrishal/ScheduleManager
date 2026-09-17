from __future__ import annotations

import csv
import io
from typing import Dict, List
from app.models.canonical import CanonicalSchedule
from app.parsers.base import BaseParser, ParserError
from app.parsers.tabular_common import build_canonical_schedule_from_rows, map_columns


class CsvParser(BaseParser):
    def parse(self, content: bytes, filename: str) -> CanonicalSchedule:
        text = None
        for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            raise ParserError("Failed to decode CSV file: unsupported encoding")

        # Sniff delimiter (comma, semicolon, tab)
        sample = text[:4096]
        delimiter = ","
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=",\t;|")
            delimiter = dialect.delimiter
        except Exception:
            # Fallback based on simple count
            first_line = text.splitlines()[0] if text.splitlines() else ""
            if "\t" in first_line:
                delimiter = "\t"
            elif ";" in first_line:
                delimiter = ";"

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows_raw = list(reader)
        if not rows_raw:
            raise ParserError("CSV file is completely empty")

        headers = [h.strip() for h in rows_raw[0]]
        col_map = map_columns(headers)

        # Convert rows into list of dicts
        dict_rows: List[Dict[str, str]] = []
        for r in rows_raw[1:]:
            if not any(r):
                continue
            row_dict = {
                headers[i]: r[i].strip() if i < len(r) else ""
                for i in range(len(headers))
            }
            dict_rows.append(row_dict)

        return build_canonical_schedule_from_rows(dict_rows, col_map, filename, self)
