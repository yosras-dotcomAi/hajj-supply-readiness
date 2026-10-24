"""
Hajj Season Medical Supply Readiness: synthetic data generator + stock simulation
---------------------------------------------------------------------------------
A FICTIONAL field hospital in Mina during the Hajj 1447 / 2026 season.
Every number below is an ASSUMPTION used to demonstrate the method.
No real hospital, patient, or supply data is used.

Outputs (CSV): items, departments, daily_multipliers, daily_consumption,
               stock_simulation (two policies), monte_carlo_summary
"""
import numpy as np
import pandas as pd

SEED = 2026
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------- calendar
# Demand multiplier vs. a normal pre-season day (ASSUMPTIONS, editable).
# Peak days (8, 10, 11 Dhul Hijjah) = 5x as stated by the project owner.
# Arafah day (2.0x) and the shape of the ramp-up / wind-down are assumptions.
DAYS = pd.date_range("2026-05-15", "2026-05-31")
MULT = {
    "2026-05-15": 1.0, "2026-05-16": 1.0, "2026-05-17": 1.0,
    "2026-05-18": 1.0, "2026-05-19": 1.0,
    "2026-05-20": 1.2, "2026-05-21": 1.3, "2026-05-22": 1.5,
    "2026-05-23": 1.6, "2026-05-24": 1.8,
    "2026-05-25": 5.0,   # 8 Dhul Hijjah
    "2026-05-26": 2.0,   # 9 Dhul Hijjah (Arafah)
    "2026-05-27": 5.0,   # 10 Dhul Hijjah (Eid al-Adha)
    "2026-05-28": 5.0,   # 11 Dhul Hijjah
    "2026-05-29": 3.0,   # 12 Dhul Hijjah
    "2026-05-30": 2.0,   # 13 Dhul Hijjah
    "2026-05-31": 1.2,   # last operating day
}
HIJRI = {"2026-05-25": "8 Dhul Hijjah", "2026-05-26": "9 Dhul Hijjah (Arafah)",
         "2026-05-27": "10 Dhul Hijjah (Eid)", "2026-05-28": "11 Dhul Hijjah",
         "2026-05-29": "12 Dhul Hijjah", "2026-05-30": "13 Dhul Hijjah"}
def phase(d):
    if d < pd.Timestamp("2026-05-20"): return "Initial operation"
    if d < pd.Timestamp("2026-05-25"): return "Pilgrim arrival"
    if d <= pd.Timestamp("2026-05-30"): return "Hajj days"
    return "Closing"

mult = pd.DataFrame({
    "date": DAYS,
    "hijri_day": [HIJRI.get(d.strftime("%Y-%m-%d"), "") for d in DAYS],
    "phase": [phase(d) for d in DAYS],
    "multiplier": [MULT[d.strftime("%Y-%m-%d")] for d in DAYS],
})

# ------------------------------------------------------------- departments
# How strongly each department responds to the surge (1.0 = full multiplier).
DEPT_SENS = {"Emergency": 1.0, "Trauma ICU": 1.0, "Burn Unit": 0.8, "ICU": 0.6,
             "Inpatient Wards": 0.7, "Pharmacy": 0.9, "Laboratory": 0.8,
             "Radiology": 0.7, "Cath Lab": 0.4}
depts = pd.DataFrame({"department": list(DEPT_SENS), "surge_sensitivity": list(DEPT_SENS.values())})

# ------------------------------------------------------------------ items
# (name, category, unit, normal daily use across the hospital)
ER = [("IV cannula 20G","piece",120),("IV cannula 18G","piece",80),("Sodium chloride 0.9% 1L bag","bag",150),
      ("Ringer's lactate 1L bag","bag",90),("Oral rehydration salts sachet","sachet",200),("Instant cooling pack","piece",60),
      ("Sterile gauze pack","pack",250),("Elastic bandage","roll",80),("Adhesive tape roll","roll",70),
      ("Sterile wound dressing","piece",120),("Disposable syringe 10 mL","piece",220),("Arm splint","piece",25),
      ("Nebulizer kit","kit",40),("Oxygen mask adult","piece",45)]
WARD = [("IV administration set","set",90),("IV extension set","set",70),("Foley catheter 16F","piece",20),
        ("Urine drainage bag","piece",25),("Examination gloves","pair",400),("Sterile gloves","pair",100),
        ("Surgical face mask","piece",150),("Nasal cannula","piece",40),("Pressure-relief dressing","piece",20),
        ("Alcohol swab","piece",300)]
ICU = [("Endotracheal tube 7.5 mm","piece",8),("Ventilator circuit","set",6),("Closed suction catheter","piece",20),
       ("Central venous catheter kit","kit",6),("Arterial line kit","kit",5),("Chest drain kit","kit",3),
       ("Nasogastric tube","piece",8),("Heat-moisture exchange filter","piece",15),
       ("ECG electrode","piece",60),("Saline flush 10 mL","piece",80)]
