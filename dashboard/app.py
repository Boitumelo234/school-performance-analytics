"""Streamlit dashboard for South African matric performance analytics."""

import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")
API_BASE = os.getenv("API_BASE", "https://school-performance-api.onrender.com").rstrip("/")
GREEN, AMBER, SLATE = "#0B6E4F", "#F4A261", "#1F2933"
ALL_DISTRICTS = "All districts"
ALL_PROVINCES = "All provinces"
ALL_YEARS = "All years"

st.set_page_config(page_title="School Performance Analytics", page_icon="🎓", layout="wide")

st.markdown(
    f"""
    <style>
      .hero {{background: linear-gradient(120deg, {GREEN}, #159A72);
              padding: 1.6rem 2rem; border-radius: 16px; margin-bottom: 1.2rem;}}
      .hero, .hero * {{color: #FFFFFF !important;}}
      .hero h1 {{margin: 0; font-size: 2rem;}}
      .hero p {{margin: .4rem 0 0; opacity: .95;}}

      div[data-testid="stMetric"] {{
          background: #FFFFFF; border: 1px solid #D5E3DC; border-left: 6px solid {GREEN};
          border-radius: 12px; padding: .9rem 1.1rem;
          box-shadow: 0 1px 4px rgba(0,0,0,.06);}}
      div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] * {{
          color: #334155 !important; font-weight: 600;}}
      div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {{
          color: {GREEN} !important; font-weight: 800;}}

      .block-container {{padding-top: 2rem;}}
      .coverage {{background: #F5F9F7; border: 1px solid #D5E3DC;
                  border-radius: 10px; padding: .6rem 1rem; margin-bottom: .8rem;
                  font-size: .9rem; color: #334155;}}
    </style>
    <div class="hero">
      <h1>🎓 School Performance Analytics</h1>
      <p>DBE National Senior Certificate results: pass-rate trends by school, district, province and poverty quintile.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ data
@st.cache_data(ttl=300, show_spinner="⏳ Loading data from the API…")
def _fetch(path: str, params: dict):
    r = requests.get(f"{API_BASE}{path}", params=params, timeout=(5, 60))
    r.raise_for_status()
    return r.json()


def get(path: str, **params):
    clean = {k: v for k, v in params.items() if v is not None}
    try:
        return _fetch(path, clean)
    except requests.Timeout:
        st.error("⏱️ The API took too long to answer. It may still be busy.")
    except requests.ConnectionError:
        st.error(f"🔌 Cannot reach the API at {API_BASE}.")
        st.caption("Start it with: `uvicorn app.main:app --reload`")
    except requests.RequestException as exc:
        st.error(f"The API returned an error: {exc}")
    st.button("🔄 Try again")
    st.stop()


def frame(path: str, **params) -> pd.DataFrame:
    return pd.DataFrame(get(path, **params))


def show(fig, height: int = 420):
    fig.update_layout(
        template="plotly_white", height=height,
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(color=SLATE),
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=1.12, x=0),
    )
    st.plotly_chart(fig, use_container_width=True, theme=None)


def csv_download_button(label: str, **params):
    """Ask the API for a CSV and offer it as a download."""
    clean = {k: v for k, v in params.items() if v is not None}
    try:
        r = requests.get(f"{API_BASE}/api/v1/export/csv", params=clean, timeout=(5, 120))
        r.raise_for_status()
        st.download_button(label, r.content, file_name="school_performance.csv", mime="text/csv")
    except requests.RequestException:
        st.caption("CSV export unavailable right now.")


meta = get("/api/v1/meta")
if not meta["years"]:
    st.warning("The database is empty. Run `python -m scripts.transform` first.")
    st.stop()

coverage = get("/api/v1/data-coverage")
years_desc = meta["years"][::-1]
latest_year = years_desc[0]

# ------------------------------------------------------------ about data
src = coverage.get("source_reports") or []
exams = coverage.get("exam_years") or []
if exams:
    coverage_html = (
        f"<b>About this data:</b> "
        f"Exam years <b>{exams[0]}–{exams[-1]}</b> · "
        f"Source reports <b>{', '.join(str(s) for s in src) if src else 'unknown'}</b> · "
        f"<b>{coverage['total_schools']:,}</b> schools · "
        f"<b>{coverage['total_rows']:,}</b> school-year rows"
    )
    st.markdown(f'<div class="coverage">{coverage_html}</div>', unsafe_allow_html=True)

# --------------------------------------------------------------- filters
DEFAULTS = {
    "province": ALL_PROVINCES,
    "district": ALL_DISTRICTS,
    "quintile": None,
    "year": latest_year,
}

st.session_state.setdefault("applied", dict(DEFAULTS))
st.session_state.setdefault("w_province", DEFAULTS["province"])
st.session_state.setdefault("w_district", DEFAULTS["district"])
st.session_state.setdefault("w_quintile", DEFAULTS["quintile"])
st.session_state.setdefault("w_year", DEFAULTS["year"])


def apply_filters():
    st.session_state.applied = {
        "province": st.session_state.w_province,
        "district": st.session_state.w_district,
        "quintile": st.session_state.w_quintile,
        "year": st.session_state.w_year,
    }
    st.toast("Filters applied", icon="✅")


def reset_filters():
    st.session_state.w_province = DEFAULTS["province"]
    st.session_state.w_district = DEFAULTS["district"]
    st.session_state.w_quintile = DEFAULTS["quintile"]
    st.session_state.w_year = DEFAULTS["year"]
    st.session_state.applied = dict(DEFAULTS)
    st.toast("Filters reset", icon="↺")


st.sidebar.header("Filters")
st.sidebar.selectbox("Province", [ALL_PROVINCES] + meta["provinces"], key="w_province")
st.sidebar.selectbox("District", [ALL_DISTRICTS] + meta["districts"], key="w_district")
st.sidebar.selectbox(
    "Quintile", [None, 1, 2, 3, 4, 5], key="w_quintile",
    format_func=lambda q: "All quintiles" if q is None else f"Quintile {q}",
)
st.sidebar.selectbox("Year", [ALL_YEARS] + years_desc, key="w_year")
st.sidebar.button("✅ Apply filters", type="primary",
                  on_click=apply_filters, use_container_width=True)
st.sidebar.button("↺ Reset", on_click=reset_filters, use_container_width=True)
st.sidebar.caption("Choose your filters, then click **Apply filters**. "
                   "Quintile 1 = poorest schools, 5 = least poor.")
if exams:
    st.sidebar.caption(
        f"Data covers exam years **{exams[0]}–{exams[-1]}**, "
        f"from DBE reports **{', '.join(str(s) for s in src)}**."
    )

applied = st.session_state.applied
province = None if applied["province"] == ALL_PROVINCES else applied["province"]
district = None if applied["district"] == ALL_DISTRICTS else applied["district"]
quintile = applied["quintile"]
year_sel = None if applied["year"] == ALL_YEARS else applied["year"]
focus_year = year_sel or latest_year

active = []
if province:
    active.append(f"Province: **{province}**")
if district:
    active.append(f"District: **{district}**")
if quintile:
    active.append(f"Quintile: **{quintile}**")
if year_sel:
    active.append(f"Year: **{year_sel}**")
st.info("Filters applied → " + (" · ".join(active) if active else "none (showing everything)"))

# ------------------------------------------------------------------ KPIs
trends = frame("/api/v1/analytics/trends", district=district, province=province, quintile=quintile)
if trends.empty:
    st.warning("No data for this combination of filters. Try a different district or quintile, "
               "or click **Reset** in the sidebar.")
    st.stop()

match = trends.index[trends["exam_year"] == focus_year]
pos = trends.index.get_loc(match[0]) if len(match) else len(trends) - 1
current = trends.iloc[pos]
previous = trends.iloc[pos - 1] if pos > 0 else None
delta = None
if previous is not None:
    diff = current.weighted_pass_rate - previous.weighted_pass_rate
    delta = f"{diff:+.1f} pts vs {int(previous.exam_year)}"

k1, k2, k3, k4 = st.columns(4)
k1.metric(f"Pass rate {int(current.exam_year)}", f"{current.weighted_pass_rate:.1f}%", delta)
k2.metric("Learners who wrote", f"{int(current.total_wrote):,}")
k3.metric("Learners who passed", f"{int(current.total_achieved):,}")
k4.metric("Schools", f"{int(current.school_count):,}")

st.write("")

VIEWS = [
    "📈 Trends", "⚖️ Poverty gap", "🗺️ Districts", "🏛️ Provinces",
    "🚀 Most improved", "🔎 School explorer",
]
view = st.radio("View", VIEWS, horizontal=True, label_visibility="collapsed", key="view")
st.divider()

# ---------------------------------------------------------------- trends
if view == VIEWS[0]:
    st.caption("Uses filters: **Province**, **District**, **Quintile** (the Year filter marks the selected year).")
    long = trends.melt(id_vars="exam_year",
                       value_vars=["weighted_pass_rate", "avg_pass_rate"],
                       var_name="metric", value_name="pass_rate")
    long["metric"] = long["metric"].map({
        "weighted_pass_rate": "Learner-weighted", "avg_pass_rate": "Average of schools"})
    fig = px.line(long, x="exam_year", y="pass_rate", color="metric", markers=True,
                  color_discrete_sequence=[GREEN, AMBER],
                  labels={"exam_year": "Year", "pass_rate": "Pass rate (%)", "metric": ""},
                  title="Pass rate over time")
    fig.update_yaxes(range=[0, 100])
    fig.update_xaxes(dtick=1)
    if year_sel:
        fig.add_vline(x=year_sel, line_dash="dot", line_color="grey")
    show(fig)
    st.caption("Learner-weighted = total passed ÷ total wrote, so large schools count more.")
    csv_download_button("⬇️ Download filtered data (CSV)",
                        district=district, province=province, quintile=quintile)
    with st.expander("Show data"):
        st.dataframe(trends, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------- gap
elif view == VIEWS[1]:
    st.caption("Uses filters: **Province**, **District**, **Year**.")
    gaps = frame("/api/v1/analytics/quintile-gaps",
                 exam_year=year_sel, district=district, province=province)
    if gaps.empty:
        st.info("No quintile data for this selection.")
    else:
        gaps["label"] = "Q" + gaps["quintile"].astype(str)
        fig = px.bar(gaps, x="label", y="weighted_pass_rate", text="weighted_pass_rate",
                     color="weighted_pass_rate", color_continuous_scale="RdYlGn",
                     range_color=[0, 100],
                     labels={"label": "Poverty quintile (Q1 = poorest)",
                             "weighted_pass_rate": "Pass rate (%)"},
                     title="Pass rate by poverty quintile")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_yaxes(range=[0, 105])
        fig.update_coloraxes(showscale=False)
        show(fig)
        if len(gaps) >= 2:
            gap = gaps.iloc[-1].weighted_pass_rate - gaps.iloc[0].weighted_pass_rate
            st.success(f"Gap between Quintile {int(gaps.iloc[-1].quintile)} and "
                       f"Quintile {int(gaps.iloc[0].quintile)}: **{gap:.1f} percentage points**.")
        with st.expander("Show data"):
            st.dataframe(gaps.drop(columns="label"), use_container_width=True, hide_index=True)

# ------------------------------------------------------------- districts
elif view == VIEWS[2]:
    st.caption(f"Uses filters: **Province**, **Quintile**, **Year** (showing {focus_year}).")
    min_schools = st.slider("Minimum schools per district", 1, 30, 3)
    dist = frame("/api/v1/analytics/districts", exam_year=focus_year,
                 quintile=quintile, province=province, min_schools=min_schools)
    if dist.empty:
        st.info("No districts match. Try lowering the minimum number of schools.")
    else:
        if district:
            hit = dist.index[dist["district_name"] == district]
            if len(hit):
                st.success(f"**{district}** ranks **#{hit[0] + 1} of {len(dist)}** districts "
                           f"({dist.loc[hit[0], 'weighted_pass_rate']:.1f}%).")
            else:
                st.info(f"{district} has too few schools for this selection to be ranked.")
        n = min(10, len(dist))
        left, right = st.columns(2)
        for col, data, title, scale in [
            (left, dist.head(n), f"Top {n} districts", "Greens"),
            (right, dist.tail(n), f"Bottom {n} districts", "Oranges_r"),
        ]:
            fig = px.bar(data, x="weighted_pass_rate", y="district_name", orientation="h",
                         text="weighted_pass_rate", color="weighted_pass_rate",
                         color_continuous_scale=scale, title=title,
                         labels={"weighted_pass_rate": "Pass rate (%)", "district_name": ""})
            fig.update_traces(texttemplate="%{text:.1f}%")
            fig.update_layout(yaxis=dict(autorange="reversed"))
            fig.update_xaxes(range=[0, 100])
            fig.update_coloraxes(showscale=False)
            with col:
                show(fig, 440)
        with st.expander("All districts"):
            st.dataframe(dist, use_container_width=True, hide_index=True)

# ------------------------------------------------------------- provinces
elif view == VIEWS[3]:
    st.caption(f"Uses filters: **Quintile**, **Year** (showing {focus_year}).")
    prov = frame("/api/v1/analytics/provinces", exam_year=focus_year, quintile=quintile)
    if prov.empty:
        st.info("No province data for this selection.")
    else:
        if province:
            hit = prov.index[prov["province_name"] == province]
            if len(hit):
                st.success(f"**{province}** ranks **#{hit[0] + 1} of {len(prov)}** provinces "
                           f"({prov.loc[hit[0], 'weighted_pass_rate']:.1f}%).")
        fig = px.bar(prov, x="province_name", y="weighted_pass_rate", text="weighted_pass_rate",
                     color="weighted_pass_rate", color_continuous_scale="RdYlGn",
                     range_color=[0, 100],
                     labels={"province_name": "", "weighted_pass_rate": "Pass rate (%)"},
                     title=f"Pass rate by province ({focus_year})")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_yaxes(range=[0, 105])
        fig.update_coloraxes(showscale=False)
        show(fig)
        with st.expander("Show data"):
            st.dataframe(prov, use_container_width=True, hide_index=True)

# -------------------------------------------------------------- improved
elif view == VIEWS[4]:
    st.caption("Uses filters: **Province**, **District**, **Quintile**.")
    c1, c2 = st.columns(2)
    min_wrote = c1.slider("Minimum learners who wrote (per year)", 10, 200, 30, step=10)
    top_n = c2.slider("Schools to show", 5, 50, 15)
    imp = frame("/api/v1/analytics/improving-schools", min_wrote=min_wrote, limit=top_n,
                district=district, province=province, quintile=quintile)
    if imp.empty:
        st.info("No schools match these filters. Try lowering the minimum learners.")
    else:
        imp["label"] = (imp["centre_name"] + " (" + imp["first_year"].astype(str)
                        + "→" + imp["last_year"].astype(str) + ")")
        fig = px.bar(imp, x="improvement", y="label", orientation="h",
                     text="improvement", color="improvement",
                     color_continuous_scale="Greens",
                     labels={"improvement": "Improvement (percentage points)", "label": ""},
                     title=f"Top {len(imp)} schools by pass-rate improvement")
        fig.update_traces(texttemplate="%{text:+.1f}")
        fig.update_layout(yaxis=dict(autorange="reversed"))
        fig.update_coloraxes(showscale=False)
        show(fig, max(380, 30 * len(imp)))
        with st.expander("Show data"):
            st.dataframe(imp.drop(columns="label"), use_container_width=True, hide_index=True)

# -------------------------------------------------------------- explorer
else:
    st.caption(f"Uses filters: **Province**, **District**, **Quintile**, **Year** (searching {focus_year}).")
    term = st.text_input("Search for a school by name (optional if a filter is set)",
                         placeholder="e.g. Hoërskool")
    if term or district or quintile or province:
        found = get("/api/v1/schools", search=term or None, district=district,
                    province=province, quintile=quintile, exam_year=focus_year, page_size=50)
        results = found["results"]
        if not results:
            st.info("No schools found. Try a different spelling or relax the filters.")
        else:
            st.caption(f"{found['total']} match(es); showing up to {len(results)}.")
            options = {
                f'{r["centre_name"]} - {r["district_name"] or "unknown district"} ({r["emis_number"]})':
                r["emis_number"] for r in results
            }
            chosen = st.selectbox("Matching schools", list(options))
            school = get(f"/api/v1/schools/{options[chosen]}")
            hist = pd.DataFrame(school["history"])

            st.subheader(school["centre_name"])
            st.caption(f'{school["district_name"] or "Unknown district"} · '
                       f'Quintile {school["quintile"] or "unknown"} · EMIS {school["emis_number"]}')
            fig = px.line(hist, x="exam_year", y="pass_rate", markers=True,
                          color_discrete_sequence=[GREEN],
                          labels={"exam_year": "Year", "pass_rate": "Pass rate (%)"},
                          title="Pass rate history")
            fig.update_yaxes(range=[0, 100])
            fig.update_xaxes(dtick=1)
            show(fig, 340)
            st.dataframe(hist, use_container_width=True, hide_index=True)
    else:
        st.caption("Type part of a school name, or pick a filter in the sidebar and click Apply.")