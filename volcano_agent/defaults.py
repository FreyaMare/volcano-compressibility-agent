"""Generic defaults and the `finalize()` step that turns a researched dataset into a
complete, runnable one.

Anything filled in here is marked with status "D" and listed in `Dataset.data_gaps`,
so the report can say exactly which numbers are not constrained for this volcano.
"""
from __future__ import annotations

import math
from typing import Optional

from .schema import OXIDES, Dataset, Level, Magma, Q

# --------------------------------------------------------------------------------------
# Approximate global average compositions by rock type (anhydrous wt%, FeO = total iron),
# rounded from the averages compiled by Le Maitre (1976). They are used ONLY when no
# analysis of the volcano's own products was found, and are always flagged "D".
# --------------------------------------------------------------------------------------
GENERIC_COMPOSITIONS = {
    "basalt":            dict(SIO2=49.2, TIO2=1.84, AL2O3=15.7, FEO=10.5, MNO=0.20, MGO=6.7, CAO=9.5, NA2O=2.9, K2O=1.1, P2O5=0.35),
    "trachybasalt":      dict(SIO2=49.2, TIO2=2.40, AL2O3=16.6, FEO=9.5, MNO=0.16, MGO=5.2, CAO=7.9, NA2O=4.0, K2O=2.6, P2O5=0.59),
    "basaltic andesite": dict(SIO2=54.0, TIO2=1.00, AL2O3=17.0, FEO=8.5, MNO=0.15, MGO=4.5, CAO=8.0, NA2O=3.3, K2O=1.2, P2O5=0.25),
    "shoshonite":        dict(SIO2=53.8, TIO2=0.70, AL2O3=15.1, FEO=8.2, MNO=0.16, MGO=4.7, CAO=7.7, NA2O=3.6, K2O=4.9, P2O5=0.39),
    "andesite":          dict(SIO2=57.9, TIO2=0.87, AL2O3=17.0, FEO=7.0, MNO=0.14, MGO=3.3, CAO=6.8, NA2O=3.5, K2O=1.6, P2O5=0.21),
    "latite":            dict(SIO2=58.2, TIO2=1.08, AL2O3=16.7, FEO=6.1, MNO=0.16, MGO=2.6, CAO=5.0, NA2O=4.4, K2O=3.2, P2O5=0.41),
    "phonolite":         dict(SIO2=56.2, TIO2=0.62, AL2O3=19.0, FEO=4.5, MNO=0.17, MGO=1.1, CAO=2.7, NA2O=7.8, K2O=5.2, P2O5=0.18),
    "trachyte":          dict(SIO2=61.2, TIO2=0.70, AL2O3=17.0, FEO=5.0, MNO=0.15, MGO=0.9, CAO=2.3, NA2O=5.5, K2O=5.0, P2O5=0.21),
    "dacite":            dict(SIO2=65.0, TIO2=0.58, AL2O3=15.9, FEO=4.5, MNO=0.09, MGO=1.8, CAO=4.3, NA2O=3.8, K2O=2.2, P2O5=0.15),
    "rhyolite":          dict(SIO2=72.8, TIO2=0.28, AL2O3=13.3, FEO=2.4, MNO=0.06, MGO=0.4, CAO=1.1, NA2O=3.6, K2O=4.3, P2O5=0.07),
}
_ALIASES = {"trachyandesite": "latite", "basaltic trachyandesite": "shoshonite",
            "tephrite": "trachybasalt", "phonotephrite": "trachybasalt",
            "tephriphonolite": "phonolite", "comendite": "rhyolite", "pantellerite": "rhyolite",
            "rhyodacite": "dacite", "benmoreite": "latite", "mugearite": "trachybasalt",
            "hawaiite": "trachybasalt", "picrite": "basalt", "foidite": "trachybasalt"}

METHOD_REFS = {
    "beta_liquid": "Spera (2000); Rivalta and Segall (2008)",
    "elastic": "Heap et al. (2020)",
}


def generic_composition(rock_type: str) -> Optional[dict]:
    rt = (rock_type or "").lower().strip()
    rt = _ALIASES.get(rt, rt)
    if rt in GENERIC_COMPOSITIONS:
        return dict(GENERIC_COMPOSITIONS[rt])
    for k in GENERIC_COMPOSITIONS:            # "high-K basalt" -> basalt
        if k in rt:
            return dict(GENERIC_COMPOSITIONS[k])
    return None


