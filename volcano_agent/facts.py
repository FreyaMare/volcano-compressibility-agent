"""Compact, rounded summary of the dataset and every computed result.

This is the ONLY numerical material the report writer sees, and the reference against
which the numbers in the written chapters are audited.
"""
from __future__ import annotations

import math
import re
from typing import Any

import numpy as np


def r3(x, sig=3):
    if x is None:
        return None
    try:
        x = float(x)
    except Exception:
        return x
    if not math.isfinite(x):
        return None
    if x == 0:
        return 0.0
    return float(f"{x:.{sig}g}")


def q(Q):
    return {"value": r3(Q.value), "range": [r3(Q.min), r3(Q.max)] if (Q.min is not None or Q.max is not None) else None,
            "status": Q.status, "source": Q.source, "note": Q.note}


def build_facts(ds, R) -> dict:
    res = R["res"]
    F: dict[str, Any] = {}
    F["volcano"] = dict(name=ds.name, country=ds.country, region=ds.region, type=ds.volcano_type,
                        tectonic_setting=ds.tectonic_setting, last_eruption=ds.last_eruption,
                        summit_elevation_m=q(ds.summit_elevation_m),
                        caldera_max_radius_km=q(ds.caldera_max_radius_km))
    F["inputs"] = dict(
        rho_crust=q(ds.rho_crust), mu_deep_GPa=q(ds.mu_deep_GPa), nu_deep=q(ds.nu_deep),
        mu_shallow_GPa=q(ds.mu_shallow_GPa), nu_shallow=q(ds.nu_shallow), dFMQ=q(ds.dFMQ),
        magmas=[dict(key=m.key, rock_type=m.rock_type, label=m.label, SiO2=r3(m.oxides["SIO2"]),
                     composition_status=m.composition_status, composition_source=m.composition_source,
                     evo_class=m.evo_class, T_C=q(m.T_C), H2O_wt=q(m.H2O_wt), CO2_wt=q(m.CO2_wt),
                     S_wt=q(m.S_wt), beta_liquid=r3(m.beta_liquid.value)) for m in ds.magmas],
        levels=[dict(name=L.name, depth_km=q(L.depth_km), published_pressure_MPa=q(L.pressure_MPa),
                     resident=L.resident, injected=L.injected, V0_m3=q(L.V0_m3), evidence=L.evidence)
                for L in ds.levels])
    s = ds.deformation_source
    if s is not None:
        F["published_source"] = dict(model=s.model, depth_km=q(s.depth_km), depth_reference=s.depth_reference,
                                     a_m=q(s.a_m), b_m=q(s.b_m), dip_deg=q(s.dip_deg), strike_deg=q(s.strike_deg),
                                     V0_m3=q(s.V0_m3), dV_m3=q(s.dV_m3), dP_MPa=q(s.dP_MPa), mu_GPa=q(s.mu_GPa),
                                     nu=q(s.nu), period=s.period, interpretation=s.interpretation, source=s.source,
                                     modelled_resident=s.resident, modelled_injected=s.injected,
                                     injected_volumes_m3=[r3(v) for v in res[res.family == "source"].iloc[0][["Ve1_m3", "Ve2_m3", "Ve3_m3"]]])
    else:
        F["published_source"] = None
    F["data_gaps"] = list(ds.data_gaps) + list(R.get("notes", []))
    F["n_generic_defaults"] = sum(1 for g in ds.data_gaps if "generic default" in g or "generic" in g)

    st = R["states"]
    F["magmatic_states"] = [dict(level=r.level, depth_km=r3(r.depth_km), P_MPa=r3(r.P_MPa), role=r.role,
                                 magma=r.magma, T_C=r3(r.T_C), P_sat_MPa=r3(r.P_sat_MPa),
                                 saturated=bool(r.saturated), phi_vol_pct=r3(100 * r.phi), gas_wt_pct=r3(100 * r.gas_wt))
                            for _, r in st.iterrows()]
    F["saturated_vapour"] = [dict(label=d["label"], magma=d["magma"], P_MPa=r3(d["P_MPa"]),
                                  phi_vol_pct=r3(100 * d["phi"]),
                                  species_mol_pct={k: r3(100 * v) for k, v in d["gas_species"].items() if v > 1e-4},
                                  fH2O_bar=r3(d["fH2O"]), fCO2_bar=r3(d["fCO2"]), fSO2_bar=r3(d["fSO2"]),
                                  fH2S_bar=r3(d["fH2S"]), rho_gas=r3(d["rho_gas"]), molar_mass_g=r3(1000 * d["gas_molmass"]),
                                  beta_m_frozen=r3(d["beta_m"]), beta_m_equilibrium=r3(d["beta_m_evo"]))
                             for d in R["saturated_detail"]]
    thin = R["thin_crack"].set_index("label")
    F["configurations"] = []
    for _, r in res.iterrows():
        d = dict(label=r.label, model=r.model, depth_km=r3(r.depth_km), pressure_depth_km=r3(r.zP_km),
                 resident=r.chamber, injected=r.intrusion, V0_m3=r3(r.V0_m3), P_MPa=r3(r.P_MPa),
                 phi_vol_pct=r3(100 * r.phi), beta_m=r3(r.beta_m), beta_c=r3(r.beta_c), beta_c_mu=r3(r.beta_c * r.mu_Pa),
                 rV=r3(r.rV), expressed_pct=r3(100 / r.rV),
                 Ve_m3=[r3(r.Ve1_m3), r3(r.Ve2_m3), r3(r.Ve3_m3)],
                 dVc_m3=[r3(r.dVc1_m3), r3(r.dVc2_m3), r3(r.dVc3_m3)],
                 uplift_mm_centre_1km_2km_smallest_Ve=[r3(r.uz1_0km_mm), r3(r.uz1_1km_mm), r3(r.uz1_2km_mm)],
                 uplift_mm_centre_1km_2km_largest_Ve=[r3(r.uz3_0km_mm), r3(r.uz3_1km_mm), r3(r.uz3_2km_mm)],
                 ratio_uz2km_to_centre=r3(r.uz3_2km_mm / r.uz3_0km_mm))
        if r.phi > 0:
            d.update(rV_equilibrium=r3(r.rV_eq), beta_m_equilibrium=r3(r.beta_m_eq),
                     uplift_mm_centre_largest_Ve_equilibrium=r3(r.uz3_0km_mm_eq))
        if r.label in thin.index:
            t = thin.loc[r.label]
            d.update(thin_crack_ratio=r3(t.ratio), a_over_d=r3(t.a_over_d), thin_crack_status=t.status)
        F["configurations"].append(d)
    F["inverse_for_target"] = dict(
        target_mm=R["target_mm"], screen_MPa=R["screen_MPa"],
        rows=[dict(label=d.label, branch=d.branch, rV=r3(d.rV), Ve_m3=r3(d.Ve), dVc_m3=r3(d.dVc), dP_MPa=r3(d.dP_MPa),
                   within_screen=bool(d.within_screen)) for _, d in R["inverse"].iterrows()])
    F["sensitivity"] = dict(
        scenario_b=[dict(level=r.level, depth_km=r3(r.depth_km), scenario=r.scenario, H2O_wt=r3(r.H2O_wt),
                         CO2_wt=r3(r.CO2_wt), H2O_multiplier=r3(r.H2O_multiplier), P_sat_MPa=r3(r.P_sat_MPa),
                         phi_vol_pct=r3(100 * r.phi), rV=r3(r.rV), uplift_centre_mm_largest_Ve=r3(r.uz_max_mm))
                    for _, r in R["scenario_b"].iterrows()],
        elastic=[dict(mu_GPa=r3(r.mu_GPa), nu=r3(r.nu), rV=r3(r.rV), uplift_centre_mm=r3(r.uz_max_mm))
                 for _, r in R["elastic"].iterrows()])
    for k in ("datum", "h2o_datum", "density", "redox", "aspect"):
        if k in R:
            F["sensitivity"][k] = [{c: (r3(v) if isinstance(v, (int, float, np.floating)) else v)
                                    for c, v in row.items()} for row in R[k].to_dict("records")]
    F["verification"] = [dict(test=v["test"], kind=v["kind"], agreement=v["agreement"]) for v in R["verification"]]
    F["consistency"] = [dict(test=v["test"], this=r3(v["this"]), published=r3(v["ref"]), agreement=v["agreement"])
                        for v in R["consistency"]]
    F["engine"] = R["engine"]
    return F


