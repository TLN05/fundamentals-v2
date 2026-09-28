"""
utils/validation.py
====================
Validation for manually-entered values. Never silently accepts an
out-of-range or malformed value -- callers should surface the returned
warning strings to the user (components/input_forms.py does this via
st.warning).
"""

from datetime import date, datetime
from typing import List, Optional


def validate_percent(value: Optional[float], field_label: str,
                      lo: float = -20.0, hi: float = 30.0) -> List[str]:
    warnings = []
    if value is None:
        return warnings
    if not isinstance(value, (int, float)):
        warnings.append(f"{field_label}: must be numeric.")
        return warnings
    if value < lo or value > hi:
        warnings.append(
            f"{field_label}: {value} is outside the plausible range "
            f"[{lo}, {hi}]. Double-check the entry."
        )
    return warnings


def validate_date_str(value: Optional[str], field_label: str) -> List[str]:
    warnings = []
    if not value:
        return warnings
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        warnings.append(f"{field_label}: date must be in YYYY-MM-DD format.")
        return warnings
    if d > date.today():
        warnings.append(f"{field_label}: date {value} is in the future.")
    return warnings


def validate_required(value, field_label: str) -> List[str]:
    if value is None or value == "":
        return [f"{field_label}: no value entered -- this metric will be "
                f"marked Unavailable and excluded (weights renormalized)."]
    return []


def validate_categorical(value: Optional[str], options: List[str], field_label: str) -> List[str]:
    if value is None:
        return []
    if value not in options:
        return [f"{field_label}: '{value}' is not one of the allowed options {options}."]
    return []
