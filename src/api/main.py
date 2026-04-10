# src/api/main.py
"""Flask application — serves API + static frontend."""

import sys
import os
import uuid
import json
import traceback
from pathlib import Path

# Add src to path for imports
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS

from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS, CSV_READ_CHUNK_SIZE
from core.llm_client import LLMRouter
from agents.planner import PlannerAgent
from agents.executor import ExecutorAgent
from agents.synthesizer import SynthesizerAgent
from ingestion.csv_profiler import CSVProfiler
from tools.viz_tool import VizTool
from memory.short_term import ShortTermMemory
from api.middleware import register_middleware
from api.schemas import ChatRequest, ChatResponse, UploadResponse

import pandas as pd
import numpy as np

# ── App Setup ────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=str(SRC_DIR / "static"), static_url_path="/static")
app.secret_key = os.urandom(24)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB
CORS(app)
register_middleware(app)

# ── Shared State ─────────────────────────────────────────────────────────
llm = LLMRouter()
planner = PlannerAgent(llm)
executor = ExecutorAgent()
synthesizer = SynthesizerAgent(llm)
profiler = CSVProfiler()
viz_tool = VizTool()
memory = ShortTermMemory()

# Per-session storage (in production, use Redis)
_sessions = {}  # session_id -> {df, profile, charts, dashboards}


def _get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "df": None,
            "profile": None,
            "charts": [],       # Generated chart configs
            "dashboards": [],   # Saved dashboards
            "csv_path": None,
            "chunk_info": None,
        }
    return _sessions[session_id]


def _load_csv_with_chunking(csv_path: Path, chunk_size: int = CSV_READ_CHUNK_SIZE):
    """Read CSV using pandas chunking and stitch chunks for full-data analysis."""
    chunks = []
    chunk_count = 0

    for chunk in pd.read_csv(str(csv_path), chunksize=chunk_size):
        chunks.append(chunk)
        chunk_count += 1

    if not chunks:
        return pd.DataFrame(), {"enabled": True, "chunk_size": chunk_size, "chunk_count": 0}

    df = pd.concat(chunks, ignore_index=True)
    return df, {
        "enabled": True,
        "chunk_size": chunk_size,
        "chunk_count": chunk_count,
    }


# ── Routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/upload", methods=["POST"])
def upload_csv():
    """Upload and profile a CSV file."""
    try:
        if "file" not in request.files:
            return jsonify(UploadResponse(success=False, error="No file provided").to_dict()), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify(UploadResponse(success=False, error="No file selected").to_dict()), 400

        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify(UploadResponse(success=False, error=f"Only CSV files allowed, got .{ext}").to_dict()), 400

        # Save file
        filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        filepath = UPLOAD_FOLDER / filename
        file.save(str(filepath))

        # Load CSV with automatic chunking so analysis uses full uploaded data.
        df, chunk_info = _load_csv_with_chunking(filepath)

        # Profile the CSV based on the full loaded dataframe
        profile = profiler.profile(str(filepath), df=df, chunk_info=chunk_info)

        # Drop ID / high-cardinality junk columns (e.g. customer_id, uuid)
        df = profiler.clean_dataframe(df, profile)

        # Remove dropped columns from profile so planner/executor don't see them
        for dropped_col in profile.get("dropped_columns", []):
            profile["columns"].pop(dropped_col, None)

        # Store in session
        session_id = request.form.get("session_id", "default")
        sess = _get_session(session_id)
        sess["df"] = df
        sess["profile"] = profile
        sess["csv_path"] = str(filepath)
        sess["chunk_info"] = chunk_info

        # Generate overview charts for dashboard builder
        overview_charts = viz_tool.generate_overview_charts(df, profile)
        sess["charts"] = overview_charts

        # Clear conversation history for new upload
        memory.clear(session_id)

        return jsonify(UploadResponse(
            success=True,
            filename=file.filename,
            profile=profile,
        ).to_dict())

    except Exception as e:
        traceback.print_exc()
        return jsonify(UploadResponse(success=False, error=str(e)).to_dict()), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """Process a user query through the agentic pipeline."""
    try:
        data = request.get_json()
        if not data or not data.get("query"):
            return jsonify({"error": "No query provided"}), 400

        req = ChatRequest.from_dict(data)
        sess = _get_session(req.session_id)

        if sess["df"] is None or sess["profile"] is None:
            return jsonify(ChatResponse(
                narrative="Please upload a CSV file first to start analyzing data.",
                error="no_data",
            ).to_dict())

        df = sess["df"]
        profile = sess["profile"]

        # Save user message to memory
        memory.add(req.session_id, "user", req.query)
        history = memory.get_last_n(req.session_id, 6)

        # ── Agentic Pipeline ──────────────────────────────────────────
        # Step 1: Planner — decide what analysis to run
        plan = planner.plan(req.query, profile)
        print(f"[PLAN] {json.dumps(plan, indent=2)}")

        # Step 2: Executor — run the analysis
        exec_result = executor.execute(plan, df)
        chart_config = exec_result["chart_config"]
        analysis_result = exec_result["analysis_result"]
        summary_data = exec_result["summary_data"]

        # Step 3: Synthesizer — craft narrative
        narrative = synthesizer.synthesize(
            req.query, plan, analysis_result, summary_data, profile, history
        )

        # Save chart to session for dashboard
        chart_id = f"chat_{uuid.uuid4().hex[:6]}"
        if chart_config.get("data", {}).get("labels") or chart_config.get("data", {}).get("datasets"):
            sess["charts"].append({
                "id": chart_id,
                "title": plan.get("description", req.query[:40]),
                "config": chart_config,
                "query": req.query,
            })

        # Save assistant response to memory
        memory.add(req.session_id, "assistant", narrative)

        response = ChatResponse(
            narrative=narrative,
            chart_config=chart_config,
            analysis_type=plan.get("analysis_type", "general"),
            provider=llm.last_provider,
        )
        return jsonify(response.to_dict())

    except Exception as e:
        traceback.print_exc()
        return jsonify(ChatResponse(
            narrative="I encountered an error while analyzing your data. Please try rephrasing your question.",
            error=str(e),
        ).to_dict()), 500


