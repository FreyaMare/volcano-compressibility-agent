"""Streamlit front-end of the Volcano Compressibility Agent.

    streamlit run app.py
"""
from __future__ import annotations

import hmac
import json
import os

import pandas as pd
import streamlit as st

from volcano_agent import physics
from volcano_agent.pipeline import analyse_and_report, load_reference, research
from volcano_agent.defaults import _num
from volcano_agent.schema import Dataset, DeformationSource, Level, Q

st.set_page_config(page_title="Volcano Compressibility Agent", page_icon="🌋", layout="wide")


@st.cache_resource(show_spinner="Installing EVo (once per server)…")
def _evo():
    try:
        return physics.ensure_evo()
    except Exception as e:  # analytic fallback will be used
        return f"unavailable: {e}"


_evo()
ss = st.session_state
ss.setdefault("ds", None)
ss.setdefault("result", None)
ss.setdefault("usage", None)

# ------------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    # The owner's key (Streamlit secrets or environment) is used only on the server and is never
    # sent to the browser. On a public deployment, set APP_PASSWORD in the secrets so that only
    # people who know the password can spend the owner's credits; everyone else pastes their own key.
    server_key, app_pw = "", ""
    try:
        server_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        app_pw = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        pass
    server_key = server_key or os.environ.get("ANTHROPIC_API_KEY", "")
    user_key = st.text_input("Your Anthropic API key", value="", type="password",
                             help="Needed for the literature research and the written chapters. "
                                  "Kept only for this browser session; never stored.")
    api_key = user_key.strip()
    if not api_key and server_key:
        if app_pw:
            pw = st.text_input("…or the access password of this app", type="password")
            if pw and hmac.compare_digest(pw, app_pw):
                api_key = server_key
                st.caption("✅ Using the app owner's key.")
            elif pw:
                st.caption("❌ Wrong password.")
        else:
            api_key = server_key
            st.caption("Using the key stored in the app secrets.")
    model = st.selectbox("Model", ["claude-opus-5-5", "claude-sonnet-5-5"], index=0,
                         help="Opus gives the most careful extraction; Sonnet is faster and cheaper.")
    depth = st.radio("Research depth", ["quick", "standard", "thorough"], index=1, horizontal=True,
                     help="Number of web searches and page reads per research stage.")
    review = st.checkbox("Let me review and edit the data before the analysis", value=True)
    st.divider()
    target = st.number_input("Target central uplift (mm)", 1.0, 200.0, 10.0, 1.0)
    screen = st.number_input("Overpressure screening threshold (MPa)", 1.0, 100.0, 10.0, 1.0)
    st.divider()
    if st.button("Load the La Fossa thesis dataset (demo)"):
        ss.ds, ss.result = load_reference("lafossa"), None
    up = st.file_uploader("…or load a saved dataset (.json)", type="json")
    if up is not None and st.button("Use uploaded dataset"):
        ss.ds, ss.result = Dataset.model_validate_json(up.read()), None

# ---------------------------------------------------------------------------------- main
st.title("🌋 Volcano Compressibility Agent")
st.caption("By **Freya Mohammadian** · method of the MSc thesis *From magma compressibility to surface deformation "
           "at La Fossa volcano (Vulcano Island, Italy)*, University of Naples Federico II, 2026.")
st.caption("Type a volcano. The agent searches the published literature for every input of the seven-step chain "
           "(melt compositions, temperatures, volatile budgets, storage depths, published deformation sources, elastic "
           "moduli), runs EVo and the Mogi / Yang / Fialko models, and writes a thesis-style report.")

c1, c2 = st.columns([4, 1])
volcano = c1.text_input("Volcano", placeholder="e.g. Campi Flegrei, Mount St. Helens, Taal, Santorini, Etna",
                        label_visibility="collapsed")
go = c2.button("Run agent", type="primary", width="stretch", disabled=not volcano)

if go:
    if not api_key:
        st.error("An Anthropic API key is needed for the literature research.")
        st.stop()
    ss.result = None
    with st.status(f"Researching {volcano}…", expanded=True) as status:
        log = st.empty()
        lines: list = []

        def on_event(s):
            lines.append(s)
            log.code("\n".join(lines[-18:]), language=None)

        try:
            ds, usage = research(volcano, api_key=api_key, model=model, depth=depth, on_event=on_event)
        except Exception as e:
            status.update(label="Research failed", state="error")
            st.exception(e)
            st.stop()
        ss.ds, ss.usage = ds, usage
        status.update(label=f"Research finished — {usage.summary()}", state="complete", expanded=False)