PHARM = [("Paracetamol 500 mg tablet","tablet",200),("Paracetamol IV 100 mL","bag",60),("Ibuprofen 400 mg tablet","tablet",150),
         ("Diclofenac injection","ampoule",50),("Ondansetron injection","ampoule",40),("Omeprazole IV","vial",40),
         ("Ceftriaxone 1 g injection","vial",80),("Amoxicillin-clavulanate IV","vial",50),("Metronidazole IV","bag",40),
         ("Insulin regular vial","vial",8),("Amlodipine tablet","tablet",100),("Aspirin 81 mg tablet","tablet",120),
         ("Heparin injection","vial",15),("Enoxaparin prefilled syringe","syringe",20),("Nitroglycerin sublingual","dose",12),
         ("Adrenaline injection","ampoule",25),("Salbutamol nebule","nebule",60),("Hydrocortisone injection","vial",30),
         ("Loperamide capsule","capsule",60),("Silver sulfadiazine cream","tube",15)]
LAB = [("EDTA blood tube","tube",120),("Serum separator tube","tube",100),("Citrate coagulation tube","tube",30),
       ("Blood culture bottle","bottle",25),("Glucose test strip","strip",150),("Urinalysis dipstick","strip",60),
       ("Troponin cartridge","cartridge",20),("Blood gas cartridge","cartridge",25),
       ("Rapid influenza test","test",20),("Kidney function reagent","test",80)]
RAD = [("CT contrast media 100 mL","vial",12),("Ultrasound gel bottle","bottle",5),("X-ray cassette cover","piece",30)]
CATH = [("Introducer sheath 6F","piece",5),("Diagnostic catheter","piece",5),("Guiding catheter","piece",3),
        ("Coronary guidewire 0.014","piece",4),("Guidewire 0.035","piece",5),("PTCA balloon","piece",3),
        ("Drug-eluting stent","piece",3),("Contrast media 100 mL (cath lab)","vial",8),("Vascular closure device","piece",3),
        ("Manifold kit","kit",4),("Pressure transducer kit","kit",4),("Radial compression band","piece",5),
        ("Hemostasis valve (Y-connector)","piece",4)]

# which departments consume each group, and their share of the item's use
GROUPS = [
    (ER,   "Medical Supplies", {"Emergency": .6, "Trauma ICU": .2, "Burn Unit": .2}),
    (WARD, "Medical Supplies", {"Inpatient Wards": 1.0}),
    (ICU,  "Medical Supplies", {"ICU": .5, "Trauma ICU": .3, "Burn Unit": .2}),
    (PHARM,"Pharmaceuticals",  {"Pharmacy": 1.0}),
    (LAB,  "Laboratory",       {"Laboratory": 1.0}),
    (RAD,  "Medical Supplies", {"Radiology": 1.0}),
    (CATH, "Medical Supplies", {"Cath Lab": 1.0}),
]
CRIT_A = {"Sodium chloride 0.9% 1L bag","Ringer's lactate 1L bag","Endotracheal tube 7.5 mm","Ventilator circuit",
          "Central venous catheter kit","Chest drain kit","Adrenaline injection","Heparin injection",
          "Enoxaparin prefilled syringe","Nitroglycerin sublingual","Ceftriaxone 1 g injection","Insulin regular vial",
          "Blood culture bottle","Troponin cartridge","Blood gas cartridge","Drug-eluting stent","Guiding catheter",
          "Coronary guidewire 0.014","PTCA balloon","Introducer sheath 6F","Oxygen mask adult","Salbutamol nebule"}
CRIT_C = {"Adhesive tape roll","Alcohol swab","Ultrasound gel bottle","Loperamide capsule","Pressure-relief dressing",
          "Elastic bandage","X-ray cassette cover","Examination gloves"}

rows, use_rows = [], []
n = 0
for lst, cat, split in GROUPS:
    for name, unit, base in lst:
        n += 1
        iid = f"I{n:03d}"
        lab = cat == "Laboratory"
        cath = "Cath Lab" in split
        rows.append({
            "item_id": iid, "item_name": name, "category": cat, "unit": unit,
            "criticality": "A" if name in CRIT_A else ("C" if name in CRIT_C else "B"),
            "supply_channel": "FOC (ministry supply)" if lab else "Standard",
            "lead_time_days": 4 if lab else (3 if cath else 2),
            "normal_daily_use": base,
            "consuming_departments": ", ".join(split),
        })
        for d, share in split.items():
            use_rows.append((iid, d, base * share))
items = pd.DataFrame(rows)
base_use = pd.DataFrame(use_rows, columns=["item_id", "department", "base_daily"])

# -------------------------------------------------- daily consumption model
def simulate_demand(generator):
    out = []
    for _, r in base_use.iterrows():
        s = DEPT_SENS[r.department]
        for d, m in zip(mult["date"], mult["multiplier"]):
            f = 1 + (m - 1) * s
            out.append((d, r.department, r.item_id, int(generator.poisson(r.base_daily * f))))
    return pd.DataFrame(out, columns=["date", "department", "item_id", "quantity"])

