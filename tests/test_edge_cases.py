"""Stress tests: unusual or incomplete datasets must still produce a complete report,
with every substitution flagged. No API key or network (other than the EVo clone) needed.
"""
import numpy as np
import pytest

from volcano_agent.defaults import finalize
from volcano_agent.pipeline import analyse_and_report
from volcano_agent.schema import Dataset, DeformationSource, Level, Magma, Q

RHY = dict(SIO2=73.0, TIO2=0.2, AL2O3=13.5, FEO=2.0, MNO=0.06, MGO=0.3, CAO=1.1, NA2O=4.0, K2O=4.8, P2O5=0.05)


def _q(v, s="M"):
    return Q(value=v, status=s, source="Test et al. (2020)")


CASES = {
    # 1. almost nothing known: one magma without analysis, one level, no source, no elevation
    "minimal": Dataset(name="Minimal", magmas=[Magma(key="BASALT", rock_type="basalt")],
                       levels=[Level(name="Only level", depth_km=_q(8.0))]),
    # 2. spheroid with volume only, depth below the surface, big edifice, caldera 10 km
    "yang_volume_only": Dataset(
        name="Yang volume only", summit_elevation_m=_q(3300), caldera_max_radius_km=_q(5.0),
        tectonic_setting="subduction arc",
        magmas=[Magma(key="ANDESITE", rock_type="andesite", oxides=dict(
            SIO2=58.0, TIO2=0.9, AL2O3=17.2, FE2O3=7.5, MNO=0.13, MGO=3.4, CAO=6.9, NA2O=3.5, K2O=1.5, P2O5=0.2, LOI=1.2),
            T_C=_q(1273.0), H2O_wt=_q(4.0), CO2_wt=_q(0.08), S_wt=_q(0.1)),
                Magma(key="DACITE", rock_type="dacite", H2O_wt=_q(5.0))],
        levels=[Level(name="Upper", depth_km=_q(6.0), resident="DACITE", injected="ANDESITE"),
                Level(name="Lower", depth_km=_q(15.0), resident="ANDESITE")],
        deformation_source=DeformationSource(model="YANG", depth_km=_q(3.0), depth_reference="below the surface",
                                             V0_m3=_q(2e9), dV_m3=_q(-5e6), dP_MPa=_q(10.0))),
    # 3. shallow crack wider than deep, very shallow and very deep levels
    "penny_shallow_deep": Dataset(
        name="Penny shallow deep", summit_elevation_m=_q(800),
        magmas=[Magma(key="RHYOLITE", rock_type="rhyolite", oxides=RHY, H2O_wt=_q(2.0)),
                Magma(key="BASALT", rock_type="basalt", H2O_wt=_q(3.0), CO2_wt=_q(0.3))],
        levels=[Level(name="Very shallow", depth_km=_q(1.0), resident="RHYOLITE"),
                Level(name="Duplicate", depth_km=_q(1.0)),
                Level(name="Moho", depth_km=_q(30.0), resident="BASALT"),
                Level(name="Nonsense", depth_km=_q(90.0))],
        deformation_source=DeformationSource(model="PENNY", depth_km=_q(1.0), a_m=_q(1500.0),
                                             dV_m3=_q(3e5), mu_GPa=_q(3e9), nu=_q(0.25))),
    # 4. gas-rich deep magma, odd silica, swapped spheroid axes, absurd aspect, submarine edifice
    "odd_values": Dataset(
        name="Odd values", summit_elevation_m=_q(-500),
        magmas=[Magma(key="BASANITE", rock_type="basanite", oxides=dict(
            SIO2=44.5, TIO2=2.8, AL2O3=14.5, FEO=11.5, MNO=0.2, MGO=9.0, CAO=11.0, NA2O=3.8, K2O=1.7, P2O5=0.8),
            H2O_wt=_q(6.0), CO2_wt=_q(1.0), S_wt=_q(0.2), T_C=_q(200.0)),
                Magma(key="HIGH_SILICA", rock_type="rhyolite", oxides=dict(
                    SIO2=77.5, TIO2=0.1, AL2O3=12.3, FEO=1.0, MNO=0.03, MGO=0.1, CAO=0.6, NA2O=3.9, K2O=4.5, P2O5=0.02),
                    H2O_wt=_q(12.0))],
        levels=[Level(name="Deep gas-rich", depth_km=_q(10.0), resident="BASANITE"),
                Level(name="Shallow", depth_km=_q(3.0), resident="HIGH_SILICA")],
        rho_crust=_q(2.6), mu_deep_GPa=_q(3e10), nu_deep=_q(0.6), dFMQ=_q(7.0),
        deformation_source=DeformationSource(model="YANG", depth_km=_q(2.0), a_m=_q(100.0), b_m=_q(900.0),
                                             aspect=_q(5.0), dip_deg=_q(0.0), strike_deg=_q(400.0))),
    # 5. no magmas at all, no depth on the source
    "no_magmas": Dataset(name="No magmas", levels=[Level(name="L", depth_km=_q(4.0), resident="trachyte")],
                         deformation_source=DeformationSource(model="MOGI", depth_km=Q())),
}


