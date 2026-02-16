# error_logging.py
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse
import pandas as pd

DEFAULT_COLS = ["Description", "UI_status", "Last_checked", "Error"]

def ensure_error_columns(df: pd.DataFrame, cols=DEFAULT_COLS) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def safe_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return ""
    return str(v).strip()

def normalize_url(u: str) -> str | None:
    u = safe_str(u)
    if not u:
        return None
    if not u.lower().startswith(("http://", "https://")):
        u = "https://" + u
    return u

def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

def mark_skipped(df: pd.DataFrame, i: int, reason: str) -> None:
    df.at[i, "UI_status"] = "skipped"
    df.at[i, "Error"] = reason
    df.at[i, "Last_checked"] = now_utc_iso()

def mark_success(df: pd.DataFrame, i: int, desc: str, ui_status: str) -> None:
    df.at[i, "Description"] = desc
    df.at[i, "UI_status"] = ui_status
    df.at[i, "Error"] = pd.NA
    df.at[i, "Last_checked"] = now_utc_iso()

def mark_empty(df: pd.DataFrame, i: int, reason: str = "No description found") -> None:
    df.at[i, "UI_status"] = "empty"
    df.at[i, "Error"] = reason
    df.at[i, "Last_checked"] = now_utc_iso()

def mark_error(df: pd.DataFrame, i: int, code: str, message: str) -> None:
    df.at[i, "UI_status"] = code
    df.at[i, "Error"] = message
    df.at[i, "Last_checked"] = now_utc_iso()

def extract_errors_table(df: pd.DataFrame) -> pd.DataFrame:
    if "Error" not in df.columns:
        return df.iloc[0:0].copy()
    err_df = df[df["Error"].notna()].copy()
    cols = [c for c in ["Company", "Website", "UI_status", "Error", "Last_checked"] if c in err_df.columns]
    return err_df[cols]
