"""End-to-end test of the agent with a fake Claude client (no network, no API key).

Exercises: the tool loop (pause_turn, search events, submit), dataset assembly with
missing data and generic defaults, a MOGI published source, the writer, the number
audit and the PDF build.
"""
import types

import pytest

from volcano_agent import llm, pipeline


def _blk(**k):
    return types.SimpleNamespace(**k)


def _msg(content, stop):
    return types.SimpleNamespace(content=content, stop_reason=stop,
                                 usage=types.SimpleNamespace(input_tokens=1000, output_tokens=200,
                                                             server_tool_use=types.SimpleNamespace(web_search_requests=1, web_fetch_requests=0)))


SYSTEM = {
    "name": "Testo Volcano", "country": "Nowhere", "region": "Test arc", "latitude": 1.0, "longitude": 2.0,
    "volcano_type": "stratovolcano", "tectonic_setting": "subduction arc", "last_eruption": "1999",
    "summit_elevation_m": {"value": 1500, "status": "M", "source": "Smith et al. (2010)"},
    "caldera_max_radius_km": {"value": None, "status": "D", "source": ""},
    "magma_series": [{"key": "BASALT", "rock_type": "basalt"}, {"key": "ANDESITE", "rock_type": "andesite"}],
    "levels": [
        {"name": "Shallow chamber", "depth_km": {"value": 4, "status": "A", "source": "Smith et al. (2010)"},
         "resident": "ANDESITE", "injected": "BASALT"},
        {"name": "Deep zone", "depth_km": {"value": 10, "status": "A", "source": "Smith et al. (2010)"},
         "resident": "BASALT", "injected": "BASALT"}],
    "dFMQ": {"value": None, "status": "D", "source": ""},
    "narrative": {"setting": "Testo is an arc volcano (Smith et al., 2010).", "plumbing": "Two levels at 4 and 10 km."},
    "references": [{"key": "Smith et al. (2010)", "citation": "Smith, A. (2010). Testo. J. Test 1, 1-2."}],
    "notes": ["Depth of the deep zone poorly constrained."],
}
GEODESY = {
    "deformation_source": {"model": "MOGI", "depth_km": {"value": 3.0, "status": "M", "source": "Roe et al. (2020)"},
                           "a_m": {"value": 400, "status": "M", "source": "Roe et al. (2020)"},
                           "dV_m3": {"value": 2e5, "status": "M", "source": "Roe et al. (2020)"},
                           "dP_MPa": {"value": 4.0, "status": "M", "source": "Roe et al. (2020)"},
                           "mu_GPa": {"value": 5, "status": "A", "source": "Roe et al. (2020)"},
                           "interpretation": "magmatic", "source": "Roe et al. (2020)"},
    "narrative": {"deformation": "InSAR showed uplift in 2020 (Roe et al., 2020)."},
    "references": [{"key": "Roe et al. (2020)", "citation": "Roe, B. (2020). Uplift at Testo. GRL 47."}],
}
PETRO = {
    "ANDESITE": {"key": "ANDESITE", "rock_type": "andesite", "label": "T-1",
                 "oxides": {"SIO2": 59.0, "TIO2": 0.8, "AL2O3": 17.0, "FE2O3": 7.0, "MNO": 0.12, "MGO": 3.0,
                            "CAO": 6.5, "NA2O": 3.6, "K2O": 1.8, "P2O5": 0.2},
                 "composition_status": "M", "composition_source": "Smith et al. (2010), Table 2",
                 "T_C": {"value": 1000, "status": "M", "source": "Smith et al. (2010)"},
                 "H2O_wt": {"value": 3.5, "min": 3, "max": 4, "status": "A", "source": "Smith et al. (2010)"},
                 "CO2_wt": {"value": 0.05, "status": "M", "source": "Smith et al. (2010)"},
                 "S_wt": {"value": None, "status": "D", "source": ""},
                 "references": []},
    "BASALT": {"key": "BASALT", "oxides": {}, "T_C": {"value": None, "status": "D", "source": ""},
               "H2O_wt": {"value": 2.0, "status": "M", "source": "Smith et al. (2010)"},
               "CO2_wt": {"value": None, "status": "D", "source": ""},
               "S_wt": {"value": None, "status": "D", "source": ""}, "references": []},
}


