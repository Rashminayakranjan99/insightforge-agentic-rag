import json

nb1 = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# 01 - Data Ingestion & Exploration\n",
                "## InsightForge Agentic RAG Pipeline\n",
                "\n",
                "This notebook demonstrates the data ingestion pipeline:\n",
                "1. CSV upload & profiling\n",
                "2. ID column detection & removal\n",
                "3. Schema analysis\n",
                "4. Embedding generation for RAG\n",
                "5. FAISS vector index creation"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import sys\n",
                "sys.path.insert(0, '../src')\n",
                "\n",
                "import pandas as pd\n",
                "import numpy as np\n",
                "from pathlib import Path\n",
                "from ingestion.csv_profiler import CSVProfiler\n",
                "from config import UPLOAD_FOLDER\n",
                "\n",
                "print('Modules loaded successfully!')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Step 1: Load & Profile a CSV Dataset\n",
                "\n",
                "The `CSVProfiler` analyzes the dataset structure, detects column types,\n",
                "identifies ID/junk columns, and generates metadata for the Planner agent."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Create sample dataset for demonstration\n",
                "np.random.seed(42)\n",
                "n = 500\n",
                "sample_df = pd.DataFrame({\n",
                "    'customer_id': range(1, n+1),\n",
                "    'order_id': [f'ORD-{i:05d}' for i in range(1, n+1)],\n",
                "    'product_category': np.random.choice(['Electronics', 'Clothing', 'Books', 'Home', 'Sports'], n),\n",
                "    'region': np.random.choice(['North', 'South', 'East', 'West'], n),\n",
                "    'revenue': np.random.uniform(10, 500, n).round(2),\n",
                "    'quantity': np.random.randint(1, 20, n),\n",
                "    'rating': np.random.uniform(1, 5, n).round(1),\n",
                "})\n",
                "\n",
                "# Save to disk\n",
                "sample_path = '../data/sample_sales.csv'\n",
                "sample_df.to_csv(sample_path, index=False)\n",
                "print(f'Sample dataset: {sample_df.shape[0]} rows x {sample_df.shape[1]} columns')\n",
                "sample_df.head()"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Profile the CSV\n",
                "profiler = CSVProfiler()\n",
                "profile = profiler.profile(sample_path)\n",
                "\n",
                "print(f'Filename: {profile[\"filename\"]}')\n",
                "print(f'Row count: {profile[\"row_count\"]}')\n",
                "print(f'\\nColumn Analysis:')\n",
                "print('-' * 70)\n",
                "for col_name, col_info in profile['columns'].items():\n",
                "    dtype = col_info['dtype']\n",
                "    unique = col_info['unique_count']\n",
                "    is_id = col_info.get('is_id', False)\n",
                "    flag = ' [ID - WILL BE DROPPED]' if is_id else ''\n",
                "    print(f'  {col_name:20s} | {dtype:8s} | unique={unique:5d} | numeric={col_info[\"is_numeric\"]}{flag}')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Step 2: ID Column Detection\n",
                "\n",
                "The profiler automatically detects columns that are identifiers based on:\n",
                "1. **Name matching**: Exact match against known ID patterns (id, uuid, order_id)\n",
                "2. **Suffix + cardinality**: Suffix like `_id` with >80% unique values\n",
                "3. **Sequential detection**: Near-unique numeric columns with step=1 diffs"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Show which columns will be dropped\n",
                "dropped = profile.get('dropped_columns', [])\n",
                "print(f'Columns flagged for removal: {dropped}')\n",
                "print(f'These columns have near-100% uniqueness and are not useful for analysis.')\n",
                "\n",
                "# Clean the dataframe\n",
                "clean_df = profiler.clean_dataframe(sample_df.copy(), profile)\n",
                "print(f'\\nBefore cleaning: {sample_df.shape[1]} columns')\n",
                "print(f'After cleaning:  {clean_df.shape[1]} columns')\n",
                "print(f'Remaining columns: {list(clean_df.columns)}')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Step 3: Document Ingestion for RAG\n",
                "\n",
                "The `DocumentIngestor` takes text, splits it into chunks (sentences),\n",
                "embeds each chunk using SentenceTransformers (all-MiniLM-L6-v2, 384-dim),\n",
                "and indexes them in a FAISS flat inner-product index for fast retrieval."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "from ingestion.document_ingestor import DocumentIngestor\n",
                "\n",
                "# Create text summary of the dataset for RAG\n",
                "cats = ', '.join(clean_df['product_category'].unique())\n",
                "regions = ', '.join(clean_df['region'].unique())\n",
                "summary_text = (\n",
                "    f'Sales dataset with {len(clean_df)} records. '\n",
                "    f'Product categories include {cats}. '\n",
                "    f'Regions covered: {regions}. '\n",
                "    f'Average revenue is ${clean_df[\"revenue\"].mean():.2f} per transaction. '\n",
                "    f'Average quantity sold is {clean_df[\"quantity\"].mean():.1f} items. '\n",
                "    f'Average customer rating is {clean_df[\"rating\"].mean():.2f} out of 5. '\n",
                "    f'Revenue ranges from ${clean_df[\"revenue\"].min():.2f} to ${clean_df[\"revenue\"].max():.2f}. '\n",
                "    f'Total revenue: ${clean_df[\"revenue\"].sum():,.2f}.'\n",
                ")\n",
                "\n",
                "print('Dataset summary for RAG ingestion:')\n",
                "print(summary_text)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Ingest into vector store\n",
                "ingestor = DocumentIngestor()\n",
                "ingestor.ingest(summary_text, source='sample_sales.csv')\n",
                "\n",
                "print(f'Chunks indexed: {len(ingestor.chunks)}')\n",
                "print(f'FAISS index size: {ingestor.index.ntotal}')\n",
                "print(f'Embedding dimension: 384')\n",
                "print(f'\\nSample chunks:')\n",
                "for i, chunk in enumerate(ingestor.chunks[:3]):\n",
                "    print(f'  [{i}] {chunk[:80]}...')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "## Summary\n",
                "\n",
                "This notebook demonstrated:\n",
                "- CSV profiling with automatic schema detection\n",
                "- ID column auto-removal (customer_id, order_id detected and dropped)\n",
                "- Text summarization of dataset for RAG\n",
                "- SentenceTransformer embedding + FAISS indexing\n",
                "\n",
                "**Next**: See `02_agentic_rag_pipeline.ipynb` for the Planner -> Executor -> Synthesizer pipeline."
            ]
        }
    ],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py", "mimetype": "text/x-python",
            "name": "python", "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3", "version": "3.12.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

