"""
Astra Charts — Plotly with purple dark theme
Auto-detects label vs value columns to avoid axis inversion.
"""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

PALETTE = [
    "#9333ea", "#06b6d4", "#f59e0b", "#10b981",
    "#e879f9", "#3b82f6", "#f97316", "#22d3ee",
    "#a855f7", "#14b8a6", "#ec4899", "#84cc16",
]

LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0", family="Inter, sans-serif"),
    title_font=dict(size=15, color="#f3e8ff"),
    legend=dict(
        bgcolor="rgba(15,0,35,0.6)",
        bordercolor="rgba(139,92,246,0.3)",
        borderwidth=1,
        font=dict(color="#e2e8f0"),
    ),
    margin=dict(l=16, r=16, t=48, b=16),
    colorway=PALETTE,
)

AXIS_STYLE = dict(
    gridcolor="rgba(139,92,246,0.15)",
    linecolor="rgba(139,92,246,0.3)",
    tickcolor="rgba(139,92,246,0.3)",
    tickfont=dict(color="#c4b5fd"),
    title_font=dict(color="#c4b5fd"),
    zerolinecolor="rgba(139,92,246,0.2)",
)


def _apply_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(**LAYOUT_BASE)
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE)
    return fig


def _classify_columns(df: pd.DataFrame, hint_x: str, hint_y: str):
    """
    Returns (label_col, value_col) — label is always the string/date column,
    value is always the numeric column. Falls back to agent hints when ambiguous.
    """
    cols = df.columns.tolist()

    string_cols = [c for c in cols if df[c].dtype == object]
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    date_cols   = [c for c in cols if pd.api.types.is_datetime64_any_dtype(df[c])]

    # Prefer hint when it matches a real column
    hint_x = hint_x if hint_x in cols else None
    hint_y = hint_y if hint_y in cols else None

    if string_cols and numeric_cols:
        label_col = string_cols[0]
        value_col = numeric_cols[0]
    elif date_cols and numeric_cols:
        label_col = date_cols[0]
        value_col = numeric_cols[0]
    else:
        label_col = hint_x or cols[0]
        value_col = hint_y or (cols[1] if len(cols) > 1 else cols[0])

    return label_col, value_col


def _fmt(v) -> str:
    if isinstance(v, float) and v >= 1000:
        return f"{v:,.0f}"
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def create_chart(df: pd.DataFrame, cfg: dict) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados para exibir", showarrow=False,
            font=dict(color="#c4b5fd", size=16),
        )
        return _apply_theme(fig)

    chart_type = cfg.get("type", "bar")
    title   = cfg.get("title", "")
    x_label = cfg.get("x_label", cfg.get("x", ""))
    y_label = cfg.get("y_label", cfg.get("y", ""))

    label_col, value_col = _classify_columns(df, cfg.get("x", ""), cfg.get("y", ""))

    # ── Auto-upgrade bar → horizontal_bar when label column has strings ──────
    if chart_type in ("bar", "horizontal_bar"):
        has_strings = df[label_col].dtype == object
        many_items  = len(df) >= 5
        long_labels = has_strings and df[label_col].astype(str).str.len().mean() > 8
        if has_strings and (many_items or long_labels):
            chart_type = "horizontal_bar"
        else:
            chart_type = "bar"

    try:
        # ── Line ─────────────────────────────────────────────────────────────
        if chart_type == "line":
            cols = df.columns.tolist()
            # For line, x = first col (date/period), y = numeric
            x_col = label_col
            y_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]

            if len(y_cols) > 1:
                fig = px.line(
                    df, x=x_col, y=y_cols, title=title,
                    labels={x_col: x_label},
                    markers=True, color_discrete_sequence=PALETTE,
                )
            else:
                y_col_line = y_cols[0] if y_cols else cols[-1]
                fig = px.line(
                    df, x=x_col, y=y_col_line, title=title,
                    labels={x_col: x_label, y_col_line: y_label},
                    markers=True, color_discrete_sequence=PALETTE,
                )
                fig.update_traces(line=dict(width=2.5), marker=dict(size=7))
            fig.update_yaxes(rangemode="tozero")

        # ── Pie / donut ───────────────────────────────────────────────────────
        elif chart_type == "pie":
            fig = px.pie(
                df, names=label_col, values=value_col, title=title,
                color_discrete_sequence=PALETTE,
                hole=0.38,
            )
            fig.update_traces(
                textfont=dict(color="#e2e8f0"),
                marker=dict(line=dict(color="#0a0010", width=1.5)),
            )

        # ── Horizontal bar (rankings, top-N with string labels) ───────────────
        elif chart_type == "horizontal_bar":
            df_s = df.sort_values(value_col, ascending=True).reset_index(drop=True)
            colors = [PALETTE[i % len(PALETTE)] for i in range(len(df_s))]

            fig = go.Figure(go.Bar(
                x=df_s[value_col],
                y=df_s[label_col],
                orientation="h",
                marker=dict(color=colors, line=dict(width=0)),
                text=[_fmt(v) for v in df_s[value_col]],
                textposition="outside",
                textfont=dict(color="#c4b5fd", size=11),
            ))
            fig.update_layout(
                title=title,
                xaxis_title=y_label or value_col,
                yaxis_title="",
                showlegend=False,
                xaxis=dict(rangemode="tozero"),
                yaxis=dict(tickfont=dict(size=12), automargin=True),
            )

        # ── Vertical bar (small categorical sets, periods) ────────────────────
        else:
            colors = [PALETTE[i % len(PALETTE)] for i in range(len(df))]
            fig = go.Figure(go.Bar(
                x=df[label_col],
                y=df[value_col],
                marker=dict(color=colors, line=dict(width=0)),
                text=[_fmt(v) for v in df[value_col]],
                textposition="outside",
                textfont=dict(color="#c4b5fd", size=10),
            ))
            fig.update_layout(
                title=title,
                xaxis_title=x_label or label_col,
                yaxis_title=y_label or value_col,
                showlegend=False,
            )
            fig.update_yaxes(rangemode="tozero")

    except Exception:
        c0 = df.columns[0]
        c1 = df.columns[1] if len(df.columns) > 1 else c0
        fig = px.bar(df, x=c0, y=c1, title=title, color_discrete_sequence=PALETTE)

    return _apply_theme(fig)