class FakeMessages:
    def __init__(self):
        self.n = 0

    def stream(self, **kw):
        tools = {t["name"] for t in kw["tools"]}
        user = kw["messages"][0]["content"]
        self.n += 1
        last = kw["messages"][-1]
        if "submit_system" in tools:
            payload, name = SYSTEM, "submit_system"
        elif "submit_geodesy" in tools:
            payload, name = GEODESY, "submit_geodesy"
        elif "submit_petrology" in tools:
            key = "ANDESITE" if "ONE magma: ANDESITE" in user else "BASALT"
            payload, name = PETRO[key], "submit_petrology"
        else:
            props = kw["tools"][-1]["input_schema"]["properties"]
            payload = {k: f"Text for {k}. The modelled r<sub>V</sub> is discussed (Smith et al., 2010). 77713.9 is unmatched."
                       for k in props}
            name = "submit_sections"
        if last["role"] == "user" and len(kw["messages"]) == 1 and name != "submit_sections":
            # first round: a search and a pause, to exercise pause_turn handling
            msg = _msg([_blk(type="server_tool_use", name="web_search", input={"query": "test"}, id="s1"),
                        _blk(type="web_search_tool_result", content=[_blk(url="https://example.org/a", title="A")])],
                       "pause_turn")
        else:
            msg = _msg([_blk(type="text", text="done"), _blk(type="tool_use", name=name, input=payload, id="t1")], "tool_use")
        return types.SimpleNamespace(__enter__=lambda *a: types.SimpleNamespace(get_final_message=lambda: msg),
                                     __exit__=lambda *a: False)


class _CM:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return types.SimpleNamespace(get_final_message=lambda: self.msg)

    def __exit__(self, *a):
        return False


class FakeClient:
    def __init__(self, *a, **k):
        fm = FakeMessages()
        orig = fm.stream

        def stream(**kw):
            ns = orig(**kw)
            return _CM(ns.__enter__().get_final_message())
        self.messages = types.SimpleNamespace(stream=stream)


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(llm.anthropic, "Anthropic", FakeClient)      # used by research and writer


def test_full_agent_with_fake_client(fake, tmp_path):
    events = []
    rr = pipeline.run_agent("Testo", api_key="sk-test", on_event=events.append)
    ds = rr.dataset
    assert any(e.startswith("search:") for e in events)
    assert {m.key for m in ds.magmas} == {"BASALT", "ANDESITE"}
    bas = ds.magma("BASALT")
    assert bas.composition_status == "D" and bas.T_C.status == "D"       # generic defaults flagged
    and_ = ds.magma("ANDESITE")
    assert abs(and_.oxides["FEO"] - 7.0 * 0.8998) < 1e-6                  # Fe2O3 -> FeO(tot)
    assert ds.deformation_source.model == "MOGI"
    assert any("generic" in g for g in ds.data_gaps)
    res = rr.results["res"]
    assert (res.family == "source").sum() == 1
    assert len(res) == 2 + 1 + 3 * 2                                     # Mogi x2, source, penny 3 radii x2
    assert rr.pdf[:4] == b"%PDF" and len(rr.pdf) > 100_000
    (tmp_path / "r.pdf").write_bytes(rr.pdf)
    assert any("Number audit" in l for l in rr.log)                       # 77713.9 caught


def test_loop_nudges_when_model_forgets_submit(monkeypatch):
    calls = {"n": 0}

    def stream(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return _CM(_msg([_blk(type="text", text="here is my answer")], "end_turn"))
        return _CM(_msg([_blk(type="tool_use", name="submit_x", input={"a": 1}, id="t")], "tool_use"))

    client = types.SimpleNamespace(messages=types.SimpleNamespace(stream=stream))
    out = llm.run_submit_loop(client, model="m", system="s", user="u", submit_name="submit_x",
                              submit_description="d", submit_schema={"type": "object", "properties": {}})
    assert out == {"a": 1} and calls["n"] == 2
