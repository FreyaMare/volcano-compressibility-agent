"""Literature-research agent: given a volcano name, search the published literature and
assemble a sourced Dataset with every input of the seven-step chain.

Three focused research stages, each a separate agent run with web search and page fetch:
  1. system     - identity, setting, eruptive history, magma series, plumbing levels
  2. geodesy    - unrest, ground deformation, published source models, elastic moduli
  3. petrology  - one run per magma: composition, temperature, H2O, CO2, S
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .llm import DEFAULT_MODEL, Usage, make_client, run_submit_loop, web_tools
from .schema import Dataset, DeformationSource, Level, Magma, Q, Reference

# ======================================================================================
# JSON schemas of the submit tools
# ======================================================================================
_Q = {
    "type": "object",
    "description": "A sourced number. value=null if not found.",
    "properties": {
        "value": {"type": ["number", "null"]},
        "min": {"type": ["number", "null"], "description": "lower end of the published range, if any"},
        "max": {"type": ["number", "null"], "description": "upper end of the published range, if any"},
        "status": {"type": "string", "enum": ["M", "U", "A", "D"]},
        "source": {"type": "string", "description": "reference key, e.g. 'Gioncada et al. (1998), Table 1'"},
        "note": {"type": "string"},
    },
    "required": ["value", "status", "source"],
}
_REFS = {
    "type": "array",
    "description": "Every publication cited in any 'source' field or narrative.",
    "items": {"type": "object", "properties": {
        "key": {"type": "string", "description": "Author et al. (Year) exactly as used in source fields"},
        "citation": {"type": "string", "description": "full reference: authors, year, title, journal, volume, pages"},
        "url": {"type": "string"}, "doi": {"type": "string"}},
        "required": ["key", "citation"]},
}
_NOTES = {"type": "array", "items": {"type": "string"},
          "description": "Data gaps, conflicts between sources, and caveats the report must mention."}

SYSTEM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Name of the volcano / active centre as used in the literature"},
        "country": {"type": "string"}, "region": {"type": "string"},
        "latitude": {"type": ["number", "null"]}, "longitude": {"type": ["number", "null"]},
        "volcano_type": {"type": "string"}, "tectonic_setting": {"type": "string"},
        "last_eruption": {"type": "string"},
        "summit_elevation_m": _Q,
        "caldera_max_radius_km": {**_Q, "description": "half the long axis of the caldera / collapse structure hosting the active centre; null if none"},
        "magma_series": {"type": "array", "description": "Magma types relevant to the plumbing system, ordered from most mafic to most evolved (max 5).",
                         "items": {"type": "object", "properties": {
                             "key": {"type": "string", "description": "UPPER_CASE id, e.g. BASALT, ANDESITE, DACITE"},
                             "rock_type": {"type": "string"},
                             "description": {"type": "string", "description": "which eruptions / units, and why relevant"}},
                             "required": ["key", "rock_type"]}},
        "levels": {"type": "array", "description": "Magmatic storage levels (max 3, preferably shallow, intermediate, deep).",
                   "items": {"type": "object", "properties": {
                       "name": {"type": "string"}, "depth_km": _Q, "pressure_MPa": _Q,
                       "resident": {"type": "string", "description": "key of the magma stored there"},
                       "injected": {"type": "string", "description": "key of the (more mafic) recharge magma"},
                       "V0_m3": {**_Q, "description": "published reservoir volume, null if none"},
                       "evidence": {"type": "string"}},
                       "required": ["name", "depth_km", "resident", "injected"]}},
        "dFMQ": {**_Q, "description": "oxygen fugacity relative to FMQ"},
        "rho_crust": {**_Q, "description": "mean crustal / edifice density, kg/m3"},
        "narrative": {"type": "object", "description": "Concise, factual, cited summaries (each 80-250 words, with (Author, Year) citations).",
                      "properties": {k: {"type": "string"} for k in
                                     ("setting", "history", "magma_series", "plumbing", "hydrothermal", "hazard")}},
        "references": _REFS, "notes": _NOTES,
    },
    "required": ["name", "magma_series", "levels", "narrative", "references"],
}

GEODESY_SCHEMA = {
    "type": "object",
    "properties": {
        "deformation_source": {
            "type": ["object", "null"],
            "description": "The best-documented published analytical source model of a recent unrest/deformation episode. null if none exists.",
            "properties": {
                "model": {"type": "string", "enum": ["MOGI", "YANG", "PENNY"],
                          "description": "MOGI = point/finite sphere (Mogi, McTigue); YANG = prolate spheroid; PENNY = horizontal circular crack / sill (Fialko). Map Okada sills to PENNY with an equivalent radius and say so in the note."},
                "depth_km": {**_Q, "description": "centroid depth below the model free surface"},
                "depth_reference": {"type": "string", "description": "e.g. 'below sea level', 'below the mean ground surface'"},
                "a_m": {**_Q, "description": "semi-major axis (YANG) or radius (MOGI, PENNY), m"},
                "b_m": {**_Q, "description": "semi-minor axis (YANG), m"},
                "aspect": {**_Q, "description": "b/a if reported"},
                "dip_deg": {**_Q, "description": "plunge from the horizontal (YANG)"},
                "strike_deg": {**_Q, "description": "azimuth of the down-dip direction, clockwise from north (YANG)"},
                "V0_m3": {**_Q, "description": "source volume"},
                "dV_m3": {**_Q, "description": "cavity volume change of the episode"},
                "dP_MPa": {**_Q, "description": "overpressure"},
                "mu_GPa": {**_Q, "description": "shear modulus used in the inversion"},
                "nu": {**_Q, "description": "Poisson ratio used in the inversion"},
                "observed_uplift_mm": {**_Q, "description": "maximum observed vertical uplift (not LOS) for the same period"},
                "period": {"type": "string"}, "interpretation": {"type": "string"},
                "source": {"type": "string"}},
            "required": ["model", "depth_km"]},
        "mu_shallow_GPa": _Q, "nu_shallow": _Q, "mu_deep_GPa": _Q, "nu_deep": _Q,
        "narrative": {"type": "object", "properties": {k: {"type": "string"} for k in
                                                       ("unrest", "deformation", "monitoring")}},
        "references": _REFS, "notes": _NOTES,
    },
    "required": ["deformation_source", "narrative", "references"],
}

_OX = {k: {"type": ["number", "null"]} for k in
       ("SIO2", "TIO2", "AL2O3", "FEO", "FE2O3", "MNO", "MGO", "CAO", "NA2O", "K2O", "P2O5")}
PETROLOGY_SCHEMA = {
    "type": "object",
    "properties": {
        "key": {"type": "string"}, "rock_type": {"type": "string"},
        "label": {"type": "string", "description": "sample id, unit and eruption of the adopted analysis"},
        "oxides": {"type": "object", "properties": _OX,
                   "description": "Major elements in wt% exactly as published. If the paper gives total iron as Fe2O3, put it in FE2O3 and leave FEO null; if it gives FeO total, use FEO."},
        "composition_status": {"type": "string", "enum": ["M", "A", "D"]},
        "composition_source": {"type": "string"},
        "T_C": {**_Q, "description": "pre-eruptive / storage temperature, °C"},
        "H2O_wt": {**_Q, "description": "dissolved H2O in melt inclusions (or hygrometry), wt%"},
        "CO2_wt": {**_Q, "description": "dissolved CO2, wt% (ppm / 10000)"},
        "S_wt": {**_Q, "description": "dissolved S, wt% (ppm / 10000)"},
        "narrative": {"type": "string", "description": "80-200 words on the volatile record of this magma and what it does / does not constrain, with citations"},
        "references": _REFS, "notes": _NOTES,
    },
    "required": ["key", "oxides", "T_C", "H2O_wt", "CO2_wt", "S_wt", "references"],
}

# ======================================================================================
# Prompts
# ======================================================================================
SYSTEM_PROMPT = """You are a research volcanologist assembling the input data for a physics-based model that links magma compressibility to surface deformation (the seven-step chain of Rivalta & Segall 2008 / Kilbride et al. 2016: storage depth -> EVo volatile saturation -> magma and chamber compressibility -> volume partitioning r_V -> Mogi / Yang / Fialko surface uplift).

