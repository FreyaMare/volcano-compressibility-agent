"""Numerical experiments of the manuscript (Sections 6 and 7). From the repository root:

    python paper/experiments.py          # VOLCANO_AGENT_EVO_DIR=/path/to/EVo reuses an EVo checkout
    python paper/figures.py

Writes results.json (and, with figures.py, the figures) next to this file. No API key needed.
"""
import json, os, sys, time, copy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from volcano_agent.schema import Dataset, Q
from volcano_agent.defaults import finalize
from volcano_agent.chain import Analysis
from volcano_agent import physics as ph

OUT = os.path.dirname(os.path.abspath(__file__))
REF = Dataset.model_validate_json(open(os.path.join(ROOT, "volcano_agent", "reference", "lafossa.json")).read())

REF_RV = [2.600000, 2.466667, 2.333333, 11.939244, 3.381570, 22.988474, 200.992341,
          1.284984, 3.738892, 25.992391, 1.029156, 1.334071, 4.117585]
REF_UZ0 = [229.5504, 38.71337, 7.105131, 42.19532, 332.2557, 8.225651, 0.164682,
           744.7670, 49.11771, 1.266856, 598.4658, 123.5135, 7.835061]


def copy_ds(ds):
    return Dataset.model_validate(ds.model_dump())


def run(ds, use_evo=True):
    d = finalize(copy_ds(ds))
    an = Analysis(d, use_evo=use_evo)
    res = an.run()
    return d, an, res


R = {}

# ------------------------------------------------------------------ 0. regression + timing
ph_cache_engine = None
t0 = time.perf_counter()
d0, an0, res0 = run(REF)
t_cold = time.perf_counter() - t0
t0 = time.perf_counter()
full = an0.run_all()
t_full_warm = time.perf_counter() - t0
n_states = len(an0.engine.cache)
rel_rv = (res0.rV.values / np.array(REF_RV) - 1)
rel_uz = (res0.uz3_0km_mm.values / np.array(REF_UZ0) - 1)
R["regression"] = dict(labels=res0.label.tolist(), rv=res0.rV.tolist(), rv_ref=REF_RV,
                       uz=res0.uz3_0km_mm.tolist(), uz_ref=REF_UZ0,
                       max_rel_rv=float(np.max(np.abs(rel_rv))), max_rel_uz=float(np.max(np.abs(rel_uz))),
                       rel_rv=rel_rv.tolist(), rel_uz=rel_uz.tolist(),
                       rv_eq_source=float(res0.rV_eq.values[3]))
R["timing"] = dict(forward_chain_cold_s=t_cold, run_all_s=t_full_warm, evo_states_cached=n_states,
                   n_configs=len(res0))
R["verification"] = [{k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in x.items()}
                     for x in full["verification"] + full["consistency"]]

# ------------------------------------------------------------------ 1. value of literature data
def strip(ds, comp=False, volatiles=False, temp=False, source=False, levels=False, elastic=False):
    d = copy_ds(ds)
    for m in d.magmas:
        if comp:
            m.oxides = {}
            m.composition_status = "D"
        if volatiles:
            m.H2O_wt, m.CO2_wt, m.S_wt = Q(), Q(), Q()
        if temp:
            m.T_C = Q()
        m.beta_liquid = Q()
    if source:
        d.deformation_source = None
    if levels:
        d.levels = []
    if elastic:
        d.mu_deep_GPa, d.nu_deep, d.mu_shallow_GPa, d.nu_shallow, d.rho_crust, d.dFMQ = Q(), Q(), Q(), Q(), Q(), Q()
    return d

variants = [
    ("V0 thesis dataset (measured / adopted)", REF),
    ("V1 no melt-inclusion volatiles", strip(REF, volatiles=True)),
    ("V2 no volatiles, no temperatures", strip(REF, volatiles=True, temp=True)),
    ("V3 rock names only (generic compositions)", strip(REF, comp=True, volatiles=True, temp=True)),
]
vals = {}
for name, ds in variants:
    d, an, res = run(ds)
    vals[name] = dict(labels=res.label.tolist(), rv=res.rV.tolist(), rv_eq=res.rV_eq.tolist(),
                      uz=res.uz3_0km_mm.tolist(), phi=res.phi.tolist(), P_sat=res.P_sat_MPa.tolist(),
                      family=res.family.tolist(), model=res.model.tolist(), depth=res.depth_km.tolist(),
                      n_gaps=len(d.data_gaps),
                      inputs={m.key: dict(T=m.T_C.value, H2O=m.H2O_wt.value, CO2=m.CO2_wt.value, S=m.S_wt.value,
                                          SiO2=m.oxides["SIO2"], evo=m.evo_class, bl=m.beta_liquid.value)
                              for m in d.magmas})
R["value_of_data"] = vals

# ------------------------------------------------------------------ 2. extraction errors
def err(name, fn, kind):
    d = copy_ds(REF)
    fn(d)
    return (name, d, kind)

def set_q(q, v):
    q.value = v