consumption = simulate_demand(rng)

# ------------------------------------------------------- stock simulation
# Policy A "Baseline planning": reorder level and order-up-to level sized on a NORMAL day.
# Policy B "Surge-aware planning": same rules, but sized on the expected demand calendar.
exp_total = {}  # expected hospital-wide daily demand per item, per date
for iid, g in base_use.groupby("item_id"):
    exp = np.zeros(len(DAYS))
    for _, r in g.iterrows():
        exp += r.base_daily * (1 + (mult["multiplier"].values - 1) * DEPT_SENS[r.department])
    exp_total[iid] = exp

def run_policy(policy, demand_by_item):
    recs = []
    for _, it in items.iterrows():
        iid, L, base = it.item_id, int(it.lead_time_days), float(it.normal_daily_use)
        stock = base * 12                     # opening stock: 12 normal days (both policies)
        pipeline = {}                         # arrival day index -> qty
        for t, d in enumerate(DAYS):
            arrived = pipeline.pop(t, 0)
            stock += arrived
            opening = stock
            dem = int(demand_by_item[iid][t])
            issued = min(stock, dem)
            unmet = dem - issued
            stock -= issued
            outstanding = sum(pipeline.values())
            if policy == "A":
                rop = base * (L + 3)
                target = base * (L + 10)
            else:
                horizon_r = slice(t + 1, min(t + 1 + L + 2, len(DAYS)))
                horizon_t = slice(t + 1, min(t + 1 + L + 8, len(DAYS)))
                rop = max(base * (L + 3), exp_total[iid][horizon_r].sum())
                target = max(base * (L + 10), exp_total[iid][horizon_t].sum())
            ordered = 0
            if stock + outstanding <= rop:
                ordered = max(0, int(np.ceil(target - stock - outstanding)))
                if ordered > 0 and t + L < len(DAYS):
                    pipeline[t + L] = pipeline.get(t + L, 0) + ordered
            recs.append((policy, d, iid, int(round(opening)), dem, int(round(issued)), int(round(unmet)),
                         int(round(stock)), int(arrived), int(ordered)))
    return pd.DataFrame(recs, columns=["policy", "date", "item_id", "opening_stock", "demand",
                                       "issued", "unmet_demand", "closing_stock", "received", "ordered"])

demand_item = consumption.groupby(["item_id", "date"])["quantity"].sum().unstack().sort_index(axis=1)
dem_map = {i: demand_item.loc[i].values for i in demand_item.index}
sim = pd.concat([run_policy("A", dem_map), run_policy("B", dem_map)], ignore_index=True)
sim["policy"] = sim["policy"].map({"A": "Baseline planning", "B": "Surge-aware planning"})

# --------------------------------------------------------- Monte Carlo
mc = []
for k in range(200):
    g = np.random.default_rng(SEED + 1000 + k)
    dm = simulate_demand(g).groupby(["item_id", "date"])["quantity"].sum().unstack().sort_index(axis=1)
    dmap = {i: dm.loc[i].values for i in dm.index}
    for p, name in (("A", "Baseline planning"), ("B", "Surge-aware planning")):
        s = run_policy(p, dmap)
        tot, un = s["demand"].sum(), s["unmet_demand"].sum()
        mc.append((k, name, 1 - un / tot, int((s["unmet_demand"] > 0).sum()),
                   int(s[s.item_id.isin(items[items.criticality == "A"].item_id)]["unmet_demand"].gt(0).sum())))
mc = pd.DataFrame(mc, columns=["run", "policy", "fill_rate", "stockout_item_days", "stockout_item_days_critical"])
mc_summary = mc.groupby("policy").agg(
    fill_rate_mean=("fill_rate", "mean"), fill_rate_p5=("fill_rate", lambda s: s.quantile(.05)),
    stockout_item_days_mean=("stockout_item_days", "mean"),
    critical_stockout_item_days_mean=("stockout_item_days_critical", "mean")).round(4).reset_index()

# ----------------------------------------------------------------- save
items.to_csv("items.csv", index=False)
depts.to_csv("departments.csv", index=False)
mult.assign(date=mult["date"].dt.strftime("%Y-%m-%d")).to_csv("daily_multipliers.csv", index=False)
consumption.assign(date=consumption["date"].dt.strftime("%Y-%m-%d")).to_csv("daily_consumption.csv", index=False)
sim.assign(date=sim["date"].dt.strftime("%Y-%m-%d")).to_csv("stock_simulation.csv", index=False)
mc_summary.to_csv("monte_carlo_summary.csv", index=False)
print(len(items), "items |", len(consumption), "consumption rows |", len(sim), "stock rows")
print(mc_summary.to_string(index=False))