Your job is to find, in the published literature, the numbers the model needs for ONE volcano, and to record exactly where each number comes from.

Rules:
- Search the web. Prefer peer-reviewed papers (journal articles, their supplementary tables), then observatory and agency reports (USGS, INGV, GVP/Smithsonian, PHIVOLCS, IGN, etc.). Read the actual papers with web_fetch when abstracts are not enough; open-access PDFs, ResearchGate, Copernicus, Frontiers, Wiley/AGU and Springer pages are often fetchable.
- NEVER invent or guess a number. If you cannot find it, give value null and status "D". A missing value is far better than an unsourced one.
- Every number carries: value, min/max if a range is published, status and source.
  status codes:  M = measured for this volcano; U = below detection, recorded at the detection limit;
                 A = adopted: a representative value you chose inside a published range (say how in the note), or a value converted from a published quantity (e.g. depth from pressure), or transferred from a related magma of the same volcano;
                 D = not found.
- source = the reference key exactly as in your references list, plus table / figure when known, e.g. "Gioncada et al. (1998), Table 1".
- Units: depth km, pressure MPa (1 kbar = 100 MPa), temperature °C, volatiles wt% (ppm / 10000), volumes m3, moduli GPa.
- If only a pressure is published, convert to depth with rho = 2500 kg/m3 (z = P / (rho g)), status A, and say so. State whether depths are below sea level or below the surface.
- Melt inclusions record dissolved volatiles at entrapment, not the total inventory; say where they were trapped if the paper says so.
- Narratives: concise, factual, in English, with (Author, Year) citations matching the reference keys. No speculation.
- Finish by calling the submit tool exactly once. Do not write a long answer in text.