errs = [
    err("H2O of rhyolite taken at range top (1.5 instead of 1.25 wt%)", lambda d: set_q(d.magma("RHYOLITE").H2O_wt, 1.5), "plausible"),
    err("H2O of rhyolite taken at range bottom (1.0 wt%)", lambda d: set_q(d.magma("RHYOLITE").H2O_wt, 1.0), "plausible"),
    err("CO2 decimal slip: 50 ppm entered as 0.05 wt% (x10)", lambda d: [set_q(d.magma(k).CO2_wt, 0.05) for k in ("RHYOLITE", "TRACHYTE", "LATITE")], "plausible"),
    err("CO2 unit slip: 50 ppm entered as 50 wt%", lambda d: [set_q(d.magma(k).CO2_wt, 50.0) for k in ("RHYOLITE", "TRACHYTE", "LATITE")], "out of range"),
    err("Temperatures entered in kelvin", lambda d: [set_q(m.T_C, m.T_C.value + 273.15) for m in d.magmas], "out of range"),
    err("Fe2O3(total) entered as FeO without conversion", lambda d: [m.oxides.__setitem__("FEO", m.oxides["FEO"] / 0.8998) for m in d.magmas], "plausible"),
    err("Spheroid semi-axes swapped (a = 59 m, b = 595 m)", lambda d: (set_q(d.deformation_source.a_m, 59.0), set_q(d.deformation_source.b_m, 595.0), set_q(d.deformation_source.aspect, 10.08)), "out of range"),
    err("Shallow shear modulus 10 GPa (intact) instead of 1 GPa (altered)", lambda d: (set_q(d.deformation_source.mu_GPa, 10.0), set_q(d.mu_shallow_GPa, 10.0)), "plausible"),
    err("Shear moduli given in Pa", lambda d: (set_q(d.deformation_source.mu_GPa, 1e9), set_q(d.mu_shallow_GPa, 1e9), set_q(d.mu_deep_GPa, 1e10)), "out of range"),
    err("Volume change published as negative (sign convention)", lambda d: set_q(d.deformation_source.dV_m3, -73108.0), "out of range"),
    err("Source depth 0.598 km read as 598 km", lambda d: set_q(d.deformation_source.depth_km, 598.0), "out of range"),
    err("Deep reservoir depth 12 km read as 1.2 km", lambda d: set_q(d.levels[2].depth_km, 1.2), "plausible"),
]
rows = []


def keyed(ds_final, res):
    """Key each configuration by (model, crack radius, level name) so that a level whose depth
    changed is still compared with itself; the published source is keyed as 'source'."""
    by_depth = {}
    for L in ds_final.levels:
        by_depth.setdefault(round(L.depth_km.value, 4), L.name)
    out = {}
    for _, r in res.iterrows():
        lev = "source" if r.family == "source" else by_depth.get(round(r.depth_km, 4), f"{r.depth_km:g} km")
        out[(r.model, None if r.penny_radius_km != r.penny_radius_km else r.penny_radius_km, lev)] = (r.rV, r.uz3_0km_mm)
    return out


base = keyed(d0, res0)
for name, d, kind in errs:
    dd, an, res = run(d)
    gaps_new = [g for g in dd.data_gaps if g not in d0.data_gaps]
    k = keyed(dd, res)
    common = [x for x in k if x in base]
    lost = [x for x in base if x not in k]
    drv = [abs(k[x][0] / base[x][0] - 1) for x in common]
    duz = [abs(k[x][1] / base[x][1] - 1) for x in common]
    s = res[res.family == "source"]
    rows.append(dict(error=name, kind=kind, flagged=bool(gaps_new), flags=gaps_new,
                     n_configs=len(res), n_common=len(common), n_lost=len(lost),
                     max_rel_rv=float(max(drv)) if drv else None, max_rel_uz=float(max(duz)) if duz else None,
                     median_rel_uz=float(np.median(duz)) if duz else None,
                     worst=str(common[int(np.argmax(duz))]) if duz else None,
                     src_rv=float(s.rV.iloc[0]) if len(s) else None,
                     src_uz=float(s.uz3_0km_mm.iloc[0]) if len(s) else None))
    r = rows[-1]
    print(f"{name[:62]:62s} flag={r['flagged']!s:5} lost={r['n_lost']} maxdRV={r['max_rel_rv']:.3g} "
          f"maxdUZ={r['max_rel_uz']:.3g} worst={r['worst']} src_rv={r['src_rv']}")
R["extraction_errors"] = rows
R["baseline"] = dict(src_rv=float(res0.rV.values[3]), src_uz=float(res0.uz3_0km_mm.values[3]))

# ------------------------------------------------------------------ 3. edge-case suite summary
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_edge_cases import CASES
from volcano_agent.pipeline import analyse_and_report
edge = []
for name, ds in CASES.items():
    t0 = time.perf_counter()
    rr = analyse_and_report(ds, write=False)
    dt = time.perf_counter() - t0
    res = rr.results["res"]
    edge.append(dict(case=name, n_configs=len(res), n_gaps=len(rr.dataset.data_gaps),
                     n_notes=len(rr.results.get("notes", [])), engines=sorted(set(e.split(";")[0] for e in res.engine)),
                     rv_min=float(res.rV.min()), rv_max=float(res.rV.max()), seconds=dt, pdf_kb=len(rr.pdf) / 1024))
R["edge_cases"] = edge

json.dump(R, open(os.path.join(OUT, "results.json"), "w"), indent=1, default=float)
print(json.dumps({k: R[k] for k in ("timing",)}, indent=1))
print("max rel rv", R["regression"]["max_rel_rv"], "max rel uz", R["regression"]["max_rel_uz"])
for e in edge: print(e)
