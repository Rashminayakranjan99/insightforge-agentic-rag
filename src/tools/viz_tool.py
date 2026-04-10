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
        """Build KPI summary cards with BI-style DAX-equivalent measures."""
        value_col = self._pick_value_column(df)
        dim_col = self._pick_dimension_column(df)
        date_col = self._pick_date_column(df)

        kpis = [{
            "label": "Total Records",
            "value": f"{len(df):,}",
            "icon": "database",
            "color": "#6366f1",
            "delta": "DAX: COUNTROWS(FactTable)",
        }]

        if value_col:
            total_val = float(df[value_col].sum())
            avg_val = float(df[value_col].mean())
            kpis.append({
                "label": f"Total {value_col}",
                "value": f"{total_val:,.2f}",
                "icon": "bar-chart",
                "color": "#ec4899",
                "delta": f"DAX: SUM(FactTable[{value_col}])",
            })
            kpis.append({
                "label": f"Avg {value_col}",
                "value": f"{avg_val:,.2f}",
                "icon": "trending-up",
                "color": "#a855f7",
                "delta": f"DAX: AVERAGE(FactTable[{value_col}])",
            })

            if dim_col:
                grouped = df.groupby(dim_col)[value_col].sum().sort_values(ascending=False)
                if not grouped.empty and total_val != 0:
                    top_label = str(grouped.index[0])
                    top_share = float(grouped.iloc[0]) / total_val * 100
                    kpis.append({
                        "label": f"Top {dim_col} Share",
                        "value": f"{top_share:.1f}%",
                        "icon": "check-circle",
                        "color": "#10b981",
                        "delta": (
                            f"{top_label} | DAX: DIVIDE(SUMX(TOPN(1,VALUES(FactTable[{dim_col}])),"
                            f"[Total {value_col}]), [Total {value_col}])"
                        ),
                    })

            if date_col:
                monthly = self._monthly_series(df, date_col, value_col)
                if len(monthly) >= 2:
                    prev_val = float(monthly.iloc[-2])
                    last_val = float(monthly.iloc[-1])
                    if prev_val != 0:
                        growth_pct = (last_val - prev_val) / abs(prev_val) * 100
                        kpis.append({
                            "label": "MoM Growth",
                            "value": f"{growth_pct:+.1f}%",
                            "icon": "trending-up",
                            "color": "#14b8a6",
                            "delta": "DAX: DIVIDE([Total]-CALCULATE([Total],DATEADD(Date[Date],-1,MONTH)),"
                                     "CALCULATE([Total],DATEADD(Date[Date],-1,MONTH)))",
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

        return {"type": "kpi_cards", "kpis": kpis[:6]}

    def build_pareto_chart(self, df: pd.DataFrame, dim_col: str, value_col: str,
                           top_n: int = 10) -> Dict[str, Any]:
        """Build Pareto chart: contribution bars + cumulative percentage line."""
        grouped = df.groupby(dim_col)[value_col].sum().sort_values(ascending=False).head(top_n)
        total = grouped.sum()
        if total == 0:
            cumulative_pct = pd.Series([0.0] * len(grouped), index=grouped.index)
        else:
            cumulative_pct = (grouped.cumsum() / total * 100).round(2)

        labels = grouped.index.astype(str).tolist()
        bar_values = grouped.round(2).tolist()
        line_values = cumulative_pct.tolist()
        n = len(labels)

        return {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "type": "bar",
                        "label": f"Total {value_col}",
                        "data": bar_values,
                        "backgroundColor": [VIZ_CHART_COLORS[i % len(VIZ_CHART_COLORS)] for i in range(n)],
                        "borderColor": [VIZ_CHART_BORDERS[i % len(VIZ_CHART_BORDERS)] for i in range(n)],
                        "borderWidth": 1,
                        "yAxisID": "y",
                    },
                    {
                        "type": "line",
                        "label": "Cumulative %",
                        "data": line_values,
                        "borderColor": "rgba(16, 185, 129, 1)",
                        "backgroundColor": "rgba(16, 185, 129, 0.15)",
                        "borderWidth": 3,
                        "pointRadius": 3,
                        "pointBackgroundColor": "rgba(16, 185, 129, 1)",
                        "tension": 0.3,
                        "fill": False,
                        "yAxisID": "y1",
                    },
                ],
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": f"Pareto: {value_col} by {dim_col}",
                        "font": {"size": 13, "weight": "bold"},
                        "color": "rgba(240,240,245,0.9)",
                    },
                    "legend": {"display": True},
                },
                "scales": {
                    "x": {"ticks": {"color": "rgba(139,139,158,0.8)"}, "grid": {"color": "rgba(255,255,255,0.06)"}},
                    "y": {"beginAtZero": True, "ticks": {"color": "rgba(139,139,158,0.8)"}, "grid": {"color": "rgba(255,255,255,0.06)"}},
                    "y1": {
                        "position": "right",
                        "beginAtZero": True,
                        "max": 100,
                        "ticks": {"color": "rgba(139,139,158,0.8)"},
                        "grid": {"drawOnChartArea": False},
                    },
                },
            },
        }

    def build_time_intelligence_chart(self, df: pd.DataFrame, date_col: str,
                                      value_col: str) -> Dict[str, Any]:
        """Build monthly total with moving average (time-intelligence BI view)."""
        monthly = self._monthly_series(df, date_col, value_col)
        monthly = monthly.tail(18)
        rolling = monthly.rolling(window=3, min_periods=1).mean()

        labels = [idx.strftime("%Y-%m") for idx in monthly.index]
        return {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": f"Monthly {value_col}",
                        "data": monthly.round(2).tolist(),
                        "borderColor": VIZ_CHART_BORDERS[0],
                        "backgroundColor": "rgba(99, 102, 241, 0.15)",
                        "borderWidth": 3,
                        "tension": 0.35,
                        "pointRadius": 2,
                        "fill": True,
                    },
                    {
                        "label": "3-Period Moving Avg",
                        "data": rolling.round(2).tolist(),
                        "borderColor": "rgba(16, 185, 129, 1)",
                        "backgroundColor": "rgba(16, 185, 129, 0.0)",
                        "borderWidth": 2,
                        "borderDash": [6, 4],
                        "pointRadius": 1,
                        "tension": 0.25,
                        "fill": False,
                    },
                ],
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": f"Time Intelligence: {value_col} trend",
                        "font": {"size": 13, "weight": "bold"},
                        "color": "rgba(240,240,245,0.9)",
                    },
                    "legend": {"display": True},
                },
                "scales": {
                    "x": {"ticks": {"color": "rgba(139,139,158,0.8)"}, "grid": {"color": "rgba(255,255,255,0.06)"}},
                    "y": {"beginAtZero": True, "ticks": {"color": "rgba(139,139,158,0.8)"}, "grid": {"color": "rgba(255,255,255,0.06)"}},
                },
            },
        }

    def _pick_value_column(self, df: pd.DataFrame) -> str:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            return ""
        return max(numeric_cols, key=lambda c: float(df[c].std(skipna=True) or 0.0))

    def _pick_dimension_column(self, df: pd.DataFrame) -> str:
        categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
        ranked = []
        for col in categorical_cols:
            nunique = int(df[col].nunique(dropna=True))
            if 2 <= nunique <= 40:
                ranked.append((nunique, col))
        if not ranked:
            return ""
        ranked.sort()
        return ranked[0][1]

    def _pick_date_column(self, df: pd.DataFrame) -> str:
        for col in df.columns:
            try:
                if np.issubdtype(df[col].dtype, np.datetime64):
                    return col
            except TypeError:
                pass
            if df[col].dtype == "object":
                sample = df[col].dropna().head(200)
                if sample.empty:
                    continue
                parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True)
                parse_ratio = float(parsed.notna().mean())
                if parse_ratio >= 0.8:
                    return col
        return ""

    def _monthly_series(self, df: pd.DataFrame, date_col: str, value_col: str) -> pd.Series:
        temp = df[[date_col, value_col]].dropna().copy()
        temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
        temp = temp.dropna(subset=[date_col])
        if temp.empty:
            return pd.Series(dtype="float64")
        temp["period"] = temp[date_col].dt.to_period("M").dt.to_timestamp()
        return temp.groupby("period")[value_col].sum().sort_index()

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
        value_col = self._pick_value_column(df)
        dim_col = self._pick_dimension_column(df)
        date_col = self._pick_date_column(df)

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

        # 10. Pareto view (DAX-style contribution analysis)
        if dim_col and value_col:
            try:
                charts.append({
                    "id": f"pareto_{dim_col}_{value_col}",
                    "title": f"Pareto: {value_col} by {dim_col}",
                    "config": self.build_pareto_chart(df, dim_col, value_col),
                })
            except Exception:
                pass

        # 11. Time intelligence trend (monthly + moving average)
        if date_col and value_col:
            try:
                time_cfg = self.build_time_intelligence_chart(df, date_col, value_col)
                if len(time_cfg.get("data", {}).get("labels", [])) >= 2:
                    charts.append({
                        "id": f"time_{date_col}_{value_col}",
                        "title": f"Time Intelligence: {value_col}",
                        "config": time_cfg,
                    })
            except Exception:
                pass

        return charts