Example of the expected level of detail (La Fossa, Vulcano; do NOT reuse these values for another volcano):
- Magma RHYOLITE: composition Gioncada et al. (1998), Table 1, sample GS91-50c (SiO2 73.54 ...), status M; T_C 1000 (1000-1030), M, Clocchiatti et al. (1994); H2O_wt 1.25 (1.0-1.5), A, "midpoint of 1-1.5 wt% reported for the 1888-1890 magmas; no rhyolite-specific MI data"; CO2_wt 0.005, U, "below detection (<50 ppm)".
- Level: "Shallow reservoir", depth 2 km (1.5-2), A, from fluid-inclusion pressures 30-60 MPa (Clocchiatti et al., 1994); resident RHYOLITE, injected TRACHYTE.
- Deformation source: YANG, depth 0.598 km below sea level, a 595 m, b 59 m, dip 69, strike 137, V0 8.83e6 m3, dV 73108 m3, dP 8.48 MPa, mu 1 GPa, nu 0.35 (Di Traglia et al., 2023, Table S1); interpretation: hydrothermal expansion.
"""


def _stage_system_user(volcano: str) -> str:
    return f"""Volcano: {volcano}

Stage 1 of 3 - the volcanic system. Find:
1. Identity: name as used in the literature, country, region, coordinates, type, tectonic setting, last eruption, summit elevation (m a.s.l.), and the size of any caldera / collapse structure around the active centre (give half the long axis as caldera_max_radius_km).
2. Eruptive history and the magma series (rock types from mafic to evolved) relevant to the present plumbing system.
3. The plumbing system: discrete magma storage levels with depths/pressures and the evidence (petrology/barometry, fluid or melt inclusions, geophysics, seismic tomography, geodesy). Choose at most 3 magmatic levels (e.g. shallow, intermediate, deep). For each, the resident magma (stored there) and the injected magma (the next more mafic magma that recharges it), using keys from your magma_series.
4. Oxygen fugacity (relative to FMQ / NNO; convert NNO to FMQ by +0.7) and a crustal density if published.
5. The hydrothermal system and hazard context.
Then call submit_system."""


def _stage_geodesy_user(volcano: str, system: dict) -> str:
    mags = ", ".join(m["key"] for m in system.get("magma_series", []))
    return f"""Volcano: {volcano} (literature name: {system.get('name', volcano)})