def evo_class(sio2: float) -> str:
    """Burgisser et al. (2015) solubility class used by EVo, by SiO2 validity range:
    basalt 45-55, phonolite 52-63, rhyolite 65-80 wt%. The 63-65 gap goes to the
    nearer class. Same rule as the thesis (Section 4.1.1)."""
    if sio2 < 55.0:          # 52-55 is the basalt/phonolite overlap: basalt, as in the thesis
        return "basalt"
    if sio2 < 64.0:          # 63-64 lies in the gap, nearer the phonolite class
        return "phonolite"
    return "rhyolite"


def beta_liquid_default(sio2: float) -> float:
    """Melt compressibility decreasing towards mafic, hotter liquids, within the
    (0.5-2)e-10 Pa^-1 interval (Spera 2000; Rivalta & Segall 2008). Reproduces the
    thesis values: rhyolite 1.2, trachyte 1.1, latite 1.0, shoshonite 0.8 (x1e-10)."""
    if sio2 >= 68:
        return 1.2e-10
    if sio2 >= 60:
        return 1.1e-10
    if sio2 >= 55:
        return 1.0e-10
    if sio2 >= 50:
        return 0.8e-10
    return 0.7e-10


def rho_melt_default(sio2: float) -> float:
    return float(min(2750, max(2250, 2300 + (73.5 - sio2) * 12.0)))


def T_default(sio2: float) -> float:
    """Rough liquidus-type trend: ~1185 C for basalt, ~1000 C for rhyolite."""
    return float(round(1185 - (sio2 - 48.0) * 7.3, -1))


_OXIDE_ALIASES = {"FEOT": "FEO", "FEO*": "FEO", "FEOTOT": "FEO", "FEOTOTAL": "FEO", "FEO(T)": "FEO",
                  "FE2O3T": "FE2O3", "FE2O3*": "FE2O3", "FE2O3TOT": "FE2O3", "FE2O3TOTAL": "FE2O3",
                  "FE2O3(T)": "FE2O3", "P2O5": "P2O5", "SIO2": "SIO2"}


