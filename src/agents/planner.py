# src/agents/planner.py
"""Planner Agent — analyzes user query + CSV profile to create an analysis plan."""

import json
import re
from core.llm_client import LLMRouter
from config import PLANNER_SYSTEM_PROMPT


class PlannerAgent:
    """Takes a user query and dataset profile, returns a structured analysis plan."""

    def __init__(self, llm: LLMRouter):
        self.llm = llm

    def plan(self, user_query: str, profile: dict) -> dict:
        """Generate an analysis plan as structured JSON.

        Args:
            user_query: Natural language question about the data
            profile: CSV profile from CSVProfiler (columns, types, stats, samples)

        Returns:
            dict with analysis_type, target_columns, visualization, etc.
        """
        heuristic = self._heuristic_plan(user_query, profile)
        if heuristic is not None:
            return heuristic

        # Build a compact schema description for the LLM
        columns_desc = []
        for col_name, col_info in profile.get("columns", {}).items():
            dtype = col_info.get("dtype", "unknown")
            unique = col_info.get("unique_count", "?")
            is_num = col_info.get("is_numeric", False)
            is_cat = col_info.get("is_categorical", False)
            col_type = "numeric" if is_num else ("categorical" if is_cat else "text")
            columns_desc.append(f"  - {col_name} ({dtype}, {col_type}, {unique} unique)")

        schema_text = "\n".join(columns_desc)
        sample_text = json.dumps(profile.get("sample_rows", [])[:3], indent=2, default=str)

        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Dataset: {profile.get('filename', 'unknown.csv')}
Rows: {profile.get('row_count', '?')}
Columns:
{schema_text}

Sample rows:
{sample_text}

User query: "{user_query}"

Output the analysis plan as JSON.""",
            },
        ]

        raw = self.llm.chat(messages, temperature=0.2, max_tokens=1024)

        # Parse JSON from LLM response (handle markdown fences)
        plan = self._parse_json(raw)

        # Validate required fields
        if "analysis_type" not in plan:
            plan["analysis_type"] = "general"
        if "target_columns" not in plan:
            plan["target_columns"] = list(profile.get("columns", {}).keys())[:2]
        if "visualization" not in plan:
            plan["visualization"] = "bar"

        return plan

    def _heuristic_plan(self, user_query: str, profile: dict) -> dict:
        """Fast deterministic plan for high-frequency intents."""
        q = (user_query or "").strip().lower()
        if not q:
            return None

        relation_terms = ("relation", "relationship", "correlation", "associated", "impact")
        if any(term in q for term in relation_terms):
            numeric_cols = [
                col_name for col_name, col_info in profile.get("columns", {}).items()
                if col_info.get("is_numeric")
            ]
            if len(numeric_cols) >= 2:
                return {
                    "analysis_type": "correlation",
                    "target_columns": numeric_cols[:4],
                    "group_by": None,
                    "aggregation": None,
                    "sort_by": None,
                    "sort_order": "desc",
                    "top_n": 12,
                    "filter_condition": None,
                    "visualization": "bar",
                    "description": "Strongest relationships across numeric columns",
                }

        return None

    def _parse_json(self, text: str) -> dict:
        """Extract JSON from LLM response, handling markdown fences."""
        # Try direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting from ```json ... ```
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding { ... } block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback
        return {
            "analysis_type": "general",
            "target_columns": [],
            "visualization": "none",
            "description": "Could not parse plan; will do general analysis.",
        }