# Notebook 2: Agentic RAG Pipeline
nb2 = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# 02 - Agentic RAG Pipeline\n",
                "## Planner -> Executor -> Synthesizer\n",
                "\n",
                "This notebook demonstrates the 3-agent pipeline that powers InsightForge:\n",
                "1. **Planner**: Uses LLM to create an analysis plan from user query + data profile\n",
                "2. **Executor**: Runs pandas operations and selects chart types\n",
                "3. **Synthesizer**: Crafts professional analyst-style narrative\n",
                "\n",
                "### Architecture\n",
                "```\n",
                "User Query + CSV Profile\n",
                "        |\n",
                "   [Planner Agent] -- LLM --> Analysis Plan (JSON)\n",
                "        |\n",
                "   [Executor Agent] -- Pandas --> Results + Chart Config\n",
                "        |\n",
                "   [Synthesizer Agent] -- LLM --> Professional Narrative\n",
                "        |\n",
                "   Response (Story + Visualization)\n",
                "```"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import sys\n",
                "sys.path.insert(0, '../src')\n",
                "\n",
                "import pandas as pd\n",
                "import numpy as np\n",
                "import json\n",
                "\n",
                "from core.llm_client import LLMRouter\n",
                "from agents.planner import PlannerAgent\n",
                "from agents.executor import ExecutorAgent\n",
                "from agents.synthesizer import SynthesizerAgent\n",
                "from ingestion.csv_profiler import CSVProfiler\n",
                "from tools.viz_tool import VizTool\n",
                "\n",
                "print('All agents loaded successfully!')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Step 1: Prepare Data\n",
                "Load and profile a sample dataset, then clean it."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Create sample data\n",
                "np.random.seed(42)\n",
                "n = 500\n",
                "df = pd.DataFrame({\n",
                "    'product_category': np.random.choice(['Electronics', 'Clothing', 'Books', 'Home', 'Sports'], n),\n",
                "    'region': np.random.choice(['North', 'South', 'East', 'West'], n),\n",
                "    'revenue': np.random.uniform(10, 500, n).round(2),\n",
                "    'quantity': np.random.randint(1, 20, n),\n",
                "    'rating': np.random.uniform(1, 5, n).round(1),\n",
                "})\n",
                "\n",
                "# Save and profile\n",
                "csv_path = '../data/sample_sales_clean.csv'\n",
                "df.to_csv(csv_path, index=False)\n",
                "\n",
                "profiler = CSVProfiler()\n",
                "profile = profiler.profile(csv_path)\n",
                "\n",
                "print(f'Dataset: {df.shape[0]} rows x {df.shape[1]} columns')\n",
                "print(f'Columns: {list(df.columns)}')\n",
                "df.head()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Step 2: Initialize the LLM Router\n",
                "\n",
                "The `LLMRouter` tries Groq (Llama 3.3 70B) first for speed,\n",
                "then falls back to Google Gemini if Groq fails."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Initialize LLM Router (reads API keys from .env)\n",
                "llm = LLMRouter()\n",
                "\n",
                "# Quick test\n",
                "response = llm.chat([{'role': 'user', 'content': 'Say hello in one word'}])\n",
                "print(f'LLM Response: {response}')\n",
                "print(f'Provider used: {llm.last_provider}')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Step 3: Planner Agent\n",
                "\n",
                "The Planner receives a user query + dataset profile and outputs a structured\n",
                "JSON analysis plan: which columns to analyze, what aggregation, which chart type."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "planner = PlannerAgent(llm)\n",
                "\n",
                "# Test with different queries\n",
                "queries = [\n",
                "    'What is the average revenue by product category?',\n",
                "    'Show me the distribution of ratings',\n",
                "    'Which region has the highest total revenue?',\n",
                "    'Is there a correlation between quantity and revenue?',\n",
                "]\n",
                "\n",
                "for q in queries:\n",
                "    plan = planner.plan(q, profile)\n",
                "    print(f'\\nQuery: \"{q}\"')\n",
                "    print(f'Plan: {json.dumps(plan, indent=2)}')\n",
                "    print('-' * 50)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Step 4: Executor Agent\n",
                "\n",
                "The Executor takes the plan and runs actual pandas operations.\n",
                "It returns raw analysis results AND a Chart.js-compatible config."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "executor = ExecutorAgent()\n",
                "\n",
                "# Execute the first query's plan\n",
                "query = 'What is the average revenue by product category?'\n",
                "plan = planner.plan(query, profile)\n",
                "result = executor.execute(plan, df)\n",
                "\n",
                "print('Analysis Result:')\n",
                "print(json.dumps(result['analysis_result'], indent=2, default=str))\n",
                "\n",
                "print(f'\\nChart Type: {result[\"chart_config\"][\"type\"]}')\n",
                "print(f'Labels: {result[\"chart_config\"][\"data\"][\"labels\"]}')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Step 5: Synthesizer Agent\n",
                "\n",
                "The Synthesizer takes the analysis results and crafts a professional,\n",
                "McKinsey-style analyst narrative with key findings and recommendations."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "synthesizer = SynthesizerAgent(llm)\n",
                "\n",
                "narrative = synthesizer.synthesize(\n",
                "    user_query=query,\n",
                "    plan=plan,\n",
                "    analysis_result=result['analysis_result'],\n",
                "    summary_data=result['summary_data'],\n",
                "    profile=profile,\n",
                ")\n",
                "\n",
                "print('=== ANALYST NARRATIVE ===')\n",
                "print(narrative)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Step 6: Full Pipeline - End to End\n",
                "\n",
                "Run the complete pipeline for a new query."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "def run_pipeline(query, df, profile, llm):\n",
                "    \"\"\"Run the complete Planner -> Executor -> Synthesizer pipeline.\"\"\"\n",
                "    planner = PlannerAgent(llm)\n",
                "    executor = ExecutorAgent()\n",
                "    synthesizer = SynthesizerAgent(llm)\n",
                "    \n",
                "    # Step 1: Plan\n",
                "    plan = planner.plan(query, profile)\n",
                "    print(f'Plan: {plan[\"analysis_type\"]} | Viz: {plan[\"visualization\"]}')\n",
                "    \n",
                "    # Step 2: Execute\n",
                "    result = executor.execute(plan, df)\n",
                "    \n",
                "    # Step 3: Synthesize\n",
                "    narrative = synthesizer.synthesize(query, plan, result['analysis_result'],\n",
                "                                       result['summary_data'], profile)\n",
                "    \n",
                "    return {\n",
                "        'plan': plan,\n",
                "        'result': result,\n",
                "        'narrative': narrative,\n",
                "        'chart_config': result['chart_config'],\n",
                "    }\n",
                "\n",
                "# Run for a new query\n",
                "output = run_pipeline('Compare revenue across regions', df, profile, llm)\n",
                "print('\\n' + output['narrative'])"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Step 7: Visualization Overview Generation\n",
                "\n",
                "The `VizTool` generates BI-style overview charts including KPI cards,\n",
                "horizontal bars, combo charts, radar charts, and more."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "viz_tool = VizTool()\n",
                "overview = viz_tool.generate_overview_charts(df, profile)\n",
                "\n",
                "print(f'Generated {len(overview)} overview charts:\\n')\n",
                "for chart in overview:\n",
                "    chart_type = chart['config'].get('type', 'custom')\n",
                "    print(f'  - {chart[\"title\"]} ({chart_type})')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "## Summary\n",
                "\n",
                "This notebook demonstrated the complete agentic RAG pipeline:\n",
                "\n",
                "| Agent | Role | Input | Output |\n",
                "|-------|------|-------|--------|\n",
                "| **Planner** | Decides analysis strategy | Query + Profile | JSON plan |\n",
                "| **Executor** | Runs pandas operations | Plan + DataFrame | Results + Chart |\n",
                "| **Synthesizer** | Crafts narrative | Results + Context | Analyst story |\n",
                "\n",
                "The pipeline runs automatically when users chat in the web interface.\n",
                "All visualizations are Chart.js-compatible and can be added to custom dashboards."
            ]
        }
    ],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py", "mimetype": "text/x-python",
            "name": "python", "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3", "version": "3.12.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

# Write both notebooks
with open(r'c:\Users\rashm\NARESH_DS_AI\code\project\insightforge-agentic-rag\notebooks\01_ingestion_exploration.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb1, f, indent=1, ensure_ascii=False)

with open(r'c:\Users\rashm\NARESH_DS_AI\code\project\insightforge-agentic-rag\notebooks\02_agentic_rag_pipeline.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb2, f, indent=1, ensure_ascii=False)

print("Both notebooks written successfully!")
