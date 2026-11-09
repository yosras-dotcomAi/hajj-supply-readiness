"""
Hajj Season Medical Supply Readiness: interactive dashboard.

A FICTIONAL field hospital in Mina during Hajj 1447 / 2026. Every number is an
assumption used to demonstrate the method. No real hospital, patient or supply data.

Run:  streamlit run app.py   (CSV files sit in the repository root)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from supply_engine import what_if

st.set_page_config(page_title="Hajj Supply Readiness", page_icon="🕋", layout="wide")

ROOT = Path(__file__).parent
TEAL, RED, AMBER, BLUE, GREY, LIGHT = "#2a9d8f", "#d1495b", "#F2B84B", "#3B8FD9", "#7F93A8", "#80C8FF"
A, B = "Baseline planning", "Surge-aware planning"
POLICY_COLOR = {A: RED, B: TEAL}
CRIT_COLOR = {"A": RED, "B": AMBER, "C": GREY}

st.markdown(
    """
<style>
.block-container{padding-top:1.4rem;max-width:1280px}
.hero h1{font-size:2.0rem;margin:0 0 .2rem 0;color:inherit}
.hero p{color:inherit;opacity:.75;margin:0 0 .8rem 0;font-size:1.02rem}
.sim{background:#16263d;border:1px solid #2F4A6D;border-left:4px solid #F2B84B;color:#E6EEF7;border-radius:8px;padding:10px 14px;font-size:.92rem;margin-bottom:1rem}
.kpi{background:#121C2E;border:1px solid #1F3250;border-radius:12px;padding:14px 16px;height:100%}
.kpi .v{font-size:1.75rem;font-weight:700;color:#fff;line-height:1.15}
.kpi .l{color:#C9DCF0;font-size:.85rem;margin-top:2px}
.kpi .s{color:#6F8CAB;font-size:.76rem;margin-top:2px}
.answer{background:#0F2238;border-left:4px solid #2a9d8f;border-radius:8px;padding:14px 18px;margin:.6rem 0 1rem 0;color:#E6EEF7}
.answer h4{margin:0 0 .4rem 0;color:#fff}
.answer b{color:#fff}
.answer .note{color:#9FB6CF}
.note{color:#7F93A8;font-size:.85rem}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def load():
    items = pd.read_csv(ROOT / "items.csv")
    dept = pd.read_csv(ROOT / "departments.csv")
    mult = pd.read_csv(ROOT / "daily_multipliers.csv", parse_dates=["date"])
    cons = pd.read_csv(ROOT / "daily_consumption.csv", parse_dates=["date"])
    sim = pd.read_csv(ROOT / "stock_simulation.csv", parse_dates=["date"]).merge(
        items[["item_id", "item_name", "category", "criticality", "lead_time_days", "normal_daily_use"]], on="item_id")
    mc = pd.read_csv(ROOT / "monte_carlo_summary.csv").set_index("policy")
    kpi = pd.read_csv(ROOT / "kpi_summary.csv").set_index("policy")
    rec = pd.read_csv(ROOT / "reorder_recommendations.csv")
    return items, dept, mult, cons, sim, mc, kpi, rec


items, dept, mult, cons, sim, mc, kpi, rec = load()


def kpi_card(col, value, label, sub=""):
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


def day_label(d):
    return pd.Timestamp(d).strftime("%d %b")


date_labels = [day_label(d) for d in mult["date"]]
PEAK = mult["multiplier"] >= 5

# ------------------------------------------------------------------ sidebar
st.sidebar.markdown("## Filters")
cat_sel = st.sidebar.multiselect("Item category", sorted(items.category.unique()), default=sorted(items.category.unique()))
crit_sel = st.sidebar.multiselect("Criticality", ["A", "B", "C"], default=["A", "B", "C"],
                                  help="A = life-critical, B = important, C = lower priority")
f_items = items[items.category.isin(cat_sel) & items.criticality.isin(crit_sel)]
fsim = sim[sim.item_id.isin(f_items.item_id)]
frec = rec[rec.item_id.isin(f_items.item_id)]
st.sidebar.markdown(f"**{len(f_items)}** of {len(items)} items selected")
st.sidebar.caption("Filters apply to the Plans compared, Items at risk and Reorder planner tabs. The Overview, Demand surge and What-if lab always use the whole hospital.")

# ------------------------------------------------------------------ header
st.markdown('<div class="hero"><h1>🕋 Hajj Season Medical Supply Readiness</h1>'
            "<p>Where does a supply plan built on a normal day break down when demand jumps to 5x?</p></div>", unsafe_allow_html=True)
st.markdown('<div class="sim"><b>Fictional field hospital, simulated data.</b> A field hospital in Mina during Hajj 1447 / 2026. Every number is an assumption created to demonstrate the method. No real hospital, patient or supply data is used.</div>', unsafe_allow_html=True)

t1, t2, t3, t4, t5, t6, t7 = st.tabs(["🎯 Overview", "📈 Demand surge", "⚖️ Plans compared", "⚠️ Items at risk", "📦 Reorder planner", "🧪 What-if lab", "📚 Method & limits"])

# ================================================================== TAB 1
with t1:
    base_total = items["normal_daily_use"].sum()
    daily = cons.groupby("date")["quantity"].sum() / base_total
    peak_idx, peak_day = daily.max(), daily.idxmax()
    ba, sb = sim[sim.policy == A], sim[sim.policy == B]
    so_a = ba[ba.unmet_demand > 0]
    per_day_a = so_a.groupby("date").size()
    worst_day, worst_n = per_day_a.idxmax(), int(per_day_a.max())
    cols = st.columns(5)
    kpi_card(cols[0], f"{peak_idx:.1f}x", "Peak hospital-wide demand", f"vs a normal day, on {day_label(peak_day)}")
    kpi_card(cols[1], f"{mc.loc[A, 'fill_rate_mean'] * 100:.1f}%", "Demand met, baseline plan", f"mean of 200 runs · worst 5%: {mc.loc[A, 'fill_rate_p5'] * 100:.1f}%")
    kpi_card(cols[2], f"{mc.loc[B, 'fill_rate_mean'] * 100:.2f}%", "Demand met, surge-aware plan", f"mean of 200 runs · worst 5%: {mc.loc[B, 'fill_rate_p5'] * 100:.2f}%")
    kpi_card(cols[3], f"{mc.loc[A, 'stockout_item_days_mean']:.0f} → {mc.loc[B, 'stockout_item_days_mean']:.0f}", "Stockout item-days", "baseline → surge-aware (mean)")
    kpi_card(cols[4], f"{mc.loc[A, 'critical_stockout_item_days_mean']:.0f} → {mc.loc[B, 'critical_stockout_item_days_mean']:.0f}", "Critical (class A) item-days", "baseline → surge-aware (mean)")

    k = kpi.loc[A]
    cover = rec["days_of_cover_at_peak_start"]
    low = rec.sort_values("days_of_cover_at_peak_start").head(3)
    st.markdown(
        '<div class="answer"><h4>Where does a plan built on a normal day break down?</h4>'
        f"<b>At the peak.</b> In the sample run, {int(k.items_with_a_stockout)} of {len(items)} items ran out at least once, including {int(k.critical_items_with_a_stockout)} of {(items.criticality == 'A').sum()} critical items. The first stockout was on {pd.Timestamp(k.first_stockout_date):%d %B}.<br>"
        f"<b>The worst day is after the peak, not during it.</b> {worst_n} items were out of stock on {day_label(worst_day)}, because resupply takes 2 to 4 days and arrives after the surge has drained stock.<br>"
        f"<b>Cover is thin when the peak starts.</b> At the end of 24 May, {int((cover < 2).sum())} of {len(rec)} items had less than 2 days of cover at peak demand. Lowest: "
        + ", ".join(f"{r.item_name} ({r.days_of_cover_at_peak_start:.1f} days)" for r in low.itertuples()) + ".<br>"
        '<span class="note">Surge-aware planning assumes the demand calendar is known in advance, so it is a best case. See the What-if lab for less accurate forecasts.</span></div>',
        unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        fig = go.Figure(go.Bar(x=date_labels, y=mult["multiplier"], marker_color=[RED if p else TEAL for p in PEAK],
                               text=[f"{m:g}x" for m in mult["multiplier"]], textposition="outside", cliponaxis=False))
        fig.update_layout(title="Assumed demand multiplier (x a normal day)", yaxis_title="x normal day")
        st.plotly_chart(style(fig, 360, False), width="stretch")
    with right:
        d = pd.DataFrame({A: so_a.groupby("date").size(), B: sb[sb.unmet_demand > 0].groupby("date").size()}).reindex(mult["date"]).fillna(0)
        fig = go.Figure()
        for p in (A, B):
            fig.add_trace(go.Scatter(x=date_labels, y=d[p], mode="lines+markers", name=p, line=dict(color=POLICY_COLOR[p], width=3)))
        fig.update_layout(title="Items out of stock per day (sample run)", yaxis_title="Items")
        st.plotly_chart(style(fig, 360), width="stretch")

# ================================================================== TAB 2
with t2:
    st.markdown("#### The demand surge")
    daily_idx = (cons.groupby("date")["quantity"].sum() / items["normal_daily_use"].sum()).reindex(mult["date"])
    left, right = st.columns([3, 2])
    with left:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=date_labels, y=mult["multiplier"], name="Assumed multiplier", marker_color="#5B7FA6"))
        fig.add_trace(go.Scatter(x=date_labels, y=daily_idx.values, name="Hospital-wide demand index (simulated)", mode="lines+markers", line=dict(color=AMBER, width=3)))
        fig.update_layout(title="Assumed multiplier vs simulated hospital-wide demand", yaxis_title="x normal day", barmode="overlay")
        st.plotly_chart(style(fig, 400), width="stretch")
    with right:
        cal = mult.assign(date=mult["date"].dt.strftime("%d %b"))[["date", "hijri_day", "phase", "multiplier"]]
        cal.columns = ["Date", "Hijri day", "Phase", "Multiplier"]
        st.dataframe(cal, hide_index=True, width="stretch", height=400)
    st.info("Hospital-wide demand peaks at about 4.4x a normal day, not 5x, because departments respond differently to the surge. A Cath Lab barely feels it (sensitivity 0.4) while Emergency feels all of it (1.0).")

    pre = cons[cons.date < "2026-05-20"].groupby("department")["quantity"].sum() / 5
    dd = cons.groupby(["department", "date"])["quantity"].sum().unstack()
    heat = dd.div(pre, axis=0).loc[dept.sort_values("surge_sensitivity", ascending=False).department]
    fig = go.Figure(go.Heatmap(z=heat.values, x=date_labels, y=heat.index, colorscale="YlOrRd", text=np.round(heat.values, 1), texttemplate="%{text}", colorbar=dict(title="x normal")))
    fig.update_layout(title="Demand by department, relative to its first five days (normal operation)")
    st.plotly_chart(style(fig, 400, False), width="stretch")

# ================================================================== TAB 3
with t3:
    st.markdown("#### Baseline vs surge-aware planning")
    st.caption("Both policies start with the same stock (12 normal days) and face the same resupply lead times. Only the reorder rules differ.")
    if fsim.empty:
        st.info("No items match the filters.")
    else:
        cols = st.columns(2)
        for col, p in zip(cols, (A, B)):
            g = fsim[fsim.policy == p]
            so = g[g.unmet_demand > 0]
            kpi_card(col, f"{(1 - g.unmet_demand.sum() / g.demand.sum()) * 100:.2f}%", p, f"{len(so)} stockout item-days · {so.item_id.nunique()} items out at least once (sample run)")
        st.markdown("&nbsp;")
        left, right = st.columns(2)
        with left:
            fig = go.Figure()
            for crit in ["A", "B", "C"]:
                g = fsim[(fsim.policy == A) & (fsim.unmet_demand > 0) & (fsim.criticality == crit)].groupby("date").size().reindex(mult["date"]).fillna(0)
                fig.add_trace(go.Bar(x=date_labels, y=g.values, name=f"Class {crit}", marker_color=CRIT_COLOR[crit]))
            fig.update_layout(barmode="stack", title="Baseline planning: items out of stock per day, by criticality", yaxis_title="Items")
            st.plotly_chart(style(fig, 380), width="stretch")
        with right:
            fr = fsim.groupby(["category", "policy"]).apply(lambda g: (1 - g.unmet_demand.sum() / g.demand.sum()) * 100, include_groups=False).unstack()
            fig = go.Figure()
            for p in (A, B):
                fig.add_trace(go.Bar(x=fr.index, y=fr[p], name=p, marker_color=POLICY_COLOR[p], text=[f"{v:.1f}%" for v in fr[p]], textposition="outside"))
            fig.update_layout(barmode="group", title="Demand met by category (sample run)", yaxis=dict(range=[max(0, float(np.floor(fr.min().min() / 5) * 5 - 5)), 105], title="Fill rate (%)"))
            st.plotly_chart(style(fig, 380), width="stretch")
        st.markdown("##### Stability across 200 simulated seasons (whole hospital)")
        mc_show = mc.rename(columns={"fill_rate_mean": "Demand met (mean)", "fill_rate_p5": "Demand met (worst 5%)", "stockout_item_days_mean": "Stockout item-days (mean)", "critical_stockout_item_days_mean": "Critical item-days (mean)"})
        mc_show[["Demand met (mean)", "Demand met (worst 5%)"]] = (mc_show[["Demand met (mean)", "Demand met (worst 5%)"]] * 100).round(2).astype(str) + "%"
        st.dataframe(mc_show.reindex([A, B]), width="stretch")
        st.caption("The gap between the two plans holds in every simulated season: even the worst 5% of surge-aware seasons beat the average baseline season.")

# ================================================================== TAB 4
with t4:
    st.markdown("#### Items at risk when the peak starts")
    if frec.empty:
        st.info("No items match the filters.")
    else:
        thin = frec[frec.days_of_cover_at_peak_start < 2]
        cols = st.columns(3)
        kpi_card(cols[0], f"{len(thin)} of {len(frec)}", "Items with under 2 days of cover", "stock at end of 24 May vs 25 May demand")
        kpi_card(cols[1], f"{(thin.criticality == 'A').sum()}", "Of those, critical (class A)", "")
        lowest = frec.sort_values("days_of_cover_at_peak_start").iloc[0]
        kpi_card(cols[2], f"{lowest.days_of_cover_at_peak_start:.1f} days", f"Lowest cover: {lowest.item_name}", "")
        top = frec.sort_values("days_of_cover_at_peak_start").head(15).iloc[::-1]
        fig = go.Figure(go.Bar(x=top.days_of_cover_at_peak_start, y=top.item_name, orientation="h", marker_color=[CRIT_COLOR[c] for c in top.criticality],
                               text=[f"{v:.1f}" for v in top.days_of_cover_at_peak_start], textposition="outside", cliponaxis=False))
        fig.add_vline(x=2, line=dict(color="#888", dash="dash"), annotation_text="2 days", annotation_position="top")
        fig.update_layout(title="Days of cover at the start of the peak (red = class A, amber = B, grey = C)", xaxis_title="Days")
        st.plotly_chart(style(fig, 520, False), width="stretch")

        st.markdown("##### Follow one item through the season")
        pick = st.selectbox("Item", frec.sort_values("days_of_cover_at_peak_start").item_name.tolist())
        iid = items.loc[items.item_name == pick, "item_id"].iloc[0]
        g = sim[sim.item_id == iid]
        fig = go.Figure()
        d0 = g[g.policy == A]
        fig.add_trace(go.Bar(x=date_labels, y=d0.demand, name="Demand", marker_color="#5B7FA6"))
        for p in (A, B):
            gp = g[g.policy == p]
            fig.add_trace(go.Scatter(x=date_labels, y=gp.closing_stock, name=f"Closing stock, {p}", mode="lines+markers", line=dict(color=POLICY_COLOR[p], width=3)))
        fig.update_layout(title=f"{pick}: demand and closing stock (sample run)", yaxis_title="Units")
        st.plotly_chart(style(fig, 400), width="stretch")
        un = int(d0.unmet_demand.sum())
        st.caption(f"Under baseline planning {pick} had {un} units of unmet demand this season." if un else f"Under baseline planning {pick} never ran out in this sample run.")

# ================================================================== TAB 5
with t5:
    st.markdown("#### Reorder levels for the peak window")
    if frec.empty:
        st.info("No items match the filters.")
    else:
        r = frec.assign(multiple=lambda d: d.recommended_reorder_level_for_peak / d.baseline_reorder_level)
        cols = st.columns(3)
        kpi_card(cols[0], f"{r.multiple.median():.1f}x", "Median increase in reorder level", "recommended vs baseline")
        kpi_card(cols[1], f"{r.multiple.max():.1f}x", "Largest increase", r.sort_values("multiple").iloc[-1].item_name)
        kpi_card(cols[2], f"{len(r)}", "Items shown", "")
        st.markdown("&nbsp;")
        view = r.sort_values("days_of_cover_at_peak_start")[["item_name", "category", "criticality", "lead_time_days", "normal_daily_use", "peak_daily_demand",
                                                            "baseline_reorder_level", "recommended_reorder_level_for_peak", "multiple", "days_of_cover_at_peak_start"]]
        view.columns = ["Item", "Category", "Class", "Lead time (days)", "Normal daily use", "Peak daily demand", "Baseline reorder level", "Recommended for peak", "Increase (x)", "Days of cover at peak start"]
        st.dataframe(view, hide_index=True, width="stretch", height=480, column_config={
            "Increase (x)": st.column_config.NumberColumn(format="%.1f x"),
            "Days of cover at peak start": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=6),
        })
        st.download_button("⬇️ Download these recommendations (CSV)", view.to_csv(index=False).encode(), "reorder_recommendations_filtered.csv", "text/csv")
        st.caption("Recommended level = the highest demand expected over the lead time plus 2 days, so an order placed at that level still covers the peak window.")

# ================================================================== TAB 6
with t6:
    st.markdown("#### What-if lab: stress-test the assumptions")
    st.caption("Change the assumptions and the dashboard re-runs the simulation across many random seasons. With the default values it reproduces the 200-run results.")
    c1, c2, c3 = st.columns(3)
    peak = c1.slider("Peak-day demand (x normal)", 2.0, 8.0, 5.0, 0.5, help="Applies to 8, 10 and 11 Dhul Hijjah")
    extra = c2.slider("Extra supplier delay (days)", 0, 3, 0, help="Added to every item's lead time")
    opening = c3.slider("Opening stock (normal days)", 6, 20, 12)
    c4, c5 = st.columns(2)
    acc = c4.slider("Forecast accuracy of the surge-aware plan", 0.4, 1.0, 1.0, 0.05, help="100% = the plan knows the exact demand calendar. Lower = it underestimates the surge.")
    runs = c5.select_slider("Simulated seasons", [20, 50, 100, 200], value=100)
    with st.spinner("Simulating..."):
        res = what_if(items, dept, mult, peak=peak, extra_lead=extra, open_days=float(opening), accuracy=acc, runs=runs)
    cols = st.columns(4)
    kpi_card(cols[0], f"{res['A']['fill_mean'] * 100:.1f}%", "Demand met, baseline", f"original: {mc.loc[A, 'fill_rate_mean'] * 100:.1f}%")
    kpi_card(cols[1], f"{res['B']['fill_mean'] * 100:.2f}%", "Demand met, surge-aware", f"original: {mc.loc[B, 'fill_rate_mean'] * 100:.2f}%")
    kpi_card(cols[2], f"{res['A']['so_mean']:.0f} → {res['B']['so_mean']:.0f}", "Stockout item-days", f"original: {mc.loc[A, 'stockout_item_days_mean']:.0f} → {mc.loc[B, 'stockout_item_days_mean']:.0f}")
    kpi_card(cols[3], f"{res['A']['so_crit_mean']:.0f} → {res['B']['so_crit_mean']:.0f}", "Critical item-days", f"original: {mc.loc[A, 'critical_stockout_item_days_mean']:.0f} → {mc.loc[B, 'critical_stockout_item_days_mean']:.0f}")
    st.markdown("&nbsp;")
    left, right = st.columns(2)
    with left:
        fig = go.Figure()
        for p, key in ((A, "A"), (B, "B")):
            fig.add_trace(go.Scatter(x=date_labels, y=res[key]["per_day"], name=p, mode="lines+markers", line=dict(color=POLICY_COLOR[p], width=3)))
        fig.update_layout(title="Average items out of stock per day", yaxis_title="Items")
        st.plotly_chart(style(fig, 380), width="stretch")
    with right:
        un = pd.Series(res["A"]["item_unmet"], index=items.item_name).sort_values().tail(10)
        fig = go.Figure(go.Bar(x=un.values, y=un.index, orientation="h", marker_color=RED))
        fig.update_layout(title="Most exposed items, baseline (avg units unmet)", xaxis_title="Units")
        st.plotly_chart(style(fig, 380, False), width="stretch")
    if acc < 1:
        st.info(f"At {acc:.0%} forecast accuracy the surge-aware plan underestimates the surge, so part of its advantage disappears. The real value of this approach depends on how good the demand forecast is.")
    st.caption("Department sensitivities, the other days' multipliers and item data are unchanged from the original model.")

# ================================================================== TAB 7
with t7:
    st.markdown("#### The scenario")
    st.markdown("A fictional field hospital in Mina during the Hajj 1447 / 2026 season, inspired by hands-on experience with medical supplies during Hajj.\n\n"
                "- **9 departments:** Emergency, Trauma ICU, Burn Unit, ICU, Inpatient Wards, Pharmacy, Laboratory, Radiology, Cath Lab\n"
                "- **80 generic items** (50 medical supplies, 20 pharmaceuticals, 10 laboratory), each with a criticality class (A, B, C), supply channel and lead time\n"
                "- **Operating period:** 15 to 31 May 2026 (17 days)\n"
                "- **Peak days:** 8, 10 and 11 Dhul Hijjah (25, 27, 28 May) assumed at **5x** a normal pre-season day")
    st.markdown("#### Method")
    st.markdown("1. **Generate demand:** daily consumption per department and item (Poisson), scaled by the demand calendar and each department's sensitivity.\n"
                "2. **Simulate stock** under two policies with the same opening stock (12 normal days) and the same lead times (2 to 4 days):\n"
                "   - **Baseline planning:** reorder level = normal daily use × (lead time + 3 days), order up to normal daily use × (lead time + 10 days).\n"
                "   - **Surge-aware planning:** the same rules, but never lower than the expected demand over the next lead time + 2 days (reorder) or + 8 days (order-up-to).\n"
                "3. **Repeat 200 times** (Monte Carlo) to check the result is stable.\n"
                "4. **Recommend** reorder levels for the peak window.")
    st.markdown("#### Department sensitivity to the surge")
    st.dataframe(dept.rename(columns={"department": "Department", "surge_sensitivity": "Surge sensitivity (1.0 = full multiplier)"}), hide_index=True, width="stretch")
    st.markdown("#### Limitations")
    st.markdown("- **Results follow from the assumptions.** Surge size, department sensitivities, opening stock and lead times are illustrative. Real figures would change the numbers, not the method.\n"
                "- **Surge-aware planning assumes the demand calendar is known in advance**, so it is a best case. A real forecast would be less accurate (try the What-if lab).\n"
                "- Supplier stock is assumed unlimited, and each item is tracked at hospital level in one central store.\n"
                "- Arafah day (26 May) is assumed at 2.0x and the ramp-up and wind-down shapes are illustrative. Edit `demand_multipliers.xlsx` or `generate_data.py` to test other patterns.")
    st.markdown("---\n**Yosra El Nagar**, Cath Lab Head Nurse moving into Healthcare Data Analytics · [LinkedIn](https://www.linkedin.com/in/yosra-nagar-9a6862118/) · [GitHub](https://github.com/yosras-dotcomAi/hajj-supply-readiness)")
