"""Small parsing helpers shared by public data adapters (no I/O)."""
import re

import jdatetime as jd
import pandas as pd

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_MISSING = {"", "-", "--", "----", "—", "null", "none", "nan", "n/a"}


def text_or_na(value):
    if value is None or pd.isna(value):
        return pd.NA
    text = str(value).strip().translate(_DIGITS)
    return pd.NA if text.casefold() in _MISSING else text


def number_series(values):
    """Parse quantities, preserving zero and rejecting malformed nonmissing data."""
    def clean(value):
        text = text_or_na(value)
        if text is pd.NA:
            return float("nan")
        return (text.replace(",", "").replace("٬", "").replace("٫", ".")
                .replace("−", "-").removesuffix("%").removesuffix("٪").strip())
    return pd.to_numeric(values.map(clean), errors="raise")


def identifier_series(values):
    """Keep identifiers as strings without decimal suffixes from nullable JSON numbers."""
    def clean(value):
        text = text_or_na(value)
        if not isinstance(value, str) and text is not pd.NA and re.fullmatch(r"\d+\.0", text):
            text = text[:-2]
        return text
    return values.map(clean).astype("string")


def boolean_series(values):
    def clean(value):
        text = text_or_na(value)
        if text is pd.NA:
            return pd.NA
        if text.casefold() in ("true", "1", "1.0"):
            return True
        if text.casefold() in ("false", "0", "0.0"):
            return False
        raise ValueError(f"Invalid boolean value: {value!r}")
    return values.map(clean).astype("boolean")


def jalali_date(value):
    text = text_or_na(value)
    if text is pd.NA:
        return pd.NA
    text = text[:10].replace("/", "-")
    if re.fullmatch(r"\d{8}", text):
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return jd.date(*map(int, text.split("-"))).isoformat()


def gregorian_series(values):
    """Date-only Gregorian values; no timezone is invented."""
    text = values.map(text_or_na).astype("string")
    return pd.to_datetime(text, format="mixed", errors="coerce").dt.normalize().astype("datetime64[ns]")


def time_string(value):
    text = text_or_na(value)
    if text is pd.NA:
        return pd.NA
    if text.isdigit():
        text = text.zfill(6)
        text = f"{text[:2]}:{text[2:4]}:{text[4:]}"
    return pd.to_datetime(text, format="%H:%M:%S").strftime("%H:%M:%S")
