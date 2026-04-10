# src/agents/executor.py
"""Executor Agent — runs pandas operations based on the Planner's analysis plan."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from config import VIZ_CHART_COLORS, VIZ_CHART_BORDERS, RELATION_TOP_K


class ExecutorAgent:
    """Executes the analysis plan on the actual DataFrame and returns structured results."""

    def __init__(self):
        pass

    def execute(self, plan: dict, df: pd.DataFrame) -> Dict[str, Any]:
        """Run the analysis plan against the DataFrame.

        Returns:
            {
                "analysis_result": {...},   # raw analysis results
                "chart_config": {...},       # Chart.js compatible config
                "summary_data": {...},       # key stats for storytelling
            }
        """
        analysis_type = plan.get("analysis_type", "general")
        target_cols = plan.get("target_columns") or []
        group_by = plan.get("group_by") or []
        aggregation = plan.get("aggregation") or "mean"
        sort_by = plan.get("sort_by")
        sort_order = plan.get("sort_order", "desc")
        top_n = plan.get("top_n")
        viz_type = plan.get("visualization") or "bar"

        # Validate columns exist
        target_cols = [c for c in target_cols if c in df.columns]
        if group_by:
            group_by = [c for c in group_by if c in df.columns]

        try:
            if analysis_type == "aggregation":
                result = self._aggregation(df, target_cols, group_by, aggregation, sort_order, top_n)
            elif analysis_type == "correlation":
                result = self._correlation(df, target_cols, top_n=top_n)
                viz_type = "scatter" if len(target_cols) == 2 else "bar"
            elif analysis_type == "distribution":
                result = self._distribution(df, target_cols)
                viz_type = "histogram" if viz_type not in ("histogram", "bar") else viz_type
            elif analysis_type == "trend":
                result = self._trend(df, target_cols, group_by)
                viz_type = "line"
            elif analysis_type == "comparison":
                result = self._comparison(df, target_cols, group_by, aggregation)
            else:
                result = self._general_summary(df, target_cols)
        except Exception as e:
            result = self._general_summary(df, target_cols)
            result["error"] = str(e)

        # Build chart config
        chart_config = self._build_chart_config(result, viz_type, plan)

        return {
            "analysis_result": result,
            "chart_config": chart_config,
            "summary_data": self._extract_summary(df, target_cols, result),
            "plan": plan,
        }

    # ── Analysis Methods ─────────────────────────────────────────────────

    def _aggregation(self, df, target_cols, group_by, agg, sort_order, top_n):
        if not target_cols:
            target_cols = df.select_dtypes(include=[np.number]).columns.tolist()[:1]
        if not target_cols:
            return {"labels": [], "values": [], "type": "aggregation"}

        value_col = target_cols[0]

        if group_by and len(group_by) > 0:
            grouped = df.groupby(group_by[0])[value_col].agg(agg).reset_index()
            grouped.columns = ["label", "value"]
            grouped = grouped.sort_values("value", ascending=(sort_order == "asc"))
            if top_n:
                grouped = grouped.head(top_n)
            return {
                "labels": grouped["label"].astype(str).tolist(),
                "values": grouped["value"].round(2).tolist(),
                "type": "aggregation",
                "agg_func": agg,
                "value_column": value_col,
                "group_column": group_by[0],
            }
        else:
            val = getattr(df[value_col], agg)()
            return {
                "labels": [f"{agg}({value_col})"],
                "values": [round(float(val), 2)],
                "type": "aggregation",
                "agg_func": agg,
                "value_column": value_col,
            }

    def _correlation(self, df, target_cols, top_n=None):
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        target_numeric = [c for c in target_cols if c in numeric_cols]

        if len(target_numeric) == 2:
            col_x, col_y = target_numeric[0], target_numeric[1]
            corr = df[col_x].corr(df[col_y])
            sampled = df[[col_x, col_y]].dropna().sample(min(200, len(df)), random_state=42)
            return {
                "x_values": sampled[col_x].round(2).tolist(),
                "y_values": sampled[col_y].round(2).tolist(),
                "correlation": round(float(corr), 4),
                "x_label": col_x,
                "y_label": col_y,
                "type": "correlation",
            }

        cols = target_numeric or numeric_cols[:8]
        if len(cols) < 2:
            return {"labels": [], "values": [], "type": "correlation_pairs"}

        corr_matrix = df[cols].corr()
        pairs = []
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                corr_val = corr_matrix.iloc[i, j]
                if pd.isna(corr_val):
                    continue
                pairs.append({
                    "pair": f"{cols[i]} <> {cols[j]}",
                    "correlation": round(float(corr_val), 4),
                    "abs_correlation": round(float(abs(corr_val)), 4),
                    "x_label": cols[i],
                    "y_label": cols[j],
                })

        if not pairs:
            return {"labels": [], "values": [], "type": "correlation_pairs"}

        limit = top_n if isinstance(top_n, int) and top_n > 0 else RELATION_TOP_K
        pairs = sorted(pairs, key=lambda x: x["abs_correlation"], reverse=True)[:limit]
        return {
            "labels": [p["pair"] for p in pairs],
            "values": [p["correlation"] for p in pairs],
            "type": "correlation_pairs",
            "pairs": pairs,
            "strongest_positive": max(pairs, key=lambda x: x["correlation"]),
            "strongest_negative": min(pairs, key=lambda x: x["correlation"]),
        }

    def _distribution(self, df, target_cols):
        if not target_cols:
            target_cols = df.select_dtypes(include=[np.number]).columns.tolist()[:1]
        if not target_cols:
            return {"labels": [], "values": [], "type": "distribution"}

        col = target_cols[0]
        if pd.api.types.is_numeric_dtype(df[col]):
            counts, edges = np.histogram(df[col].dropna(), bins=min(20, df[col].nunique()))
            labels = [f"{edges[i]:.1f}-{edges[i+1]:.1f}" for i in range(len(counts))]
            return {
                "labels": labels,
                "values": counts.tolist(),
                "type": "distribution",
                "column": col,
                "stats": {
                    "mean": round(float(df[col].mean()), 2),
                    "median": round(float(df[col].median()), 2),
                    "std": round(float(df[col].std()), 2),
                    "min": round(float(df[col].min()), 2),
                    "max": round(float(df[col].max()), 2),
                },
            }
        else:
            vc = df[col].value_counts().head(15)
            return {
                "labels": vc.index.astype(str).tolist(),
                "values": vc.values.tolist(),
                "type": "distribution",
                "column": col,
            }

    def _trend(self, df, target_cols, group_by):
        if not target_cols:
            return {"labels": [], "values": [], "type": "trend"}

        # Try to find a date/time column for x-axis
        date_col = None
        if group_by:
            date_col = group_by[0]
        else:
            for c in df.columns:
                if df[c].dtype == "object":
                    try:
                        pd.to_datetime(df[c].head(5))
                        date_col = c
                        break
                    except (ValueError, TypeError):
                        continue

        value_col = target_cols[0]

        if date_col:
            temp = df[[date_col, value_col]].dropna().copy()
            try:
                temp[date_col] = pd.to_datetime(temp[date_col])
                temp = temp.sort_values(date_col)
            except (ValueError, TypeError):
                temp = temp.head(50)

            # Sample if too many points
            if len(temp) > 100:
                step = len(temp) // 100
                temp = temp.iloc[::step]

            return {
                "labels": temp[date_col].astype(str).tolist(),
                "values": temp[value_col].round(2).tolist(),
                "type": "trend",
                "x_label": date_col,
                "y_label": value_col,
            }
        else:
            # Just plot values in order
            vals = df[value_col].dropna().head(100)
            return {
                "labels": list(range(len(vals))),
                "values": vals.round(2).tolist(),
                "type": "trend",
                "y_label": value_col,
            }

    def _comparison(self, df, target_cols, group_by, agg):
        if group_by and target_cols:
            grouped = df.groupby(group_by[0])[target_cols[0]].agg(agg).reset_index()
            grouped.columns = ["label", "value"]
            grouped = grouped.sort_values("value", ascending=False).head(15)
            return {
                "labels": grouped["label"].astype(str).tolist(),
                "values": grouped["value"].round(2).tolist(),
                "type": "comparison",
            }
        return self._general_summary(df, target_cols)

    def _general_summary(self, df, target_cols):
        numeric = df.select_dtypes(include=[np.number])
        summary = {}
        for col in (target_cols or numeric.columns.tolist()[:5]):
            if col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    summary[col] = {
                        "mean": round(float(df[col].mean()), 2),
                        "median": round(float(df[col].median()), 2),
                        "min": round(float(df[col].min()), 2),
                        "max": round(float(df[col].max()), 2),
                        "std": round(float(df[col].std()), 2),
                    }
                else:
                    vc = df[col].value_counts().head(5)
                    summary[col] = {
                        "top_values": dict(zip(vc.index.astype(str).tolist(), vc.values.tolist())),
                        "unique_count": int(df[col].nunique()),
                    }

        # Build a simple bar chart of numeric column means
        num_cols = numeric.columns.tolist()[:8]
        if num_cols:
            means = [round(float(df[c].mean()), 2) for c in num_cols]
            return {
                "labels": num_cols,
                "values": means,
                "type": "general",
                "column_summaries": summary,
            }
        else:
            first_col = df.columns[0]
            vc = df[first_col].value_counts().head(10)
            return {
                "labels": vc.index.astype(str).tolist(),
                "values": vc.values.tolist(),
                "type": "general",
                "column_summaries": summary,
            }

    # ── Chart Config Builder ─────────────────────────────────────────────

    def _build_chart_config(self, result: dict, viz_type: str, plan: dict) -> dict:
        """Build a Chart.js-compatible configuration object."""
        labels = result.get("labels", [])
        values = result.get("values", [])

        # Handle scatter data
        if result.get("type") == "correlation" and "x_values" in result:
            scatter_data = [
                {"x": x, "y": y}
                for x, y in zip(result["x_values"], result["y_values"])
            ]
            return {
                "type": "scatter",
                "data": {
                    "datasets": [{
                        "label": f'{result.get("x_label", "X")} vs {result.get("y_label", "Y")}',
                        "data": scatter_data,
                        "backgroundColor": VIZ_CHART_COLORS[0],
                        "borderColor": VIZ_CHART_BORDERS[0],
                        "pointRadius": 4,
                        "pointHoverRadius": 6,
                    }]
                },
                "options": {
                    "responsive": True,
                    "maintainAspectRatio": False,
                    "plugins": {
                        "title": {"display": True, "text": plan.get("description", "Correlation Analysis")},
                        "legend": {"display": True},
                    },
                    "scales": {
                        "x": {"title": {"display": True, "text": result.get("x_label", "")}},
                        "y": {"title": {"display": True, "text": result.get("y_label", "")}},
                    },
                },
            }

        if result.get("type") == "correlation_pairs":
            corr_values = result.get("values", [])
            colors = [
                "rgba(16, 185, 129, 0.8)" if v >= 0 else "rgba(239, 68, 68, 0.8)"
                for v in corr_values
            ]
            borders = [
                "rgba(16, 185, 129, 1)" if v >= 0 else "rgba(239, 68, 68, 1)"
                for v in corr_values
            ]
            return {
                "type": "bar",
                "data": {
                    "labels": result.get("labels", []),
                    "datasets": [{
                        "label": plan.get("description", "Correlation strength"),
                        "data": corr_values,
                        "backgroundColor": colors,
                        "borderColor": borders,
                        "borderWidth": 2,
                        "borderRadius": 4,
                    }],
                },
                "options": {
                    "indexAxis": "y",
                    "responsive": True,
                    "maintainAspectRatio": False,
                    "plugins": {
                        "title": {"display": True, "text": plan.get("description", "Column relationships")},
                        "legend": {"display": False},
                    },
                    "scales": {
                        "x": {
                            "min": -1,
                            "max": 1,
                            "grid": {"color": "rgba(255,255,255,0.06)"},
                        },
                        "y": {
                            "ticks": {"autoSkip": False},
                            "grid": {"color": "rgba(255,255,255,0.06)"},
                        },
                    },
                },
            }

        # Map histogram to bar
        chart_type = viz_type
        if chart_type == "histogram":
            chart_type = "bar"

        n = len(labels)
        bg_colors = [VIZ_CHART_COLORS[i % len(VIZ_CHART_COLORS)] for i in range(n)]
        border_colors = [VIZ_CHART_BORDERS[i % len(VIZ_CHART_BORDERS)] for i in range(n)]

        dataset = {
            "label": plan.get("description", "Data"),
            "data": values,
            "backgroundColor": bg_colors,
            "borderColor": border_colors,
            "borderWidth": 2,
        }

        # Line chart styling
        if chart_type == "line":
            dataset["fill"] = True
            dataset["tension"] = 0.4
            dataset["backgroundColor"] = "rgba(99, 102, 241, 0.15)"
            dataset["borderColor"] = VIZ_CHART_BORDERS[0]
            dataset["borderWidth"] = 3
            dataset["pointBackgroundColor"] = VIZ_CHART_COLORS[0]
            dataset["pointRadius"] = 3

        config = {
            "type": chart_type,
            "data": {
                "labels": [str(l) for l in labels],
                "datasets": [dataset],
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": plan.get("description", "Analysis Result"),
                        "font": {"size": 14, "weight": "bold"},
                    },
                    "legend": {"display": chart_type in ("pie", "doughnut")},
                },
            },
        }

        # Add scales for non-circular charts
        if chart_type not in ("pie", "doughnut"):
            config["options"]["scales"] = {
                "x": {
                    "ticks": {"maxRotation": 45, "autoSkip": True, "maxTicksLimit": 20},
                    "grid": {"color": "rgba(255,255,255,0.06)"},
                },
                "y": {
                    "beginAtZero": True,
                    "grid": {"color": "rgba(255,255,255,0.06)"},
                },
            }

        return config

    # ── Summary Extractor ────────────────────────────────────────────────

    def _extract_summary(self, df, target_cols, result):
        """Extract key stats for the synthesizer's storytelling."""
        summary = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "numeric_columns": df.select_dtypes(include=[np.number]).columns.tolist(),
            "categorical_columns": df.select_dtypes(exclude=[np.number]).columns.tolist(),
            "analysis_type": result.get("type", "general"),
            "data_points": len(result.get("labels", result.get("x_values", []))),
        }
        if result.get("type") == "correlation_pairs":
            summary["strongest_positive"] = result.get("strongest_positive")
            summary["strongest_negative"] = result.get("strongest_negative")
        return summary
