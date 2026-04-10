# src/tools/viz_tool.py
"""Visualization Tool - BI-style chart generation with smart selection + KPI cards."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from config import VIZ_CHART_COLORS, VIZ_CHART_BORDERS


class VizTool:
    """Generates Chart.js configs with BI-style visuals: KPI cards, combo charts,
    polar area, radar, stacked bars, horizontal bars, and more."""

    def auto_select_chart(self, df: pd.DataFrame, x_col: str = None, y_col: str = None) -> str:
        """Intelligently select the best chart type based on data characteristics."""
        if x_col and y_col:
            x_numeric = pd.api.types.is_numeric_dtype(df[x_col]) if x_col in df.columns else False
            y_numeric = pd.api.types.is_numeric_dtype(df[y_col]) if y_col in df.columns else False

            if x_numeric and y_numeric:
                return "scatter"
            elif not x_numeric and y_numeric:
                nunique = df[x_col].nunique()
                if nunique <= 6:
                    return "doughnut"
                elif nunique <= 15:
                    return "bar"
                else:
                    return "bar"

        if x_col and x_col in df.columns:
            try:
                pd.to_datetime(df[x_col].head(5))
                return "line"
            except (ValueError, TypeError):
                pass

        return "bar"

    def build_quick_chart(self, df: pd.DataFrame, chart_type: str,
                          labels: list, values: list, title: str = "Chart") -> Dict[str, Any]:
        """Build a standalone Chart.js config."""
        n = len(labels)
        bg_colors = [VIZ_CHART_COLORS[i % len(VIZ_CHART_COLORS)] for i in range(n)]
        border_colors = [VIZ_CHART_BORDERS[i % len(VIZ_CHART_BORDERS)] for i in range(n)]

        dataset = {
            "label": title,
            "data": values,
            "backgroundColor": bg_colors,
            "borderColor": border_colors,
            "borderWidth": 2,
        }

        if chart_type == "line":
            dataset["fill"] = True
            dataset["tension"] = 0.4
            dataset["backgroundColor"] = "rgba(99, 102, 241, 0.15)"
            dataset["borderColor"] = VIZ_CHART_BORDERS[0]
            dataset["borderWidth"] = 3
            dataset["pointRadius"] = 3
            dataset["pointBackgroundColor"] = VIZ_CHART_COLORS[0]

        if chart_type == "polarArea":
            dataset["borderWidth"] = 1

        if chart_type == "radar":
            dataset["fill"] = True
            dataset["backgroundColor"] = "rgba(99, 102, 241, 0.2)"
            dataset["borderColor"] = VIZ_CHART_BORDERS[0]
            dataset["borderWidth"] = 2
            dataset["pointBackgroundColor"] = VIZ_CHART_COLORS[0]

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
                    "title": {"display": True, "text": title,
                              "font": {"size": 13, "weight": "bold"},
                              "color": "rgba(240,240,245,0.9)"},
                    "legend": {"display": chart_type in ("pie", "doughnut", "polarArea", "radar")},
                },
            },
        }

        if chart_type not in ("pie", "doughnut", "polarArea", "radar"):
            config["options"]["scales"] = {
                "x": {"ticks": {"maxRotation": 45, "autoSkip": True, "color": "rgba(139,139,158,0.8)"},
                       "grid": {"color": "rgba(255,255,255,0.06)"}},
                "y": {"beginAtZero": True,
                       "ticks": {"color": "rgba(139,139,158,0.8)"},
                       "grid": {"color": "rgba(255,255,255,0.06)"}},
            }

        return config

    def build_kpi_cards(self, df: pd.DataFrame, profile: dict) -> Dict[str, Any]:
        """Build KPI summary cards data (rendered with custom HTML, not Chart.js)."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        kpis = []

        # Total rows
        kpis.append({
            "label": "Total Records",
            "value": f"{len(df):,}",
            "icon": "database",
            "color": "#6366f1",
        })

        # First numeric column aggregates
        if numeric_cols:
            col = numeric_cols[0]
            kpis.append({
                "label": f"Avg {col}",
                "value": f"{df[col].mean():,.2f}",
                "icon": "trending-up",
                "color": "#a855f7",
                "delta": f"Range: {df[col].min():,.0f} - {df[col].max():,.0f}",
            })

        if len(numeric_cols) >= 2:
            col = numeric_cols[1]
            kpis.append({
                "label": f"Total {col}",
                "value": f"{df[col].sum():,.2f}",
                "icon": "bar-chart",
                "color": "#ec4899",
            })

        # Missing data %
        total_cells = df.shape[0] * df.shape[1]
        missing_pct = (df.isna().sum().sum() / total_cells * 100) if total_cells > 0 else 0
        kpis.append({
            "label": "Data Quality",
            "value": f"{100 - missing_pct:.1f}%",
            "icon": "check-circle",
            "color": "#10b981",
            "delta": f"{missing_pct:.1f}% missing",
        })

        return {"type": "kpi_cards", "kpis": kpis}

    def build_stacked_bar(self, df: pd.DataFrame, cat_col: str, val_col: str,
                          stack_col: str, title: str) -> Dict[str, Any]:
        """Build a stacked bar chart (BI-style)."""
        pivot = df.pivot_table(index=cat_col, columns=stack_col, values=val_col,
                               aggfunc="sum", fill_value=0)
        # Limit to top categories
        pivot = pivot.head(10)
        pivot = pivot[pivot.columns[:6]]  # max 6 stacks

        datasets = []
        for i, col in enumerate(pivot.columns):
            datasets.append({
                "label": str(col),
                "data": pivot[col].round(2).tolist(),
                "backgroundColor": VIZ_CHART_COLORS[i % len(VIZ_CHART_COLORS)],
                "borderColor": VIZ_CHART_BORDERS[i % len(VIZ_CHART_BORDERS)],
                "borderWidth": 1,
            })

        return {
            "type": "bar",
            "data": {
                "labels": [str(l) for l in pivot.index.tolist()],
                "datasets": datasets,
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "title": {"display": True, "text": title,
                              "font": {"size": 13, "weight": "bold"},
                              "color": "rgba(240,240,245,0.9)"},
                    "legend": {"display": True,
                               "labels": {"color": "rgba(139,139,158,0.8)"}},
                },
                "scales": {
                    "x": {"stacked": True,
                           "ticks": {"color": "rgba(139,139,158,0.8)"},
                           "grid": {"color": "rgba(255,255,255,0.06)"}},
                    "y": {"stacked": True, "beginAtZero": True,
                           "ticks": {"color": "rgba(139,139,158,0.8)"},
                           "grid": {"color": "rgba(255,255,255,0.06)"}},
                },
            },
        }

    def build_horizontal_bar(self, labels: list, values: list, title: str) -> Dict[str, Any]:
        """Build a horizontal bar chart (great for ranked comparisons)."""
        n = len(labels)
        config = {
            "type": "bar",
            "data": {
                "labels": [str(l) for l in labels],
                "datasets": [{
                    "label": title,
                    "data": values,
                    "backgroundColor": [VIZ_CHART_COLORS[i % len(VIZ_CHART_COLORS)] for i in range(n)],
                    "borderColor": [VIZ_CHART_BORDERS[i % len(VIZ_CHART_BORDERS)] for i in range(n)],
                    "borderWidth": 2,
                    "borderRadius": 4,
                }],
            },
            "options": {
                "indexAxis": "y",
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "title": {"display": True, "text": title,
                              "font": {"size": 13, "weight": "bold"},
                              "color": "rgba(240,240,245,0.9)"},
                    "legend": {"display": False},
                },
                "scales": {
                    "x": {"beginAtZero": True,
                           "ticks": {"color": "rgba(139,139,158,0.8)"},
                           "grid": {"color": "rgba(255,255,255,0.06)"}},
                    "y": {"ticks": {"color": "rgba(139,139,158,0.8)"},
                           "grid": {"color": "rgba(255,255,255,0.06)"}},
                },
            },
        }
        return config

    def build_combo_chart(self, labels: list, bar_values: list, line_values: list,
                          bar_label: str, line_label: str, title: str) -> Dict[str, Any]:
        """Build a combo bar + line chart (common BI pattern)."""
        n = len(labels)
        return {
            "type": "bar",
            "data": {
                "labels": [str(l) for l in labels],
                "datasets": [
                    {
                        "type": "bar",
                        "label": bar_label,
                        "data": bar_values,
                        "backgroundColor": [VIZ_CHART_COLORS[i % len(VIZ_CHART_COLORS)] for i in range(n)],
                        "borderColor": [VIZ_CHART_BORDERS[i % len(VIZ_CHART_BORDERS)] for i in range(n)],
                        "borderWidth": 1,
                        "borderRadius": 3,
                        "yAxisID": "y",
                    },
                    {
                        "type": "line",
                        "label": line_label,
                        "data": line_values,
                        "borderColor": VIZ_CHART_BORDERS[4],
                        "backgroundColor": "rgba(20, 184, 166, 0.1)",
                        "borderWidth": 3,
                        "pointRadius": 4,
                        "pointBackgroundColor": VIZ_CHART_COLORS[4],
                        "tension": 0.4,
                        "fill": True,
                        "yAxisID": "y1",
                    },
                ],
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "title": {"display": True, "text": title,
                              "font": {"size": 13, "weight": "bold"},
                              "color": "rgba(240,240,245,0.9)"},
                    "legend": {"display": True,
                               "labels": {"color": "rgba(139,139,158,0.8)"}},
                },
                "scales": {
                    "x": {"ticks": {"color": "rgba(139,139,158,0.8)"},
                           "grid": {"color": "rgba(255,255,255,0.06)"}},
                    "y": {"position": "left", "beginAtZero": True,
                           "ticks": {"color": "rgba(139,139,158,0.8)"},
                           "grid": {"color": "rgba(255,255,255,0.06)"}},
                    "y1": {"position": "right", "beginAtZero": True,
                            "ticks": {"color": "rgba(139,139,158,0.8)"},
                            "grid": {"drawOnChartArea": False}},
                },
            },
        }

    def generate_overview_charts(self, df: pd.DataFrame, profile: dict) -> List[Dict[str, Any]]:
        """Generate BI-style overview charts for dashboard quick-picks."""
        charts = []
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

        # 1. KPI Cards (always first)
        kpi_data = self.build_kpi_cards(df, profile)
        charts.append({
            "id": "kpi_overview",
            "title": "Key Performance Indicators",
            "config": kpi_data,
        })

        # 2. Top categories as HORIZONTAL bar (BI-style ranked view)
        if categorical_cols:
            col = categorical_cols[0]
            vc = df[col].value_counts().head(10)
            h_bar = self.build_horizontal_bar(
                vc.index.astype(str).tolist(),
                vc.values.tolist(),
                f"Top {col} (Ranked)"
            )
            charts.append({
                "id": f"hbar_{col}",
                "title": f"Top {col} (Ranked)",
                "config": h_bar,
            })

        # 3. Distribution of first numeric (histogram-style bar)
        if numeric_cols:
            col = numeric_cols[0]
            counts, edges = np.histogram(df[col].dropna(), bins=min(15, max(5, df[col].nunique())))
            labels = [f"{edges[i]:.1f}" for i in range(len(counts))]
            charts.append({
                "id": f"dist_{col}",
                "title": f"Distribution of {col}",
                "config": self.build_quick_chart(df, "bar", labels, counts.tolist(),
                                                  f"Distribution of {col}"),
            })

        # 4. Doughnut for first categorical
        if categorical_cols:
            col = categorical_cols[0]
            vc = df[col].value_counts().head(8)
            charts.append({
                "id": f"donut_{col}",
                "title": f"{col} Composition",
                "config": self.build_quick_chart(df, "doughnut",
                                                  vc.index.astype(str).tolist(),
                                                  vc.values.tolist(),
                                                  f"{col} Composition"),
            })

        # 5. Combo chart: if we have cat + 2 numeric cols
        if categorical_cols and len(numeric_cols) >= 2:
            cat = categorical_cols[0]
            n1, n2 = numeric_cols[0], numeric_cols[1]
            grouped = df.groupby(cat)[[n1, n2]].mean().sort_values(n1, ascending=False).head(10)
            combo = self.build_combo_chart(
                grouped.index.astype(str).tolist(),
                grouped[n1].round(2).tolist(),
                grouped[n2].round(2).tolist(),
                f"Avg {n1}", f"Avg {n2}",
                f"{n1} vs {n2} by {cat}"
            )
            charts.append({
                "id": f"combo_{n1}_{n2}",
                "title": f"{n1} vs {n2} by {cat}",
                "config": combo,
            })

        # 6. Polar Area for second categorical (if exists)
        if len(categorical_cols) >= 2:
            col = categorical_cols[1]
            vc = df[col].value_counts().head(8)
            charts.append({
                "id": f"polar_{col}",
                "title": f"{col} - Polar View",
                "config": self.build_quick_chart(df, "polarArea",
                                                  vc.index.astype(str).tolist(),
                                                  vc.values.tolist(),
                                                  f"{col} Distribution"),
            })

        # 7. Radar chart for numeric column stats (normalized)
        if len(numeric_cols) >= 3:
            # Normalize means to 0-100 scale for radar readability
            cols = numeric_cols[:6]
            means = [float(df[c].mean()) for c in cols]
            max_val = max(means) if max(means) > 0 else 1
            normalized = [round(m / max_val * 100, 1) for m in means]
            charts.append({
                "id": "radar_stats",
                "title": "Column Metrics (Radar)",
                "config": self.build_quick_chart(df, "radar", cols, normalized,
                                                  "Normalized Column Averages"),
            })

        # 8. Stacked bar if we have 2 categoricals + 1 numeric
        if len(categorical_cols) >= 2 and numeric_cols:
            try:
                stacked = self.build_stacked_bar(
                    df, categorical_cols[0], numeric_cols[0], categorical_cols[1],
                    f"{numeric_cols[0]} by {categorical_cols[0]} (Stacked by {categorical_cols[1]})"
                )
                charts.append({
                    "id": f"stacked_{categorical_cols[0]}",
                    "title": f"Stacked: {categorical_cols[0]} x {categorical_cols[1]}",
                    "config": stacked,
                })
            except Exception:
                pass  # Skip if pivot fails

        # 9. Numeric means comparison bar
        if len(numeric_cols) >= 2:
            means = [round(float(df[c].mean()), 2) for c in numeric_cols[:8]]
            charts.append({
                "id": "numeric_means",
                "title": "Numeric Column Averages",
                "config": self.build_quick_chart(df, "bar", numeric_cols[:8], means,
                                                  "Column Averages Comparison"),
            })

        return charts