# ------------------------------------------------------------------------- number audit
_NUM = re.compile(r"(?<![A-Za-z_])[-−]?\d+(?:[.,]\d+)?(?:\s?[×x]\s?10\^?[-−]?\d+|[eE][-+]?\d+)?")


def _numbers_in(obj, out: set):
    if isinstance(obj, dict):
        for v in obj.values():
            _numbers_in(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numbers_in(v, out)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)) and obj is not None and math.isfinite(obj):
        out.add(float(obj))
    elif isinstance(obj, str):
        for m in _NUM.findall(obj):
            v = _parse(m)
            if v is not None:
                out.add(v)


def _parse(tok: str):
    t = tok.replace("−", "-").replace(",", "").replace(" ", "")
    m = re.match(r"^(-?\d+(?:\.\d+)?)(?:[×x]10\^?(-?\d+))$", t)
    try:
        if m:
            return float(m.group(1)) * 10 ** int(m.group(2))
        return float(t)
    except ValueError:
        return None


def audit_numbers(text: str, facts: dict) -> list[str]:
    """Return numbers in `text` that cannot be matched to any number in `facts`, allowing
    for the rounding implied by the number of digits written and for the unit changes
    % <-> fraction and km <-> m. A heuristic: it catches most invented numbers, not all."""
    ref: set = set()
    _numbers_in(facts, ref)
    ref_l = sorted(abs(v) for v in ref if v != 0)
    scal = (1, 100, 0.01, 1e3, 1e-3)
    bad = []
    for tok in _NUM.findall(text):
        v = _parse(tok)
        if v is None:
            continue
        a = abs(v)
        if a == 0 or (a <= 10 and float(a).is_integer()) or (1800 <= a <= 2100 and float(a).is_integer()):
            continue
        mant = re.split(r"[×xeE]", tok.replace(",", ""))[0]
        dec = len(mant.split(".")[1]) if "." in mant else 0
        mval = abs(_parse(mant) or a)
        tol = max(0.003, 0.5 * 10 ** (-dec) / mval) if mval else 0.003
        tol = min(tol, 0.06)
        if not any(abs(a / (r * s) - 1) <= tol for r in ref_l for s in scal):
            bad.append(tok)
    return list(dict.fromkeys(bad))
