"""The seven-step chain applied to an arbitrary volcano, plus the inverse analysis,
geometric screens, verification checks and sensitivity analyses of the thesis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from . import physics as ph
from .schema import Dataset

DISTS_M = [0.0, 1000.0, 2000.0]
DEEP_VE = [1e6, 5e6, 1e7]


@dataclass
class Config:
    model: str                      # MOGI / YANG / PENNY
    family: str                     # "level" or "source"
    label: str
    depth_km: float                 # source depth below the model free surface
    zP_km: float                    # depth used for the lithostatic pressure
    resident: str
    injected: str
    V0: float
    Ve: List[float]
    mu: float
    nu: float
    penny_a_km: Optional[float] = None
    aspect: Optional[float] = None
    dip: Optional[float] = None
    strike: Optional[float] = None


def _penny_radii(ds: Dataset) -> List[float]:
    rmax = ds.caldera_max_radius_km.v(None)
    if rmax is None or rmax <= 0:
        return [0.5, 1.0, 2.0]
    radii = [r for r in (0.5, 1.0, 2.0, 4.0) if r <= rmax + 1e-9]
    return radii or [0.5]


def source_Ve(ds: Dataset) -> List[float]:
    src = ds.deformation_source
    dv = src.dV_m3.v(None) if src else None
    base = 10 ** math.ceil(math.log10(dv)) if dv and dv > 0 else 1e5
    return [base, 5 * base, 10 * base]


class Analysis:
    """Holds a finalised Dataset and runs every calculation of the thesis on it."""

    def __init__(self, ds: Dataset, use_evo: bool = True,
                 log: Callable[[str], None] | None = None):
        self.ds = ds
        self.log = log or (lambda s: None)
        self.engine = ph.VolatileEngine(use_evo=use_evo)
        if use_evo and not self.engine.use_evo:
            self.log("EVo could not be installed; using the analytic solubility fallback.")
        self.base = dict(
            rho=ds.rho_crust.value, g=9.81,
            mu_deep=ds.mu_deep_GPa.value * 1e9, nu_deep=ds.nu_deep.value,
            dFMQ=ds.dFMQ.value, src_zP_km=None, magma={},
            src_aspect=None, src_mu=None)

    # ------------------------------------------------------------------ magma state
    def magma_dict(self, key: str, P: dict) -> dict:
        m = self.ds.magma(key)
        d = dict(oxides=m.oxides, evo_class=m.evo_class, T_C=m.T_C.value, H2O_wt=m.H2O_wt.value,
                 CO2_wt=m.CO2_wt.value, S_wt=m.S_wt.value, beta_liquid=m.beta_liquid.value,
                 rho_melt=m.rho_melt)
        d.update(P.get("magma", {}).get(key, {}))
        return d

    def state(self, key: str, P_MPa: float, P: dict | None = None) -> dict:
        P = {**self.base, **(P or {})}
        return self.engine.state(self.magma_dict(key, P), P_MPa, P["dFMQ"])

    # ------------------------------------------------------------------ scenario matrix
    def configs(self, P: dict | None = None) -> List[Config]:
        P = {**self.base, **(P or {})}
        ds = self.ds
        out: List[Config] = []
        for L in ds.levels:
            z = L.depth_km.value
            out.append(Config("MOGI", "level", f"Mogi sphere, {z:g} km", z, z, L.resident, L.injected,
                              L.V0_m3.value, DEEP_VE, P["mu_deep"], P["nu_deep"]))
        src = ds.deformation_source
        if src is not None:
            z = src.depth_km.value
            zP = P["src_zP_km"] if P.get("src_zP_km") is not None else z
            mu = P["src_mu"] if P.get("src_mu") is not None else src.mu_GPa.value * 1e9
            c = Config(src.model, "source", "", z, zP, src.resident, src.injected,
                       src.V0_m3.value, source_Ve(ds), mu, src.nu.value)
            if src.model == "YANG":
                c.aspect = P["src_aspect"] or (src.aspect.v(None) or src.b_m.value / src.a_m.value)
                c.dip, c.strike = src.dip_deg.value, src.strike_deg.value
                c.label = "Published source geometry (prolate spheroid)"
            elif src.model == "PENNY":
                c.penny_a_km = src.a_m.value / 1e3
                c.label = "Published source geometry (penny crack)"
            else:
                c.label = "Published source geometry (sphere)"
            out.append(c)
        for a in _penny_radii(ds):
            for L in ds.levels:
                z = L.depth_km.value
                if a > z + 1e-9:          # crack wider than deep: outside the half-space solution
                    continue
                out.append(Config("PENNY", "level", f"Penny crack a = {a:g} km, {z:g} km", z, z,
                                  L.resident, L.injected, L.V0_m3.value, DEEP_VE,
                                  P["mu_deep"], P["nu_deep"], penny_a_km=a))
        return out

    # ------------------------------------------------------------------ one configuration
    def compute(self, c: Config, P: dict | None = None) -> dict:
        P = {**self.base, **(P or {})}
        d_m = c.depth_km * 1e3
        P_Pa = ph.pressure_Pa(c.zP_km, P["rho"], P["g"])                    # (1)
        mag = self.magma_dict(c.resident, P)
        st = self.engine.state(mag, P_Pa / 1e6, P["dFMQ"])                    # (2)
        phi = st["phi"]
        b_liq, b_gas = mag["beta_liquid"], ph.beta_gas(P_Pa)
        b_m = ph.beta_magma(phi, b_gas, b_liq)                                 # (3)
        b_eq = st["beta_m_evo"] if (phi > 0 and np.isfinite(st["beta_m_evo"])) else b_m
        if c.model == "MOGI":                                                  # (4)
            b_c = ph.beta_c_sphere(c.mu)
        elif c.model == "YANG":
            b_c = ph.beta_c_yang(c.V0, c.aspect, c.mu)
        else:
            b_c = ph.beta_c_penny(c.penny_a_km * 1e3, c.V0, d_m, c.mu, c.nu)
        rV = ph.rV_factor(b_m, b_c)                                            # (5)
        rV_eq = ph.rV_factor(b_eq, b_c)
        out = dict(model=c.model, family=c.family, label=c.label, penny_radius_km=c.penny_a_km,
                   depth_km=c.depth_km, zP_km=c.zP_km, chamber=c.resident, intrusion=c.injected,
                   V0_m3=c.V0, P_MPa=P_Pa / 1e6, T_C=mag["T_C"], engine=st["engine"],
                   saturated=st["saturated"], P_sat_MPa=st["P_sat_MPa"], phi=phi,
                   gas_wt=st["gas_wt"], beta_liquid=b_liq, beta_gas=b_gas, beta_m=b_m,
                   beta_m_eq=b_eq, beta_c=b_c, rV=rV, rV_eq=rV_eq, mu_Pa=c.mu, nu=c.nu,
                   aspect=c.aspect, dip=c.dip, strike=c.strike)
        unit = self.uplift(c, 1.0, DISTS_M)          # displacement per m3 of cavity change
        for k, Ve in enumerate(c.Ve, start=1):
            dVc = Ve / rV                                                      # (6)
            out[f"Ve{k}_m3"], out[f"dVc{k}_m3"] = Ve, dVc
            for dist, w in zip(DISTS_M, unit * dVc):                           # (7)
                out[f"uz{k}_{int(dist / 1000)}km_mm"] = w * 1e3
            out[f"uz{k}_0km_mm_eq"] = unit[0] * Ve / rV_eq * 1e3
        out["uz_per_dVc_mm"] = unit[0] * 1e3
        return out

    def uplift(self, c: Config, dVc: float, dists) -> np.ndarray:
        d_m = c.depth_km * 1e3
        if c.model == "MOGI":
            return ph.uplift_mogi(dVc, d_m, dists, c.nu)
        if c.model == "YANG":
            return ph.uplift_yang(dVc, c.V0, c.aspect, d_m, c.mu, c.nu, c.dip, c.strike, dists, 0.0)
        return ph.uplift_penny(dVc, c.penny_a_km * 1e3, d_m, c.mu, c.nu, dists)

    def run(self, P: dict | None = None) -> pd.DataFrame:
        cfgs = self.configs(P)
        return pd.DataFrame([self.compute(c, P) for c in cfgs])

    # ================================================================== full analysis
    def run_all(self, target_mm: float = 10.0, screen_MPa: float = 10.0,
                progress: Callable[[str], None] | None = None) -> dict:
        say = progress or self.log
        R: Dict[str, object] = {}
        say("Steps 1-7: forward chain for every configuration")
        res = self.run()
        R["res"] = res
        R["configs"] = self.configs()
        R["notes"] = self.model_notes(res)
        say("Magmatic state of every reservoir")
        R["states"] = self.states_table()
        R["saturated_detail"] = self.saturated_detail(res)
        say("Inverse analysis and screens")
        R["inverse"] = self.inverse(res, target_mm, screen_MPa)
        R["thin_crack"] = self.thin_crack(res)
        say("Verification against closed-form solutions")
        R["verification"] = self.verification()
        R["consistency"] = self.consistency()
        say("Sensitivity: volatile budget (Scenario B)")
        R["scenario_b"] = self.scenario_b()
        if self.ds.deformation_source is not None:
            say("Sensitivity: pressure datum and dissolved H2O of the shallow source")
            R["datum"] = self.datum_sensitivity()
            R["h2o_datum"] = self.h2o_datum_grid()
            R["density"] = self.density_sensitivity()
            R["redox"] = self.redox_sensitivity()
            if self.ds.deformation_source.model == "YANG":
                R["aspect"] = self.aspect_sensitivity()
        say("Sensitivity: elastic parameters")
        R["elastic"] = self.elastic_sensitivity()
        R["target_mm"], R["screen_MPa"] = target_mm, screen_MPa
        R["engine"] = "EVo" if self.engine.use_evo else "analytic fallback"
        return R

    def model_notes(self, res: pd.DataFrame) -> List[str]:
        """Caveats produced by the calculation itself (reported with the data gaps)."""
        notes = [f"Penny crack a = {a:g} km at {L.depth_km.value:g} km not modelled: the crack would be "
                 f"wider than it is deep (a/d > 1), outside the validity of the half-space solution."
                 for a in _penny_radii(self.ds) for L in self.ds.levels if a > L.depth_km.value + 1e-9]
        seen = set()
        for _, r in res.iterrows():
            key = (r.chamber, round(r.P_MPa, 2))
            if key in seen:
                continue
            seen.add(key)
            if r.engine.startswith("analytic"):
                notes.append(f"{r.chamber.capitalize()} at {r.P_MPa:.1f} MPa: EVo did not converge; the gas fraction "
                             "comes from the simple analytic solubility model (H2O square-root law, Henrian CO2).")
            elif ";" in r.engine:
                notes.append(f"{r.chamber.capitalize()} at {r.P_MPa:.1f} MPa (EVo): {r.engine.split(';', 1)[1].strip()}.")
            if r.phi > 0 and r.beta_m_eq < r.beta_m:
                notes.append(f"{r.label}: the equilibrium compressibility from the EVo density path is below the "
                             "frozen-phase value, because at this pressure the ideal-gas β_gas = 1/P of the frozen rule "
                             "overestimates the vapour compressibility (thesis Section 5.6.7); the frozen branch is "
                             "the upper bound here.")
        for _, r in res[res.model == "MOGI"].iterrows():
            radius = (3 * r.V0_m3 / (4 * np.pi)) ** (1 / 3)
            if radius / (r.depth_km * 1e3) > 0.4:
                notes.append(f"{r.label}: the equivalent sphere radius ({radius:.0f} m) exceeds 0.4 of its depth; "
                             "the point-source approximation is marginal (finite-source corrections of McTigue, 1987, "
                             "not applied).")
        return list(dict.fromkeys(notes))

    # ------------------------------------------------------------------ tables
    def states_table(self) -> pd.DataFrame:
        rows = []
        ds = self.ds
        levels = []
        if ds.deformation_source is not None:
            s = ds.deformation_source
            levels.append(("Published source level", s.depth_km.value, s.resident, s.injected))
        levels += [(L.name, L.depth_km.value, L.resident, L.injected) for L in ds.levels]
        for lab, z, rc, ic in levels:
            P = ph.pressure_Pa(z, self.base["rho"]) / 1e6
            for role, comp in (("resident", rc), ("injected", ic)):
                st = self.state(comp, P)
                rows.append(dict(level=lab, depth_km=z, P_MPa=P, role=role, magma=comp,
                                 T_C=self.ds.magma(comp).T_C.value, P_sat_MPa=st["P_sat_MPa"],
                                 saturated=st["saturated"], phi=st["phi"], gas_wt=st["gas_wt"]))
        return pd.DataFrame(rows)

    def saturated_detail(self, res: pd.DataFrame | None = None) -> List[dict]:
        out = []
        res = self.run() if res is None else res
        for _, r in res.iterrows():
            if r.phi > 0:
                st = self.state(r.chamber, r.P_MPa)
                d = {k: st.get(k) for k in ("P_MPa", "T_C", "P_sat_MPa", "phi", "gas_wt", "gas_molmass",
                                            "rho_gas", "rho_melt", "rho_bulk", "fO2_dFMQ", "fH2O",
                                            "fCO2", "fSO2", "fH2S", "fS2", "melt_H2O_wt",
                                            "melt_CO2_wt", "melt_S_wt", "beta_m_evo")}
                d["gas_species"] = st.get("gas_species", {})
                d["label"], d["magma"] = r.label, r.chamber
                d["beta_m"] = r.beta_m
                if not any(x["magma"] == d["magma"] and abs(x["P_MPa"] - d["P_MPa"]) < 1e-6 for x in out):
                    out.append(d)
        return out

    def inverse(self, res: pd.DataFrame, target_mm: float, screen_MPa: float) -> pd.DataFrame:
        rows = []
        for _, r in res.iterrows():
            dVc = target_mm / r.uz_per_dVc_mm
            for branch, rv, bm in (("frozen", r.rV, r.beta_m), ("equilibrium", r.rV_eq, r.beta_m_eq)):
                if branch == "equilibrium" and r.phi <= 0:
                    continue
                Ve = dVc * rv
                dP = dVc / (r.V0_m3 * r.beta_c) / 1e6
                rows.append(dict(label=r.label, model=r.model, family=r.family, depth_km=r.depth_km,
                                 penny_radius_km=r.penny_radius_km, branch=branch, rV=rv,
                                 Ve=Ve, dVc=dVc, dP_MPa=dP, within_screen=dP <= screen_MPa))
        return pd.DataFrame(rows).sort_values("Ve").reset_index(drop=True)

    def thin_crack(self, res: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, r in res[res.model == "PENNY"].iterrows():
            a = r.penny_radius_km * 1e3
            wbar = r.V0_m3 / (np.pi * a ** 2)
            ratio = wbar / (2 * a)
            ad = r.penny_radius_km / r.depth_km
            status = ("violated" if ratio > 0.1 else
                      ("satisfied; a/d >= 1" if ad >= 1.0 - 1e-9 else "clean on both criteria"))
            rows.append(dict(label=r.label, family=r.family, a_km=r.penny_radius_km,
                             depth_km=r.depth_km, V0=r.V0_m3, wbar=wbar, ratio=ratio, a_over_d=ad,
                             rV=r.rV, status=status))
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------ verification
    def verification(self) -> List[dict]:
        out = []
        mu, nu = 10e9, 0.25
        # 1. crack volume vs Sneddon full space, deep limit a/d = 0.1
        a, d = 500.0, 5000.0
        s, dP = ph.penny_source(a, d, mu, nu)
        sned = 8 * (1 - nu) * a ** 3 * dP / (3 * mu)
        out.append(dict(test="Crack ΔV vs Sneddon full-space solution, a/d = 0.1", kind="verification",
                        this=s.dV / sned, ref=1.0, agreement=f"{100 * abs(s.dV / sned - 1):.1f}%"))
        # 2. free-surface amplification at a/d = 1
        s1, dP1 = ph.penny_source(2000.0, 2000.0, mu, nu)
        amp = s1.dV / (8 * (1 - nu) * 2000.0 ** 3 * dP1 / (3 * mu))
        out.append(dict(test="Crack free-surface amplification, a/d = 1", kind="verification",
                        this=amp, ref=1.286, agreement=f"{100 * abs(amp / 1.286 - 1):.1f}% (thesis value 1.286)"))
        # 3. crack uplift vs point-sill limit 3 dV/(2 pi d^2)
        s2, dP2 = ph.penny_source(200.0, 5000.0, mu, nu)
        uz = ph.uplift_penny(s2.dV, 200.0, 5000.0, mu, nu, [0.0])[0]
        lim = 3 * s2.dV / (2 * np.pi * 5000.0 ** 2)
        out.append(dict(test="Crack central uplift vs point-sill limit (a/d = 0.04)", kind="verification",
                        this=uz / lim, ref=1.0, agreement=f"{100 * abs(uz / lim - 1):.1f}%"))
        # 4. spheroid A = 0.99 vs sphere
        V0 = 1e9
        bc = ph.beta_c_yang(V0, 0.99, mu) * mu
        out.append(dict(test="Spheroid β<sub>c</sub>·μ at A = 0.99 vs exact sphere 0.750", kind="verification",
                        this=bc, ref=0.75, agreement=f"{100 * (bc / 0.75 - 1):+.1f}%"))
        dV = 1e6
        uy = ph.uplift_yang(dV, V0, 0.99, 5000.0, mu, nu, 89.0, 0.0, [0.0])[0]
        um = ph.uplift_mogi(dV, 5000.0, [0.0], nu)[0]
        out.append(dict(test="Spheroid (A = 0.99) central uplift vs Mogi", kind="verification",
                        this=uy / um, ref=1.0, agreement=f"{100 * abs(uy / um - 1):.1f}%"))
        # 5. Mogi closed form
        out.append(dict(test="Mogi uplift at r = 0 vs (1−ν)ΔV/(πd²)", kind="verification",
                        this=float(ph.uplift_mogi(dV, 5000.0, [0.0], nu)[0] / ((1 - nu) * dV / (np.pi * 5000.0 ** 2))),
                        ref=1.0, agreement="exact"))
        return out

    def consistency(self) -> List[dict]:
        """Compare with the published pressure-volume mechanics of the deformation source."""
        src = self.ds.deformation_source
        out = []
        if src is None:
            return out
        mu = src.mu_GPa.value * 1e9
        z = src.depth_km.value * 1e3
        c = [x for x in self.configs() if x.family == "source"][0]
        if src.model == "YANG":
            bcmu = ph.beta_c_yang(c.V0, c.aspect, mu) * mu
        elif src.model == "MOGI":
            bcmu = 0.75
        else:
            bcmu = ph.beta_c_penny(c.penny_a_km * 1e3, c.V0, z, mu, c.nu) * mu
        dVp, dPp = src.dV_m3.v(None), src.dP_MPa.v(None)
        if dVp and dPp and src.mu_GPa.status != "D":
            bc_pub = mu * dVp / (c.V0 * dPp * 1e6)
            out.append(dict(test="β<sub>c</sub>·μ of the source vs value implied by published ΔV, ΔP, V<sub>0</sub>",
                            kind="consistency", this=bcmu, ref=bc_pub,
                            agreement=f"{100 * (bcmu / bc_pub - 1):+.1f}%"))
            dV_mine = bcmu / mu * c.V0 * dPp * 1e6
            out.append(dict(test=f"ΔV<sub>c</sub> at the published ΔP = {dPp:g} MPa", kind="consistency",
                            this=dV_mine, ref=dVp, agreement=f"{100 * (dV_mine / dVp - 1):+.1f}%"))
        if dVp:
            uz = self.uplift(c, dVp, [0.0, 1000.0, 2000.0]) * 1e3
            obs = src.observed_uplift_mm.v(None)
            out.append(dict(test="Uplift above the centroid for the published ΔV<sub>c</sub>", kind="consistency",
                            this=float(uz[0]), ref=obs if obs else float("nan"),
                            agreement=(f"{100 * (uz[0] / obs - 1):+.0f}% vs observed {obs:g} mm" if obs else
                                       f"{uz[0]:.1f} mm at centre, {uz[1]:.1f} mm at 1 km, {uz[2]:.2f} mm at 2 km")))
        return out

    # ------------------------------------------------------------------ sensitivities
    def scenario_b(self) -> pd.DataFrame:
        rows = []
        for L in self.ds.levels:
            z = L.depth_km.value
            m = self.ds.magma(L.resident)
            # graded trial multipliers of the thesis (Table 4.5), interpolated in depth:
            # 2 km x1.6/2.0/2.4, 5 km x2.8/3.2/3.6, 12 km x2.96/3.7/4.44
            f = [float(np.interp(z, [2.0, 5.0, 12.0], col))
                 for col in ([1.6, 2.8, 2.963], [2.0, 3.2, 3.704], [2.4, 3.6, 4.444])]
            co2 = [0.01, 0.02, 0.05] if z < 3.5 else ([0.05, 0.10, 0.15] if z < 8 else [0.20, 0.30, 0.40])
            trials = [("A", m.H2O_wt.value, m.CO2_wt.value)] + [
                (f"B{i + 1}", float(min(m.H2O_wt.value * fi, 7.0)), float(max(m.CO2_wt.value, ci)))
                for i, (fi, ci) in enumerate(zip(f, co2))]
            for tag, h, cc in trials:
                P = {"magma": {L.resident: {"H2O_wt": h, "CO2_wt": cc}}}
                c = [x for x in self.configs(P) if x.model == "MOGI" and x.family == "level" and x.depth_km == z][0]
                r = self.compute(c, P)
                rows.append(dict(level=L.name, depth_km=z, magma=L.resident, scenario=tag, H2O_wt=h,
                                 CO2_wt=cc, P_sat_MPa=r["P_sat_MPa"], phi=r["phi"], rV=r["rV"],
                                 uz_max_mm=r["uz3_0km_mm"], H2O_multiplier=h / m.H2O_wt.value))
        return pd.DataFrame(rows)

    def _datums(self):
        """Pressure datums of the shallow source. A depth below sea level under an edifice
        understates the real overburden (thesis Section 3.1.1); a depth already referred to the
        ground surface is bracketed by +/-0.2 km instead."""
        src = self.ds.deformation_source
        z = src.depth_km.value
        elev = self.ds.summit_elevation_m.v(None)
        ref = (src.depth_reference or "").lower()
        below_sea_level = ("sea" in ref or "b.s.l" in ref or "bsl" in ref or ref == "")
        if below_sea_level and elev and elev > 50:
            e = elev / 1000.0
            return [("model depth (sea-level datum)", z), ("half of the edifice load", z + 0.5 * e),
                    ("full edifice load", z + e)]
        lo = max(0.05, z - 0.2)
        return [("model depth", z), ("overburden −0.2 km", lo), ("overburden +0.2 km", z + 0.2)]

    def datum_sensitivity(self) -> pd.DataFrame:
        rows = []
        for lab, zP in self._datums():
            P = {"src_zP_km": zP}
            c = [x for x in self.configs(P) if x.family == "source"][0]
            r = self.compute(c, P)
            rows.append(dict(datum=lab, zP_km=zP, P_MPa=r["P_MPa"], P_sat_MPa=r["P_sat_MPa"], phi=r["phi"],
                             rV=r["rV"], rV_eq=r["rV_eq"], uz_max_mm=r["uz3_0km_mm"],
                             uz_max_mm_eq=r["uz3_0km_mm_eq"], Ve_max=r["Ve3_m3"]))
        return pd.DataFrame(rows)

    def h2o_datum_grid(self) -> pd.DataFrame:
        src = self.ds.deformation_source
        m = self.ds.magma(src.resident)
        rows = []
        for f in (0.8, 1.0, 1.2):
            h = m.H2O_wt.value * f
            for lab, zP in self._datums():
                P = {"src_zP_km": zP, "magma": {src.resident: {"H2O_wt": h}}}
                c = [x for x in self.configs(P) if x.family == "source"][0]
                r = self.compute(c, P)
                rows.append(dict(H2O_wt=h, datum=lab, zP_km=zP, P_MPa=r["P_MPa"], P_sat_MPa=r["P_sat_MPa"],
                                 phi=r["phi"], rV=r["rV"], rV_eq=r["rV_eq"], uz_max_mm=r["uz3_0km_mm"],
                                 uz_max_mm_eq=r["uz3_0km_mm_eq"]))
        return pd.DataFrame(rows)

    def density_sensitivity(self) -> pd.DataFrame:
        rows = []
        for rho in (2300.0, 2500.0, 2700.0):
            P = {"rho": rho}
            c = [x for x in self.configs(P) if x.family == "source"][0]
            r = self.compute(c, P)
            rows.append(dict(rho=rho, P_MPa=r["P_MPa"], phi=r["phi"], rV=r["rV"], uz_max_mm=r["uz3_0km_mm"]))
        return pd.DataFrame(rows)

    def redox_sensitivity(self) -> pd.DataFrame:
        rows = []
        src = self.ds.deformation_source
        for d in (self.base["dFMQ"] - 1, self.base["dFMQ"], self.base["dFMQ"] + 1):
            P = {"dFMQ": d}
            c = [x for x in self.configs(P) if x.family == "source"][0]
            zP = c.zP_km
            st = self.state(src.resident, ph.pressure_Pa(zP, self.base["rho"]) / 1e6, P)
            rows.append(dict(dFMQ=d, phi=st["phi"], fSO2=st["fSO2"], fH2S=st["fH2S"]))
        return pd.DataFrame(rows)

    def aspect_sensitivity(self) -> pd.DataFrame:
        rows = []
        base = [x for x in self.configs() if x.family == "source"][0].aspect
        for A in sorted({round(base, 4), 0.2, 0.3, 0.5, 0.99}):
            P = {"src_aspect": A}
            c = [x for x in self.configs(P) if x.family == "source"][0]
            r = self.compute(c, P)
            rows.append(dict(aspect=A, beta_c_mu=r["beta_c"] * r["mu_Pa"], rV=r["rV"]))
        return pd.DataFrame(rows)

    def elastic_sensitivity(self) -> pd.DataFrame:
        rows = []
        L = self.ds.levels[0]
        z = L.depth_km.value
        for mu in (5e9, 10e9, 20e9, 40e9):
            for nu in (0.15, 0.25, 0.35):
                P = {"mu_deep": mu, "nu_deep": nu}
                c = [x for x in self.configs(P) if x.model == "MOGI" and x.family == "level" and x.depth_km == z][0]
                r = self.compute(c, P)
                rows.append(dict(level=L.name, mu_GPa=mu / 1e9, nu=nu, rV=r["rV"], uz_max_mm=r["uz3_0km_mm"],
                                 dP_for_target=None))
        return pd.DataFrame(rows)