Stage 2 of 3 - unrest and ground deformation. Find:
1. The history of unrest and ground deformation (levelling, tilt, GNSS, InSAR) and the main episodes.
2. The best-documented published ANALYTICAL source model of a recent deformation episode (Mogi/McTigue sphere, Yang prolate spheroid, Fialko penny crack or Okada sill), with all its parameters from the paper or its supplementary tables: depth and its reference surface, dimensions, dip/strike, source volume, volume change, overpressure, and the shear modulus and Poisson ratio used. Prefer the authors' preferred model. Note the authors' interpretation (magmatic / hydrothermal). If no analytical source model has been published, deformation_source = null.
3. Elastic parameters appropriate for the shallow edifice and for the deeper crust (from rock-physics studies of this volcano if possible).
Magma keys already identified: {mags}. Then call submit_geodesy."""


def _stage_petrology_user(volcano: str, system: dict, magma: dict) -> str:
    lv = [f"{L.get('name')} ({(L.get('depth_km') or {}).get('value')} km, resident {L.get('resident')}, injected {L.get('injected')})"
          for L in system.get("levels", [])]
    return f"""Volcano: {volcano} (literature name: {system.get('name', volcano)})
Storage levels: {'; '.join(lv)}

Stage 3 - petrology of ONE magma: {magma['key']} ({magma.get('rock_type', '')}) - {magma.get('description', '')}

