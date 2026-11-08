"""
What-if engine for the Hajj supply-readiness dashboard.

It re-implements the demand model and the two stock policies from generate_data.py
with adjustable assumptions. With the default settings and the same seeds it
reproduces monte_carlo_summary.csv.
"""
import numpy as np
import pandas as pd

SEED = 2026
PEAK_DATES = ["2026-05-25", "2026-05-27", "2026-05-28"]  # 8, 10, 11 Dhul Hijjah

# share of each item's use by department (same split table as generate_data.py)
SPLITS = {
    "Emergency, Trauma ICU, Burn Unit": {"Emergency": .6, "Trauma ICU": .2, "Burn Unit": .2},
    "Inpatient Wards": {"Inpatient Wards": 1.0},
    "ICU, Trauma ICU, Burn Unit": {"ICU": .5, "Trauma ICU": .3, "Burn Unit": .2},
    "Pharmacy": {"Pharmacy": 1.0},
    "Laboratory": {"Laboratory": 1.0},
    "Radiology": {"Radiology": 1.0},
    "Cath Lab": {"Cath Lab": 1.0},
}


def build_rows(items, dept):
    """One row per (item, department), in the same order as the generator."""
    sens = dict(zip(dept["department"], dept["surge_sensitivity"]))
    item_idx, base, s = [], [], []
    for i, r in enumerate(items.itertuples()):
        split = SPLITS.get(r.consuming_departments)
        if split is None:
            deps = [d.strip() for d in r.consuming_departments.split(",")]
            split = {d: 1 / len(deps) for d in deps}
        for d, share in split.items():
            item_idx.append(i)
            base.append(r.normal_daily_use * share)
            s.append(sens[d])
    return np.array(item_idx), np.array(base, float), np.array(s, float)


def run_policy(policy, dem, items, exp_plan, open_days, extra_lead):
    n_items, T = dem.shape
    base_u = items["normal_daily_use"].to_numpy(float)
    lead = items["lead_time_days"].to_numpy(int) + int(extra_lead)
    unmet = np.zeros((n_items, T))
    for i in range(n_items):
        L, base = int(lead[i]), base_u[i]
        stock, pipe = base * open_days, {}
        for t in range(T):
            stock += pipe.pop(t, 0)
            d = int(dem[i, t])
            issued = min(stock, d)
            unmet[i, t] = d - issued
            stock -= issued
            out = sum(pipe.values())
            if policy == "A":
                rop, target = base * (L + 3), base * (L + 10)
            else:
                rop = max(base * (L + 3), exp_plan[i, t + 1:min(t + 1 + L + 2, T)].sum())
                target = max(base * (L + 10), exp_plan[i, t + 1:min(t + 1 + L + 8, T)].sum())
            if stock + out <= rop:
                ordered = max(0, int(np.ceil(target - stock - out)))
                if ordered > 0 and t + L < T:
                    pipe[t + L] = pipe.get(t + L, 0) + ordered
    return unmet


def what_if(items, dept, mult_df, peak=5.0, extra_lead=0, open_days=12.0,
            accuracy=1.0, runs=30, seed=SEED + 1000):
    """Average results over `runs` simulated seasons under the chosen assumptions."""
    dates = pd.to_datetime(mult_df["date"]).dt.strftime("%Y-%m-%d").tolist()
    mult = mult_df["multiplier"].to_numpy(float).copy()
    for k, d in enumerate(dates):
        if d in PEAK_DATES:
            mult[k] = peak
    plan_mult = 1 + (mult - 1) * accuracy
    item_idx, base, sens = build_rows(items, dept)
    lam = base[:, None] * (1 + (mult[None, :] - 1) * sens[:, None])
    lam_plan = base[:, None] * (1 + (plan_mult[None, :] - 1) * sens[:, None])
    n_items, T = len(items), len(dates)
    exp_plan = np.zeros((n_items, T))
    np.add.at(exp_plan, item_idx, lam_plan)
    crit = (items["criticality"] == "A").to_numpy()

    res = {p: {"fill": [], "so": [], "so_crit": [], "per_day": np.zeros(T), "item_unmet": np.zeros(n_items)}
           for p in ("A", "B")}
    demand_total = 0.0
    for k in range(runs):
        g = np.random.default_rng(seed + k)
        draw = g.poisson(lam)
        dem = np.zeros((n_items, T))
        np.add.at(dem, item_idx, draw)
        demand_total += dem.sum()
        for p in ("A", "B"):
            un = run_policy(p, dem, items, exp_plan, open_days, extra_lead)
            r = res[p]
            r["fill"].append(1 - un.sum() / dem.sum())
            r["so"].append(int((un > 0).sum()))
            r["so_crit"].append(int((un[crit] > 0).sum()))
            r["per_day"] += (un > 0).sum(axis=0) / runs
            r["item_unmet"] += un.sum(axis=1) / runs
    out = {"dates": dates, "mult": mult, "runs": runs, "mean_demand": demand_total / runs}
    for p in ("A", "B"):
        r = res[p]
        out[p] = {
            "fill_mean": float(np.mean(r["fill"])), "fill_p5": float(np.percentile(r["fill"], 5)),
            "so_mean": float(np.mean(r["so"])), "so_crit_mean": float(np.mean(r["so_crit"])),
            "per_day": r["per_day"], "item_unmet": r["item_unmet"],
        }
    return out
