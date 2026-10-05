# Data specification

Everything the agent looks for, every default it may fall back on, every scenario it builds and every
output it writes. Equation numbers refer to [`METHODS.md`](METHODS.md).

## 1. Status codes

Every physical input is a *sourced quantity*: `value`, optional `min`/`max` (published range), `status`,
`source` (reference key + table/figure) and `note`.

| Code | Meaning | Example |
|---|---|---|
| **M** | measured for this volcano | S = 1000 ppm in latite melt inclusions |
| **U** | analytical upper limit, assigned as a positive number | CO₂ below detection, entered at the 50 ppm limit |
| **A** | adopted: a representative value chosen inside a published range, converted from a published quantity, or transferred from a related magma of the same volcano | H₂O = 1.25 wt%, midpoint of 1.0–1.5 wt% |
| **D** | generic default: nothing was found, a textbook value is used | crustal density 2500 kg m⁻³ |

Every **D** input is listed in Section 4.7 of the report and counted on its title page.

## 2. What the research agent collects

The research runs in three stages, each a separate model session with web search and page fetch, ending with
a structured "submit" call whose JSON schema is defined in `volcano_agent/research.py`.

| Stage | Collected |
|---|---|
| 1 · system | name, country, region, coordinates, type, tectonic setting, last eruption, summit elevation (m), caldera half-length (km); magma series (≤ 5 types, mafic → evolved); ≤ 3 storage levels with depth, published pressure, resident and injected magma, reservoir volume, evidence; oxygen fugacity (ΔFMQ); crustal density; cited narrative notes (setting, history, magma series, plumbing, hydrothermal system, hazard); references |
| 2 · geodesy | the best-documented published analytical source model (MOGI / YANG / PENNY) with depth and its reference surface, dimensions, plunge and trend, V₀, ΔV, ΔP, μ and ν used in the inversion, observed uplift, period, interpretation; shallow and deep elastic moduli; notes on unrest, deformation, monitoring |
| 3 · petrology (one per magma) | representative major-element analysis (sample, unit, table), temperature, dissolved H₂O, CO₂, S with ranges and status, a cited note on what the volatile record does and does not constrain |

Research effort per stage (`depth` setting): **quick** 6 searches / 3 page reads, **standard** 12 / 6,
**thorough** 20 / 10 (petrology stages: two searches fewer, minimum 4). Fetched pages are capped at
25 000 tokens.

Unit conventions required from the agent: depth km, pressure MPa (1 kbar = 100 MPa), temperature °C, volatiles
wt% (ppm / 10⁴), volumes m³, moduli GPa. A depth derived from a pressure uses ρ = 2500 kg m⁻³ (status A).
NNO is converted to FMQ by +0.7.

## 3. Defaults applied by `finalize()` (status D unless stated)

| Input | Default | Basis |
|---|---|---|
| Crustal density ρ_c | 2500 kg m⁻³ | plausible range 2300–2700 |
| Deep shear modulus μ / Poisson ratio ν | 10 GPa / 0.25 | intact-rock end of 1–10 GPa (Heap et al. 2020) |
| Shallow μ / ν | 1 GPa / 0.35 | damaged, altered rock (Heap et al. 2020) |
| ΔFMQ | +1 (arc / subduction setting), 0 otherwise | |
| Composition | approximate global average of the rock type (Le Maitre 1976) | only if no analysis was found |
| Temperature | 1185 − 7.3 (SiO₂ − 48) °C, rounded to 10 °C | ≈ 1185 °C basalt, ≈ 1000 °C rhyolite |
| H₂O / CO₂ / S | 1.5 / 0.01 / 0.05 wt% | only if no melt-inclusion data were found |
| β_liquid (status A) | SiO₂ ≥ 68: 1.2; 60–68: 1.1; 55–60: 1.0; 50–55: 0.8; < 50: 0.7 (× 10⁻¹⁰ Pa⁻¹) | Spera (2000); Rivalta & Segall (2008); reproduces the thesis values |
| EVo solubility class | SiO₂ < 55 basalt; 55–64 phonolite; ≥ 64 rhyolite | Burgisser et al. (2015) validity ranges, as in the thesis |
| Storage levels | 3, 6, 10 km (resident: most evolved → most mafic) | only if none were found |
| Reservoir volume V₀ | 5×10⁸ (z < 3.5 km), 5×10⁹ (< 8 km), 5×10¹⁰ m³ | La Fossa reference scheme |
| Spheroid source | b = 0.3 a if b missing; V₀ = (4/3)πab² (A); plunge 89°, trend 0° if missing | |
| Sphere source | V₀ = (4/3)πr³ (A) or 5×10⁷ m³ | |
| Crack source | a = min(500 m, d/2); V₀ = πa²(0.1a) | thin sill, w̄/2a = 0.05 |

Plausibility checks (each logged as a gap):

| Input | Accepted range | Otherwise |
|---|---|---|
| H₂O / CO₂ / S | 0.01–8 / 10⁻⁴–2 / 10⁻⁴–1 wt% | clamped |
| Temperature | 650–1350 °C; values that are clearly kelvin are converted | discarded → default |
| Crustal density | 1800–3300 kg m⁻³ | discarded → default |
| Shear modulus | 0.05–100 GPa (values given in Pa are converted) | discarded → default |
| Poisson ratio | 0.01–0.49 | discarded → default |
| ΔFMQ | −3 to +4 | discarded → default |
| Storage depth | 0.2–40 km; duplicate depths removed | level dropped |
| Source depth | 0.05–20 km | source dropped |
| Spheroid | axes swapped if b > a; aspect ratio clamped to 0.02–0.99; plunge to 1–89.99° | — |
| Source ΔV, ΔP | negative (deflation) values: magnitude used | — |
| Oxide analysis | fewer than 7 oxides or total < 85 wt% | generic composition |

