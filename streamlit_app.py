"""
LGC Transfer Flow Dashboard
============================
Streamlit app that reads lgc_transfer_data.json and visualises
LGC transfers by holdings account, parent entity, and flow.

Deploy on Streamlit Cloud:
  1. Push this file + lgc_transfer_data.json to your GitHub repo
  2. Go to share.streamlit.io → connect your repo → set main file = streamlit_app.py
  3. Done — dashboard auto-refreshes when GitHub Actions commits new data daily

Requirements (add to requirements.txt):
  streamlit
  plotly
  pandas
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LGC Transfer Tracker",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Syne', sans-serif; }

  .main { background: #0d1117; }

  .metric-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 8px;
  }
  .metric-label {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.12em;
    color: #8b949e;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .metric-value {
    font-family: 'Syne', sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: #e6edf3;
    line-height: 1.1;
  }
  .metric-delta {
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    color: #3fb950;
    margin-top: 4px;
  }
  .section-header {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.15em;
    color: #8b949e;
    text-transform: uppercase;
    border-bottom: 1px solid #21262d;
    padding-bottom: 8px;
    margin: 24px 0 16px 0;
  }
  .stDataFrame { border: 1px solid #21262d; border-radius: 8px; }
  div[data-testid="stSidebar"] { background: #161b22; border-right: 1px solid #21262d; }
  .stSelectbox label, .stMultiSelect label, .stDateInput label { color: #8b949e; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data(path: str = "lgc_transfer_data.json") -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame()
    with open(path) as f:
        cache = json.load(f)
    records = [rec for recs in cache.values() for rec in recs]
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    df["volume_lgc"] = pd.to_numeric(df["volume_lgc"], errors="coerce").fillna(0)
    return df

df_all = load_data()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚡ LGC Tracker")
    st.markdown("---")

    if df_all.empty:
        st.warning("No data loaded yet. Run the daily tracker first.")
        st.stop()

    # Date range
    st.markdown("**Date range**")
    min_date = df_all["date"].min().date()
    max_date = df_all["date"].max().date()
    date_from = st.date_input("From", value=max_date - timedelta(days=90),
                               min_value=min_date, max_value=max_date)
    date_to   = st.date_input("To",   value=max_date,
                               min_value=min_date, max_value=max_date)

    st.markdown("**Parent entity**")
    all_entities = sorted(df_all["parent_entity"].dropna().unique())
    selected_entities = st.multiselect(
        "Filter by entity",
        options=all_entities,
        default=[],
        placeholder="All entities"
    )

    st.markdown("**Fuel source**")
    all_fuels = sorted(df_all["fuel_source"].dropna().unique())
    selected_fuels = st.multiselect(
        "Filter by fuel",
        options=all_fuels,
        default=[],
        placeholder="All fuel sources"
    )

    st.markdown("---")
    st.markdown(
        f"<span style='font-family:DM Mono,monospace;font-size:11px;color:#8b949e'>"
        f"Last data: {max_date}<br>Records: {len(df_all):,}</span>",
        unsafe_allow_html=True
    )

# ── Apply filters ─────────────────────────────────────────────────────────────
df = df_all[
    (df_all["date"].dt.date >= date_from) &
    (df_all["date"].dt.date <= date_to)
].copy()

if selected_entities:
    df = df[df["parent_entity"].isin(selected_entities)]
if selected_fuels:
    df = df[df["fuel_source"].isin(selected_fuels)]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## LGC Transfer Flow Tracker")
st.markdown(
    f"<span style='font-family:DM Mono,monospace;font-size:12px;color:#8b949e'>"
    f"CER REC Registry  ·  {date_from} → {date_to}  ·  "
    f"{len(df):,} transfers</span>",
    unsafe_allow_html=True
)
st.markdown("")

# ── KPI metrics ───────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

total_vol    = int(df["volume_lgc"].sum())
unique_accs  = df["owner_account"].nunique()
unique_ents  = df["parent_entity"].nunique()
top_entity   = df.groupby("parent_entity")["volume_lgc"].sum().idxmax() if not df.empty else "—"

with col1:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label">Total LGCs received</div>
        <div class="metric-value">{total_vol:,}</div>
        <div class="metric-delta">MWh equivalent</div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label">Unique accounts</div>
        <div class="metric-value">{unique_accs:,}</div>
        <div class="metric-delta">receiving transfers</div>
    </div>""", unsafe_allow_html=True)