@pytest.mark.parametrize("name", list(CASES))
def test_case_runs_and_is_flagged(name):
    rr = analyse_and_report(CASES[name], write=False)
    res = rr.results["res"]
    assert len(res) >= 2
    for col in ("rV", "uz3_0km_mm", "beta_c", "P_MPa"):
        assert np.all(np.isfinite(res[col].values)), (name, col)
    assert (res.rV >= 1).all()
    assert (res.uz3_0km_mm > 0).all()
    assert rr.pdf[:4] == b"%PDF"
    assert rr.dataset.data_gaps, "substitutions must be reported"


def test_specific_fixes():
    d = finalize(Dataset.model_validate(CASES["yang_volume_only"].model_dump()))
    s = d.deformation_source
    assert s.a_m.value and s.b_m.value and abs(s.aspect.value - 0.3) < 1e-9      # geometry from V0 + default A
    assert s.dV_m3.value == 5e6                                                  # sign removed
    a = d.magma("ANDESITE")
    assert abs(a.T_C.value - 999.85) < 0.1                                       # kelvin converted
    assert "FE2O3" not in a.oxides and 97 <= sum(a.oxides.values()) <= 101.5   # LOI dropped, Fe converted

    d = finalize(Dataset.model_validate(CASES["penny_shallow_deep"].model_dump()))
    assert [L.depth_km.value for L in d.levels] == [1.0, 30.0]                   # duplicate and 90 km dropped
    assert d.deformation_source.mu_GPa.value == 3.0                              # Pa -> GPa

    d = finalize(Dataset.model_validate(CASES["odd_values"].model_dump()))
    s = d.deformation_source
    assert s.a_m.value == 900.0 and s.b_m.value == 100.0                         # axes swapped back
    assert 0.02 <= s.aspect.value <= 0.99 and 1.0 <= s.dip_deg.value <= 89.99
    assert d.rho_crust.status == "D" and d.nu_deep.status == "D" and d.dFMQ.status == "D"
    assert d.magma("BASANITE").evo_class == "basalt" and d.magma("HIGH_SILICA").evo_class == "rhyolite"
    assert d.magma("HIGH_SILICA").H2O_wt.value == 8.0                            # clamped

    d = finalize(Dataset.model_validate(CASES["no_magmas"].model_dump()))
    assert d.deformation_source is None and d.magmas[0].key == "TRACHYTE"


def test_crack_wider_than_deep_is_skipped():
    rr = analyse_and_report(CASES["penny_shallow_deep"], write=False)
    labels = set(rr.results["res"].label)
    assert "Penny crack a = 2 km, 1 km" not in labels and "Penny crack a = 1 km, 1 km" in labels
    assert any("a/d > 1" in n for n in rr.results["notes"])