Oxide names are normalised (`FeOt`, `FeO*`, `Fe2O3T` …).
Total iron given as Fe₂O₃ is converted with FeO = 0.8998 Fe₂O₃; analyses whose oxide total lies outside
97–101.5 wt% are renormalised anhydrous.

## 4. Scenario design (Scenario A)

* **Magmatic levels** (≤ 3–4): each evaluated as a **Mogi sphere** and as **penny cracks** of radius
  0.5, 1, 2 (and 4) km, keeping only radii ≤ the caldera half-length when it is known, and never a crack wider
  than it is deep (a/d > 1 lies outside the half-space solution; such cases are listed, not modelled).
* **Injected volumes:** 10⁶, 5×10⁶, 10⁷ m³ per magmatic level.
* **Published deformation source** (if any): its own geometry and μ, ν; resident = most evolved magma
  (a *hypothetical magmatic end-member*); injected volumes 10ⁿ, 5×10ⁿ, 10ⁿ⁺¹ m³ with
  10ⁿ = 10^ceil(log₁₀ ΔV_published) (10⁵ m³ if ΔV unknown); pressure at the model depth (sea-level datum).
* **Outputs per configuration:** P, P_sat, φ, β_liquid, β_gas, β_m (frozen), β_m^eff (equilibrium), β_c,
  r_V (both branches), ΔV_c, u_z at 0, 1, 2 km.

## 5. Derived analyses

| Analysis | Definition |
|---|---|
| Inverse | V_e, ΔV_c and ΔP for a target central uplift (default 10 mm), both branches for gas-bearing rows |
| Pressure screen | ΔP > 10 MPa flagged as above the reference screening threshold (not a failure criterion) |
| Thin-crack check | w̄/(2a) = V₀/(2πa³) ≤ 0.1; a/d ≥ 1 flagged as the validity limit |
| Scenario B | H₂O × (1.6, 2.0, 2.4) at 2 km, × (2.8, 3.2, 3.6) at 5 km, × (2.96, 3.70, 4.44) at 12 km, interpolated in depth; CO₂ trials 0.01/0.02/0.05 (< 3.5 km), 0.05/0.10/0.15 (< 8 km), 0.20/0.30/0.40 wt% (deeper) |
| Pressure datum | depth below sea level under an edifice > 50 m high: model depth; + half the summit elevation; + full summit elevation. Depth already referred to the ground surface (or no edifice): model depth and ± 0.2 km |
| H₂O × datum | shallow-source H₂O × 0.8, 1.0, 1.2 on the three datums, both branches |
| Other levers | ρ_c 2300/2500/2700; ΔFMQ ± 1; spheroid aspect ratio {published, 0.2, 0.3, 0.5, 0.99}; deep μ 5/10/20/40 GPa × ν 0.15/0.25/0.35 |
| Verification | crack ΔV vs Sneddon (a/d = 0.1); crack free-surface amplification (a/d = 1); crack uplift vs point-sill limit; spheroid A = 0.99 vs sphere (β_c and uplift); Mogi closed form |
| Consistency | β_cμ, ΔV_c at the published ΔP, and uplift above the centroid, against the published source |
| Calculation caveats | states where EVo used temperature-independent solubility coefficients (T outside the calibrated range of the H₂O law: 790–1010 °C rhyolite class, 800–1250 °C phonolite class) or did not converge (analytic fallback); equilibrium branch below the frozen branch at high pressure (ideal-gas β_gas, thesis §5.6.7); Mogi spheres with radius > 0.4 depth |

## 6. Outputs

| File | Content |
|---|---|
| `<volcano>_report.pdf` | title page with provenance box, contents, abstract, Chapters 1–7, ≈ 15 tables, 6 figures, references, Appendix A (complete results), B (provenance of every input), C (research log and number audit) |
| `<volcano>_dataset.json` | the complete dataset with every value, range, status, source and note — can be edited and re-loaded in the app |
| `<volcano>_results.csv` | one row per configuration: `label, model, family, depth_km, zP_km, chamber, intrusion, V0_m3, P_MPa, T_C, engine, saturated, P_sat_MPa, phi, gas_wt, beta_liquid, beta_gas, beta_m, beta_m_eq, beta_c, rV, rV_eq, mu_Pa, nu, Ve{1,2,3}_m3, dVc{1,2,3}_m3, uz{1,2,3}_{0,1,2}km_mm, uz{1,2,3}_0km_mm_eq` |

## 7. Reference dataset

`volcano_agent/reference/lafossa.json` is the La Fossa (Vulcano) dataset of the thesis, Scenario A
(Tables 2.1, 2.2, 4.1–4.3 of the thesis), built by `volcano_agent/reference/build_lafossa.py`.
Running the chain on it reproduces the thesis results:

| Quantity | Thesis | This code |
|---|---|---|
| r_V, 13 configurations | 2.600 … 200.99 | identical to < 3×10⁻⁷ relative |
| Central uplift, largest injection | 229.55 … 0.1647 mm | identical to < 3×10⁻⁷ relative |
| r_V of the 2021 geometry, equilibrium branch | 42.32 | 42.32 |
| Scenario B r_V (2 / 5 / 12 km) | 4.04–50.1 / 3.94–12.8 / 2.60–3.61 | same |
| β_cμ of the 2021 spheroid vs published | 0.978 vs 0.976 | same |
| Uplift above the 2021 centroid | 36.8 mm | 36.8 mm |
