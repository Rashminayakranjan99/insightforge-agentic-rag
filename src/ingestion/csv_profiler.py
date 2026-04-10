import pandas as pd
import re
from pathlib import Path
from typing import Dict, Any, List
import json

# Common ID column name patterns (case-insensitive)
_ID_PATTERNS = re.compile(
    r"^(id|_id|uuid|guid|index|serial|row_?num|row_?id|"
    r"sr_?no|s_?no|record_?id|transaction_?id|txn_?id|"
    r"order_?id|invoice_?id|ticket_?id|log_?id|entry_?id)$",
    re.IGNORECASE,
)

_ID_SUFFIX_PATTERNS = re.compile(
    r"(_id|_uuid|_guid|_key|_pk|_fk|_index|_serial|_num|_number|_code)$",
    re.IGNORECASE,
)


class CSVProfiler:
    """Profiles CSV once at ingest.  Feeds Planner schema awareness.
    Automatically detects and flags ID / high-cardinality junk columns."""

    # ── public API ───────────────────────────────────────────────────

    def profile(self, csv_path: str, df: pd.DataFrame = None,
                chunk_info: Dict[str, Any] = None) -> Dict[str, Any]:
        # Reuse uploaded dataframe when available so profiling reflects full loaded data.
        if df is None:
            df = pd.read_csv(csv_path)

        id_columns: List[str] = []
        profile = {
            "filename": Path(csv_path).name,
            "row_count": len(df),
            "columns": {},
            "sample_rows": self._safe_sample(df, 3),
            "dropped_columns": [],
            "chunking": chunk_info or {
                "enabled": False,
                "chunk_size": None,
                "chunk_count": 1,
            },
        }

        for col in df.columns:
            nunique = int(df[col].nunique())
            n_rows = len(df)
            is_numeric = pd.api.types.is_numeric_dtype(df[col])
            uniqueness_ratio = nunique / n_rows if n_rows > 0 else 0

            is_id = self._is_id_column(col, df[col], uniqueness_ratio, is_numeric)

            profile["columns"][col] = {
                "dtype": str(df[col].dtype),
                "null_count": int(df[col].isna().sum()),
                "unique_count": nunique,
                "min": str(df[col].min()) if is_numeric else None,
                "max": str(df[col].max()) if is_numeric else None,
                "is_numeric": is_numeric,
                "is_categorical": uniqueness_ratio < 0.1,
                "is_id": is_id,
            }

            if is_id:
                id_columns.append(col)

        profile["dropped_columns"] = id_columns

        # Save metadata
        metadata_path = Path(csv_path).with_suffix(".meta.json")
        metadata_path.write_text(json.dumps(profile, indent=2, default=str))

        return profile

    def clean_dataframe(self, df: pd.DataFrame, profile: Dict[str, Any]) -> pd.DataFrame:
        """Drop detected ID / junk columns from the DataFrame."""
        drop_cols = profile.get("dropped_columns", [])
        cols_to_drop = [c for c in drop_cols if c in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            print(f"[PROFILER] Dropped ID/junk columns: {cols_to_drop}")
        return df

    # ── private helpers ──────────────────────────────────────────────

    def _is_id_column(self, col_name: str, series: pd.Series,
                      uniqueness_ratio: float, is_numeric: bool) -> bool:
        """Heuristic: detect identifier / non-analytical columns.

        A column is flagged as ID if ANY of these hold:
        1. Name exactly matches common ID patterns (e.g. 'id', 'uuid')
        2. Name ends with ID suffixes AND uniqueness > 80%
        3. Uniqueness ratio > 90% AND (numeric-sequential or string-hash-like)
        """
        name_lower = col_name.strip().lower()

        # Rule 1: exact name match
        if _ID_PATTERNS.match(name_lower):
            return True

        # Rule 2: suffix match + high cardinality
        if _ID_SUFFIX_PATTERNS.search(name_lower) and uniqueness_ratio > 0.8:
            return True

        # Rule 3: near-unique column with sequential or hash-like values
        if uniqueness_ratio > 0.9 and len(series) > 20:
            if is_numeric:
                # Check if values are sequential (like auto-increment IDs)
                non_null = series.dropna()
                if len(non_null) > 10:
                    diffs = non_null.sort_values().diff().dropna()
                    # If 90%+ diffs are 1 -> sequential ID
                    if (diffs == 1).mean() > 0.9:
                        return True
            else:
                # String column with very high uniqueness -> likely hash/code/ID
                # But exclude date-like columns
                sample = series.dropna().head(5).astype(str)
                avg_len = sample.str.len().mean()
                # Short strings with high uniqueness = IDs (e.g. 'ORD-12345')
                if avg_len < 30 and uniqueness_ratio > 0.95:
                    return True

        return False

    def _safe_sample(self, df: pd.DataFrame, n: int) -> list:
        """Get sample rows as list of dicts, handling non-serializable types."""
        try:
            return json.loads(df.head(n).to_json(orient="records", default_handler=str))
        except Exception:
            return df.head(n).astype(str).to_dict(orient="records")
