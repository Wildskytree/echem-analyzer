"""CorrTest CSStudio electrochemical data file parser."""

from __future__ import annotations

import base64
import binascii
import gzip
import hashlib
import os
import re
from typing import List, Optional, Tuple

import numpy as np

from echem_core.model import Measurement, Technique


_FLOAT_RE = r"([-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?)"
_EXP_TYPE_MAP = {
    "ID_CV": Technique.CV,
    "ID_LSV": Technique.LSV,
    "ID_EIS": Technique.EIS,
    "ID_CA": Technique.CA,
    "ID_CP": Technique.CP,
    "ID_POTSQUAREWAVE": Technique.CA,
    "ID_POTSTEP": Technique.CA,
    "ID_POTENTIALSTEP": Technique.CA,
    "ID_CHRONOAMPEROMETRY": Technique.CA,
    "ID_CHRONOPOTENTIOMETRY": Technique.CP,
}


def parse_corrtest_file(filepath: str) -> Measurement:
    """Parse a CorrTest CSStudio text file into a Measurement.

    CorrTest files store experiment metadata in a base64-encoded gzip blob on
    the first line, followed by tab-separated E(V), i(A/cm2), and T(s) data.
    If the metadata blob is missing or invalid, data parsing still proceeds and
    available metadata is left as None.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File does not exist: {filepath}")

    file_hash = _compute_file_hash(filepath)
    content, encoding = _read_text_file(filepath)
    lines = content.splitlines()
    if not any(line.strip() for line in lines):
        raise ValueError(f"File is empty: {filepath}")

    first_line = _first_non_empty_line(lines) or ""
    metadata_text, header_error = _decode_metadata_header(first_line)
    metadata = _parse_metadata(metadata_text, first_line, filepath)
    metadata["_source_format"] = "CorrTest CSStudio"
    metadata["_encoding"] = encoding
    if metadata_text:
        metadata["_corrtest_metadata"] = metadata_text
    if header_error:
        metadata["_corrtest_header_error"] = header_error

    headers, data = _parse_tabular_data(lines)
    technique = metadata.get("_technique") or _infer_technique_from_headers(headers)

    if technique == Technique.EIS:
        potential, current, time, column_mapping = _extract_eis_data_columns(headers, data)
        metadata["frequency"] = potential.tolist()
        metadata["z_real"] = current.tolist()
        metadata["z_imag"] = time.tolist()
    else:
        potential, current, time, column_mapping = _extract_data_columns(headers, data)
    if technique is None:
        technique = _infer_technique_from_potential(potential)
    metadata.pop("_technique", None)

    metadata["_raw_columns"] = headers
    metadata["_column_mapping"] = column_mapping

    return Measurement(
        technique=technique,
        potential=potential,
        current=current,
        time=time,
        metadata=metadata,
        file_hash=file_hash,
    )


def _compute_file_hash(filepath: str) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        sha256.update(f.read())
    return sha256.hexdigest()


def _read_text_file(filepath: str) -> Tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"):
        try:
            with open(filepath, "r", encoding=encoding) as f:
                return f.read(), encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Unable to decode file: {filepath}")


def _first_non_empty_line(lines: List[str]) -> Optional[str]:
    for line in lines:
        if line.strip():
            return line.strip()
    return None


def _decode_metadata_header(first_line: str) -> Tuple[Optional[str], Optional[str]]:
    blob = _extract_gzip_blob(first_line)
    if not blob:
        return None, "missing CorrTest metadata header"

    try:
        compressed = base64.b64decode(blob, validate=True)
        metadata_bytes = gzip.decompress(compressed)
    except (binascii.Error, OSError, EOFError) as exc:
        return None, f"invalid CorrTest metadata header: {exc}"

    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"):
        try:
            return metadata_bytes.decode(encoding), None
        except (UnicodeDecodeError, UnicodeError):
            continue
    return metadata_bytes.decode("latin-1", errors="replace"), None


def _extract_gzip_blob(first_line: str) -> Optional[str]:
    cleaned = first_line.lstrip("\ufeff").strip()
    if cleaned.startswith("H4sI"):
        return re.split(r"[\s,]+", cleaned, maxsplit=1)[0]

    for part in re.split(r"[\s,]+", cleaned):
        if part.startswith("H4sI"):
            return part.strip()
    return None


def _parse_metadata(
    metadata_text: Optional[str],
    first_line: str,
    filepath: str,
) -> dict:
    metadata = {
        "sample_name": os.path.basename(filepath),
        "instrument": "CorrTest CSStudio",
        "scan_rate": None,
        "area_cm2": None,
        "temperature": None,
    }

    text = metadata_text or ""
    exp_type = _extract_exp_type(text) or _extract_exp_type(first_line)
    if exp_type is not None:
        metadata["exp_type"] = exp_type
        metadata["_technique"] = _technique_from_exp_type(exp_type)

    scan_rate_mv_s = _search_float(
        text,
        (
            rf"\bScanRate\s*=\s*{_FLOAT_RE}",
            rf"Scan\s*Rate\s*\([^)]*mV/s[^)]*\)\s*:\s*{_FLOAT_RE}",
            rf"Scan\s*Rate\s*[:=]\s*{_FLOAT_RE}",
        ),
    )
    if scan_rate_mv_s is not None:
        metadata["scan_rate"] = scan_rate_mv_s / 1000.0
        metadata["scan_rate_mV_s"] = scan_rate_mv_s

    area = _search_float(
        text,
        (
            rf"\bArea\s*=\s*{_FLOAT_RE}",
            rf"Surface\s+Area\s*:\s*{_FLOAT_RE}",
        ),
    )
    if area is not None:
        metadata["area_cm2"] = area

    temperature = _search_float(
        text,
        (
            rf"\bTemp\s*=\s*{_FLOAT_RE}",
            rf"Temperature\s*(?:\([^)]*\))?\s*:\s*{_FLOAT_RE}",
        ),
    )
    if temperature is not None:
        metadata["temperature"] = temperature
        metadata["temperature_c"] = temperature

    date_match = re.search(
        r"\bDat[ae]\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})"
        r"\s+Time\s*:\s*([0-9:]+)",
        text,
        flags=re.IGNORECASE,
    )
    if date_match:
        metadata["date"] = f"{date_match.group(1)} {date_match.group(2)}"

    filename_match = re.search(r"\bFileName=([^&\r\n]+)", text)
    if filename_match:
        metadata["corrtest_filename"] = filename_match.group(1).strip()

    return metadata


def _extract_exp_type(text: str) -> Optional[str]:
    exp_type_match = re.search(
        r"\bExpType\s*[:=]\s*(ID_[A-Z0-9_]+)\b",
        text,
        flags=re.IGNORECASE,
    )
    if exp_type_match:
        return exp_type_match.group(1).upper()

    for match in re.finditer(r"\bID_[A-Z0-9_]+\b", text, flags=re.IGNORECASE):
        exp_type = match.group(0).upper()
        if _technique_from_exp_type(exp_type) is not None:
            return exp_type
    return None


def _technique_from_exp_type(exp_type: str) -> Optional[Technique]:
    exp_type = exp_type.upper()
    technique = _EXP_TYPE_MAP.get(exp_type)
    if technique is not None:
        return technique
    if "EIS" in exp_type or "IMP" in exp_type:
        return Technique.EIS
    if any(token in exp_type for token in ("POTSTEP", "POTSQUAREWAVE", "CHRONOAMP", "I-T", "IT")):
        return Technique.CA
    if any(token in exp_type for token in ("CHRONOPOT", "CP")):
        return Technique.CP
    return None


def _search_float(text: str, patterns: Tuple[str, ...]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return float(match.group(1))
    return None


def _parse_tabular_data(lines: List[str]) -> Tuple[List[str], np.ndarray]:
    header_row = _find_data_header(lines)
    if header_row is None:
        raise ValueError("Unable to find CorrTest tab-separated data header")

    headers = _split_row(lines[header_row])
    data_rows: List[List[float]] = []

    for line in lines[header_row + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        parts = _split_row(stripped)
        if len(parts) < 2:
            continue
        try:
            data_rows.append([float(part) for part in parts[: len(headers)]])
        except ValueError:
            continue

    if not data_rows:
        raise ValueError("CorrTest file contains no numeric data rows")

    return headers, np.array(data_rows, dtype=float)


def _find_data_header(lines: List[str]) -> Optional[int]:
    for idx, line in enumerate(lines):
        parts = _split_row(line)
        if len(parts) < 2:
            continue
        normalized = [_normalize_header(part) for part in parts]
        has_potential = any(
            part in {"e(v)", "potential(v)", "potential/v"} for part in normalized
        )
        has_current = any(
            part.startswith("i(") or "current" in part for part in normalized
        )
        if has_potential and has_current:
            return idx
        if _infer_technique_from_headers(parts) == Technique.EIS:
            return idx
    return None


def _split_row(line: str) -> List[str]:
    if "\t" in line:
        return [part.strip() for part in line.strip().split("\t") if part.strip()]
    return [part.strip() for part in line.strip().split() if part.strip()]


def _normalize_header(header: str) -> str:
    return (
        header.strip()
        .lower()
        .replace(" ", "")
        .replace("\u00b2", "2")
        .replace("\u03a9", "ohm")
        .replace("\u2126", "ohm")
        .replace("\u03c9", "ohm")
        .replace("\u2032", "'")
        .replace("\u2019", "'")
        .replace("\u2033", '"')
        .replace("\u2212", "-")
    )


def _infer_technique_from_headers(headers: List[str]) -> Optional[Technique]:
    normalized = [_normalize_header(header) for header in headers]
    has_frequency = any(_is_frequency_header(header) for header in normalized)
    has_z_real = any(_is_z_real_header(header) for header in normalized)
    has_z_imag = any(_is_z_imag_header(header) for header in normalized)
    has_impedance = any("impedance" in header for header in normalized)
    if has_frequency and (has_z_real or has_z_imag or has_impedance):
        return Technique.EIS
    return None


def _is_frequency_header(header: str) -> bool:
    return "freq" in header or header in {"f(hz)", "f/hz", "frequency"}


def _is_z_real_header(header: str) -> bool:
    if _is_z_imag_header(header):
        return False
    return any(
        token in header
        for token in ("zreal", "z_real", "zre", "z_re", "rez", "re(z)", "z'")
    )


def _is_z_imag_header(header: str) -> bool:
    return any(
        token in header
        for token in ("zimag", "z_imag", "z_im", "zim", "imz", "im(z)", "z''", 'z"')
    )


def _extract_data_columns(
    headers: List[str],
    data: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], dict]:
    col_count = data.shape[1]
    if col_count < 2:
        raise ValueError("CorrTest data must contain at least two columns")

    potential_idx = _find_column(
        headers,
        ("e(v)", "potential(v)", "potential/v"),
        default=0,
    )
    current_idx = _find_current_column(headers, default=1)
    time_idx = _find_column(
        headers,
        ("t(s)", "time(s)", "time/s"),
        default=2 if col_count >= 3 else None,
    )

    if potential_idx is None or current_idx is None:
        raise ValueError("CorrTest data must contain potential and current columns")
    if potential_idx >= col_count or current_idx >= col_count:
        raise ValueError("CorrTest data columns do not match the header")

    time = data[:, time_idx] if time_idx is not None and time_idx < col_count else None
    column_mapping = {
        "potential": headers[potential_idx],
        "current": headers[current_idx],
    }
    if time_idx is not None and time_idx < col_count:
        column_mapping["time"] = headers[time_idx]
    return data[:, potential_idx], data[:, current_idx], time, column_mapping


def _extract_eis_data_columns(
    headers: List[str],
    data: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    col_count = data.shape[1]
    if col_count < 3:
        raise ValueError("CorrTest EIS data must contain frequency, Z', and Z'' columns")

    frequency_idx = _find_matching_column(headers, _is_frequency_header, default=0)
    z_real_idx = _find_matching_column(headers, _is_z_real_header, default=1)
    z_imag_idx = _find_matching_column(headers, _is_z_imag_header, default=2)

    if (
        frequency_idx is None
        or z_real_idx is None
        or z_imag_idx is None
        or frequency_idx >= col_count
        or z_real_idx >= col_count
        or z_imag_idx >= col_count
    ):
        raise ValueError("CorrTest EIS data columns do not match the header")

    column_mapping = {
        "frequency": headers[frequency_idx],
        "z_real": headers[z_real_idx],
        "z_imag": headers[z_imag_idx],
    }
    return (
        data[:, frequency_idx],
        data[:, z_real_idx],
        data[:, z_imag_idx],
        column_mapping,
    )


def _find_column(
    headers: List[str],
    candidates: Tuple[str, ...],
    default: Optional[int],
) -> Optional[int]:
    normalized = [_normalize_header(header) for header in headers]
    for idx, header in enumerate(normalized):
        if header in candidates:
            return idx
    return default


def _find_matching_column(headers: List[str], predicate, default: Optional[int]) -> Optional[int]:
    normalized = [_normalize_header(header) for header in headers]
    for idx, header in enumerate(normalized):
        if predicate(header):
            return idx
    return default


def _find_current_column(headers: List[str], default: int) -> int:
    normalized = [_normalize_header(header) for header in headers]
    for idx, header in enumerate(normalized):
        if header.startswith("i(") or "current" in header:
            return idx
    return default


def _infer_technique_from_potential(potential: np.ndarray) -> Technique:
    if len(potential) < 3:
        return Technique.LSV

    diff = np.diff(potential)
    sign_changes = np.sum(diff[:-1] * diff[1:] < 0)
    if sign_changes >= 1:
        return Technique.CV
    return Technique.LSV


__all__ = ["parse_corrtest_file"]