@app.route("/api/columns", methods=["GET"])
def get_columns():
    """Return column info for the uploaded CSV."""
    session_id = request.args.get("session_id", "default")
    sess = _get_session(session_id)

    if sess["profile"] is None:
        return jsonify({"error": "No CSV uploaded"}), 400

    return jsonify({
        "columns": sess["profile"].get("columns", {}),
        "filename": sess["profile"].get("filename", ""),
        "row_count": sess["profile"].get("row_count", 0),
        "chunking": sess["profile"].get("chunking", sess.get("chunk_info")),
    })


@app.route("/api/charts", methods=["GET"])
def get_charts():
    """Return all generated charts for dashboard builder."""
    session_id = request.args.get("session_id", "default")
    sess = _get_session(session_id)

    return jsonify({"charts": sess.get("charts", [])})


@app.route("/api/dashboard", methods=["POST"])
def save_dashboard():
    """Save a dashboard configuration."""
    try:
        data = request.get_json()
        session_id = data.get("session_id", "default")
        chart_ids = data.get("chart_ids", [])
        name = data.get("name", "My Dashboard")

        sess = _get_session(session_id)
        all_charts = {c["id"]: c for c in sess.get("charts", [])}

        selected = [all_charts[cid] for cid in chart_ids if cid in all_charts]

        dashboard = {
            "id": f"dash_{uuid.uuid4().hex[:6]}",
            "name": name,
            "charts": selected,
        }
        sess["dashboards"].append(dashboard)

        return jsonify({"success": True, "dashboard": dashboard})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards", methods=["GET"])
def get_dashboards():
    """Return all saved dashboards."""
    session_id = request.args.get("session_id", "default")
    sess = _get_session(session_id)
    return jsonify({"dashboards": sess.get("dashboards", [])})


@app.route("/api/quick-chart", methods=["POST"])
def quick_chart():
    """Generate a custom chart on demand."""
    try:
        data = request.get_json()
        session_id = data.get("session_id", "default")
        chart_type = data.get("chart_type", "bar")
        x_column = data.get("x_column")
        y_column = data.get("y_column")
        aggregation = data.get("aggregation", "mean")

        sess = _get_session(session_id)
        if sess["df"] is None:
            return jsonify({"error": "No CSV uploaded"}), 400

        df = sess["df"]

        if x_column and y_column and x_column in df.columns and y_column in df.columns:
            if pd.api.types.is_numeric_dtype(df[y_column]):
                grouped = df.groupby(x_column)[y_column].agg(aggregation).reset_index()
                grouped = grouped.sort_values(y_column, ascending=False).head(15)
                labels = grouped[x_column].astype(str).tolist()
                values = grouped[y_column].round(2).tolist()
            else:
                vc = df[x_column].value_counts().head(15)
                labels = vc.index.astype(str).tolist()
                values = vc.values.tolist()
        elif x_column and x_column in df.columns:
            if pd.api.types.is_numeric_dtype(df[x_column]):
                counts, edges = np.histogram(df[x_column].dropna(), bins=15)
                labels = [f"{edges[i]:.1f}" for i in range(len(counts))]
                values = counts.tolist()
            else:
                vc = df[x_column].value_counts().head(15)
                labels = vc.index.astype(str).tolist()
                values = vc.values.tolist()
        else:
            return jsonify({"error": "Invalid column selection"}), 400

        title = f"{aggregation.title()} of {y_column} by {x_column}" if y_column else f"Distribution of {x_column}"
        config = viz_tool.build_quick_chart(df, chart_type, labels, values, title)

        chart_entry = {
            "id": f"custom_{uuid.uuid4().hex[:6]}",
            "title": title,
            "config": config,
        }
        sess["charts"].append(chart_entry)

        return jsonify({"success": True, "chart": chart_entry})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── Run ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  InsightForge - Agentic RAG Analytics Platform")
    print("  Open: http://127.0.0.1:5000")
    print("=" * 60 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