# -------------------------------------------------------------------------- review step
def _s(x) -> str:
    """Cell value to clean string ('' for None / NaN)."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return str(x).strip()


def _qcols(prefix, q: Q):
    return {prefix: q.value, f"{prefix} status": q.status, f"{prefix} source": q.source}


def review_editor(ds: Dataset) -> Dataset:
    st.subheader(f"Data found for {ds.name}")
    st.caption("Status codes: **M** measured · **U** detection limit · **A** adopted representative value · "
               "**D** not found (a generic default will be used and flagged). Edit any value, then run the analysis.")
    if ds.data_gaps:
        with st.expander(f"Caveats and data gaps reported by the agent ({len(ds.data_gaps)})"):
            for g in ds.data_gaps:
                st.markdown(f"- {g}")
    status_col = st.column_config.SelectboxColumn(options=["M", "U", "A", "D"], required=True)
    mrows = []
    for m in ds.magmas:
        r = {"key": m.key, "rock type": m.rock_type, "sample": m.label,
             "SiO2": _num(m.oxides.get("SIO2") or m.oxides.get("SiO2")), "composition": m.composition_status}
        for p, q in (("T (°C)", m.T_C), ("H2O wt%", m.H2O_wt), ("CO2 wt%", m.CO2_wt), ("S wt%", m.S_wt)):
            r.update(_qcols(p, q))
        mrows.append(r)
    st.markdown("**Magmas**")
    num_cols = {p: st.column_config.NumberColumn(format="%.4g") for p in ("T (°C)", "H2O wt%", "CO2 wt%", "S wt%")}
    mdf = st.data_editor(pd.DataFrame(mrows), num_rows="fixed", width="stretch", key=f"mag_ed_{ds.slug}",
                         disabled=["key", "SiO2", "composition"],
                         column_config={**num_cols, **{f"{p} status": status_col for p in num_cols}})
    st.markdown("**Storage levels**")
    keys = [m.key for m in ds.magmas]
    ldf = st.data_editor(pd.DataFrame([{"name": L.name, "depth km": L.depth_km.value, "status": L.depth_km.status,
                                        "resident": L.resident, "injected": L.injected, "V0 m3": L.V0_m3.value,
                                        "evidence": L.evidence, "source": L.depth_km.source} for L in ds.levels],
                                      columns=["name", "depth km", "status", "resident", "injected", "V0 m3",
                                               "evidence", "source"]),
                         num_rows="dynamic", width="stretch", key=f"lev_ed_{ds.slug}",
                         column_config={"resident": st.column_config.SelectboxColumn(options=keys),
                                        "injected": st.column_config.SelectboxColumn(options=keys),
                                        "status": status_col,
                                        "depth km": st.column_config.NumberColumn(min_value=0.0, max_value=40.0),
                                        "V0 m3": st.column_config.NumberColumn(format="%.3g")})
    src_txt = None
    with st.expander("Published deformation source (JSON)", expanded=False):
        src_txt = st.text_area("source", value=(ds.deformation_source.model_dump_json(indent=1)
                                                if ds.deformation_source else "null"), height=260,
                               label_visibility="collapsed")
    with st.expander("Narrative notes and references"):
        for k, v in ds.narrative.items():
            st.markdown(f"**{k}** — {v}")
        for r in ds.references:
            st.markdown(f"- {r.citation or r.key} {r.url}")

    # write the edits back (keeping provenance fields the tables do not show)
    new = Dataset.model_validate(ds.model_dump())
    for m, (_, r) in zip(new.magmas, mdf.iterrows()):
        m.rock_type, m.label = _s(r["rock type"]), _s(r["sample"])
        for p, attr in (("T (°C)", "T_C"), ("H2O wt%", "H2O_wt"), ("CO2 wt%", "CO2_wt"), ("S wt%", "S_wt")):
            q = getattr(m, attr)
            q.value = _num(r[p])
            q.status = _s(r[f"{p} status"]) or ("A" if q.value is not None else "D")
            q.source = _s(r[f"{p} source"])
    old_levels = {L.name: L for L in ds.levels}
    levels = []
    for _, r in ldf.iterrows():
        z = _num(r["depth km"])
        if z is None:
            continue
        L = Level.model_validate(old_levels[_s(r["name"])].model_dump()) if _s(r["name"]) in old_levels \
            else Level(name=_s(r["name"]) or f"Level {z:g} km")
        L.name = _s(r["name"]) or L.name
        if L.depth_km.value != z:
            L.depth_km = Q(value=z, status=_s(r["status"]) or "A", source=_s(r["source"]))
        else:
            L.depth_km.status, L.depth_km.source = _s(r["status"]) or L.depth_km.status, _s(r["source"])
        v0 = _num(r["V0 m3"])
        if v0 != L.V0_m3.value:
            L.V0_m3 = Q(value=v0, status="A" if v0 is not None else "D", note="edited by the user")
        L.resident, L.injected, L.evidence = _s(r["resident"]), _s(r["injected"]), _s(r["evidence"])
        levels.append(L)
    new.levels = levels
    try:
        js = json.loads(src_txt) if src_txt else None
        new.deformation_source = DeformationSource.model_validate(js) if js else None
    except Exception as e:
        st.warning(f"Deformation-source JSON not valid, kept the original: {e}")
    return new


def run_analysis(ds: Dataset):
    with st.status("Running the seven-step chain and writing the report…", expanded=True) as status:
        log = st.empty()
        lines: list = []

        def on_event(s):
            lines.append(s)
            log.code("\n".join(lines[-14:]), language=None)

        try:
            rr = analyse_and_report(ds, api_key=api_key or None, model=model, target_mm=target, screen_MPa=screen,
                                    write=bool(api_key),
                                    usage=ss.usage, on_event=on_event)
        except Exception as e:
            status.update(label="Analysis failed", state="error")
            st.exception(e)
            return
        ss.result = rr
        status.update(label="Report ready", state="complete", expanded=False)


if ss.ds is not None and ss.result is None:
    edited = review_editor(ss.ds) if review else ss.ds
    cc1, cc2 = st.columns([1, 1])
    cc2.download_button("Download dataset (JSON)", edited.model_dump_json(indent=1),
                        file_name=f"{edited.slug}_dataset.json", mime="application/json")
    if not review or cc1.button("Run analysis and write the report", type="primary"):
        run_analysis(edited)

# ------------------------------------------------------------------------------ results
rr = ss.result
if rr is not None:
    ds, R = rr.dataset, rr.results
    res = R["res"]
    st.success(f"Report for **{ds.name}** is ready.")
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇️ Download the PDF report", rr.pdf, file_name=f"{ds.slug}_report.pdf",
                       mime="application/pdf", type="primary", width="stretch")
    d2.download_button("Dataset with provenance (JSON)", rr.dataset_json(), file_name=f"{ds.slug}_dataset.json",
                       mime="application/json", width="stretch")
    d3.download_button("Complete results (CSV)", res.to_csv(index=False), file_name=f"{ds.slug}_results.csv",
                       mime="text/csv", width="stretch")
    sat = res[res.phi > 0]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Configurations", len(res))
    m2.metric("Gas-bearing reservoirs", int((R["states"].query("role == 'resident'").saturated).sum()))
    m3.metric("r_V range", f"{res.rV.min():.2f} – {res.rV.max():.1f}")
    m4.metric("Flagged inputs", len(ds.data_gaps))
    tabs = st.tabs(["Summary", "Magmatic state", "Partitioning & uplift", f"Inverse ({R['target_mm']:g} mm)",
                    "Sensitivity", "Data provenance"])
    with tabs[0]:
        st.markdown(rr.chapters.get("abstract", "").replace("<sub>", "").replace("</sub>", "")
                    .replace("<sup>", "^").replace("</sup>", ""))
        from volcano_agent import figures as F
        st.image(F.plumbing(ds, R), width="stretch")
    with tabs[1]:
        st.dataframe(R["states"], width="stretch")
    with tabs[2]:
        cols = ["label", "depth_km", "P_MPa", "phi", "beta_m", "beta_c", "rV", "rV_eq", "uz1_0km_mm", "uz3_0km_mm",
                "uz3_1km_mm", "uz3_2km_mm"]
        st.dataframe(res[cols], width="stretch")
        from volcano_agent import figures as F
        st.image(F.profiles(rr.analysis, R, R["thin_crack"]), width="stretch")
    with tabs[3]:
        st.dataframe(R["inverse"], width="stretch")
    with tabs[4]:
        st.dataframe(R["scenario_b"], width="stretch")
        if "datum" in R:
            st.dataframe(R["datum"], width="stretch")
    with tabs[5]:
        for g in ds.data_gaps:
            st.markdown(f"- {g}")
        st.json(json.loads(rr.dataset_json()), expanded=False)
    if st.button("Start a new volcano"):
        ss.ds, ss.result, ss.usage = None, None, None
        st.rerun()
