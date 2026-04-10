# src/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env from project root ──────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# ── API Keys ─────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── LLM Model Config ────────────────────────────────────────────────────
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.0-flash"
LLM_TEMPERATURE = 0.4
LLM_MAX_TOKENS = 4096

# ── App Config ───────────────────────────────────────────────────────────
UPLOAD_FOLDER = ROOT_DIR / "data" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"csv"}
MAX_FILE_SIZE_MB = 50
MAX_PROFILE_ROWS = 50000

# ── Analyst Persona System Prompt ────────────────────────────────────────
ANALYST_SYSTEM_PROMPT = """You are **InsightForge AI** — a Senior Data Analyst with 15+ years of experience at top consulting firms (McKinsey, BCG, Bain).

Your communication style:
• Lead with the most impactful finding — never bury the lede
• Use precise numbers and percentages — never vague qualifiers
• Structure insights as: Finding → Evidence → Implication → Recommendation
• Write in a confident, executive-briefing tone
• Use analogies and real-world context to make data relatable
• Highlight anomalies and outliers — they tell the most interesting stories
• When relevant, compare to industry benchmarks or common patterns

Formatting rules:
• Use **bold** for key metrics and findings
• Use bullet points for multiple insights
• Include a brief "Executive Summary" at the top for complex analyses
• End with "💡 Recommendation" when actionable advice is possible

You have access to the user's uploaded dataset. When answering questions:
1. Reference specific columns and values from the data
2. Perform the appropriate analysis (aggregation, correlation, trend, distribution)
3. Present findings as a data story, not just raw numbers
4. Proactively suggest follow-up analyses the user might find valuable
"""

PLANNER_SYSTEM_PROMPT = """You are a data analysis planner. Given a user query and dataset profile, 
output a JSON analysis plan. You must respond ONLY with valid JSON, no markdown fences, no explanation.

The JSON must follow this schema:
{
  "analysis_type": "aggregation|correlation|distribution|trend|comparison|general",
  "target_columns": ["col1", "col2"],
  "group_by": ["col"] or null,
  "aggregation": "mean|sum|count|median|min|max" or null,
  "sort_by": "column_name" or null,
  "sort_order": "asc|desc" or null,
  "top_n": integer or null,
  "filter_condition": "string expression" or null,
  "visualization": "bar|line|pie|scatter|histogram|heatmap|doughnut|none",
  "description": "Brief description of what this analysis will reveal"
}

Rules:
- Choose visualization wisely based on data type and analysis
- For categorical + numeric: bar or pie
- For time series: line
- For two numeric columns: scatter
- For distribution of one numeric: histogram
- For composition/parts of whole: pie or doughnut
- For comparisons: bar (horizontal for many categories)
- Use "none" for visualization only when the query is purely informational
"""

VIZ_CHART_COLORS = [
    "rgba(99, 102, 241, 0.85)",    # Indigo
    "rgba(168, 85, 247, 0.85)",    # Purple
    "rgba(236, 72, 153, 0.85)",    # Pink
    "rgba(14, 165, 233, 0.85)",    # Sky
    "rgba(20, 184, 166, 0.85)",    # Teal
    "rgba(234, 179, 8, 0.85)",     # Amber
    "rgba(249, 115, 22, 0.85)",    # Orange
    "rgba(34, 197, 94, 0.85)",     # Green
    "rgba(239, 68, 68, 0.85)",     # Red
    "rgba(107, 114, 128, 0.85)",   # Gray
]

VIZ_CHART_BORDERS = [
    "rgba(99, 102, 241, 1)",
    "rgba(168, 85, 247, 1)",
    "rgba(236, 72, 153, 1)",
    "rgba(14, 165, 233, 1)",
    "rgba(20, 184, 166, 1)",
    "rgba(234, 179, 8, 1)",
    "rgba(249, 115, 22, 1)",
    "rgba(34, 197, 94, 1)",
    "rgba(239, 68, 68, 1)",
    "rgba(107, 114, 128, 1)",
]