def _num(v) -> Optional[float]:
    """Coerce a value from the agent or an edited table to float (None if impossible)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    import re
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(v).replace(",", "."))
    return float(m.group(0)) if m else None


def _sane(q: Q, lo: float, hi: float, what: str, gaps: list):
    """Discard a value outside its physically plausible range (it is then defaulted)."""
    if q is not None and q.value is not None and not (lo <= q.value <= hi):
        gaps.append(f"{what} = {q.value:g} is outside the plausible range {lo:g}-{hi:g} and was discarded.")
        q.value = None


def _fill(q: Q, value: float, note: str, gaps: list, what: str, source: str = "") -> Q:
    if q is None:
        q = Q()
    if q.value is None:
        q.value = float(value)
        q.status = "D"
        q.note = (q.note + " " if q.note else "") + note
        if source:
            q.source = source
        gaps.append(f"{what}: no published value found; generic default {value:g} used ({note}).")
    return q


def finalize(ds: Dataset) -> Dataset:
    """Fill every missing input with a flagged default and check internal consistency."""
    gaps = list(ds.data_gaps)

    # ---------------------------------------------------------------- crust & elasticity
    _sane(ds.rho_crust, 1800, 3300, "Crustal density (kg/m3)", gaps)
    for q, lab in ((ds.mu_deep_GPa, "Deep shear modulus (GPa)"), (ds.mu_shallow_GPa, "Shallow shear modulus (GPa)")):
        if q.value is not None and q.value > 1e3:                # given in Pa
            gaps.append(f"{lab}: {q.value:g} read as pascal and converted to {q.value / 1e9:g} GPa.")
            q.value = q.value / 1e9
        _sane(q, 0.05, 100, lab, gaps)
    _sane(ds.nu_deep, 0.01, 0.49, "Deep Poisson ratio", gaps)
    _sane(ds.nu_shallow, 0.01, 0.49, "Shallow Poisson ratio", gaps)
    _sane(ds.dFMQ, -3, 4, "Oxygen fugacity (dFMQ)", gaps)
    ds.rho_crust = _fill(ds.rho_crust, 2500, "mean crustal density, plausible range 2300-2700 kg/m3", gaps, "Crustal density")
    ds.mu_deep_GPa = _fill(ds.mu_deep_GPa, 10.0, "intact-rock end of the 1-10 GPa range of Heap et al. (2020)", gaps, "Deep shear modulus", METHOD_REFS["elastic"])
    ds.nu_deep = _fill(ds.nu_deep, 0.25, "standard Poisson ratio for crustal rock", gaps, "Deep Poisson ratio")
    ds.mu_shallow_GPa = _fill(ds.mu_shallow_GPa, 1.0, "damaged / hydrothermally altered rock (Heap et al. 2020)", gaps, "Shallow shear modulus", METHOD_REFS["elastic"])
    ds.nu_shallow = _fill(ds.nu_shallow, 0.35, "altered shallow rock", gaps, "Shallow Poisson ratio")
    arc = "arc" in (ds.tectonic_setting or "").lower() or "subduction" in (ds.tectonic_setting or "").lower()
    ds.dFMQ = _fill(ds.dFMQ, 1.0 if arc else 0.0,
                    "oxidised arc magma" if arc else "moderately reduced, non-arc magma", gaps, "Oxygen fugacity (dFMQ)")
    ds.summit_elevation_m = ds.summit_elevation_m or Q()

    # ---------------------------------------------------------------- magmas
    for m in ds.magmas:
        m.key = m.key.upper().replace(" ", "_")
        comp = {}
        for k, v in (m.oxides or {}).items():
            fv = _num(v)
            if fv is None:
                continue
            kk = _OXIDE_ALIASES.get(k.upper().replace(" ", "").replace("_", ""), k.upper())
            comp[kk] = comp.get(kk, 0.0) + fv
        if "FE2O3" in comp and "FEO" not in comp:          # all iron as Fe2O3 -> FeO(tot)
            comp["FEO"] = 0.8998 * comp.pop("FE2O3")
        elif "FE2O3" in comp and "FEO" in comp:
            comp["FEO"] = comp["FEO"] + 0.8998 * comp.pop("FE2O3")
        comp = {k: comp.get(k, 0.0) for k in OXIDES}
        if comp["SIO2"] > 0 and (sum(comp.values()) < 85.0 or sum(1 for v in comp.values() if v > 0) < 7):
            gaps.append(f"{m.key.capitalize()}: the published analysis found is incomplete "
                        f"(total {sum(comp.values()):.1f} wt%); a generic composition is used instead.")
            comp["SIO2"] = 0.0
        if comp["SIO2"] <= 0:
            g = generic_composition(m.rock_type or m.key)
            if g is None:
                g = generic_composition("andesite")
            comp = g
            m.composition_status = "D"
            m.composition_source = "Generic average composition (approx. Le Maitre, 1976)"
            gaps.append(f"{m.key.capitalize()}: no whole-rock analysis found; generic {m.rock_type or 'andesite'} composition used.")
        s = sum(comp.values())
        if not (97.0 <= s <= 101.5):                       # e.g. analyses including LOI/H2O
            comp = {k: v * 100.0 / s for k, v in comp.items()}
            m.composition_source += f" [renormalised anhydrous from total {s:.2f}]"
        m.oxides = comp
        sio2 = comp["SIO2"]
        m.evo_class = evo_class(sio2)
        m.rho_melt = rho_melt_default(sio2)
        nm = m.key.capitalize()
        tdef = T_default(sio2)
        t = m.T_C.value
        if t is not None and 1200 <= t < 1800 and (t > 1300 or (t - tdef > 120 and abs(t - 273.15 - tdef) < abs(t - tdef))):
            # almost certainly a temperature in kelvin
            gaps.append(f"{nm} temperature {m.T_C.value:g} read as kelvin and converted to °C.")
            m.T_C.value = round(m.T_C.value - 273.15, 1)
        if m.T_C.value is not None and not (650 <= m.T_C.value <= 1350):
            gaps.append(f"{nm} temperature {m.T_C.value:g} °C is implausible and was discarded.")
            m.T_C.value = None
        m.T_C = _fill(m.T_C, T_default(sio2), "SiO2-temperature trend", gaps, f"{nm} temperature")
        m.H2O_wt = _fill(m.H2O_wt, 1.5, "no melt-inclusion data", gaps, f"{nm} H2O")
        m.CO2_wt = _fill(m.CO2_wt, 0.01, "no melt-inclusion data", gaps, f"{nm} CO2")
        m.S_wt = _fill(m.S_wt, 0.05, "no melt-inclusion data", gaps, f"{nm} S")
        if m.beta_liquid is None or m.beta_liquid.value is None:
            m.beta_liquid = Q(value=beta_liquid_default(sio2), status="A",
                              source=METHOD_REFS["beta_liquid"],
                              note="adopted by composition within (0.5-2)e-10 Pa^-1")
        # plausibility clamps (EVo needs strictly positive budgets)
        for q, lo, hi, lab in ((m.H2O_wt, 0.01, 8.0, "H2O"), (m.CO2_wt, 1e-4, 2.0, "CO2"), (m.S_wt, 1e-4, 1.0, "S")):
            if q.value < lo or q.value > hi:
                old = q.value
                q.value = min(max(q.value, lo), hi)
                gaps.append(f"{nm} {lab} = {old:g} wt% outside the plausible range; clamped to {q.value:g}.")

    if not ds.magmas:
        names = []
        for L in ds.levels:
            names += [x for x in (L.resident, L.injected) if x]
        names = list(dict.fromkeys(n.upper().replace(" ", "_") for n in names)) or ["BASALT", "ANDESITE"]
        gaps.append("No magma types were found; generic compositions are used for " + ", ".join(names) + ".")
        ds.magmas = [Magma(key=n, rock_type=n.lower().replace("_", " ")) for n in names]
        ds.data_gaps = gaps
        return finalize(ds)
    keys = {m.key for m in ds.magmas}
    by_sio2 = sorted(ds.magmas, key=lambda m: m.oxides["SIO2"])
    most_evolved, most_mafic = by_sio2[-1].key, by_sio2[0].key

    def _next_mafic(key):
        order = [m.key for m in by_sio2]
        i = order.index(key)
        return order[i - 1] if i > 0 else order[0]

    # ---------------------------------------------------------------- storage levels
    if not ds.levels:
        gaps.append("No published storage levels found: generic levels at 3, 6 and 10 km are used.")
        mags = [m.key for m in reversed(by_sio2)]
        for i, z in enumerate((3.0, 6.0, 10.0)):
            res = mags[min(i, len(mags) - 1)]
            ds.levels.append(Level(name=f"Generic level {z:g} km", depth_km=Q(value=z, status="D"),
                                   resident=res, injected=_next_mafic(res)))
    good, seen = [], set()
    for L in sorted(ds.levels, key=lambda L: L.depth_km.v(0) or 0):
        z = L.depth_km.value
        if z is None or not (0.2 <= z <= 40.0):
            gaps.append(f"Storage level '{L.name}' has no usable depth ({z}); it was not modelled.")
            continue
        if round(z, 2) in seen:
            gaps.append(f"Storage level '{L.name}' duplicates the depth {z:g} km of another level; it was not modelled.")
            continue
        seen.add(round(z, 2))
        good.append(L)
    if not good:
        gaps.append("No usable storage depth: generic levels at 3, 6 and 10 km are used.")
        mags = [m.key for m in reversed(by_sio2)]
        good = [Level(name=f"Generic level {z:g} km", depth_km=Q(value=z, status="D"),
                      resident=mags[min(i, len(mags) - 1)], injected="") for i, z in enumerate((3.0, 6.0, 10.0))]
    ds.levels = good[:4]
    rho = ds.rho_crust.value or 2500.0
    for L in ds.levels:
        P = L.pressure_MPa.value
        if P is not None and P > 0:
            z_from_P = P * 1e6 / (rho * 9.81) / 1e3
            ratio = L.depth_km.value / z_from_P
            if not (1 / 1.6 <= ratio <= 1.6):
                gaps.append(f"Storage level '{L.name}': depth {L.depth_km.value:g} km is inconsistent with its published "
                            f"pressure {P:g} MPa (≈{z_from_P:.1f} km at ρ = {rho:g} kg/m3); check both values in the source.")
    for L in ds.levels:
        L.resident = (L.resident or "").upper().replace(" ", "_")
        L.injected = (L.injected or "").upper().replace(" ", "_")
        if L.resident not in keys:
            L.resident = most_evolved if (L.depth_km.v(0) or 0) < 4 else most_mafic
        if L.injected not in keys:
            L.injected = _next_mafic(L.resident)
        z = L.depth_km.v(5.0)
        # thesis convention: initial volume grows with depth (5e8, 5e9, 5e10 m3)
        default_V0 = 5e8 if z < 3.5 else (5e9 if z < 8.0 else 5e10)
        L.V0_m3 = _fill(L.V0_m3, default_V0, "scenario volume growing with depth, as in the La Fossa scheme",
                        gaps, f"{L.name} reservoir volume")

    # ---------------------------------------------------------------- published source
    src = ds.deformation_source
    if src is not None and (src.depth_km.value is None or not (0.05 <= src.depth_km.value <= 20.0)):
        gaps.append(f"The published deformation source has no usable depth ({src.depth_km.value}); it was not modelled.")
        src = None
    if src is not None:
        src.resident = (src.resident or "").upper().replace(" ", "_")
        if src.resident not in keys:
            src.resident = most_evolved
        src.injected = (src.injected or "").upper().replace(" ", "_")
        if src.injected not in keys:
            src.injected = _next_mafic(src.resident)
        if src.mu_GPa.value is not None and src.mu_GPa.value > 1e3:
            gaps.append(f"Source shear modulus {src.mu_GPa.value:g} read as pascal and converted to "
                        f"{src.mu_GPa.value / 1e9:g} GPa.")
            src.mu_GPa.value /= 1e9
        _sane(src.mu_GPa, 0.05, 100, "Source shear modulus (GPa)", gaps)
        _sane(src.nu, 0.01, 0.49, "Source Poisson ratio", gaps)
        src.mu_GPa = src.mu_GPa if src.mu_GPa.value is not None else Q(**ds.mu_shallow_GPa.model_dump())
        src.nu = src.nu if src.nu.value is not None else Q(**ds.nu_shallow.model_dump())
        for q in (src.dV_m3, src.dP_MPa):                  # deflation episodes are published as negative
            if q.value is not None and q.value < 0:
                gaps.append(f"Published source: a negative value ({q.value:g}) was read as a deflation "
                            "episode; its magnitude is used.")
                q.value = abs(q.value)
                q.note = (q.note + " " if q.note else "") + "published as negative (deflation); magnitude used"
        for q in (src.a_m, src.b_m, src.V0_m3, src.dV_m3, src.dP_MPa, src.aspect):
            if q.value is not None and q.value <= 0:
                q.value, q.status = None, "D"
        d_m = src.depth_km.value * 1e3
        if src.model == "YANG":
            a, b, A, V0 = src.a_m.value, src.b_m.value, src.aspect.value, src.V0_m3.value
            if a is not None and b is not None and b > a:                # semi-axes swapped
                gaps.append(f"Published spheroid: semi-minor axis ({b:g} m) larger than semi-major axis "
                            f"({a:g} m); the two were swapped.")
                src.a_m, src.b_m = src.b_m, src.a_m
                a, b = b, a
            if A is not None and A > 1:
                gaps.append(f"Published spheroid: aspect ratio {A:g} > 1 read as a/b and inverted to {1 / A:.3g}.")
                A = 1.0 / A
            if A is None:
                A = b / a if (a and b) else None
            if A is None:
                A = 0.3
                gaps.append("Published spheroidal source: aspect ratio unknown; 0.3 assumed.")
            A = min(max(A, 0.02), 0.99)
            src.aspect = Q(value=A, status=src.aspect.status if src.aspect.value else "A",
                           source=src.aspect.source or src.source, note=src.aspect.note)
            if a is None and V0 is None:
                gaps.append("Published spheroidal source lacks both size and volume; it was not modelled.")
                src = None
            else:
                if a is None:
                    a = (3 * V0 / (4 * math.pi * A * A)) ** (1 / 3)
                    src.a_m = Q(value=a, status="A", note="from the published volume and aspect ratio")
                if src.b_m.value is None:
                    src.b_m = Q(value=A * a, status="A", note="from the aspect ratio")
                if V0 is None:
                    src.V0_m3 = Q(value=4 / 3 * math.pi * a * src.b_m.value ** 2, status="A",
                                  note="(4/3) pi a b^2 from the published semi-axes")
                src.dip_deg = _fill(src.dip_deg, 89.0, "vertical spheroid assumed", gaps, "Source plunge")
                src.strike_deg = _fill(src.strike_deg, 0.0, "azimuth unknown", gaps, "Source azimuth")
                src.dip_deg.value = min(max(src.dip_deg.value, 1.0), 89.99)
                if a * math.sin(math.radians(src.dip_deg.value)) >= d_m:
                    gaps.append("The published spheroid reaches the free surface (a·sin(plunge) ≥ depth): "
                                "the Yang solution is outside its range of validity; treat its results with caution.")
        elif src.model == "MOGI":
            if src.V0_m3.value is None:
                r = src.a_m.v(None)
                if r is not None:
                    src.V0_m3 = Q(value=4 / 3 * math.pi * r ** 3, status="A", note="from the published radius")
                else:
                    src.V0_m3 = Q(value=5e7, status="D", note="no radius published")
                    gaps.append("Published spherical source: no radius; V0 = 5e7 m3 assumed.")
        elif src.model == "PENNY":
            if src.a_m.value is None:
                src.a_m = Q(value=min(500.0, 0.5 * d_m), status="D", note="radius unknown")
                gaps.append(f"Published crack source: radius unknown; {src.a_m.value:g} m assumed.")
            if src.V0_m3.value is None:
                a = src.a_m.value
                src.V0_m3 = Q(value=math.pi * a * a * (0.1 * a), status="D",
                              note="thin sill with mean opening 0.1a (w/2a = 0.05)")
    ds.deformation_source = src
    ds.data_gaps = list(dict.fromkeys(gaps))
    return ds