Find:
1. A representative whole-rock (or glass) major-element analysis of this magma at this volcano, preferably of a sample whose melt inclusions were analysed for volatiles. Give all oxides as published (wt%), the sample id, unit/eruption and the table.
2. The pre-eruptive / storage temperature (geothermometry, melt-inclusion homogenisation, experiments).
3. Dissolved volatiles from melt inclusions (FTIR, SIMS, Raman) or hygrometry: H2O, CO2, S in wt%. Give the published range (min/max) and choose a representative value (status A, say how). If CO2 or S is below detection, record the detection limit with status U.
Use key "{magma['key']}". Then call submit_petrology."""


# ======================================================================================
# Assembly
# ======================================================================================
def _q(d) -> Q:
    """Turn the agent's {value, min, max, status, source, note} into a Q, tolerating
    numbers sent as strings ("1.2", "~1000", "1.0-1.5") and unknown status codes."""
    from .defaults import _num
    if isinstance(d, (int, float, str)) and not isinstance(d, bool):
        d = {"value": d}
    if not isinstance(d, dict):
        return Q()
    val, lo, hi = _num(d.get("value")), _num(d.get("min")), _num(d.get("max"))
    raw = d.get("value")
    if isinstance(raw, str):                         # a range written as text
        import re
        nums = [float(x) for x in re.findall(r"\d*\.?\d+", raw.replace(",", "."))]
        if len(nums) >= 2 and re.search(r"\d\s*(?:-|–|to)\s*\d", raw):
            lo, hi = (lo if lo is not None else min(nums[:2])), (hi if hi is not None else max(nums[:2]))
            val = (lo + hi) / 2
    status = str(d.get("status") or "").strip().upper()[:1]
    if status not in ("M", "U", "A", "D"):
        status = "A" if val is not None else "D"
    if val is None:
        status = "D"
    return Q(value=val, min=lo, max=hi, status=status, source=str(d.get("source") or ""),
             note=str(d.get("note") or ""))


def _merge_refs(*lists) -> List[Reference]:
    seen: Dict[str, Reference] = {}
    for lst in lists:
        for r in lst or []:
            try:
                ref = Reference(**{k: (r.get(k) or "") for k in ("key", "citation", "url", "doi")})
            except Exception:
                continue
            if ref.key and ref.key not in seen:
                seen[ref.key] = ref
    return list(seen.values())


def _magma_list(system: dict) -> List[dict]:
    """The magma series as clean dicts with an upper-case key (tolerates strings and gaps)."""
    out = []
    for m in system.get("magma_series") or []:
        if isinstance(m, str):
            m = {"key": m, "rock_type": m}
        if not isinstance(m, dict):
            continue
        key = str(m.get("key") or m.get("rock_type") or "").strip()
        if not key:
            continue
        out.append({**m, "key": key.upper().replace(" ", "_"), "rock_type": str(m.get("rock_type") or key)})
    return out


def assemble(volcano: str, system: dict, geodesy: dict, petro: List[dict],
             consulted: List[dict]) -> Dataset:
    from .defaults import _num
    system = system if isinstance(system, dict) else {}
    geodesy = geodesy if isinstance(geodesy, dict) else {}
    ds = Dataset(name=str(system.get("name") or volcano))
    for k in ("country", "region", "volcano_type", "tectonic_setting", "last_eruption"):
        setattr(ds, k, str(system.get(k) or ""))
    ds.latitude, ds.longitude = _num(system.get("latitude")), _num(system.get("longitude"))
    ds.summit_elevation_m = _q(system.get("summit_elevation_m"))
    ds.caldera_max_radius_km = _q(system.get("caldera_max_radius_km"))
    ds.dFMQ = _q(system.get("dFMQ"))
    ds.rho_crust = _q(system.get("rho_crust"))
    for k in ("mu_shallow_GPa", "nu_shallow", "mu_deep_GPa", "nu_deep"):
        setattr(ds, k, _q(geodesy.get(k)))

    by_key = {str(p.get("key", "")).upper().replace(" ", "_"): p for p in petro if isinstance(p, dict)}
    for m in _magma_list(system)[:5]:
        key = m["key"]
        p = by_key.get(key, {})
        ox = {k: _num(v) for k, v in (p.get("oxides") or {}).items() if _num(v) is not None}
        mg = Magma(key=key, rock_type=p.get("rock_type") or m.get("rock_type", ""),
                   label=p.get("label", ""), oxides=ox,
                   composition_status=p.get("composition_status") or ("M" if ox else "D"),
                   composition_source=p.get("composition_source", ""),
                   T_C=_q(p.get("T_C")), H2O_wt=_q(p.get("H2O_wt")), CO2_wt=_q(p.get("CO2_wt")),
                   S_wt=_q(p.get("S_wt")))
        ds.magmas.append(mg)
        if p.get("narrative"):
            ds.narrative[f"volatiles_{key.lower()}"] = p["narrative"]

    for L in [x for x in (system.get("levels") or []) if isinstance(x, dict)][:3]:
        ds.levels.append(Level(name=str(L.get("name") or "Level"), depth_km=_q(L.get("depth_km")),
                               pressure_MPa=_q(L.get("pressure_MPa")), resident=str(L.get("resident") or ""),
                               injected=str(L.get("injected") or ""), V0_m3=_q(L.get("V0_m3")),
                               evidence=str(L.get("evidence") or "")))
    ds.levels = [L for L in ds.levels if L.depth_km.value is not None and L.depth_km.value > 0]

    s = geodesy.get("deformation_source")
    if isinstance(s, dict) and _q(s.get("depth_km")).value:
        model = str(s.get("model") or "").upper()
        model = model if model in ("MOGI", "YANG", "PENNY") else (
            "YANG" if ("SPHEROID" in model or "ELLIPS" in model) else
            "PENNY" if ("SILL" in model or "CRACK" in model or "OKADA" in model) else "MOGI")
        ds.deformation_source = DeformationSource(
            model=model,
            depth_km=_q(s.get("depth_km")),
            a_m=_q(s.get("a_m")), b_m=_q(s.get("b_m")), aspect=_q(s.get("aspect")),
            dip_deg=_q(s.get("dip_deg")), strike_deg=_q(s.get("strike_deg")),
            V0_m3=_q(s.get("V0_m3")), dV_m3=_q(s.get("dV_m3")), dP_MPa=_q(s.get("dP_MPa")),
            mu_GPa=_q(s.get("mu_GPa")), nu=_q(s.get("nu")),
            observed_uplift_mm=_q(s.get("observed_uplift_mm")),
            period=str(s.get("period") or ""), interpretation=str(s.get("interpretation") or ""),
            source=str(s.get("source") or ""), depth_reference=str(s.get("depth_reference") or ""))

    for src in (system.get("narrative") or {}, geodesy.get("narrative") or {}):
        if isinstance(src, dict):
            for k, v in src.items():
                if v:
                    ds.narrative[str(k)] = str(v)
    ds.references = _merge_refs(system.get("references"), geodesy.get("references"),
                                *[p.get("references") for p in petro])
    for lst in (system.get("notes"), geodesy.get("notes"), *[p.get("notes") for p in petro]):
        ds.data_gaps += [str(n) for n in (lst or []) if n]
    urls = list(dict.fromkeys(c["url"] for c in consulted))
    ds.research_log = [f"{len(urls)} distinct web sources returned by searches"] + urls[:200]
    return ds


def research_volcano(volcano: str, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
                     on_event: Callable[[str], None] | None = None,
                     depth: str = "standard") -> tuple[Dataset, Usage]:
    """Run the three research stages and return (raw Dataset, usage). Call
    defaults.finalize() on the result before running the chain."""
    say = on_event or (lambda s: None)
    client = make_client(api_key)
    usage, consulted = Usage(), []
    n = {"quick": (6, 3), "standard": (12, 6), "thorough": (20, 10)}[depth]

    say("Stage 1/3 - volcanic system, magma series and plumbing levels")
    system = run_submit_loop(client, model=model, system=SYSTEM_PROMPT, user=_stage_system_user(volcano),
                             submit_name="submit_system", submit_description="Submit the volcanic-system data.",
                             submit_schema=SYSTEM_SCHEMA, server_tools=web_tools(*n), on_event=say,
                             usage=usage, sources=consulted)
    say(f"Found {len(_magma_list(system))} magma types and {len(system.get('levels') or [])} storage levels")

    say("Stage 2/3 - unrest, ground deformation and published source models")
    geodesy = run_submit_loop(client, model=model, system=SYSTEM_PROMPT,
                              user=_stage_geodesy_user(volcano, system), submit_name="submit_geodesy",
                              submit_description="Submit the deformation data.", submit_schema=GEODESY_SCHEMA,
                              server_tools=web_tools(*n), on_event=say, usage=usage, sources=consulted)

    petro = []
    # research the magmas the scenario actually uses first
    used = []
    for L in system.get("levels") or []:
        if isinstance(L, dict):
            used += [str(L.get("resident") or "").upper().replace(" ", "_"),
                     str(L.get("injected") or "").upper().replace(" ", "_")]
    mags = sorted(_magma_list(system)[:5], key=lambda m: 0 if m["key"] in used else 1)
    for i, m in enumerate(mags, 1):
        say(f"Stage 3/3 - petrology of {m['key'].lower()} ({i}/{len(mags)})")
        try:
            petro.append(run_submit_loop(client, model=model, system=SYSTEM_PROMPT,
                                         user=_stage_petrology_user(volcano, system, m),
                                         submit_name="submit_petrology",
                                         submit_description="Submit the petrological data of this magma.",
                                         submit_schema=PETROLOGY_SCHEMA,
                                         server_tools=web_tools(max(4, n[0] - 2), n[1]),
                                         on_event=say, usage=usage, sources=consulted))
        except Exception as err:                # one failed magma must not kill the run
            say(f"petrology of {m['key']} failed ({err}); generic values will be flagged")
    ds = assemble(volcano, system, geodesy, petro, consulted)
    ds.research_log.insert(0, f"Model {model}; {usage.summary()}")
    return ds, usage
