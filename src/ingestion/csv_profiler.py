import pandas as pd
from pathlib import Path
from typing import Dict, Any
import json

class CSVProfiler:
    """Profiles CSV once at ingest. Feeds Planner schema awareness.
    Avoids scanning entire file at query time → huge latency win."""
    
    def profile(self, csv_path: str) -> Dict[str, Any]:
        df = pd.read_csv(csv_path, nrows=10000)  # safety cap for huge files
        
        profile = {
            "filename": Path(csv_path).name,
            "row_count": len(df),
            "columns": {},
            "sample_rows": df.head(3).to_dict(orient="records")
        }
        
        for col in df.columns:
            profile["columns"][col] = {
                "dtype": str(df[col].dtype),
                "null_count": int(df[col].isna().sum()),
                "unique_count": int(df[col].nunique()),
                "min": str(df[col].min()) if pd.api.types.is_numeric_dtype(df[col]) else None,
                "max": str(df[col].max()) if pd.api.types.is_numeric_dtype(df[col]) else None,
                "is_numeric": pd.api.types.is_numeric_dtype(df[col]),
                "is_categorical": df[col].nunique() / len(df) < 0.1  # heuristic
            }
        
        # Save metadata for Planner
        metadata_path = Path(csv_path).with_suffix('.meta.json')
        metadata_path.write_text(json.dumps(profile, indent=2))
        
        return profile
