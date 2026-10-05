"""Physics engine of the seven-step chain, generalised from the La Fossa thesis notebook
(github.com/FreyaMare/lafossa-magma-compressibility, release v1.0.0).

The numerics are unchanged from the notebook; what changed is that compositions,
volatile budgets and elastic parameters are no longer hard-wired to Vulcano but come
from a `Dataset`. Running the engine on the La Fossa reference dataset reproduces the
thesis results to machine precision (tests/test_lafossa_regression.py).
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

R_GAS = 8.314
EVO_REPO = "https://github.com/pipliggins/EVo.git"
EVO_COMMIT = "2487939e18d98292f9b8f3a1f0dea04b707bd89f"   # the commit used for the thesis


# ======================================================================================
# EVo installation (cloned once, pinned to the thesis commit)
# ======================================================================================
def ensure_evo(evo_dir: str | None = None) -> str:
    """Make EVo importable; clone it at the pinned commit if needed. Returns its path."""
    evo_dir = evo_dir or os.environ.get("VOLCANO_AGENT_EVO_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "volcano_agent", "EVo")
    if not os.path.isdir(os.path.join(evo_dir, "src", "evo")):
        os.makedirs(os.path.dirname(evo_dir), exist_ok=True)
        subprocess.run(["git", "clone", "-q", EVO_REPO, evo_dir], check=True)
        subprocess.run(["git", "-C", evo_dir, "checkout", "-q", EVO_COMMIT], check=True)
    src = os.path.abspath(os.path.join(evo_dir, "src"))
    if src not in sys.path:
        sys.path.insert(0, src)
    import evo  # noqa: F401  (import check)
    _patch_evo()
    return evo_dir


def _evo_exit(msg=None):
    raise SystemExit(msg)


_EVO_WARNINGS: list = []


def _solubility_temp(T, limits):
    """Replacement for evo.messages.solubility_temp. EVo's own version crashes on an invalid
    format string ('{T:3Ng}') before it can print its warning; the intended behaviour is to
    continue with temperature-independent solubility coefficients, which is what EVo does
    once this function returns. The event is recorded so the report can flag it."""
    _EVO_WARNINGS.append(f"T = {T - 273.15:.0f} °C outside the calibrated range "
                         f"{limits[0] - 273.15:.0f}–{limits[1] - 273.15:.0f} °C of the H2O solubility law; "
                         "temperature-independent coefficients used")


def _patch_evo():
    from evo import messages as _msgs
    _msgs.query_yes_no = lambda *a, **k: True          # never block on prompts
    _msgs.solubility_temp = _solubility_temp           # EVo bug: invalid format spec
    for _n, _m in list(sys.modules.items()):           # bare exit() must raise SystemExit
        if _n == "evo" or _n.startswith("evo."):
            setattr(_m, "exit", _evo_exit)


ENV_TEMPLATE = """COMPOSITION: {evoclass}
RUN_TYPE: closed
SINGLE_STEP: False
FIND_SATURATION: True
ATOMIC_MASS_SET: False
GAS_SYS: cohs
FE_SYSTEM: True
OCS: False
S_SAT_WARN: False
T_START: {T_K}
P_START: 3000
P_STOP: {P_stop_bar}
DP_MIN: 0.1
DP_MAX: 50
MASS: 100
WgT: 0.00001
LOSS_FRAC: 0.9999
DENSITY_MODEL: spera2000
FO2_MODEL: kc1991
FMQ_MODEL: frost1991
H2O_MODEL: burguisser2015
H2_MODEL: gaillard2003
C_MODEL: burguisser2015
CO_MODEL: None
CH4_MODEL: None
SULFIDE_CAPACITY: oneill2020
SULFATE_CAPACITY: nash2019
SCSS: liu2007
N_MODEL: libourel2003
FO2_buffer_SET: True
FO2_buffer: FMQ
FO2_buffer_START: {dFMQ}
FO2_SET: False
FO2_START: 8.3e-12
FH2_SET: False
FH2_START: 0.24
FH2O_SET: False
FH2O_START: 1000
FCO2_SET: False
FCO2_START: 1
WTH2O_SET: True
WTH2O_START: {H2O_frac}
WTCO2_SET: True
WTCO2_START: {CO2_frac}
SULFUR_SET: True
SULFUR_START: {S_frac}
NITROGEN_SET: False
NITROGEN_START: 0.0001
GRAPHITE_SATURATED: False
GRAPHITE_START: 0.0001
"""

_GAS_SPECIES = ("mH2O", "mH2", "mCO2", "mCO", "mCH4", "mSO2", "mH2S", "mS2", "mO2")

# analytic fallback (only if EVo cannot run): (wt%/sqrt(MPa), ppm/MPa) by EVo class
_SOL = {"rhyolite": (0.41, 3.8), "phonolite": (0.39, 4.75), "basalt": (0.36, 5.5)}


# ======================================================================================
# Elastic sources (dMODELS python port, with the two numpy-2 fixes of the thesis)
# ======================================================================================
import dmodelspy.sill as _sillmod  # noqa: E402


def _gauleg_fixed(x1, x2, N):
    z, w = np.polynomial.legendre.leggauss(int(N))
    return 0.5 * (x2 + x1) + 0.5 * (x2 - x1) * z, 0.5 * (x2 - x1) * w


_sillmod._gauleg = _gauleg_fixed

from dmodelspy import Sill as _Sill, Spheroid as _Spheroid  # noqa: E402


class SillFixed(_Sill):
    """Fialko et al. (2001) penny-shaped crack, numpy-2-safe displacement."""

    def calc_displ(self, x, y, z):
        from numpy import arange, array, cosh, sinh, sqrt, zeros
        from scipy.special import jv as besselj
        if self._dV is None:
            self._calc_base()
        x = (array(x, ndmin=1, dtype=float) - self.x0) / self.a
        y = (array(y, ndmin=1, dtype=float) - self.y0) / self.a
        z = (array(z, ndmin=1, dtype=float) - self.z0) / self.a
        r = sqrt(x ** 2 + y ** 2)
        h = self.z0 / self.a
        Uz, Ur = zeros(r.shape), zeros(r.shape)
        for i in arange(r.size):
            czh = (z[i] + h) * self._csi_col
            J0 = besselj(0, r[i] * self._csi_col)
            Uzi = J0 * (((1 - 2 * self.nu) * self._Barr - czh * self._Aarr) * sinh(czh)
                        + (2 * (1 - self.nu) * self._Aarr - czh * self._Barr) * cosh(czh))
            Uz[i] = (self._wcsi_row @ Uzi).item()
            J1 = besselj(1, r[i] * self._csi_col)
            Uri = J1 * (((1 - 2 * self.nu) * self._Aarr + czh * self._Barr) * sinh(czh)
                        + (2 * (1 - self.nu) * self._Barr + czh * self._Aarr) * cosh(czh))
            Ur[i] = (self._wcsi_row @ Uri).item()
        rs = np.where(r == 0, 1.0, r)
        return (self.a * self.P_G * Ur * x / rs,
                self.a * self.P_G * Ur * y / rs,
                -self.a * self.P_G * Uz)


def pressure_Pa(depth_km, rho, g=9.81):
    """Step 1: lithostatic pressure, Eq. (3.1)."""
    return rho * g * depth_km * 1e3


def beta_gas(P_Pa):
    """Ideal-gas isothermal compressibility, 1/P, Eq. (3.10)."""
    return 1.0 / P_Pa


def beta_magma(phi, beta_vol, beta_liq):
    """Frozen-phase mixture rule, Eq. (3.12)."""
    return phi * beta_vol + (1.0 - phi) * beta_liq


def rV_factor(beta_m, beta_c):
    """Volume-partitioning factor, Eq. (3.24)."""
    return 1.0 + beta_m / beta_c


def mogi_uz(dVc, z0, r, nu):
    """Mogi (1958) point source, volume form, Eq. (3.25)."""
    r = np.atleast_1d(np.asarray(r, dtype=float))
    return (1 - nu) * dVc / np.pi * z0 / (z0 ** 2 + r ** 2) ** 1.5


def beta_c_sphere(mu):
    """Sphere, 3/(4 mu), Eq. (3.16)."""
    return 3.0 / (4.0 * mu)


def spheroid_dV(a, aspect, dP, mu):
    """Shape-corrected cavity volume change of a pressurised prolate spheroid, Eq. (3.17)."""
    A = aspect
    return np.pi * a * (A * a) ** 2 * dP / mu * (A ** 2 / 3.0 - 0.7 * A + 1.37)


def yang_semi_major(V0, aspect):
    return (3.0 * V0 / (4.0 * np.pi * aspect ** 2)) ** (1.0 / 3.0)


def yang_source(V0, aspect, z0, mu, nu, dip, strike, dP_ref=None):
    a = yang_semi_major(V0, aspect)
    dP = 1e-4 * mu if dP_ref is None else dP_ref
    sp = _Spheroid(0., 0., z0, a=a, asrat=aspect, P_G=dP / mu, mu=mu, nu=nu,
                   theta=min(dip, 89.99), phi=strike)
    return sp, a, dP


def beta_c_yang(V0, aspect, mu):
    """Eq. (3.18): (3/4mu)[A^2/3 - 0.7A + 1.37]."""
    a = yang_semi_major(V0, aspect)
    return spheroid_dV(a, aspect, 1.0, mu) / V0


def penny_source(a, z0, mu, nu, dP_ref=None):
    dP = 1e-4 * mu if dP_ref is None else dP_ref
    return SillFixed(0., 0., z0, P_G=dP / mu, a=a, nu=nu), dP


def beta_c_penny(a, V0, z0, mu, nu):
    """Fialko half-space crack compliance normalised by the stored volume, Eq. (3.20)."""
    s, dP = penny_source(a, z0, mu, nu)
    return s.dV / (V0 * dP)


def uplift_mogi(dVc, z0, dists, nu):
    return mogi_uz(dVc, z0, np.asarray(dists), nu)


def uplift_yang(dVc, V0, aspect, z0, mu, nu, dip, strike, dists, azimuth=0.0):
    sp, a, dP = yang_source(V0, aspect, z0, mu, nu, dip, strike)
    scale = dVc / spheroid_dV(a, aspect, dP, mu)
    az = np.deg2rad(azimuth)
    d = np.asarray(dists, dtype=float)
    x, y = d * np.sin(az), d * np.cos(az)
    _, _, w = sp.calc_displ(x, y, np.zeros_like(d))
    return w * scale


def uplift_yang_map(dVc, V0, aspect, z0, mu, nu, dip, strike, X, Y):
    sp, a, dP = yang_source(V0, aspect, z0, mu, nu, dip, strike)
    scale = dVc / spheroid_dV(a, aspect, dP, mu)
    W = sp.calc_displ(X.ravel(), Y.ravel(), np.zeros(X.size))[2] * scale
    return W.reshape(X.shape)


def uplift_penny(dVc, a, z0, mu, nu, dists):
    s, dP = penny_source(a, z0, mu, nu)
    scale = dVc / s.dV
    d = np.asarray(dists, dtype=float)
    _, _, w = s.calc_displ(d, np.zeros_like(d), np.zeros_like(d))
    return w * scale


# ======================================================================================
# Volatile equilibrium (step 2) for an arbitrary magma
# ======================================================================================
class VolatileEngine:
    """Runs EVo for a magma given as a dict with keys: oxides, evo_class, T_C, H2O_wt,
    CO2_wt, S_wt, rho_melt. Results are cached by the full state key."""

    def __init__(self, use_evo: bool = True, workdir: str | None = None):
        self.use_evo = use_evo
        self.workdir = workdir or os.path.join(tempfile.gettempdir(), "volcano_agent_evo")
        self.cache: dict = {}
        if use_evo:
            try:
                ensure_evo()
            except Exception as err:          # no git / no network -> analytic fallback
                self.use_evo = False
                self.evo_error = repr(err)

    @staticmethod
    def _key(m, P_MPa, dFMQ):
        return (json.dumps(m["oxides"], sort_keys=True), m["evo_class"], round(P_MPa, 3),
                m["T_C"], m["H2O_wt"], m["CO2_wt"], m["S_wt"], dFMQ)

    def state(self, m: dict, P_MPa: float, dFMQ: float) -> dict:
        key = self._key(m, P_MPa, dFMQ)
        if key in self.cache:
            return self.cache[key]
        res = self._run_evo(m, P_MPa, dFMQ) if self.use_evo else self.simple(m, P_MPa)
        self.cache[key] = res
        return res

    # ---------------------------------------------------------------------------- EVo
    def _blank(self, m, P_MPa):
        return dict(P_MPa=P_MPa, T_C=m["T_C"], phi=0.0, saturated=False, P_sat_MPa=np.nan,
                    gas_molmass=np.nan, rho_melt=m["rho_melt"], rho_gas=np.nan,
                    rho_bulk=np.nan, fO2_dFMQ=np.nan, fH2O=np.nan, fCO2=np.nan, fSO2=np.nan,
                    fH2S=np.nan, fS2=np.nan, gas_wt=0.0, XH2O_gas=np.nan, XCO2_gas=np.nan,
                    beta_m_evo=np.nan, engine="EVo", gas_species={})

    @staticmethod
    def _fill_from_df(res, df):
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        res.update(
            phi=float(last["Exsol_vol%"]) / 100.0, saturated=True,
            P_sat_MPa=float(df["P"].iloc[0]) / 10.0,
            gas_molmass=float(last["mol_mass"]), rho_melt=float(last["rho_melt"]),
            rho_bulk=float(last["rho_bulk"]),
            fO2_dFMQ=float(last["FMQ"]), fH2O=float(last["fH2O"]), fCO2=float(last["fCO2"]),
            fSO2=float(last["fSO2"]), fH2S=float(last["fH2S"]), fS2=float(last["fS2"]),
            gas_wt=float(last["Gas_wt"]) / 100.0,
            XH2O_gas=float(last["mH2O"]), XCO2_gas=float(last["mCO2"]))
        res["gas_species"] = {k[1:]: float(last[k]) for k in _GAS_SPECIES if k in last.index}
        for key, col in (("melt_H2O_wt", "H2O_melt"), ("melt_CO2_wt", "CO2_melt"),
                         ("melt_S_wt", "Stot_melt")):
            if col in last.index:
                res[key] = float(last[col])
        wg = res["gas_wt"]
        if wg > 0:
            inv = 1.0 / float(last["rho_bulk"]) - (1 - wg) / res["rho_melt"]
            if inv > 0:
                res["rho_gas"] = wg / inv
        if len(df) > 1 and last["P"] != prev["P"]:   # equilibrium compressibility, Eq. (3.13)
            dP = (float(prev["P"]) - float(last["P"])) * 1e5
            res["beta_m_evo"] = (np.log(float(prev["rho_bulk"])) - np.log(float(last["rho_bulk"]))) / dP

    def _run_evo(self, m, P_MPa, dFMQ):
        import evo
        _patch_evo()
        os.makedirs(self.workdir, exist_ok=True)
        tag = hashlib.md5(json.dumps(self._key(m, P_MPa, dFMQ)).encode()).hexdigest()[:10]
        chem = os.path.join(self.workdir, f"chem_{tag}.yaml")
        env = os.path.join(self.workdir, f"env_{tag}.yaml")
        with open(chem, "w") as f:
            for ox, val in m["oxides"].items():
                f.write(f"{ox}: {val}\n")
        with open(env, "w") as f:
            f.write(ENV_TEMPLATE.format(
                evoclass=m["evo_class"], T_K=m["T_C"] + 273.15,
                P_stop_bar=max(int(round(P_MPa * 10.0)), 1), dFMQ=dFMQ,
                H2O_frac=max(m["H2O_wt"], 1e-3) / 100.0,
                CO2_frac=max(m["CO2_wt"], 1e-4) / 100.0,
                S_frac=max(m["S_wt"], 1e-4) / 100.0))
        res = self._blank(m, P_MPa)
        buf = io.StringIO()
        sat_re = re.compile(r"saturation pressure \(([\d.eE+-]+)\s*bar\)")
        del _EVO_WARNINGS[:]
        try:
            with contextlib.redirect_stdout(buf):
                df = evo.run_evo(chem, env, None, folder=os.path.join(self.workdir, tag))
            self._fill_from_df(res, df)
        except SystemExit as e:
            mm = sat_re.search(str(e) + " " + buf.getvalue())
            if mm:
                res["P_sat_MPa"] = float(mm.group(1)) / 10.0
            res["saturated"] = False
        except Exception as err:                     # solver hiccup -> nudge P_STOP, retry
            done = False
            for bump in (1, 2, 5):
                try:
                    with open(env) as f:
                        txt = f.read()
                    p0 = int(round(max(P_MPa * 10.0, 1.0)))
                    txt = re.sub(r"P_STOP: \d+", f"P_STOP: {p0 + bump}", txt)
                    with open(env, "w") as f:
                        f.write(txt)
                    with contextlib.redirect_stdout(buf):
                        df = evo.run_evo(chem, env, None, folder=os.path.join(self.workdir, tag))
                    self._fill_from_df(res, df)
                    res["engine"] = f"EVo (P_STOP+{bump} bar)"
                    done = True
                    break
                except SystemExit as e2:
                    mm = sat_re.search(str(e2))
                    if mm:
                        res["P_sat_MPa"] = float(mm.group(1)) / 10.0
                    res["saturated"] = False
                    done = True
                    break
                except Exception:
                    continue
            if not done:
                res = self.simple(m, P_MPa)
                res["engine"] = f"analytic fallback (EVo {type(err).__name__})"
        if _EVO_WARNINGS and res["engine"].startswith("EVo"):
            res["engine"] += "; " + _EVO_WARNINGS[0]
        return res

    # ---------------------------------------------------------------- analytic fallback
    def simple(self, m, P_MPa):
        sw, kc = _SOL.get(m["evo_class"], _SOL["phonolite"])
        T_K = m["T_C"] + 273.15
        h2o_sat = sw * np.sqrt(P_MPa)
        co2_sat = kc * P_MPa * 1e-4
        ex_h2o = max(m["H2O_wt"] - h2o_sat, 0.0) / 100.0
        ex_co2 = max(m["CO2_wt"] - co2_sat, 0.0) / 100.0
        wg = ex_h2o + ex_co2
        res = self._blank(m, P_MPa)
        res.update(engine="analytic fallback", saturated=wg > 0, gas_wt=wg,
                   P_sat_MPa=(m["H2O_wt"] / sw) ** 2)
        if wg <= 0:
            return res
        n_h2o, n_co2 = ex_h2o / 18.015e-3, ex_co2 / 44.01e-3
        M = (ex_h2o + ex_co2) / (n_h2o + n_co2)
        rho_g = P_MPa * 1e6 * M / (R_GAS * T_K)
        Vg, Vl = wg / rho_g, (1 - wg) / m["rho_melt"]
        res.update(phi=Vg / (Vg + Vl), gas_molmass=M, rho_gas=rho_g,
                   XH2O_gas=n_h2o / (n_h2o + n_co2), XCO2_gas=n_co2 / (n_h2o + n_co2))
        return res
