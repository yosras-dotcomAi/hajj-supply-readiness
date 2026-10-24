"""
Analysis of the simulated Hajj-season supply data (run generate_data.py first).
Outputs: kpi_summary.csv, reorder_recommendations.csv and 5 charts (PNG).
"""
import pandas as pd
import matplotlib.pyplot as plt

TEAL, GREY, RED, DARK = "#2a9d8f", "#b0b0b0", "#d1495b", "#264653"
items = pd.read_csv("items.csv")
mult = pd.read_csv("daily_multipliers.csv", parse_dates=["date"])
dept = pd.read_csv("departments.csv")
cons = pd.read_csv("daily_consumption.csv", parse_dates=["date"])
sim = pd.read_csv("stock_simulation.csv", parse_dates=["date"]).merge(
    items[["item_id", "item_name", "category", "criticality", "lead_time_days", "normal_daily_use"]], on="item_id")
A, B = "Baseline planning", "Surge-aware planning"
sa, sb = sim[sim.policy == A], sim[sim.policy == B]

# ---------- 1. hospital-wide demand index vs a normal day
base_total = items["normal_daily_use"].sum()
daily = cons.groupby("date")["quantity"].sum().reset_index()
daily["index"] = daily["quantity"] / base_total

# ---------- 2. KPIs (single seeded run)
def kpis(s):
    tot, un = s["demand"].sum(), s["unmet_demand"].sum()
    so = s[s.unmet_demand > 0]
    return {
        "fill_rate": round(1 - un / tot, 4),
        "stockout_item_days": int(len(so)),
        "items_with_a_stockout": int(so["item_id"].nunique()),
        "critical_items_with_a_stockout": int(so[so.criticality == "A"]["item_id"].nunique()),
        "first_stockout_date": so["date"].min().strftime("%Y-%m-%d") if len(so) else "none",
    }
k = pd.DataFrame({A: kpis(sa), B: kpis(sb)}).T.reset_index().rename(columns={"index": "policy"})
k.to_csv("kpi_summary.csv", index=False)
print(k.to_string(index=False))
print("Peak hospital-wide demand index:", round(daily["index"].max(), 2))

# ---------- 3. reorder recommendations for the peak window
exp = {}
dm = {r.department: r.surge_sensitivity for r in dept.itertuples()}
import numpy as np
bu = {}
for r in items.itertuples():
    deps = [d.strip() for d in r.consuming_departments.split(",")]
    # recover per-department base from observed shares in the generator (same split table)
    bu[r.item_id] = deps
cons_idx = cons.groupby(["item_id", "date"])["quantity"].sum().unstack()
pre = ["2026-05-15", "2026-05-19"]
rows = []
for r in items.itertuples():
    series = cons_idx.loc[r.item_id]
    peak_day = series.max()
    window = r.lead_time_days + 2
    need_peak = series.rolling(window).sum().max()
    close_24 = sa[(sa.item_id == r.item_id) & (sa.date == "2026-05-24")]["closing_stock"].iloc[0]
    exp_25 = series.loc["2026-05-25"]
    rows.append({
        "item_id": r.item_id, "item_name": r.item_name, "category": r.category, "criticality": r.criticality,
        "lead_time_days": r.lead_time_days, "normal_daily_use": r.normal_daily_use,
        "peak_daily_demand": int(peak_day),
        "baseline_reorder_level": int(r.normal_daily_use * (r.lead_time_days + 3)),
        "recommended_reorder_level_for_peak": int(need_peak),
        "stock_end_of_24_May_baseline": int(close_24),
        "days_of_cover_at_peak_start": round(close_24 / exp_25, 2),
    })
rec = pd.DataFrame(rows).sort_values(["days_of_cover_at_peak_start"])
rec.to_csv("reorder_recommendations.csv", index=False)

# ---------- charts
# 1: multiplier curve
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(mult["date"].dt.strftime("%d %b"), mult["multiplier"], color=[RED if m >= 5 else TEAL for m in mult["multiplier"]])
ax.set_ylabel("Demand multiplier (x normal day)")
ax.set_title("Assumed Demand Pattern: Field Hospital in Mina, Hajj 2026")
ax.tick_params(axis="x", labelrotation=60)
plt.tight_layout(); plt.savefig("chart_demand_pattern.png", dpi=150); plt.close()

# 2: stockout item-days per day
d = pd.DataFrame({
    A: sa[sa.unmet_demand > 0].groupby("date").size(),
    B: sb[sb.unmet_demand > 0].groupby("date").size()}).reindex(mult["date"]).fillna(0)
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(d.index.strftime("%d %b"), d[A], color=RED, marker="o", label=A)
ax.plot(d.index.strftime("%d %b"), d[B], color=TEAL, marker="o", label=B)
ax.set_ylabel("Items out of stock (count)")
ax.set_title("Items With Unmet Demand Per Day")
ax.legend(); ax.tick_params(axis="x", labelrotation=60)
plt.tight_layout(); plt.savefig("chart_stockouts_per_day.png", dpi=150); plt.close()

# 3: fill rate by category
fr = sim.groupby(["category", "policy"]).apply(lambda g: 1 - g.unmet_demand.sum() / g.demand.sum()).unstack() * 100
fr = fr[[A, B]]
fig, ax = plt.subplots(figsize=(8, 4))
fr.plot.bar(ax=ax, color=[RED, TEAL], rot=0)
ax.set_ylim(80, 100.5); ax.set_ylabel("Fill rate (%)")
ax.set_title("Demand Fulfilled by Category")
plt.tight_layout(); plt.savefig("chart_fill_rate_by_category.png", dpi=150); plt.close()

# 4: top at-risk items (baseline policy), unmet share of demand
risk = sa.groupby("item_name").apply(lambda g: g.unmet_demand.sum() / g.demand.sum() * 100).sort_values().tail(10)
fig, ax = plt.subplots(figsize=(8, 5))
ax.barh(risk.index, risk.values, color=RED)
ax.set_xlabel("Unmet demand (% of season demand)")
ax.set_title("Top 10 Items at Risk Under Baseline Planning")
plt.tight_layout(); plt.savefig("chart_top_items_at_risk.png", dpi=150); plt.close()

# 5: stock trajectory of one critical item
it = rec[(rec.criticality == "A")].sort_values("days_of_cover_at_peak_start").iloc[0]["item_id"]
nm = items.loc[items.item_id == it, "item_name"].iloc[0]
fig, ax = plt.subplots(figsize=(9, 4))
for s, c, lab in ((sa, RED, A), (sb, TEAL, B)):
    t = s[s.item_id == it]
    ax.plot(t["date"].dt.strftime("%d %b"), t["closing_stock"], color=c, marker="o", label=lab)
ax.set_ylabel("Closing stock (units)"); ax.set_title(f"Stock Level Over the Season: {nm}")
ax.legend(); ax.tick_params(axis="x", labelrotation=60)
plt.tight_layout(); plt.savefig("chart_stock_trajectory_example.png", dpi=150); plt.close()
print("Example item for chart 5:", nm)
print(rec.head(8)[["item_name","criticality","days_of_cover_at_peak_start","recommended_reorder_level_for_peak","baseline_reorder_level"]].to_string(index=False))