with col3:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label">Parent entities</div>
        <div class="metric-value">{unique_ents:,}</div>
        <div class="metric-delta">identified</div>
    </div>""", unsafe_allow_html=True)

with col4:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label">Top entity</div>
        <div class="metric-value" style="font-size:16px;padding-top:4px">{top_entity}</div>
        <div class="metric-delta">by volume received</div>
    </div>""", unsafe_allow_html=True)

# ── Plotly theme ──────────────────────────────────────────────────────────────
PLOT_BG    = "#0d1117"
PAPER_BG   = "#0d1117"
GRID_COLOR = "#21262d"
TEXT_COLOR = "#8b949e"
FONT_FAMILY = "Syne, sans-serif"

base_layout = dict(
    paper_bgcolor=PAPER_BG,
    plot_bgcolor=PLOT_BG,
    font=dict(family=FONT_FAMILY, color=TEXT_COLOR, size=12),
    margin=dict(l=16, r=16, t=32, b=16),
    xaxis=dict(gridcolor=GRID_COLOR, linecolor=GRID_COLOR, tickcolor=GRID_COLOR),
    yaxis=dict(gridcolor=GRID_COLOR, linecolor=GRID_COLOR, tickcolor=GRID_COLOR),
)

GREEN_PALETTE = [
    "#3fb950", "#2ea043", "#1a7f37", "#116329",
    "#0d4a1f", "#238636", "#56d364", "#7ee787"
]

# ── Chart 1: Sankey flow diagram ──────────────────────────────────────────────
st.markdown('<div class="section-header">Certificate flow — account to account</div>',
            unsafe_allow_html=True)

if df.empty:
    st.info("No data for selected filters.")
else:
    # Build Sankey: accreditation_code → owner_account (top 30 by volume)
    sankey_df = (
        df.groupby(["accreditation", "owner_account"])["volume_lgc"]
        .sum()
        .reset_index()
        .sort_values("volume_lgc", ascending=False)
        .head(40)
    )

    # Replace empty accreditation codes
    sankey_df["accreditation"] = sankey_df["accreditation"].replace("", "Unknown source")
    sankey_df = sankey_df[sankey_df["volume_lgc"] > 0]

    if not sankey_df.empty:
        all_nodes   = list(pd.unique(sankey_df[["accreditation", "owner_account"]].values.ravel()))
        node_index  = {n: i for i, n in enumerate(all_nodes)}
        sources     = sankey_df["accreditation"].map(node_index).tolist()
        targets     = sankey_df["owner_account"].map(node_index).tolist()
        values      = sankey_df["volume_lgc"].tolist()

        n = len(all_nodes)
        node_colors = []
        src_set = set(sankey_df["accreditation"])
        for node in all_nodes:
            if node in src_set:
                node_colors.append("rgba(63,185,80,0.85)")
            else:
                node_colors.append("rgba(56,139,253,0.85)")

        fig_sankey = go.Figure(go.Sankey(
            arrangement="snap",
            node=dict(
                pad=18,
                thickness=16,
                line=dict(color="#21262d", width=0.5),
                label=all_nodes,
                color=node_colors,
                hovertemplate="%{label}<br>Volume: %{value:,} LGCs<extra></extra>",
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color="rgba(63,185,80,0.18)",
                hovertemplate="%{source.label} → %{target.label}<br>%{value:,} LGCs<extra></extra>",
            ),
        ))
        fig_sankey.update_layout(
            **base_layout,
            height=500,
            margin=dict(l=16, r=16, t=16, b=16),
        )
        st.plotly_chart(fig_sankey, use_container_width=True)
    else:
        st.info("Not enough flow data to build Sankey.")

