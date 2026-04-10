import pandas as pd
from pathlib import Path
from typing import Dict, Any
import RestrictedPython  # we'll add to requirements later
# For now use safe exec pattern

class PandasTool:
    """Natural language → safe pandas code → result. NEVER raw exec in prod."""
    def __init__(self):
        pass  # registry will inject CSV paths later
    
    def execute(self, action_spec: str, csv_path: str) -> Dict[str, Any]:
        """Production safety: We will replace with RestrictedPython in Week 5."""
        df = pd.read_csv(csv_path)
        # Placeholder: in real impl, LLM generates code → we validate + run safely
        # For Day 2: simple group-by example (you will expand)
        result = {"summary": "Executed action", "data": df.head(3).to_dict()}
        return result