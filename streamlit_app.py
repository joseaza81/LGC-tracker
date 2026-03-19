import os, json
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="LGC Transfer Tracker", page_icon="⚡", layout="wide")

HERE = Path(__file__).parent
DATA = HERE / "lgc_transfer_data.json"

st.write(str(DATA))
st.write(DATA.exists())

if not DATA.exists():
    st.error(f"Cannot find data file at: {DATA}")
    st.stop()

with open(DATA) as f:
    raw = json.load(f)

records = [r for recs in raw.values() for r in recs]

if not records:
    st.warning("Data file is empty. Run the daily tracker first.")
    st.stop()

df = pd.DataFrame(records)
df["date"] = pd.to_datetime(df["date"])
df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
df["volume_lgc"] = pd.to_numeric(df["volume_lgc"], errors="coerce").fillna(0)

st.sidebar.markdown("### ⚡ LGC Tracker")
st.sidebar.markdown("---")

min_d, max_d = df["date"].min().date(), df["date"].max().date()
d_from = st.sidebar.date_input("From", value=max_d - timedelta(days=90), min_value=min_d, max_value=max_d)
d_to   = st.sidebar.date_input("To",   value=max_d, min_value=min_d, max_value=max_d)

entities = sorted(df["parent_entity"].dropna().unique())
sel_ent  = st.sidebar.multiselect("Parent entity", entities, placeholder="All entities")

fuels    = sorted(df["fuel_source"].dropna().unique())
sel_fuel = st.sidebar.multiselect("Fuel source", fuels, placeholder="All fuel sources")

st.sidebar.markdown(f"Last data: `{max_d}`  \nRecords: `{len(df):,}`")

mask = (df["date"].dt.date >= d_from) & (df["date"].dt.date <= d_to)
if sel_ent:  mask &= df["parent_entity"].isin(sel_ent)
if sel_fuel: mask &= df["fuel_source"].isin(sel_fuel)
dff = df[mask].copy()

st.title("⚡ LGC Transfer Flow Tracker")
st.caption(f"CER REC Registry  ·  {d_from} → {d_to}  ·  {len(dff):,} transfers")

if dff.empty:
    st.info("No transfers match the selected filters.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total LGCs", f"{int(dff['volume_lgc'].sum()):,}")
c2.metric("Unique accounts", dff["owner_account"].nunique())
c3.metric("Parent entities", dff["parent_entity"].nunique())
top = dff.groupby("parent_entity")["volume_lgc"].sum().idxmax()
c4.metric("Top entity", top)

st.divider()

st.subheader("Certificate flow — accreditation to account")
sdf = (dff.groupby(["accreditation","owner_account"])["volume_lgc"]
         .sum().reset_index()
         .sort_values("volume_lgc", ascending=False).head(40))
sdf["accreditation"] = sdf["accreditation"].replace("","Unknown source")
sdf = sdf[sdf["volume_lgc"] > 0]

if not sdf.empty:
    nodes   = list(pd.unique(sdf[["accreditation","owner_account"]].values.ravel()))
    idx     = {n:i for i,n in enumerate(nodes)}
    src_set = set(sdf["accreditation"])
    colors  = ["rgba(63,185,80,0.85)" if n in src_set else "rgba(56,139,253,0.85)" for n in nodes]
    fig = go.Figure(go.Sankey(
        node=dict(pad=15, thickness=15, label=nodes, color=colors,
                  hovertemplate="%{label}<br>%{value:,} LGCs<extra></extra>"),
        link=dict(source=sdf["accreditation"].map(idx).tolist(),
                  target=sdf["owner_account"].map(idx).tolist(),
                  value=sdf["volume_lgc"].tolist(),
                  color="rgba(63,185,80,0.15)",
                  hovertemplate="%{source.label} → %{target.label}<br>%{value:,} LGCs<extra></extra>")
    ))
    fig.update_layout(height=480, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

col_l, col_r = st.columns(2)

with col_l:
    st.subheader("Top receiving accounts")
    top15 = (dff.groupby(["owner_account","parent_entity"])["volume_lgc"]
               .sum().reset_index()
               .sort_values("volume_lgc", ascending=False).head(15))
    fig2 = go.Figure(go.Bar(
        x=top15["volume_lgc"], y=top15["owner_account"].str[:30],
        orientation="h",
        marker=dict(color=top15["volume_lgc"],
                    colorscale=[[0,"#0d4a1f"],[0.5,"#2ea043"],[1,"#7ee787"]]),
        text=top15["parent_entity"].str[:22], textposition="inside",
        hovertemplate="<b>%{y}</b><br>%{x:,} LGCs<extra></extra>",
    ))
    fig2.update_layout(height=400, yaxis=dict(autorange="reversed"),
                       margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig2, use_container_width=True)

with col_r:
    st.subheader("Monthly volume trend")
    mon = (dff.groupby("month")["volume_lgc"].sum().reset_index().sort_values("month"))
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=mon["month"], y=mon["volume_lgc"],
        mode="lines+markers", name="Monthly",
        line=dict(color="#3fb950", width=2),
        fill="tozeroy", fillcolor="rgba(63,185,80,0.08)"))
    if len(mon) >= 3:
        mon["roll"] = mon["volume_lgc"].rolling(3, center=True).mean()
        fig3.add_trace(go.Scatter(x=mon["month"], y=mon["roll"],
            mode="lines", name="3-month avg",
            line=dict(color="#56d364", width=1.5, dash="dot")))
    fig3.update_layout(height=400, margin=dict(l=10,r=10,t=10,b=10),
                       legend=dict(x=0.01,y=0.99))
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

st.subheader("Raw transfer log")
show = dff[["date","owner_account","parent_entity","fuel_source",
            "generation_state","generation_year","volume_lgc","accreditation","status"]].copy()
show = show.sort_values("date", ascending=False)
show["date"] = show["date"].dt.strftime("%d %b %Y")
show["volume_lgc"] = show["volume_lgc"].apply(lambda x: f"{int(x):,}")
show.columns = ["Date","Account","Parent Entity","Fuel","State","Gen Year","Volume (LGCs)","Accreditation","Status"]
st.dataframe(show, use_container_width=True, hide_index=True, height=350)

st.caption("Source: CER REC Registry Public API · Updated daily via GitHub Actions · 1 LGC = 1 MWh renewable generation")