# ── Charts 2 + 3 side by side ─────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.markdown('<div class="section-header">Top receiving accounts</div>',
                unsafe_allow_html=True)

    top_n = (
        df.groupby(["owner_account", "parent_entity"])["volume_lgc"]
        .sum()
        .reset_index()
        .sort_values("volume_lgc", ascending=False)
        .head(15)
    )
    top_n["label"] = top_n["owner_account"].str[:30]

    fig_bar = go.Figure(go.Bar(
        x=top_n["volume_lgc"],
        y=top_n["label"],
        orientation="h",
        marker=dict(
            color=top_n["volume_lgc"],
            colorscale=[[0, "#0d4a1f"], [0.5, "#2ea043"], [1, "#7ee787"]],
            showscale=False,
        ),
        text=top_n["parent_entity"].str[:25],
        textposition="inside",
        textfont=dict(size=10, color="#0d1117"),
        hovertemplate="<b>%{y}</b><br>%{x:,} LGCs<br>Entity: %{text}<extra></extra>",
    ))
    fig_bar.update_layout(
        **base_layout,
        height=420,
        yaxis=dict(autorange="reversed", gridcolor=GRID_COLOR,
                   tickfont=dict(size=11)),
        xaxis=dict(gridcolor=GRID_COLOR, tickformat=","),
        bargap=0.3,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_right:
    st.markdown('<div class="section-header">Monthly volume trend</div>',
                unsafe_allow_html=True)

    monthly = (
        df.groupby("month")["volume_lgc"]
        .sum()
        .reset_index()
        .sort_values("month")
    )

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=monthly["month"],
        y=monthly["volume_lgc"],
        mode="lines+markers",
        line=dict(color="#3fb950", width=2.5),
        marker=dict(color="#3fb950", size=6,
                    line=dict(color="#0d1117", width=1.5)),
        fill="tozeroy",
        fillcolor="rgba(63,185,80,0.08)",
        hovertemplate="%{x|%b %Y}<br><b>%{y:,} LGCs</b><extra></extra>",
    ))

    # Rolling average
    if len(monthly) >= 3:
        monthly["rolling"] = monthly["volume_lgc"].rolling(3, center=True).mean()
        fig_line.add_trace(go.Scatter(
            x=monthly["month"],
            y=monthly["rolling"],
            mode="lines",
            line=dict(color="#56d364", width=1.5, dash="dot"),
            name="3-month avg",
            hovertemplate="%{x|%b %Y}<br>3-month avg: %{y:,.0f}<extra></extra>",
        ))

    fig_line.update_layout(
        **base_layout,
        height=420,
        showlegend=True,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=TEXT_COLOR),
            x=0.01, y=0.99,
        ),
        yaxis=dict(gridcolor=GRID_COLOR, tickformat=","),
        xaxis=dict(gridcolor=GRID_COLOR),
    )
    st.plotly_chart(fig_line, use_container_width=True)

# ── Chart 4: Raw transfers table ──────────────────────────────────────────────
st.markdown('<div class="section-header">Raw transfer log</div>',
            unsafe_allow_html=True)

show_cols = ["date", "owner_account", "parent_entity",
             "fuel_source", "generation_state", "generation_year",
             "volume_lgc", "accreditation", "status"]

display_df = (
    df[show_cols]
    .sort_values("date", ascending=False)
    .rename(columns={
        "date":             "Date",
        "owner_account":    "Registry Account",
        "parent_entity":    "Parent Entity",
        "fuel_source":      "Fuel Source",
        "generation_state": "State",
        "generation_year":  "Gen Year",
        "volume_lgc":       "Volume (LGCs)",
        "accreditation":    "Accreditation",
        "status":           "Status",
    })
)
display_df["Volume (LGCs)"] = display_df["Volume (LGCs)"].apply(lambda x: f"{int(x):,}")
display_df["Date"] = display_df["Date"].dt.strftime("%d %b %Y")

st.dataframe(
    display_df,
    use_container_width=True,
    height=380,
    hide_index=True,
)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<span style='font-family:DM Mono,monospace;font-size:11px;color:#8b949e'>"
    "Source: CER REC Registry Public API  ·  Updated daily via GitHub Actions  ·  "
    "LGC = Large-scale Generation Certificate  ·  1 LGC = 1 MWh renewable generation"
    "</span>",
    unsafe_allow_html=True,
)
