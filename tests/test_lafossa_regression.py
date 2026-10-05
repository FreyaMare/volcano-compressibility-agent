"""The generalised engine, run on the La Fossa reference dataset, must reproduce the
thesis results (Scenario A, Chapter 5) to the tolerance of the original notebook test.

    pytest -v tests/
Set VOLCANO_AGENT_EVO_DIR=/path/to/EVo to reuse an existing EVo checkout.
"""
import pathlib

import numpy as np
import pytest

from volcano_agent.chain import Analysis
from volcano_agent.defaults import finalize
from volcano_agent.schema import Dataset

REF = pathlib.Path(__file__).resolve().parents[1] / "volcano_agent" / "reference" / "lafossa.json"

# row order: Mogi 2/5/12 km, published 2021 spheroid, penny a=0.5 (2/5/12), a=1, a=2
REF_RV = [2.600000, 2.466667, 2.333333, 11.939244, 3.381570, 22.988474, 200.992341,
          1.284984, 3.738892, 25.992391, 1.029156, 1.334071, 4.117585]
REF_UZ0 = [229.5504, 38.71337, 7.105131, 42.19532, 332.2557, 8.225651, 0.164682,
           744.7670, 49.11771, 1.266856, 598.4658, 123.5135, 7.835061]


@pytest.fixture(scope="module")
def R():
    ds = finalize(Dataset.model_validate_json(REF.read_text()))
    an = Analysis(ds)
    assert an.engine.use_evo, "EVo must be available for the regression test"
    return an.run_all()


def test_partitioning_factor(R):
    np.testing.assert_allclose(R["res"].rV.values, REF_RV, rtol=1e-5)


def test_central_uplift(R):
    np.testing.assert_allclose(R["res"].uz3_0km_mm.values, REF_UZ0, rtol=1e-5)


def test_equilibrium_branch(R):
    assert abs(R["res"].rV_eq.values[3] - 42.32) < 0.01


def test_saturation(R):
    phi = R["res"].phi.values
    assert abs(phi[3] - 0.15541) < 1e-3
    assert all(p == 0 for i, p in enumerate(phi) if i != 3)


def test_scenario_b(R):
    b = R["scenario_b"]
    got = b[b.scenario != "A"].rV.round(2).tolist()
    np.testing.assert_allclose(got, [4.04, 22.44, 50.12, 3.94, 7.84, 12.76, 2.60, 2.93, 3.61], atol=0.02)


def test_inverse_screen(R):
    inv = R["inverse"]
    bad = inv[~inv.within_screen]
    assert len(bad) == 3 and set(bad.depth_km) == {5.0, 12.0}


def test_consistency_with_published_source(R):
    c = R["consistency"]
    assert abs(c[0]["this"] / c[0]["ref"] - 1) < 0.005
    assert abs(c[2]["this"] - 36.8) < 0.1
