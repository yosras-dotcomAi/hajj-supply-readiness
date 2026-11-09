"""
Access-site infection after cardiac catheterisation: STEMI vs elective PCI
Interactive Streamlit dashboard.

All data are SIMULATED (see generate_data.py). No real patient or hospital data.
Run:  streamlit run app.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

# ------------------------------------------------------------------ setup
st.set_page_config(page_title="Cath Lab Access-Site Infection", page_icon="🫀", layout="wide")

DATA = Path(__file__).parent / "data"
BLUE, LIGHT, AMBER, RED, GREY, GREEN = "#3B8FD9", "#80C8FF", "#F2B84B", "#E5636D", "#7F93A8", "#4CB782"
CASE_ORDER = ["Elective", "NSTEMI", "STEMI"]
CASE_COLOR = {"Elective": LIGHT, "NSTEMI": AMBER, "STEMI": RED}
OUTCOMES = {"Suspected infection": "suspected_infection_30d", "Confirmed infection": "confirmed_infection_30d"}

st.markdown(
    """
<style>
.block-container{padding-top:1.4rem;max-width:1280px}
.hero h1{font-size:2.0rem;margin:0 0 .2rem 0;color:inherit}
.hero p{color:inherit;opacity:.75;margin:0 0 .8rem 0;font-size:1.02rem}
.sim{background:#16263d;border:1px solid #2F4A6D;border-left:4px solid #F2B84B;color:#E6EEF7;border-radius:8px;padding:10px 14px;font-size:.92rem;margin-bottom:1rem}
.kpi{background:#121C2E;border:1px solid #1F3250;border-radius:12px;padding:14px 16px;height:100%}
.kpi .v{font-size:1.85rem;font-weight:700;color:#fff;line-height:1.15}
.kpi .l{color:#C9DCF0;font-size:.85rem;margin-top:2px}
.kpi .s{color:#6F8CAB;font-size:.76rem;margin-top:2px}
.answer{background:#0F2238;border-left:4px solid #3B8FD9;border-radius:8px;padding:14px 18px;margin:.6rem 0 1rem 0;color:#E6EEF7}
.answer h4{margin:0 0 .4rem 0;color:#fff}
.answer b{color:#fff}
.answer .note{color:#9FB6CF}
.note{color:#7F93A8;font-size:.85rem}
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ statistics
def exact_ci(k, n, alpha=0.05):
    """Exact (Clopper-Pearson) CI for a proportion, returned per 1,000."""
    if n == 0:
        return np.nan, np.nan
    lo = 0.0 if k == 0 else stats.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return lo * 1000, hi * 1000


def rate_row(k, n):
    lo, hi = exact_ci(k, n)
    return {"n": int(n), "events": int(k), "rate": (k / n * 1000) if n else np.nan, "lo": lo, "hi": hi}


def rate_by(df, col, outcome, order=None):
    rows = []
    for level, g in df.groupby(col, observed=True):
        rows.append({"group": level, **rate_row(g[outcome].sum(), len(g))})
    out = pd.DataFrame(rows)
    if order is not None and not out.empty:
        out["group"] = pd.Categorical(out["group"], order, ordered=True)
        out = out.sort_values("group")
    return out


def rate_ratio(a, n1, b, n2):
    """Rate (risk) ratio a/n1 vs b/n2 with 95% log-method CI and Fisher exact p."""
    p = stats.fisher_exact([[a, n1 - a], [b, n2 - b]])[1]
    if a == 0 or b == 0:
        return np.nan, np.nan, np.nan, p
    rr = (a / n1) / (b / n2)
    se = np.sqrt(1 / a - 1 / n1 + 1 / b - 1 / n2)
    return rr, np.exp(np.log(rr) - 1.96 * se), np.exp(np.log(rr) + 1.96 * se), p


def fmt_rate(r):
    return f"{r['rate']:.1f} ({r['lo']:.1f} to {r['hi']:.1f})"


# ------------------------------------------------------------------ data
@st.cache_data
def load():
    proc = pd.read_csv(DATA / "procedures.csv", parse_dates=["procedure_date"])
    ops = pd.read_csv(DATA / "operators.csv")
    ev = pd.read_csv(DATA / "infection_events.csv")
    proc = proc.merge(ops, on="operator_id", how="left")
    proc["month"] = proc["procedure_date"].dt.to_period("M").dt.to_timestamp()
    proc["timing"] = np.where(proc["out_of_hours"] == 1, "Out of hours", "In hours")
    return proc, ev


proc_all, events_all = load()


def kpi(col, value, label, sub=""):
    col.markdown(f'<div class="kpi"><div class="v">{value}</div><div class="l">{label}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


def style(fig, h=380, legend=True):
    fig.update_layout(
        height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=50, b=70 if legend else 10), showlegend=legend, font=dict(size=13),
        legend=dict(orientation="h", y=-0.18, x=0, yanchor="top"),
    )
    fig.update_xaxes(gridcolor="rgba(127,127,127,0.25)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(127,127,127,0.25)", zeroline=False)
    return fig


def err_bar(fig, df, **kw):
    fig.add_trace(go.Bar(
        x=df["group"], y=df["rate"], error_y=dict(type="data", symmetric=False, array=df["hi"] - df["rate"], arrayminus=df["rate"] - df["lo"], color="#8DA3BA"),
        text=[f"{v:.1f}" for v in df["rate"]], textposition="outside", cliponaxis=False, **kw))
    return fig


# ------------------------------------------------------------------ sidebar
st.sidebar.markdown("## Controls")
outcome_label = st.sidebar.radio("Outcome level", list(OUTCOMES), help="Suspected = clinical signs prompting review. Confirmed = deep/bloodstream or culture-positive.")
OUT = OUTCOMES[outcome_label]
case_sel = st.sidebar.multiselect("Case type", CASE_ORDER, default=CASE_ORDER)
access_sel = st.sidebar.multiselect("Access route", ["Radial", "Femoral"], default=["Radial", "Femoral"])
dmin, dmax = proc_all["procedure_date"].min().date(), proc_all["procedure_date"].max().date()
dr = st.sidebar.date_input("Procedure dates", (dmin, dmax), min_value=dmin, max_value=dmax)
d0, d1 = (dr if isinstance(dr, tuple) and len(dr) == 2 else (dmin, dmax))

view = proc_all[
    proc_all["case_type"].isin(case_sel) & proc_all["access_site"].isin(access_sel)
    & (proc_all["procedure_date"].dt.date >= d0) & (proc_all["procedure_date"].dt.date <= d1)
]
st.sidebar.markdown(f"**{len(view):,}** of {len(proc_all):,} procedures selected")
st.sidebar.caption("Filters apply to every tab except the STEMI vs elective comparison, which always uses all procedures so it matches the README.")

# ------------------------------------------------------------------ header
st.markdown(
    '<div class="hero"><h1>🫀 Access-Site Infection After Cardiac Catheterisation</h1>'
    "<p>STEMI vs elective PCI: infection rates, risk factors and the infection-control steps behind them</p></div>",
    unsafe_allow_html=True,
)
st.markdown('<div class="sim"><b>Simulated data.</b> This dashboard uses no patient or hospital data. The dataset is built to resemble UK cardiac audit structure, and the extra risk for STEMI cases is an assumption. Results show how the analysis works, not what a real cath lab achieves.</div>', unsafe_allow_html=True)

t1, t2, t3, t4, t5, t6, t7 = st.tabs([
    "🎯 Overview", "⚖️ STEMI vs elective", "🧩 Risk factors", "🧼 Infection-control steps",
    "📈 Control chart", "🦠 Infection events", "📚 Sources & method",
])

# ================================================================== TAB 1
with t1:
    if view.empty:
        st.info("No procedures match the filters.")
    else:
        n = len(view)
        s = rate_row(view["suspected_infection_30d"].sum(), n)
        c = rate_row(view["confirmed_infection_30d"].sum(), n)
        cols = st.columns(5)
        kpi(cols[0], f"{n:,}", "PCI procedures", f"{d0:%b %Y} to {d1:%b %Y}")
        kpi(cols[1], f"{s['rate']:.1f}", "Suspected per 1,000", f"{s['events']} cases · 95% CI {s['lo']:.1f} to {s['hi']:.1f}")
        kpi(cols[2], f"{c['rate']:.1f}", "Confirmed per 1,000", f"{c['events']} cases · 95% CI {c['lo']:.1f} to {c['hi']:.1f}")
        kpi(cols[3], f"{(view['access_site'] == 'Radial').mean() * 100:.0f}%", "Radial access", "rest femoral")
        kpi(cols[4], f"{view['skin_prep_complete'].mean() * 100:.1f}%", "Complete skin preparation", "process measure")

    # The project question, always answered on all procedures
    a = proc_all
    el, st_ = a[a.case_type == "Elective"], a[a.case_type == "STEMI"]
    lines = []
    for lab, col in OUTCOMES.items():
        k1, k0 = st_[col].sum(), el[col].sum()
        rr, lo, hi, p = rate_ratio(k1, len(st_), k0, len(el))
        r1, r0 = rate_row(k1, len(st_)), rate_row(k0, len(el))
        if p < 0.05:
            verdict = "a statistically significant difference"
        else:
            verdict = f"<b>not</b> statistically significant (only {k1} vs {k0} events, so chance cannot be ruled out)"
        lines.append(f"<b>{lab}:</b> STEMI {r1['rate']:.1f} vs elective {r0['rate']:.1f} per 1,000. Rate ratio {rr:.2f} (95% CI {lo:.2f} to {hi:.2f}), Fisher p = {p:.3f}, {verdict}.")
    st.markdown(
        '<div class="answer"><h4>The project question: do STEMI patients have a higher 30-day access-site infection rate than elective patients?</h4>'
        + "<br>".join(lines)
        + '<br><span class="note">Based on all procedures. This gap is partly built into the simulation (STEMI cases were given higher infection odds, more femoral access and less complete skin preparation), so it demonstrates the method, not a real finding.</span></div>',
        unsafe_allow_html=True,
    )

    if not view.empty:
        left, right = st.columns(2)
        with left:
            df = rate_by(view, "case_type", OUT, CASE_ORDER)
            fig = go.Figure()
            fig = err_bar(fig, df, marker_color=[CASE_COLOR[g] for g in df["group"]], showlegend=False)
            fig.update_layout(title=f"{outcome_label} per 1,000 procedures (exact 95% CI)", yaxis_title="Per 1,000")
            st.plotly_chart(style(fig, 380, False), width="stretch")
        with right:
            vol = view.groupby(["month", "case_type"], observed=True).size().reset_index(name="n")
            fig = go.Figure()
            for ct in CASE_ORDER:
                d = vol[vol.case_type == ct]
                fig.add_trace(go.Bar(x=d["month"], y=d["n"], name=ct, marker_color=CASE_COLOR[ct]))
            fig.update_layout(barmode="stack", title="Procedure volume by month", yaxis_title="Procedures")
            st.plotly_chart(style(fig, 380), width="stretch")

# ================================================================== TAB 2
with t2:
    st.markdown("#### STEMI vs elective PCI (all procedures)")
    rows = []
    for lab, g in [("Elective", el), ("NSTEMI", a[a.case_type == "NSTEMI"]), ("STEMI", st_), ("All procedures", a)]:
        sr, cr = rate_row(g["suspected_infection_30d"].sum(), len(g)), rate_row(g["confirmed_infection_30d"].sum(), len(g))
        rows.append({"Group": lab, "Procedures": len(g), "Suspected cases": sr["events"], "Suspected per 1,000 (95% CI)": fmt_rate(sr),
                     "Confirmed cases": cr["events"], "Confirmed per 1,000 (95% CI)": fmt_rate(cr)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    left, right = st.columns([3, 2])
    with left:
        fig = go.Figure()
        for lab, col, colr in [("Suspected", "suspected_infection_30d", BLUE), ("Confirmed", "confirmed_infection_30d", RED)]:
            d = rate_by(a, "case_type", col, CASE_ORDER)
            fig = err_bar(fig, d, name=lab, marker_color=colr)
        fig.update_layout(barmode="group", title="Rate per 1,000 by case type (exact 95% CI)", yaxis_title="Per 1,000")
        st.plotly_chart(style(fig, 400), width="stretch")
    with right:
        st.markdown("**STEMI vs elective (Fisher's exact test)**")
        for lab, col in OUTCOMES.items():
            k1, k0 = st_[col].sum(), el[col].sum()
            rr, lo, hi, p = rate_ratio(k1, len(st_), k0, len(el))
            badge = "🟢 significant" if p < 0.05 else "⚪ not significant"
            st.markdown(f"**{lab}**: rate ratio **{rr:.2f}** (95% CI {lo:.2f} to {hi:.2f}), p = {p:.3f} · {badge}  \n<span class='note'>{k1} events in {len(st_)} STEMI vs {k0} in {len(el)} elective</span>", unsafe_allow_html=True)
        st.markdown("<span class='note'>With so few events, wide confidence intervals are expected. A p-value above 0.05 means the data cannot separate the difference from chance, not that there is no difference.</span>", unsafe_allow_html=True)

    st.markdown("#### Why the groups differ: case mix and process")
    mix = a.groupby("case_type", observed=True).agg(
        Procedures=("procedure_id", "count"),
        **{"Femoral access %": ("access_site", lambda x: (x == "Femoral").mean() * 100)},
        **{"Skin prep incomplete %": ("skin_prep_complete", lambda x: (x == 0).mean() * 100)},
        **{"Out of hours %": ("out_of_hours", lambda x: x.mean() * 100)},
        **{"Mechanical support %": ("mechanical_support", lambda x: x.mean() * 100)},
        **{"Diabetes %": ("diabetes", lambda x: x.mean() * 100)},
        **{"Mean age": ("age", "mean")},
    ).reindex(CASE_ORDER).round(1)
    st.dataframe(mix, width="stretch")
    st.caption("STEMI cases use femoral access more, skip complete skin preparation more often and run out of hours more. These differences are part of why their infection rate is higher in this simulation.")

# ================================================================== TAB 3
with t3:
    st.markdown(f"#### {outcome_label} by risk factor (per 1,000, exact 95% CI)")
    if view.empty:
        st.info("No procedures match the filters.")
    else:
        d = view
        defs = [
            ("Skin preparation", [("Complete", d.skin_prep_complete == 1), ("Incomplete", d.skin_prep_complete == 0)]),
            ("Access route", [("Radial", d.access_site == "Radial"), ("Femoral", d.access_site == "Femoral")]),
            ("Haemostasis", [("Radial band", d.haemostasis_method == "Radial band"), ("Closure device", d.haemostasis_method == "Closure device"), ("Manual compression", d.haemostasis_method == "Manual compression")]),
            ("Timing", [("In hours", d.out_of_hours == 0), ("Out of hours", d.out_of_hours == 1)]),
            ("Diabetes", [("No", d.diabetes == 0), ("Yes", d.diabetes == 1)]),
            ("Mechanical support", [("No", d.mechanical_support == 0), ("Yes", d.mechanical_support == 1)]),
            ("BMI", [("Under 35", d.bmi < 35), ("35 or more", d.bmi >= 35)]),
            ("Age", [("Under 75", d.age < 75), ("75 or more", d.age >= 75)]),
            ("Kidney disease", [("No", d.ckd == 0), ("Yes", d.ckd == 1)]),
        ]
        rows = []
        for factor, levels in defs:
            for lvl, m in levels:
                g = d[m]
                if len(g):
                    rows.append({"Factor": factor, "Level": lvl, **rate_row(g[OUT].sum(), len(g))})
        rf = pd.DataFrame(rows)
        rf["label"] = rf["Factor"] + ": " + rf["Level"]
        rf = rf.iloc[::-1]
        thin = rf["events"] < 5
        fig = go.Figure(go.Scatter(
            x=rf["rate"], y=rf["label"], mode="markers",
            marker=dict(size=11, color=np.where(thin, GREY, BLUE), line=dict(width=1, color="#fff")),
            error_x=dict(type="data", symmetric=False, array=rf["hi"] - rf["rate"], arrayminus=rf["rate"] - rf["lo"], color="#8DA3BA", thickness=1.6),
            customdata=np.c_[rf["events"], rf["n"]],
            hovertemplate="%{y}<br>%{x:.1f} per 1,000<br>%{customdata[0]} events in %{customdata[1]} procedures<extra></extra>"))
        fig.update_layout(xaxis_title="Per 1,000 procedures", title="Grey dots: fewer than 5 events, so the estimate is very imprecise")
        st.plotly_chart(style(fig, 560, False), width="stretch")
        show = rf.iloc[::-1][["Factor", "Level", "n", "events", "rate", "lo", "hi"]].rename(columns={"n": "Procedures", "events": "Events", "rate": "Per 1,000", "lo": "CI low", "hi": "CI high"})
        with st.expander("Show the table"):
            st.dataframe(show.round(1), hide_index=True, width="stretch")
        st.caption("Femoral groups have higher rates than radial, and incomplete skin preparation has a higher rate than complete preparation. Intervals overlap for out-of-hours and diabetes, so those differences are small. These patterns partly reflect the assumptions used to create the data.")

        with st.expander("Operators and cath lab rooms (interpret with caution)"):
            c1, c2 = st.columns(2)
            for col, grp, title in [(c1, "operator_id", "By operator"), (c2, "lab_room", "By cath lab room")]:
                dd = rate_by(view, grp, OUT)
                fig = go.Figure()
                fig = err_bar(fig, dd, marker_color=BLUE, showlegend=False)
                fig.update_layout(title=title, yaxis_title="Per 1,000")
                col.plotly_chart(style(fig, 320, False), width="stretch")
            st.info("Operator and room comparisons are not reliable at this event count. Intervals are wide and overlap. They are shown for completeness, not for ranking people.")

# ================================================================== TAB 4
with t4:
    st.markdown("#### The infection-control steps, one at a time")
    st.caption("Each step is a thing the team controls. The cards show how often the step is completed and the infection rate when it is done or missed.")
    if view.empty:
        st.info("No procedures match the filters.")
    else:
        d = view
        steps = [
            ("1. Complete skin preparation", d.skin_prep_complete == 1, "Done", "Missed"),
            ("2. Radial access chosen", d.access_site == "Radial", "Radial", "Femoral"),
            ("3. Sheath out within 2 hours", d.sheath_dwell_hours <= 2, "Within 2 h", "Over 2 h"),
        ]
        cols = st.columns(3)
        for col, (title, mask, yes, no) in zip(cols, steps):
            ry, rn = rate_row(d.loc[mask, OUT].sum(), mask.sum()), rate_row(d.loc[~mask, OUT].sum(), (~mask).sum())
            comp = mask.mean() * 100
            sub = (f"{yes}: {ry['rate']:.1f} per 1,000 ({ry['events']} cases)<br>{no}: "
                   + (f"{rn['rate']:.1f} per 1,000 ({rn['events']} cases)" if rn["n"] else "no procedures"))
            kpi(col, f"{comp:.1f}%", title, sub)

        st.markdown("&nbsp;")
        left, right = st.columns(2)
        with left:
            comp = d.groupby("case_type", observed=True).agg(
                **{"Skin prep complete": ("skin_prep_complete", "mean")},
                **{"Radial access": ("access_site", lambda x: (x == "Radial").mean())},
                **{"Sheath out within 2 h": ("sheath_dwell_hours", lambda x: (x <= 2).mean())},
            ).reindex([c for c in CASE_ORDER if c in d.case_type.unique()]) * 100
            fig = go.Figure(go.Heatmap(z=comp.values, x=comp.columns, y=comp.index, colorscale="Blues", zmin=60, zmax=100,
                                       text=np.round(comp.values, 1), texttemplate="%{text}%", showscale=False))
            fig.update_layout(title="Step completion by case type")
            st.plotly_chart(style(fig, 330, False), width="stretch")
        with right:
            prep = d.groupby(["case_type", "timing"], observed=True)["skin_prep_complete"].mean().mul(100).unstack()
            prep = prep.reindex([c for c in CASE_ORDER if c in prep.index])
            fig = go.Figure(go.Heatmap(z=prep.values, x=prep.columns, y=prep.index, colorscale="Blues", zmin=60, zmax=100,
                                       text=np.round(prep.values, 1), texttemplate="%{text}%", showscale=False))
            fig.update_layout(title="Skin preparation completion: case type by timing")
            st.plotly_chart(style(fig, 330, False), width="stretch")
        st.info("Where the gap is: complete skin preparation is lowest in STEMI cases, the most time-critical group, and dips for out-of-hours NSTEMI cases. Elective cases all run in hours, so their cell is empty. A checklist or a ready prep-pack at the lab door would help most in the urgent pathway.")

        st.markdown("##### Femoral haemostasis")
        fem = d[d.access_site == "Femoral"]
        if len(fem):
            hm = rate_by(fem, "haemostasis_method", OUT)
            fig = go.Figure()
            fig = err_bar(fig, hm, marker_color=BLUE, showlegend=False)
            fig.update_layout(title="Femoral cases: closure device vs manual compression", yaxis_title="Per 1,000")
            st.plotly_chart(style(fig, 320, False), width="stretch")
        st.caption("Associations in simulated data. The size of each gap follows the assumptions in generate_data.py, so treat them as a demonstration of how to monitor a bundle, not as proof that a step works.")

# ================================================================== TAB 5
with t5:
    st.markdown(f"#### Monthly {outcome_label.lower()} rate (p-chart)")
    if view.empty:
        st.info("No procedures match the filters.")
    else:
        mth = view.groupby("month").agg(n=("procedure_id", "count"), k=(OUT, "sum")).reset_index()
        pbar = mth.k.sum() / mth.n.sum()
        mth["rate"] = mth.k / mth.n * 1000
        mth["ucl"] = (pbar + 3 * np.sqrt(pbar * (1 - pbar) / mth.n)) * 1000
        mth["lcl"] = ((pbar - 3 * np.sqrt(pbar * (1 - pbar) / mth.n)) * 1000).clip(lower=0)
        mth["ma3"] = mth.k.rolling(3).sum() / mth.n.rolling(3).sum() * 1000
        out_pts = mth[mth.rate > mth.ucl]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mth.month, y=mth.ucl, mode="lines", name="Upper control limit (3 sigma)", line=dict(color=RED, dash="dash", shape="hv")))
        fig.add_trace(go.Scatter(x=mth.month, y=mth.lcl, mode="lines", name="Lower control limit", line=dict(color=GREY, dash="dot", shape="hv")))
        fig.add_hline(y=pbar * 1000, line=dict(color=GREY, width=1), annotation_text=f"Centre line {pbar * 1000:.1f}", annotation_position="bottom right")
        fig.add_trace(go.Scatter(x=mth.month, y=mth.rate, mode="lines+markers", name="Monthly rate", line=dict(color=BLUE, width=2.5), marker=dict(size=8)))
        fig.add_trace(go.Scatter(x=mth.month, y=mth.ma3, mode="lines", name="3-month moving rate", line=dict(color=AMBER, width=2)))
        if len(out_pts):
            fig.add_trace(go.Scatter(x=out_pts.month, y=out_pts.rate, mode="markers", name="Above upper limit", marker=dict(size=13, color=RED, symbol="diamond")))
        fig.update_layout(yaxis_title="Per 1,000 procedures", xaxis_title="Procedure month")
        st.plotly_chart(style(fig, 460), width="stretch")
        if len(out_pts):
            st.error(f"{len(out_pts)} month(s) crossed the upper control limit: " + ", ".join(out_pts.month.dt.strftime("%b %Y")) + ". In a real unit this would trigger a review.")
        else:
            st.success("No month crossed the upper control limit, so the monthly rate looks stable across the selected period.")
        st.caption("Events are rare, so single months jump around. The control limits show how much month-to-month movement is just chance.")
        with st.expander("Show the monthly numbers"):
            st.dataframe(mth.assign(month=mth.month.dt.strftime("%b %Y"))[["month", "n", "k", "rate", "ucl"]].rename(columns={"n": "Procedures", "k": "Cases", "rate": "Per 1,000", "ucl": "Upper limit"}).round(1), hide_index=True, width="stretch")

# ================================================================== TAB 6
with t6:
    ev = events_all.merge(view[["procedure_id", "case_type", "access_site"]], on="procedure_id", how="inner")
    st.markdown("#### What happened in the suspected infections")
    if ev.empty:
        st.info("No infection events in the selected procedures.")
    else:
        cols = st.columns(4)
        kpi(cols[0], f"{len(ev)}", "Suspected infections", "events in the selection")
        kpi(cols[1], f"{ev.confirmed.mean() * 100:.0f}%", "Confirmed", f"{int(ev.confirmed.sum())} of {len(ev)}")
        kpi(cols[2], f"{ev.readmitted.mean() * 100:.0f}%", "Readmitted", f"{int(ev.readmitted.sum())} patients")
        kpi(cols[3], f"{ev.days_to_onset.median():.0f} days", "Median time to onset", f"range {ev.days_to_onset.min()} to {ev.days_to_onset.max()} days")
        st.markdown("&nbsp;")
        c1, c2 = st.columns(2)
        sev = ev.severity.value_counts().reindex(["Superficial", "Deep", "Bloodstream"]).dropna()
        fig = go.Figure(go.Bar(x=sev.index, y=sev.values, marker_color=[LIGHT, AMBER, RED][: len(sev)], text=sev.values, textposition="outside"))
        fig.update_layout(title="Severity", yaxis_title="Cases")
        c1.plotly_chart(style(fig, 330, False), width="stretch")
        org = ev.organism.value_counts().sort_values()
        fig = go.Figure(go.Bar(x=org.values, y=org.index, orientation="h", marker_color=BLUE, text=org.values, textposition="outside"))
        fig.update_layout(title="Organism or culture result", xaxis_title="Cases")
        c2.plotly_chart(style(fig, 330, False), width="stretch")
        c3, c4 = st.columns(2)
        bucket = pd.cut(ev.days_to_onset, [0, 7, 14, 30], labels=["Days 1 to 7", "Days 8 to 14", "Days 15 to 30"]).value_counts().sort_index()
        fig = go.Figure(go.Bar(x=bucket.index.astype(str), y=bucket.values, marker_color=BLUE, text=bucket.values, textposition="outside"))
        fig.update_layout(title="Time to onset after the procedure", yaxis_title="Cases")
        c3.plotly_chart(style(fig, 330, False), width="stretch")
        tr = ev.treatment.value_counts().sort_values()
        fig = go.Figure(go.Bar(x=tr.values, y=tr.index, orientation="h", marker_color=LIGHT, text=tr.values, textposition="outside"))
        fig.update_layout(title="Treatment", xaxis_title="Cases")
        c4.plotly_chart(style(fig, 330, False), width="stretch")
        st.caption("Only a few dozen events, so these breakdowns show how the analysis works. They are not stable estimates.")

# ================================================================== TAB 7
with t7:
    st.markdown("#### About this project")
    st.markdown(
        "**Question.** Do patients treated with primary PCI for STEMI have a higher rate of access-site infection within 30 days than patients treated electively, and which factors (access route, haemostasis method, skin preparation, mechanical support) are linked to infection?\n\n"
        "**Why.** I am a cath lab head nurse. Access-site infection is rare after cardiac catheterisation but serious when it happens, and infection-control teams track it per 1,000 procedures. Because events are rare, the dashboard reports exact confidence intervals and avoids claiming differences the data cannot support."
    )
    st.markdown("**Outcome levels.** *Suspected*: clinical signs at the access site that prompt review. *Confirmed*: a deep or bloodstream infection, or a culture-positive infection.")
    st.markdown("#### Data sources behind the simulated numbers")
    src = pd.DataFrame([
        ["Radial access share", "About 89% (2019/20)", "[NAPCI 2021 Summary Report (NICOR)](https://www.hqip.org.uk/wp-content/uploads/2026/03/NAPCI-Domain-Report_2021_FINAL.pdf)"],
        ["Radial use and ACS share of PCI", "About 94% radial, 70% ACS (2022/23)", "[BCIS national audit, reported by TCTMD](https://www.tctmd.com/news/uk-cardiac-audit-reveals-some-good-some-appalling-trends-pci)"],
        ["Case mix", "Roughly 38%, 32%, 30%", "[NICOR PCI Hospital Report, Norfolk and Norwich, 2015 to 2018](https://www.nnuh.nhs.uk/wp-content/uploads/2022/07/NICOR-outcome-data.pdf)"],
        ["Femoral groin infection", "About 0.2% manual, 0.6% closure device", "[Meta-analysis, Am Heart J 2010;159:518-531](https://cardiovascularbusiness.com/node/1602)"],
        ["Infection after closure devices", "Reported range 0% to 5.1%", "[Malekpour and Castillo, HMP Global](https://www.hmpgloballearningnetwork.com/site/vdm/content/infection-perilous-complication-closure-device)"],
        ["Femoral vs radial arterial catheters (ICU)", "Femoral about 4 times radial", "[Lorente et al., Critical Care 2006](https://link.springer.com/doi/10.1186/cc4930)"],
    ], columns=["Item", "Value used", "Source"])
    md = "| Item | Value used | Source |\n|---|---|---|\n" + "\n".join(f"| {a} | {b} | {c} |" for a, b, c in src.values.tolist())
    st.markdown(md)
    st.markdown("#### Assumptions (not published effect sizes)")
    st.dataframe(pd.DataFrame({
        "Factor": ["STEMI", "NSTEMI", "Diabetes", "BMI 35 or more", "Mechanical support", "Incomplete skin preparation", "Age 75 or more", "Suspected vs confirmed"],
        "Odds multiplier": ["1.5", "1.25", "1.6", "1.5", "2.0", "1.8", "1.2", "Suspected about 2.5 times more frequent"],
    }), hide_index=True, width="stretch")
    st.markdown("#### Methods")
    st.markdown("- Rates are per 1,000 procedures with **exact (Clopper-Pearson) 95% confidence intervals**.\n- STEMI vs elective uses a **rate ratio with a log-method 95% CI** and **Fisher's exact test**.\n- The monthly chart is a **p-chart** with 3-sigma limits around the overall rate.\n- Full analysis code: `analysis.py`. SQL queries: `sql/queries.sql`.")
    st.markdown("#### Limitations")
    st.markdown("Only 22 suspected and 10 confirmed events, so subgroup estimates are very imprecise and operator comparisons are not reliable. A real evaluation would need approved hospital data, case definitions from national surveillance criteria, and adjustment for confounders.")
    st.markdown("---\n**Yosra El Nagar**, Cath Lab Head Nurse moving into Healthcare Data Analytics · [LinkedIn](https://www.linkedin.com/in/yosra-nagar-9a6862118/) · [GitHub](https://github.com/yosras-dotcomAi/cath-lab-access-site-infection)")
